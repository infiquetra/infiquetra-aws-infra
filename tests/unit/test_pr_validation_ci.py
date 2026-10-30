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
    tmp_path: Path, results: dict[str, str], findings: str = "0"
) -> tuple[subprocess.CompletedProcess[str], str]:
    summary = _jobs()["validation-summary"]
    assert summary["if"] == "always()"
    # Only declared dependencies are available in GitHub's needs context.
    needs = {
        job: {"result": result, "outputs": {}}
        for job, result in results.items()
        if job in summary["needs"]
    }
    if "security-scan" in needs:
        needs["security-scan"]["outputs"] = {"security-findings-count": findings}
    context = {"needs": needs}

    def render(match: re.Match[str]) -> str:
        expression = match[1].strip()
        if expression.startswith("github."):
            return "offline-control"
        assert expression.startswith("needs."), expression
        value: Any = context
        for key in expression.split("."):
            value = value.get(key, {}) if isinstance(value, dict) else {}
        return value if isinstance(value, str) else ""

    script = re.sub(r"\$\{\{(.*?)\}\}", render, summary["steps"][0]["run"])
    report = tmp_path / "summary.md"
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        env={**os.environ, "GITHUB_STEP_SUMMARY": str(report)},
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
    assert args.read_text().splitlines() == ["run", "--frozen", "pytest", "tests/unit/"]
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
