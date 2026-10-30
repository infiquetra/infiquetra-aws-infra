"""Scanner report integrity and actual workflow invocation controls.

CLI shims below are transport/failure injection, never evidence of real scanning.
Fixtures use the observed Bandit 1.9/Semgrep 1/Checkov 3 report schemas.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from tools import ci_scanners as scanners

ROOT = Path(__file__).parents[2]
VERSIONS = {"bandit": "1.9.4", "semgrep": "1.183.0", "checkov": "3.4.0"}
SCANNERS = tuple(VERSIONS)


def _report(tool: str, findings: int = 0) -> dict[str, Any]:
    if tool == "bandit":
        metrics = {
            f"{prefix}.{rank}": findings if rank == "HIGH" else 0
            for prefix in ("SEVERITY", "CONFIDENCE")
            for rank in ("HIGH", "MEDIUM", "LOW", "UNDEFINED")
        }
        metrics.update(loc=1, nosec=0, skipped_tests=0)
        return {
            "generated_at": "2026-10-29T00:00:00Z",
            "errors": [],
            "metrics": {"./sample.py": metrics, "_totals": metrics.copy()},
            "results": [
                {
                    "filename": "./sample.py",
                    "test_id": "B102",
                    "line_number": 1,
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                }
                for _ in range(findings)
            ],
        }
    if tool == "semgrep":
        return {
            "version": VERSIONS[tool],
            "errors": [],
            "skipped_rules": [],
            "paths": {"scanned": ["sample.py"]},
            "results": [
                {
                    "check_id": "fixture.rule",
                    "path": "sample.py",
                    "start": {"line": 1, "col": 1},
                    "end": {"line": 1, "col": 2},
                    "extra": {"severity": "WARNING"},
                }
                for _ in range(findings)
            ],
        }

    def check(state: str) -> dict[str, Any]:
        return {
            "check_id": "CKV_AWS_1",
            "resource": "Sample",
            "file_path": "/Sample.template.json",
            "check_result": {"result": state},
        }

    return {
        "check_type": "cloudformation",
        "results": {
            "passed_checks": [check("PASSED")],
            "failed_checks": [check("FAILED") for _ in range(findings)],
            "skipped_checks": [],
            "parsing_errors": [],
        },
        "summary": {
            "passed": 1,
            "failed": findings,
            "skipped": 0,
            "parsing_errors": 0,
            "resource_count": 1,
            "checkov_version": VERSIONS[tool],
        },
    }


def _targets(path: Path) -> None:
    (path / "cdk.out").mkdir(exist_ok=True)
    (path / "cdk.out/Sample.template.json").write_text(
        json.dumps({"Resources": {"Sample": {"Type": "AWS::S3::Bucket"}}})
    )


@pytest.fixture
def directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    _targets(tmp_path)
    return tmp_path


def _write(tool: str, value: Any) -> None:
    path = scanners.REPORTS[tool]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.mark.parametrize("tool", SCANNERS)
@pytest.mark.parametrize("findings", [0, 1])
def test_realistic_report_findings_remain_advisory(
    directory: Path, tool: str, findings: int
) -> None:
    _write(tool, _report(tool, findings))
    code = int(findings > 0) if tool != "semgrep" else 0
    result = scanners.validate_report(tool, code, VERSIONS[tool])
    assert result == scanners.Counts(findings, 1)


def test_checkov_accepts_single_framework_list(directory: Path) -> None:
    _write("checkov", [_report("checkov", 1)])
    assert scanners.validate_report("checkov", 1, VERSIONS["checkov"]).findings == 1


@pytest.mark.parametrize("tool", SCANNERS)
@pytest.mark.parametrize(
    "data", ["", "{", "null", "[]", '{"results":[],"results":[]}', '{"results":NaN}']
)
def test_missing_corrupt_or_unsupported_report_never_becomes_zero(
    directory: Path, tool: str, data: str
) -> None:
    path = scanners.REPORTS[tool]
    path.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(scanners.ScanError):
        scanners.validate_report(tool, 0, VERSIONS[tool])
    path.mkdir()
    with pytest.raises(scanners.ScanError):
        scanners.validate_report(tool, 0, VERSIONS[tool])
    path.rmdir()
    path.write_text(data)
    with pytest.raises(scanners.ScanError):
        scanners.validate_report(tool, 0, VERSIONS[tool])


CORRUPTIONS = [
    ("bandit", ("errors",), [{"reason": "parse error"}]),
    ("bandit", ("results",), {}),
    ("bandit", ("metrics", "_totals", "loc"), 0),
    ("bandit", ("metrics", "_totals", "SEVERITY.HIGH"), True),
    ("bandit", ("metrics", "_totals", "SEVERITY.HIGH"), -1),
    ("bandit", ("metrics", "_totals", "CONFIDENCE.HIGH"), "0"),
    ("bandit", ("metrics", "_totals", "SEVERITY.LOW"), 2),
    (
        "semgrep",
        ("errors",),
        [{"code": 2, "level": "warn", "type": "Internal matching error"}],
    ),
    (
        "semgrep",
        ("errors",),
        [{"code": 3, "level": "warn", "type": ["PartialParsing", []]}],
    ),
    ("semgrep", ("skipped_rules",), [{"rule_id": "fixture.rule"}]),
    ("semgrep", ("paths", "scanned"), []),
    ("semgrep", ("paths", "scanned"), ["sample.py", "sample.py"]),
    ("semgrep", ("version",), "2.0.0"),
    ("semgrep", ("time",), {"fixpoint_timeouts": ["sample.py"]}),
    ("checkov", ("summary", "failed"), True),
    ("checkov", ("summary", "failed"), -1),
    ("checkov", ("summary", "failed"), "0"),
    ("checkov", ("summary", "failed"), 2),
    ("checkov", ("summary", "resource_count"), 0),
    ("checkov", ("summary", "resource_count"), 2),
    ("checkov", ("results", "parsing_errors"), ["Sample.template.json"]),
    ("checkov", ("summary", "parsing_errors"), 1),
    ("checkov", ("results", "parsing_errors"), {}),
    ("checkov", ("summary", "checkov_version"), "4.0.0"),
    ("checkov", ("check_type",), "terraform"),
    ("checkov", ("errors",), ["runner failed"]),
    ("checkov", ("errors",), False),
    ("checkov", ("results", "passed_checks"), []),
]


@pytest.mark.parametrize(("tool", "keys", "value"), CORRUPTIONS)
def test_report_errors_types_counts_and_incomplete_scans_fail(
    directory: Path, tool: str, keys: tuple[str, ...], value: Any
) -> None:
    report = _report(tool)
    target = report
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    _write(tool, report)
    with pytest.raises(scanners.ScanError):
        scanners.validate_report(tool, 0, VERSIONS[tool])


@pytest.mark.parametrize("tool", SCANNERS)
@pytest.mark.parametrize("code", [1, 2, 3, 7, 127, -9, True])
def test_nonzero_exit_with_valid_zero_report_is_not_success(
    directory: Path, tool: str, code: int
) -> None:
    _write(tool, _report(tool))
    with pytest.raises(scanners.ScanError):
        scanners.validate_report(tool, code, VERSIONS[tool])


@pytest.mark.parametrize("tool", SCANNERS)
def test_arbitrary_exit_with_findings_is_not_a_finding_exit(
    directory: Path, tool: str
) -> None:
    _write(tool, _report(tool, 1))
    with pytest.raises(scanners.ScanError):
        scanners.validate_report(tool, 2, VERSIONS[tool])


def test_empty_synthesized_targets_fail(directory: Path) -> None:
    (directory / "cdk.out/Sample.template.json").unlink()
    _write("checkov", _report("checkov"))
    with pytest.raises(scanners.ScanError, match="no synthesized"):
        scanners.validate_report("checkov", 0, VERSIONS["checkov"])


DRIVER = """import json, os, pathlib, subprocess, sys
tool = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with pathlib.Path(os.environ['SCAN_TRACE']).open('a') as f:
    f.write(json.dumps([tool, *args]) + '\\n')
if tool == 'uv':
    assert args.pop(0) == 'run'
    if args[0] == '--frozen': args.pop(0)
    program = args.pop(0)
    if program == 'python': os.execv(sys.executable, [sys.executable, *args])
    assert program == 'bandit'
    os.execv(str(pathlib.Path(sys.argv[0]).parent / 'bandit'), ['bandit', *args])
if tool == 'pip':
    assert args == ['install', 'checkov']
    sys.exit(0)
cfg = json.loads(pathlib.Path(os.environ['SCAN_CONFIG']).read_text())[tool]
if args == ['--version']:
    if cfg['mode'] == 'version-error': sys.exit(2)
    print('9.0.0' if cfg['mode'] == 'unknown-version' else cfg['version'])
    sys.exit(0)
if cfg['mode'] != 'missing-report':
    path = pathlib.Path(cfg['report_path'])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{' if cfg['mode'] == 'malformed' else json.dumps(cfg['report']))
sys.exit(cfg['exit'])
"""


def _cli_environment(
    path: Path, changes: dict[str, dict[str, Any]] | None = None
) -> dict[str, str]:
    binary = path / "bin"
    binary.mkdir()
    config = {}
    for tool in SCANNERS:
        config[tool] = {
            "mode": "valid",
            "version": VERSIONS[tool],
            "exit": 0,
            "report": _report(tool),
            "report_path": str(scanners.REPORTS[tool]),
        }
        config[tool].update((changes or {}).get(tool, {}))
    (path / "config.json").write_text(json.dumps(config))
    for tool in (*SCANNERS, "uv", "pip"):
        program = binary / tool
        program.write_text(f"#!{sys.executable}\n" + DRIVER)
        program.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{binary}{os.pathsep}{os.environ['PATH']}",
        "SCAN_CONFIG": str(path / "config.json"),
        "SCAN_TRACE": str(path / "trace.jsonl"),
        "GITHUB_WORKSPACE": str(ROOT),
        "GITHUB_OUTPUT": str(path / "outputs"),
        "GITHUB_STEP_SUMMARY": str(path / "summary"),
    }


def _steps(workflow: str) -> list[dict[str, Any]]:
    document = yaml.safe_load((ROOT / f".github/workflows/{workflow}.yml").read_text())
    return list(next(iter(document["jobs"].values()))["steps"])


def _run_step(
    path: Path,
    workflow: str,
    name: str,
    environment: dict[str, str],
    steps: dict[str, Any] | None = None,
) -> subprocess.CompletedProcess[str]:
    step = next(s for s in _steps(workflow) if s.get("id") == name)
    assert "${{" not in step["run"]
    context = steps or {}
    variables = {}
    for key, expression in step.get("env", {}).items():
        parts = expression.removeprefix("${{").removesuffix("}}").strip().split(".")
        assert parts.pop(0) == "steps"
        value: Any = context
        for part in parts:
            value = value.get(part, {}) if isinstance(value, dict) else {}
        variables[key] = value if isinstance(value, str) else ""
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=path,
        env={**environment, **variables},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("tool", SCANNERS)
@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "finding",
        "exit-error",
        "missing-report",
        "malformed",
        "version-error",
        "unknown-version",
        "missing-tool",
        "report-error",
    ],
)
def test_actual_workflow_scanner_invocation_and_failure_injection(
    directory: Path, tool: str, mode: str
) -> None:
    report = _report(tool, int(mode == "finding"))
    if mode == "report-error":
        if tool == "checkov":
            report["results"]["parsing_errors"] = ["Sample.template.json"]
        else:
            report["errors"] = [{"code": 2, "level": "warn", "reason": "partial scan"}]
    code = 2 if mode == "exit-error" else int(mode == "finding" and tool != "semgrep")
    env = _cli_environment(
        directory, {tool: {"mode": mode, "report": report, "exit": code}}
    )
    if mode == "missing-tool":
        (directory / "bin" / tool).unlink()
        # Avoid falling through to a real globally installed scanner.
        (directory / "bin" / tool).write_text("#!/bin/sh\nexit 127\n")
        (directory / "bin" / tool).chmod(0o755)
    # A stale valid report must not rescue a CLI that produces no report.
    _write(tool, _report(tool))
    workflow = (
        "reusable-cdk-synthesis" if tool == "checkov" else "reusable-security-scan"
    )
    result = _run_step(directory, workflow, tool, env)
    assert (result.returncode == 0) == (mode in ("valid", "finding")), result.stderr
    receipt = json.loads((directory / f"{tool}-execution.json").read_text())
    assert receipt["execution"] == ("success" if result.returncode == 0 else "failure")
    outputs = (directory / "outputs").read_text()
    if result.returncode:
        assert f"{tool}-issues=" not in outputs
    else:
        assert f"{tool}-issues={int(mode == 'finding')}" in outputs
        trace = [
            json.loads(line)
            for line in (directory / "trace.jsonl").read_text().splitlines()
        ]
        expected = {
            "bandit": [
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
        assert expected[tool] in trace


def _successful_scans(path: Path) -> dict[str, str]:
    env = _cli_environment(path)
    for tool in SCANNERS:
        workflow = (
            "reusable-cdk-synthesis" if tool == "checkov" else "reusable-security-scan"
        )
        assert _run_step(path, workflow, tool, env).returncode == 0
    (path / "outputs").unlink()
    return env


def test_actual_summaries_count_findings_and_keep_them_advisory(
    directory: Path,
) -> None:
    env = _cli_environment(
        directory,
        {
            "bandit": {"report": _report("bandit", 1), "exit": 1},
            "semgrep": {"report": _report("semgrep", 2)},
            "checkov": {"report": _report("checkov", 2), "exit": 1},
        },
    )
    context: dict[str, Any] = {}
    for tool in SCANNERS:
        workflow = (
            "reusable-cdk-synthesis" if tool == "checkov" else "reusable-security-scan"
        )
        assert _run_step(directory, workflow, tool, env).returncode == 0
        context[tool] = {"outcome": "success"}
    assert (
        _run_step(
            directory, "reusable-security-scan", "count-findings", env, context
        ).returncode
        == 0
    )
    context.update(
        {
            "cdk-synth": {"outcome": "success", "outputs": {"status": "pass"}},
            "cfn-lint": {"outcome": "success", "outputs": {"status": "pass"}},
        }
    )
    assert (
        _run_step(
            directory, "reusable-cdk-synthesis", "final-status", env, context
        ).returncode
        == 0
    )
    output = (directory / "outputs").read_text()
    assert "total=3\n" in output and "status=pass\n" in output
    assert "checkov-issues=2\n" in output


@pytest.mark.parametrize("producer", ["cdk-synth", "cfn-lint"])
@pytest.mark.parametrize("status", ["fail", "", "shell-payload"])
def test_success_outcomes_do_not_rescue_missing_or_untrusted_status(
    directory: Path, producer: str, status: str
) -> None:
    env = _successful_scans(directory)
    marker = directory / "payload-executed"
    if status == "shell-payload":
        status = f'pass";exit 0;#\n$(touch "{marker}")\n`touch "{marker}"`'
    context = {
        name: {"outcome": "success", "outputs": {"status": "pass"}}
        for name in ("cdk-synth", "cfn-lint", "checkov")
    }
    context[producer]["outputs"] = {"status": status}
    result = _run_step(
        directory, "reusable-cdk-synthesis", "final-status", env, context
    )
    assert result.returncode == 1
    assert "status=pass" not in (directory / "outputs").read_text()
    assert not marker.exists()


@pytest.mark.parametrize(
    "producer", ["bandit", "semgrep", "cdk-synth", "cfn-lint", "checkov"]
)
@pytest.mark.parametrize(
    "status", ["success", "failure", "cancelled", "skipped", "", None]
)
def test_actual_final_status_requires_all_producers(
    directory: Path, producer: str, status: str | None
) -> None:
    env = _successful_scans(directory)
    context = {
        name: {"outcome": "success", "outputs": {"status": "pass"}}
        for name in ("bandit", "semgrep", "cdk-synth", "cfn-lint", "checkov")
    }
    if status is None:
        del context[producer]
    else:
        context[producer]["outcome"] = status
    source = producer in ("bandit", "semgrep")
    workflow, step = (
        ("reusable-security-scan", "count-findings")
        if source
        else ("reusable-cdk-synthesis", "final-status")
    )
    result = _run_step(directory, workflow, step, env, context)
    assert (result.returncode == 0) == (status == "success"), result.stderr
    output = (
        (directory / "outputs").read_text() if (directory / "outputs").exists() else ""
    )
    assert ("total=0" in output if source else "status=pass" in output) == (
        status == "success"
    )


@pytest.mark.parametrize("tool", SCANNERS)
@pytest.mark.parametrize(
    "damage", ["missing-receipt", "corrupt-receipt", "changed-report", "wrong-count"]
)
def test_success_outcome_cannot_rescue_invalid_execution_evidence(
    directory: Path, tool: str, damage: str
) -> None:
    env = _successful_scans(directory)
    receipt = directory / f"{tool}-execution.json"
    if damage == "missing-receipt":
        receipt.unlink()
    elif damage == "corrupt-receipt":
        receipt.write_text("{")
    elif damage == "changed-report":
        scanners.REPORTS[tool].write_text("{}")
    else:
        value = json.loads(receipt.read_text())
        value["findings"] = True
        receipt.write_text(json.dumps(value))
    context = {
        name: {"outcome": "success", "outputs": {"status": "pass"}}
        for name in ("bandit", "semgrep", "cdk-synth", "cfn-lint", "checkov")
    }
    source = tool != "checkov"
    workflow, step = (
        ("reusable-security-scan", "count-findings")
        if source
        else ("reusable-cdk-synthesis", "final-status")
    )
    assert _run_step(directory, workflow, step, env, context).returncode != 0


def test_source_scanners_remain_reachable_after_independent_failure(
    directory: Path,
) -> None:
    env = _cli_environment(directory, {"bandit": {"mode": "exit-error", "exit": 2}})
    context: dict[str, Any] = {}
    for name in ("bandit", "semgrep", "count-findings"):
        step = next(s for s in _steps("reusable-security-scan") if s.get("id") == name)
        # These status predicates explicitly run diagnostics after earlier failure.
        run = (
            step.get("if") == "${{ !cancelled() }}"
            or step.get("if") == "always()"
            or all(v["outcome"] == "success" for v in context.values())
        )
        if run:
            result = _run_step(directory, "reusable-security-scan", name, env, context)
            context[name] = {
                "outcome": "success" if result.returncode == 0 else "failure"
            }
        else:
            context[name] = {"outcome": "skipped"}
    assert context == {
        "bandit": {"outcome": "failure"},
        "semgrep": {"outcome": "success"},
        "count-findings": {"outcome": "failure"},
    }


def test_checkov_uses_genuine_synth_and_survives_independent_lint_failure(
    directory: Path,
) -> None:
    step = next(s for s in _steps("reusable-cdk-synthesis") if s.get("id") == "checkov")
    assert step["if"] == "${{ !cancelled() && steps.cdk-synth.outcome == 'success' }}"
    env = _cli_environment(directory)
    context = {
        "cdk-synth": {"outcome": "success", "outputs": {"status": "pass"}},
        "cfn-lint": {"outcome": "failure", "outputs": {"status": "fail"}},
    }
    result = _run_step(directory, "reusable-cdk-synthesis", "checkov", env, context)
    assert result.returncode == 0
    assert scanners.REPORTS["checkov"].is_file()
    context["checkov"] = {"outcome": "success"}
    assert (
        _run_step(
            directory, "reusable-cdk-synthesis", "final-status", env, context
        ).returncode
        == 1
    )


CI_PATHS = {
    ".github/workflows/reusable-security-scan.yml",
    ".github/workflows/reusable-cdk-synthesis.yml",
    "tools/ci_scanners.py",
    "tests/unit/test_ci_scanners.py",
    ".github/workflows/deploy-infrastructure.yml",
    "docs/engineering-journal/DECISIONS.md",
}


def test_exact_ci_filter_retains_mixed_foundation_deployment() -> None:
    document = yaml.safe_load(
        (ROOT / ".github/workflows/deploy-infrastructure.yml").read_text()
    )
    ignored = document[True]["push"]["paths-ignore"]
    assert all("*" not in p and "?" not in p and "!" not in p for p in ignored)

    def selected(paths: set[str], rules: list[str]) -> bool:
        return any(path not in rules for path in paths)

    assert not selected(CI_PATHS, ignored)
    for path in CI_PATHS:
        assert selected(CI_PATHS, [rule for rule in ignored if rule != path])
    for path in (
        "app.py",
        "infiquetra_aws_infra/organization_stack.py",
        "infiquetra_aws_infra/sso_stack.py",
        "pyproject.toml",
        "infiquetra_aws_infra/lambda_src/qa_mail_reader/handler.py",
    ):
        assert selected(CI_PATHS | {path}, ignored)
