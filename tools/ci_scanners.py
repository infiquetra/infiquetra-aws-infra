"""Fixed CI scanner invocations: valid findings advisory; execution errors fatal.

Supported report families: Bandit 1.9, Semgrep 1, Checkov 3. Required fields,
counts, target coverage and CLI exits must agree; other families fail closed.
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
import subprocess
import sys
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
    prefix = {"bandit": "1.9.", "semgrep": "1.", "checkov": "3."}[tool]
    _require(
        bool(re.fullmatch(r"\d+\.\d+\.\d+", text)) and text.startswith(prefix),
        "unsupported scanner/report version",
    )
    return text


def template_resources() -> tuple[int, set[str]]:
    paths = sorted(Path("cdk.out").rglob("*.template.json"))
    _require(bool(paths), "no synthesized CloudFormation templates")
    total = 0
    for path in paths:
        total += len(_object(_object(read_json(path)).get("Resources")))
    _require(total > 0, "synthesized templates have no resources")
    return total, {str(path.relative_to("cdk.out")) for path in paths}


def _bandit(report: dict[str, Any]) -> Counts:
    _require(not _array(report.get("errors")), "Bandit reports scan errors")
    _text(report.get("generated_at"))
    results = _array(report.get("results"))
    metrics = _object(report.get("metrics"))
    totals = _object(metrics.get("_totals"))
    files = {key: _object(value) for key, value in metrics.items() if key != "_totals"}
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


def _semgrep(report: dict[str, Any], version: str) -> Counts:
    _require(report.get("version") == version, "Semgrep CLI/report version mismatch")
    _require(
        not _array(report.get("errors")), "Semgrep reports scan errors/incompleteness"
    )
    _require(not _array(report.get("skipped_rules")), "Semgrep skipped required rules")
    paths = _array(_object(report.get("paths")).get("scanned"))
    scanned = {_text(path) for path in paths}
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
        _require(_text(item.get("path")) in scanned, "Semgrep finding outside scan")
        _text(_object(item.get("extra")).get("severity"))
        for position in ("start", "end"):
            point = _object(item.get(position))
            _require(
                _count(point.get("line")) > 0 and _count(point.get("col")) > 0,
                "invalid Semgrep finding position",
            )
    return Counts(len(results), len(scanned))


def _checkov(value: Any, version: str) -> Counts:
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
            _require(
                _text(item.get("file_path")).lstrip("/") in targets,
                "Checkov finding outside synthesized templates",
            )
            _require(
                _object(item.get("check_result")).get("result") == label.upper(),
                "inconsistent Checkov check state",
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
    if tool == "bandit":
        counts = _bandit(_object(report))
    elif tool == "semgrep":
        counts = _semgrep(_object(report), version)
    else:
        counts = _checkov(report, version)
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
        with Path(f"{tool}-scanner.log").open("w") as log:
            result = subprocess.run(
                COMMANDS[tool], stdout=log, stderr=subprocess.STDOUT, check=False
            )
        receipt["exit_code"] = result.returncode
        counts = validate_report(tool, result.returncode, receipt["version"])
        receipt.update(
            asdict(counts),
            execution="success",
            report_sha256=hashlib.sha256(REPORTS[tool].read_bytes()).hexdigest(),
        )
        _output(f"{tool}-issues={counts.findings}\nexecution-status=success")
        _summary(
            f"**{tool}**: execution/report success; finding policy advisory; "
            f"{counts.findings} finding(s), {counts.scanned} targets/resources; "
            f"version {receipt['version']}"
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
