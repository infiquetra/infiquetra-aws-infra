"""Exercise the actual PR admission shell without AWS or GitHub services."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

WORKFLOW = Path(__file__).parents[2] / ".github/workflows/pull-request-validation.yml"
REQUIRED_JOBS = (
    "code-quality",
    "security-scan",
    "cdk-synthesis",
    "monitoring-iam",
    "nonprod-role-ci-guards",
    "unit-tests",
)


def _jobs() -> dict[str, Any]:
    return dict(yaml.safe_load(WORKFLOW.read_text())["jobs"])


def _run_summary(
    tmp_path: Path,
    results: dict[str, str],
    findings: str = "0",
    *,
    metadata: dict[str, str] | None = None,
    outputs: dict[str, dict[str, str]] | None = None,
) -> tuple[subprocess.CompletedProcess[str], str]:
    summary = _jobs()["validation-summary"]
    assert summary["if"] == "always()"
    # Only declared dependencies are available in GitHub's needs context.
    needs: dict[str, Any] = {
        job: {"result": result, "outputs": {}}
        for job, result in results.items()
        if job in summary["needs"]
    }
    if "security-scan" in needs:
        needs["security-scan"]["outputs"] = {"security-findings-count": findings}
    for job, values in {
        "code-quality": {"quality-status": "pass"},
        "cdk-synthesis": {"synthesis-status": "pass", "template-count": "3"},
    }.items():
        if job in needs:
            needs[job]["outputs"].update(values)
    for job, values in (outputs or {}).items():
        if job in needs:
            needs[job]["outputs"].update(values)
    github = {
        "sha": "a" * 40,
        "head_ref": "feature/offline-unit-tests",
        "ref_name": "main",
        "actor": "offline-reviewer",
        **(metadata or {}),
    }
    context = {"needs": needs, "github": github}

    def environment_value(expression: str) -> str:
        for operand in expression.split("||"):
            assert operand.strip().startswith(("needs.", "github.")), operand
            value: Any = context
            for key in operand.strip().split("."):
                value = value.get(key, {}) if isinstance(value, dict) else {}
            if isinstance(value, str) and value:
                return value
        return ""

    step = summary["steps"][0]
    script = step["run"]
    assert "${{" not in script, (
        "Summary inputs must be environment data, not Bash source"
    )
    step_environment = {}
    for key, expression in step["env"].items():
        match = re.fullmatch(r"\$\{\{(.*?)\}\}", expression)
        assert match is not None, expression
        step_environment[key] = environment_value(match[1])
    report = tmp_path / "summary.md"
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        env={
            **os.environ,
            **step_environment,
            "GITHUB_STEP_SUMMARY": str(report),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, report.read_text()


@pytest.mark.parametrize("findings", ["0", "22"])
def test_summary_accepts_success_with_existing_advisory_findings(
    tmp_path: Path, findings: str
) -> None:
    result, report = _run_summary(
        tmp_path, dict.fromkeys(REQUIRED_JOBS, "success"), findings
    )
    assert result.returncode == 0, result.stderr
    assert "Ready for merge and deployment!" in report
    assert "Offline Unit Tests**: Complete suite passed" in report
    if findings != "0":
        assert f"{findings} finding(s) detected" in report


@pytest.mark.parametrize("job", REQUIRED_JOBS)
@pytest.mark.parametrize("status", ["failure", "cancelled", "skipped", "", "unknown"])
def test_summary_rejects_every_unsuccessful_producer(
    tmp_path: Path, job: str, status: str
) -> None:
    results = dict.fromkeys(REQUIRED_JOBS, "success")
    results[job] = status
    result, report = _run_summary(tmp_path, results)
    assert result.returncode == 1, result.stderr
    assert "Ready for merge and deployment!" not in report
    if job == "security-scan":
        assert "Security Scan**: Validation failed" in report


@pytest.mark.parametrize("job", REQUIRED_JOBS)
def test_summary_rejects_missing_producer(tmp_path: Path, job: str) -> None:
    results = dict.fromkeys(REQUIRED_JOBS, "success")
    del results[job]
    result, report = _run_summary(tmp_path, results)
    assert result.returncode == 1, result.stderr
    assert "Ready for merge and deployment!" not in report


@pytest.mark.parametrize("head_ref", ["feature/offline-unit-tests", ""])
def test_summary_reports_normal_metadata_and_branch_fallback(
    tmp_path: Path, head_ref: str
) -> None:
    result, report = _run_summary(
        tmp_path,
        dict.fromkeys(REQUIRED_JOBS, "success"),
        metadata={"head_ref": head_ref},
    )
    assert result.returncode == 0, result.stderr
    assert f"**Commit**: {'a' * 40}" in report
    assert f"**Branch**: {head_ref or 'main'}" in report
    assert "**Triggered by**: offline-reviewer" in report
    assert "Successful (3 template(s) generated)" in report


@pytest.mark.parametrize(
    "branch_template",
    [
        'x";exit${IFS}0;#',
        'x";touch${IFS}@MARKER@;exit${IFS}0;#',
        "x$(touch${IFS}@MARKER@)",
        "x`touch${IFS}@MARKER@`",
    ],
    ids=["early-exit", "quoted-command", "dollar-substitution", "backticks"],
)
@pytest.mark.parametrize(
    "unit_status", ["success", "failure", "cancelled", "skipped", "", None]
)
def test_summary_treats_valid_hostile_branches_as_data(
    tmp_path: Path, branch_template: str, unit_status: str | None
) -> None:
    marker = tmp_path / "payload-executed"
    branch = branch_template.replace("@MARKER@", str(marker))
    subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        capture_output=True,
        check=True,
    )
    results = dict.fromkeys(REQUIRED_JOBS, "success")
    if unit_status is None:
        del results["unit-tests"]
    else:
        results["unit-tests"] = unit_status
    result, report = _run_summary(tmp_path, results, metadata={"head_ref": branch})
    assert result.returncode == (0 if unit_status == "success" else 1), result.stderr
    assert not marker.exists()
    assert f"**Branch**: {branch}" in report


def _shell_payload(marker: Path) -> str:
    return f'quote"\n$(touch "{marker}")\n`touch "{marker}"`\n";exit 0;#'


@pytest.mark.parametrize("field", ["sha", "head_ref", "actor"])
@pytest.mark.parametrize("unit_status", ["success", "failure"])
def test_summary_transports_multiline_metadata_without_execution(
    tmp_path: Path, field: str, unit_status: str
) -> None:
    marker = tmp_path / "payload-executed"
    payload = _shell_payload(marker)
    results = dict.fromkeys(REQUIRED_JOBS, "success")
    results["unit-tests"] = unit_status
    result, report = _run_summary(tmp_path, results, metadata={field: payload})
    assert result.returncode == (0 if unit_status == "success" else 1), result.stderr
    assert payload in report
    assert not marker.exists()


@pytest.mark.parametrize(
    ("job", "output", "displayed"),
    [
        ("code-quality", "quality-status", False),
        ("security-scan", "security-findings-count", True),
        ("cdk-synthesis", "synthesis-status", False),
        ("cdk-synthesis", "template-count", True),
    ],
)
@pytest.mark.parametrize("unit_status", ["success", "failure"])
def test_summary_transports_producer_outputs_without_execution(
    tmp_path: Path, job: str, output: str, displayed: bool, unit_status: str
) -> None:
    marker = tmp_path / "payload-executed"
    payload = _shell_payload(marker)
    results = dict.fromkeys(REQUIRED_JOBS, "success")
    results["unit-tests"] = unit_status
    result, report = _run_summary(tmp_path, results, outputs={job: {output: payload}})
    assert result.returncode == (0 if unit_status == "success" else 1), result.stderr
    if displayed:
        assert payload in report
    assert not marker.exists()


@pytest.mark.parametrize("job", REQUIRED_JOBS)
def test_summary_rejects_shell_payload_in_producer_result(
    tmp_path: Path, job: str
) -> None:
    marker = tmp_path / "payload-executed"
    results = dict.fromkeys(REQUIRED_JOBS, "success")
    results[job] = _shell_payload(marker)
    result, report = _run_summary(tmp_path, results)
    assert result.returncode == 1, result.stderr
    assert "Ready for merge and deployment!" not in report
    assert not marker.exists()


@pytest.mark.parametrize("exit_code", [0, 23])
def test_unit_command_runs_complete_suite_and_propagates_failure(
    tmp_path: Path, exit_code: int
) -> None:
    uv = tmp_path / "uv"
    uv.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" > "$UNIT_ARGS"\nexit "$UNIT_EXIT"\n'
    )
    uv.chmod(0o755)
    args = tmp_path / "args.txt"
    step = next(
        step
        for step in _jobs()["unit-tests"]["steps"]
        if step.get("id") == "unit-tests"
    )
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        env={
            **os.environ,
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "UNIT_ARGS": str(args),
            "UNIT_EXIT": str(exit_code),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert args.read_text().splitlines() == [
        "run",
        "--frozen",
        "python",
        "-m",
        "pytest",
        "tests/unit/",
    ]
    assert result.returncode == exit_code, result.stderr


@pytest.mark.parametrize("changed_file", [None, "pyproject.toml", "uv.lock"])
def test_unit_setup_rejects_rewritten_dependencies(
    tmp_path: Path, changed_file: str | None
) -> None:
    # A temporary index suffices; this control creates no commits.
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("reviewed\n")
    subprocess.run(
        ["git", "add", "pyproject.toml", "uv.lock"], cwd=tmp_path, check=True
    )
    if changed_file:
        (tmp_path / changed_file).write_text("rewritten by setup\n")
    steps = _jobs()["unit-tests"]["steps"]
    verify = next(step for step in steps if step.get("id") == "verify-dependencies")
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", verify["run"]],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) == (changed_file is None), result.stdout
