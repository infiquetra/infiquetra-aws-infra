"""Fixed CI scanner invocations: valid findings advisory; execution errors fatal.

Supported planners: Bandit 1.9.4, Semgrep 1.183.0, Checkov 3.4.0. Required
fields, independent target plans and CLI exits must agree; other versions fail
closed. Checkov graph-check applicability remains an explicit coverage limit.
Exit/output contracts: bandit.readthedocs.io/en/latest/man/bandit.html,
docs.semgrep.dev/cli-reference#exit-codes and checkov.io/2.Basics/
CLI%20Command%20Reference.html (output-file-path is a DIRECTORY).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

COMMANDS = {
    "bandit": [
        "uv",
        "run",
        "bandit",
        "-c",
        "pyproject.toml",
        "-r",
        ".",
        "-f",
        "json",
        "-o",
        "bandit-report.json",
    ],
    "semgrep": [
        "semgrep",
        "--config=auto",
        "--json",
        "--output=semgrep-report.json",
        ".",
    ],
    "checkov": [
        "checkov",
        "-d",
        "cdk.out",
        "--framework",
        "cloudformation",
        "--output",
        "json",
        "--output-file",
        "checkov-cfn-report.json",
    ],
}
REPORTS = {
    "bandit": Path("bandit-report.json"),
    "semgrep": Path("semgrep-report.json"),
    "checkov": Path("checkov-cfn-report.json/results_json.json"),
}
MAX_REPORT_BYTES = 128 * 1024 * 1024
VERSIONS = {"bandit": "1.9.4", "semgrep": "1.183.0", "checkov": "3.4.0"}


class ScanError(ValueError):
    """An execution or report-integrity failure, never a policy finding."""


@dataclass(frozen=True)
class Counts:
    findings: int
    scanned: int


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScanError(message)


def _object(value: Any) -> dict[str, Any]:
    _require(isinstance(value, dict), "expected report object")
    return dict(value)


def _array(value: Any) -> list[Any]:
    _require(isinstance(value, list), "expected report array")
    return list(value)


def _count(value: Any) -> int:
    _require(type(value) is int and value >= 0, "expected nonnegative integer count")
    return int(value)


def _text(value: Any) -> str:
    _require(isinstance(value, str) and bool(value), "expected nonempty report string")
    return str(value)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ScanError("nonfinite JSON number")


def read_json(path: Path) -> Any:
    _require(path.is_file(), "required JSON report is missing or is a directory")
    _require(0 < path.stat().st_size <= MAX_REPORT_BYTES, "empty or oversized report")
    try:
        return json.loads(
            path.read_text(), object_pairs_hook=_pairs, parse_constant=_invalid_constant
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ScanError("malformed JSON report") from exc


def _version(tool: str, value: Any) -> str:
    text = _text(value)
    _require(
        text == VERSIONS[tool],
        "unsupported scanner/report version",
    )
    return text


def _target(value: Any) -> str:
    text = _text(value)
    _require(
        not text.startswith("/")
        and "\\" not in text
        and not any(ord(char) < 32 for char in text)
        and ".." not in text.split("/"),
        "invalid target path",
    )
    path = Path(text).as_posix()
    _require(path != ".", "invalid target path")
    return path


def _targets(values: Any) -> set[str]:
    paths = _array(values)
    normalized = {_target(path) for path in paths}
    _require(len(normalized) == len(paths), "duplicate normalized targets")
    return normalized


def _scope_path(tool: str) -> Path:
    return Path(f"{tool}-scope.json")


def _scope(tool: str, version: str) -> dict[str, Any]:
    scope = _object(read_json(_scope_path(tool)))
    argv = COMMANDS[tool][3:] if tool == "bandit" else COMMANDS[tool][1:]
    _require(
        type(scope.get("schema")) is int
        and scope["schema"] == 1
        and scope.get("tool") == tool
        and scope.get("version") == version
        and scope.get("root") == str(Path.cwd().resolve())
        and scope.get("argv") == argv
        and scope.get("mode") == "scan",
        "missing or mismatched independent scanner plan",
    )
    expected = _targets(scope.get("targets"))
    _require(bool(expected), "scanner planned no applicable targets")
    hashes = _object(scope.get("target_sha256"))
    _require(set(hashes) == expected, "incomplete planned source binding")
    for path in expected:
        _require(
            Path(path).resolve().is_relative_to(Path.cwd().resolve())
            and Path(path).is_file()
            and hashes[path] == hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "planned scanner source changed or disappeared",
        )
    if tool == "bandit":
        _require(
            scope.get("config_sha256")
            == hashlib.sha256(Path("pyproject.toml").read_bytes()).hexdigest(),
            "Bandit config changed after discovery",
        )
    if tool == "semgrep":
        _require(
            bool(re.fullmatch(r"[0-9a-f]{64}", _text(scope.get("rules_sha256"))))
            and bool(_array(scope.get("rule_ids"))),
            "missing Semgrep resolved rule identity",
        )
    return scope


def _coverage(observed: Any, scope: dict[str, Any]) -> set[str]:
    targets = _targets(observed)
    expected = _targets(scope.get("targets"))
    _require(targets == expected, "report target coverage differs from scanner plan")
    return targets


def _identities(value: Any, width: int) -> set[tuple[str, ...]]:
    rows = _array(value)
    identities = set()
    for row in rows:
        fields = _array(row)
        _require(len(fields) == width, "invalid planned check identity")
        identities.add((_target(fields[0]), *(_text(item) for item in fields[1:])))
    _require(len(identities) == len(rows), "duplicate planned check identity")
    return identities


def template_resources() -> tuple[int, set[str]]:
    paths = sorted(Path("cdk.out").rglob("*.template.json"))
    _require(bool(paths), "no synthesized CloudFormation templates")
    total = 0
    for path in paths:
        total += len(_object(_object(read_json(path)).get("Resources")))
    _require(total > 0, "synthesized templates have no resources")
    return total, {str(path.relative_to("cdk.out")) for path in paths}


def _bandit(report: dict[str, Any], scope: dict[str, Any]) -> Counts:
    _require(not _array(report.get("errors")), "Bandit reports scan errors")
    _text(report.get("generated_at"))
    results = _array(report.get("results"))
    metrics = _object(report.get("metrics"))
    totals = _object(metrics.get("_totals"))
    files = {key: _object(value) for key, value in metrics.items() if key != "_totals"}
    _coverage(list(files), scope)
    _require(bool(files) and _count(totals.get("loc")) > 0, "Bandit scanned no code")
    for key in ("loc", "nosec", "skipped_tests"):
        _require(
            _count(totals.get(key)) == sum(_count(m.get(key)) for m in files.values()),
            "inconsistent Bandit metrics",
        )
    for result in results:
        item = _object(result)
        _require(_text(item.get("filename")) in files, "Bandit finding outside scan")
        _text(item.get("test_id"))
        _require(_count(item.get("line_number")) > 0, "invalid Bandit finding line")
    for prefix, field in (
        ("SEVERITY", "issue_severity"),
        ("CONFIDENCE", "issue_confidence"),
    ):
        observed = Counter(_text(_object(item).get(field)) for item in results)
        _require(
            set(observed) <= {"HIGH", "MEDIUM", "LOW", "UNDEFINED"},
            "invalid Bandit rank",
        )
        for rank in ("HIGH", "MEDIUM", "LOW", "UNDEFINED"):
            key = f"{prefix}.{rank}"
            _require(
                _count(totals.get(key))
                == observed[rank]
                == sum(_count(m.get(key)) for m in files.values()),
                "inconsistent Bandit finding count",
            )
    return Counts(len(results), len(files))


def _semgrep(report: dict[str, Any], version: str, scope: dict[str, Any]) -> Counts:
    _require(report.get("version") == version, "Semgrep CLI/report version mismatch")
    _require(
        not _array(report.get("errors")), "Semgrep reports scan errors/incompleteness"
    )
    _require(not _array(report.get("skipped_rules")), "Semgrep skipped required rules")
    paths = _array(_object(report.get("paths")).get("scanned"))
    scanned = {_text(path) for path in paths}
    _coverage(paths, scope)
    _require(
        bool(scanned) and len(scanned) == len(paths),
        "empty or duplicate Semgrep targets",
    )
    if "time" in report:
        _require(
            not _array(_object(report["time"]).get("fixpoint_timeouts", [])),
            "Semgrep reports matching timeouts",
        )
    results = _array(report.get("results"))
    for result in results:
        item = _object(result)
        _text(item.get("check_id"))
        _require(
            item["check_id"] in scope["rule_ids"], "finding outside resolved rules"
        )
        _require(_text(item.get("path")) in scanned, "Semgrep finding outside scan")
        _text(_object(item.get("extra")).get("severity"))
        for position in ("start", "end"):
            point = _object(item.get(position))
            _require(
                _count(point.get("line")) > 0 and _count(point.get("col")) > 0,
                "invalid Semgrep finding position",
            )
    return Counts(len(results), len(scanned))


def _checkov(value: Any, version: str, scope: dict[str, Any]) -> Counts:
    if isinstance(value, list):
        _require(len(value) == 1, "expected one CloudFormation report")
        value = value[0]
    report = _object(value)
    _require(
        report.get("check_type") == "cloudformation",
        "unexpected Checkov framework/schema",
    )
    results, summary = _object(report.get("results")), _object(report.get("summary"))
    _require(
        summary.get("checkov_version") == version, "Checkov CLI/report version mismatch"
    )
    for key in ("errors", "error"):
        for container in (report, results):
            if key in container:
                _require(not _array(container[key]), "Checkov reports execution errors")
    expected_resources, targets = template_resources()
    _coverage(["cdk.out/" + path for path in targets], scope)
    planned_resources = _identities(scope.get("resources"), 2)
    source_resources = {
        (path, f"{_text(_object(resource).get('Type'))}.{name}")
        for path in targets
        for name, resource in _object(read_json(Path("cdk.out") / path))[
            "Resources"
        ].items()
    }
    _require(
        planned_resources == source_resources,
        "Checkov parser/resource inventory mismatch",
    )
    expected_checks = _identities(scope.get("checks"), 3)
    evaluated = _identities(scope.get("evaluations"), 4)
    _require(
        not _array(scope.get("evaluation_errors")), "Checkov check execution errors"
    )
    _require(
        {item[:3] for item in evaluated} == expected_checks
        and len(evaluated) == len(expected_checks)
        and all(
            item[3] in {"PASSED", "FAILED", "SKIPPED", "UNKNOWN"} for item in evaluated
        ),
        "incomplete Checkov registry execution",
    )
    # UNKNOWN is omitted by Checkov's JSON serializer. Preserve its explicit
    # actual execution evidence; never invent passed checks for such resources.
    unknown = {item[:3] for item in evaluated if item[3] == "UNKNOWN"}
    observed_checks: set[tuple[str, str, str]] = set()
    _require(
        _count(summary.get("resource_count")) == expected_resources,
        "incomplete Checkov resource coverage",
    )
    for label in ("passed", "failed", "skipped"):
        records = _array(results.get(f"{label}_checks"))
        _require(
            _count(summary.get(label)) == len(records), "inconsistent Checkov counts"
        )
        for record in records:
            item = _object(record)
            _text(item.get("check_id"))
            _text(item.get("resource"))
            path = _target(_text(item.get("file_path")).removeprefix("/"))
            identity = (path, item["resource"], item["check_id"])
            _require(identity not in observed_checks, "duplicate Checkov check target")
            observed_checks.add(identity)
            _require(
                identity[:2] in planned_resources,
                "Checkov check outside parsed resource inventory",
            )
            _require(
                identity in expected_checks
                or item["check_id"] in scope["graph_rule_ids"],
                "unexpected Checkov check target",
            )
            _require(
                _text(item.get("file_path")).lstrip("/") in targets,
                "Checkov finding outside synthesized templates",
            )
            _require(
                _object(item.get("check_result")).get("result") == label.upper(),
                "inconsistent Checkov check state",
            )
            if identity in expected_checks:
                _require(
                    (*identity, label.upper()) in evaluated,
                    "Checkov report disagrees with executed check state",
                )
    _require(
        expected_checks - unknown <= observed_checks
        and not (unknown & observed_checks),
        "incomplete Checkov applicable resource check coverage",
    )
    _require(
        not _array(results.get("parsing_errors"))
        and _count(summary.get("parsing_errors")) == 0,
        "Checkov reports template parsing errors",
    )
    _require(summary["passed"] + summary["failed"] > 0, "Checkov executed no checks")
    return Counts(summary["failed"], expected_resources)


def validate_report(tool: str, exit_code: int, version: str) -> Counts:
    _version(tool, version)
    report = read_json(REPORTS[tool])
    if tool == "checkov":
        template_resources()
    scope = _scope(tool, version)
    if tool == "bandit":
        counts = _bandit(_object(report), scope)
    elif tool == "semgrep":
        counts = _semgrep(_object(report), version, scope)
    else:
        counts = _checkov(report, version, scope)
    # No --error for Semgrep and no --exit-zero/--soft-fail for the other tools.
    expected = int(counts.findings > 0) if tool != "semgrep" else 0
    _require(
        type(exit_code) is int and exit_code == expected,
        "unexpected scanner exit or inconsistent finding exit",
    )
    return counts


def _append(variable: str, text: str) -> None:
    if path := os.environ.get(variable):
        with Path(path).open("a") as stream:
            stream.write(text + "\n")


def _output(text: str) -> None:
    _append("GITHUB_OUTPUT", text)


def _summary(text: str) -> None:
    print(text)
    _append("GITHUB_STEP_SUMMARY", text)


def _receipt_path(tool: str) -> Path:
    return Path(f"{tool}-execution.json")


def _planned_command(tool: str) -> list[str]:
    adapter = str(Path(__file__).with_name("ci_scanner_plan.py").resolve())
    if tool == "bandit":
        return ["uv", "run", "python", adapter, tool, *COMMANDS[tool][3:]]
    executable = shutil.which(tool)
    _require(executable is not None, "scanner executable missing")
    # pip installs each CLI beside its environment's Python. Never run the
    # adapter with the unrelated uv interpreter used by this parent helper.
    python = Path(str(executable)).parent / "python"
    _require(python.is_file(), "scanner environment interpreter missing")
    return [str(python), adapter, tool, *COMMANDS[tool][1:]]


def run_scan(tool: str) -> int:
    receipt: dict[str, Any] = {
        "schema": 1,
        "tool": tool,
        "execution": "failure",
        "finding_policy": "advisory",
        "command": COMMANDS[tool],
    }
    try:
        _receipt_path(tool).unlink(missing_ok=True)
        _scope_path(tool).unlink(missing_ok=True)
        REPORTS[tool].unlink(missing_ok=True)
        if tool == "checkov":
            template_resources()
        version_command = (
            ["uv", "run", "bandit", "--version"]
            if tool == "bandit"
            else [tool, "--version"]
        )
        probe = subprocess.run(
            version_command, capture_output=True, text=True, check=False
        )
        Path(f"{tool}-version.log").write_text(probe.stdout + probe.stderr)
        receipt["version_exit_code"] = probe.returncode
        _require(probe.returncode == 0, "scanner version/startup failed")
        versions = re.findall(r"(?m)^(?:bandit )?(\d+\.\d+\.\d+)\s*$", probe.stdout)
        _require(len(versions) == 1, "unrecognized scanner version output")
        receipt["version"] = _version(tool, versions[0])
        # Keep diagnostic evidence without echoing finding snippets into summaries.
        # Keep the plan outside the scanned tree until execution finishes.
        # It is generated from the actual invocation, never from report counts.
        with tempfile.TemporaryDirectory(prefix="ci-scanner-plan-") as temporary:
            plan_path = Path(temporary) / "scope.json"
            receipt["adapter_command"] = _planned_command(tool)
            with Path(f"{tool}-scanner.log").open("w") as log:
                result = subprocess.run(
                    receipt["adapter_command"],
                    env={
                        **os.environ,
                        "CI_SCANNER_PLAN": str(plan_path),
                        "CI_SCANNER_MODE": "scan",
                    },
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            if plan_path.is_file():
                _scope_path(tool).write_bytes(plan_path.read_bytes())
        receipt["exit_code"] = result.returncode
        counts = validate_report(tool, result.returncode, receipt["version"])
        if tool == "checkov":
            scope = _scope(tool, receipt["version"])
            receipt["unknown_checks"] = [
                row for row in scope["evaluations"] if row[3] == "UNKNOWN"
            ]
            receipt["graph_coverage_limit"] = scope["graph_coverage_limit"]
        receipt.update(
            asdict(counts),
            execution="success",
            report_sha256=hashlib.sha256(REPORTS[tool].read_bytes()).hexdigest(),
            scope_sha256=hashlib.sha256(_scope_path(tool).read_bytes()).hexdigest(),
        )
        _output(f"{tool}-issues={counts.findings}\nexecution-status=success")
        _summary(
            f"**{tool}**: execution/report success; finding policy advisory; "
            f"{counts.findings} finding(s), {counts.scanned} targets/resources; "
            f"version {receipt['version']}"
        )
        if tool == "checkov":
            _summary(
                f"Checkov: {len(receipt['unknown_checks'])} explicit UNKNOWN check(s); "
                + receipt["graph_coverage_limit"]
            )
        status = 0
    except (ScanError, OSError) as exc:
        receipt["error"] = (
            str(exc)
            if isinstance(exc, ScanError)
            else "scanner/report I/O or startup failed"
        )
        _output("execution-status=failure")
        _summary(
            f"**{tool}**: execution/report FAILED; {receipt['error']}; "
            "findings not admitted"
        )
        status = 1
    _receipt_path(tool).write_text(json.dumps(receipt, indent=2) + "\n")
    return status


def _admitted_counts(tool: str) -> Counts:
    receipt = _object(read_json(_receipt_path(tool)))
    _require(
        type(receipt.get("schema")) is int
        and receipt.get("schema") == 1
        and receipt.get("tool") == tool
        and receipt.get("execution") == "success"
        and receipt.get("finding_policy") == "advisory"
        and receipt.get("command") == COMMANDS[tool],
        "missing or unsuccessful scanner execution receipt",
    )
    counts = validate_report(
        tool,
        _count(receipt.get("exit_code")),
        _version(tool, receipt.get("version")),
    )
    _require(
        receipt.get("report_sha256")
        == hashlib.sha256(REPORTS[tool].read_bytes()).hexdigest()
        and receipt.get("scope_sha256")
        == hashlib.sha256(_scope_path(tool).read_bytes()).hexdigest()
        and counts
        == Counts(_count(receipt.get("findings")), _count(receipt.get("scanned"))),
        "scanner receipt/report mismatch",
    )
    return counts


def finish(kind: str) -> int:
    try:
        if kind == "source-summary":
            _require(
                all(
                    os.environ.get(key) == "success"
                    for key in ("BANDIT_OUTCOME", "SEMGREP_OUTCOME")
                ),
                "source scanner step failed, cancelled, skipped or missing",
            )
            total = sum(
                _admitted_counts(tool).findings for tool in ("bandit", "semgrep")
            )
            _output(f"total={total}")
            _summary(
                f"**Source security**: execution/report success; {total} "
                "advisory finding(s); detailed reports in artifacts"
            )
        else:
            _require(
                all(
                    os.environ.get(key) == "success"
                    for key in (
                        "CDK_SYNTH_OUTCOME",
                        "CFN_LINT_OUTCOME",
                        "CHECKOV_OUTCOME",
                    )
                )
                and all(
                    os.environ.get(key) == "pass"
                    for key in ("CDK_SYNTH_STATUS", "CFN_LINT_STATUS")
                ),
                "synthesis/lint/template scan failed, cancelled, skipped or missing",
            )
            _admitted_counts("checkov")
            _output("status=pass")
            _summary(
                "**CDK synthesis and validation**: success; template scanner "
                "execution/report success; finding policy advisory"
            )
        return 0
    except (ScanError, OSError) as exc:
        if kind == "synthesis-summary":
            _output("status=fail")
        message = (
            str(exc)
            if isinstance(exc, ScanError)
            else "scanner receipt/report I/O failed"
        )
        _summary(f"**{kind}**: FAILED; {message}; no successful admission")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=[*COMMANDS, "source-summary", "synthesis-summary"]
    )
    action = parser.parse_args().action
    return run_scan(action) if action in COMMANDS else finish(action)


if __name__ == "__main__":
    sys.exit(main())
