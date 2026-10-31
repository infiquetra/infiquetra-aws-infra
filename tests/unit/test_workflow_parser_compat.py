"""Inert argument/printf and syntax controls; never run deploy/cloud blocks."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).parents[2]
# Original public log expressions, paired with the actual parser-safe source.
LOG_CASES = [
    (
        ".github/actions/setup-aws-credentials/action.yml",
        'echo "📍 Region: ${{ inputs.aws-region }}"',
        "echo '📍 Region: '\"$CI_AWS_REGION\"",
    ),
    (
        ".github/workflows/deploy-infrastructure.yml",
        'echo "# 🎯 Deployment Results" >> $GITHUB_STEP_SUMMARY',
        "echo '# 🎯 Deployment Results' >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/pull-request-validation.yml",
        'echo "# 🎯 Pull Request Validation Summary"',
        "echo '# 🎯 Pull Request Validation Summary'",
    ),
    (
        ".github/workflows/pull-request-validation.yml",
        'echo "## 📝 Details"',
        "echo '## 📝 Details'",
    ),
    (
        ".github/workflows/pull-request-validation.yml",
        'echo "### 🚀 Ready for merge and deployment!"',
        "echo '### 🚀 Ready for merge and deployment!'",
    ),
    (
        ".github/workflows/reusable-aws-deployment.yml",
        'echo "## 🏢 Deploying Organization Stack" >> $GITHUB_STEP_SUMMARY',
        "echo '## 🏢 Deploying Organization Stack' >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-aws-deployment.yml",
        'echo "## 👥 Deploying SSO Stack" >> $GITHUB_STEP_SUMMARY',
        "echo '## 👥 Deploying SSO Stack' >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-aws-deployment.yml",
        'echo "🏷️ **Created deployment tag**: \\`$TAG_NAME\\`" >> $GITHUB_STEP_SUMMARY',
        "echo '🏷️ **Created deployment tag**: `'\"$TAG_NAME\"'`' >> "
        "$GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-aws-deployment.yml",
        'echo "## 📊 Deployment Summary" >> $GITHUB_STEP_SUMMARY',
        "echo '## 📊 Deployment Summary' >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-cdk-synthesis.yml",
        'echo "## 🏗️ CDK Synthesis Results" >> $GITHUB_STEP_SUMMARY',
        "echo '## 🏗️ CDK Synthesis Results' >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-cdk-synthesis.yml",
        'echo "📄 **Templates generated**: $TEMPLATE_COUNT" >> $GITHUB_STEP_SUMMARY',
        "echo '📄 **Templates generated**: '\"$TEMPLATE_COUNT\""
        " >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-cdk-synthesis.yml",
        'echo "## 💰 Cost Estimation" >> $GITHUB_STEP_SUMMARY',
        "echo '## 💰 Cost Estimation' >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-cdk-synthesis.yml",
        'echo "### 💡 Additional Costs May Apply For:" >> $GITHUB_STEP_SUMMARY',
        "echo '### 💡 Additional Costs May Apply For:' >> $GITHUB_STEP_SUMMARY",
    ),
    (
        ".github/workflows/reusable-code-quality.yml",
        'echo "## 🧹 Code Quality Results" >> $GITHUB_STEP_SUMMARY',
        "echo '## 🧹 Code Quality Results' >> $GITHUB_STEP_SUMMARY",
    ),
]


def _steps(path: str) -> list[dict[str, Any]]:
    document = yaml.safe_load((ROOT / path).read_text())
    if "runs" in document:
        return list(document["runs"]["steps"])
    return [s for job in document["jobs"].values() for s in job.get("steps", [])]


def _step(path: str, identity: str) -> dict[str, Any]:
    return next(s for s in _steps(path) if s.get("id", s.get("name")) == identity)


def _inert(script: str, values: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    # No inherited credentials, profiles, BASH_ENV or command substitution from
    # data. Callers pass inert expressions or setup blocks with refusing stubs.
    return subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-euo", "pipefail", "-c", script],
        env={
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "BASH_ENV": "/dev/null",
            "ENV": "/dev/null",
            **values,
        },
        capture_output=True,
        timeout=5,
    )


@pytest.mark.parametrize(("path", "before", "after"), LOG_CASES)
@pytest.mark.parametrize(
    "value", ["3", "space and 'quotes'", r"literal $(false) `false` \\ text"]
)
def test_log_quoting_preserves_one_argument_and_stdout(
    path: str,
    before: str,
    after: str,
    value: str,
) -> None:
    actual_lines = {
        line.strip()
        for step in _steps(path)
        for line in step.get("run", "").splitlines()
    }
    assert after in actual_lines
    # The region is a real intended input value; the other samples are Bash
    # variable data in both versions, not emulation of GHA source injection.
    before = before.replace("${{ inputs.aws-region }}", "us-east-1")
    values = {"TEMPLATE_COUNT": value, "TAG_NAME": value, "CI_AWS_REGION": "us-east-1"}
    arguments = [
        line.removeprefix("echo ").split(" >> ", 1)[0] for line in (before, after)
    ]
    old_argv, new_argv = [
        _inert(r"printf '%s\0' " + text, values) for text in arguments
    ]
    assert old_argv.returncode == new_argv.returncode == 0
    assert old_argv.stdout == new_argv.stdout
    assert len(old_argv.stdout.split(b"\0")) == 2
    old_stdout, new_stdout = [_inert("echo " + text, values) for text in arguments]
    assert old_stdout.returncode == new_stdout.returncode == 0
    assert old_stdout.stdout == new_stdout.stdout


@pytest.mark.parametrize("version", ["2.1144.0", "2.166.0", "2.249.0", "next"])
def test_version_is_environment_data_and_validation_failure_stops_install(
    version: str, tmp_path: Path
) -> None:
    step = _step(".github/actions/setup-node-cdk/action.yml", "install-cdk")
    assert step["env"]["CI_CDK_VERSION"] == "${{ inputs.cdk-version }}"
    assert "${{" not in step["run"]
    # Refuse at the validator boundary without executing Node/npm/CDK. The
    # actual script must preserve numeric input as data and propagate refusal.
    result = _inert(
        "node() { printf '%s\\0' \"$CI_CDK_VERSION\"; return 23; }\n"
        "npm() { echo unexpected-install; return 99; }\n" + step["run"],
        {"CI_CDK_VERSION": version, "GITHUB_WORKSPACE": str(tmp_path)},
    )
    if version == "next":
        assert result.returncode == 1
        assert result.stdout == b""
    else:
        assert result.returncode == 23
        assert result.stdout == f"{version}\0".encode()


def test_tag_transport_is_one_inert_argument_and_keeps_binding() -> None:
    step = _step(".github/workflows/reusable-aws-deployment.yml", "create-tag")
    binding = step["env"]["CI_GITHUB_TOKEN"]
    assert binding == "${{ github.token }}"
    assert step["env"]["CI_REPOSITORY"] == "${{ github.repository }}"
    line = next(
        line.strip()
        for line in step["run"].splitlines()
        if line.strip().startswith("git push ")
    )
    word = line.removeprefix("git push ").removesuffix(' "$TAG_NAME"')
    result = _inert(
        r"printf '%s\0' " + word,
        {"CI_GITHUB_TOKEN": "example-token", "CI_REPOSITORY": "example/repo"},
    )
    assert result.returncode == 0
    assert (
        result.stdout
        == b"https://x-access-token:example-token@github.com/example/repo\0"
    )


@pytest.mark.parametrize("value", ["true", "false"])
def test_approval_boolean_contract_and_condition(value: str) -> None:
    path = ".github/workflows/reusable-aws-deployment.yml"
    document = yaml.safe_load((ROOT / path).read_text())
    assert (
        document[True]["workflow_call"]["inputs"]["require-approval"]["type"]
        == "boolean"
    )
    for identity in ("deploy-org", "deploy-sso"):
        step = _step(path, identity)
        assert step["env"]["CI_REQUIRE_APPROVAL"] == "${{ inputs.require-approval }}"
        line = next(
            line.strip()
            for line in step["run"].splitlines()
            if line.strip().startswith("if [[")
        )
        assert line == 'if [[ "$CI_REQUIRE_APPROVAL" == "true" ]]; then'
        result = _inert(
            line + " printf approved; else printf automatic; fi",
            {"CI_REQUIRE_APPROVAL": value},
        )
        assert result.returncode == 0
        assert result.stdout == (b"approved" if value == "true" else b"automatic")


@pytest.mark.parametrize(
    "failed", [None, "CI_RUFF_LINT_STATUS", "CI_RUFF_FORMAT_STATUS", "CI_MYPY_STATUS"]
)
@pytest.mark.parametrize("status", ["fail", "", "unknown"])
def test_quality_gate_condition_still_requires_three_passes(
    failed: str | None,
    status: str,
) -> None:
    step = _step(".github/workflows/reusable-code-quality.yml", "final-status")
    assert step["env"] == {
        "CI_RUFF_LINT_STATUS": "${{ steps.ruff-lint.outputs.status }}",
        "CI_RUFF_FORMAT_STATUS": "${{ steps.ruff-format.outputs.status }}",
        "CI_MYPY_STATUS": "${{ steps.mypy.outputs.status }}",
    }
    condition = step["run"].split("; then", 1)[0] + "; then"
    values = dict.fromkeys(step["env"], "pass")
    if failed:
        values[failed] = status
    result = _inert(condition + " printf pass; else printf fail; exit 1; fi", values)
    assert (result.returncode == 0) == (failed is None)
    assert result.stdout == (b"pass" if failed is None else b"fail")


PARSER_PATHS = {
    ".github/workflows/reusable-code-quality.yml",
    "tests/unit/test_workflow_parser_compat.py",
}

DEPLOYMENT_PATHS = {
    ".github/actions/setup-aws-credentials/action.yml",
    ".github/actions/setup-node-cdk/action.yml",
    ".github/workflows/reusable-aws-deployment.yml",
    ".github/actions/setup-python-uv/action.yml",
    "uv.lock",
}


def test_exact_parser_filter_keeps_mixed_and_unknown_infrastructure_selected() -> None:
    document = yaml.safe_load(
        (ROOT / ".github/workflows/deploy-infrastructure.yml").read_text()
    )
    ignored = document[True]["push"]["paths-ignore"]
    assert all(not any(character in path for character in "*?!") for path in ignored)
    assert set(ignored) >= PARSER_PATHS
    for deployment in DEPLOYMENT_PATHS:
        assert deployment not in ignored
        assert any(path not in ignored for path in {deployment})
        assert any(path not in ignored for path in PARSER_PATHS | {deployment})
    assert not any(path not in ignored for path in PARSER_PATHS)
    for removed in PARSER_PATHS:
        assert any(path not in set(ignored) - {removed} for path in PARSER_PATHS)
    for runtime in (
        "app.py",
        "infiquetra_aws_infra/organization_stack.py",
        "infiquetra_aws_infra/sso_stack.py",
        "pyproject.toml",
        "unknown-shared-input",
    ):
        assert any(path not in ignored for path in PARSER_PATHS | {runtime})


@pytest.mark.parametrize(
    "path",
    sorted(
        {path for path, _, _ in LOG_CASES}
        | {".github/actions/setup-node-cdk/action.yml"}
    ),
)
def test_workflow_shell_syntax_only(path: str) -> None:
    for step in _steps(path):
        if "run" not in step:
            continue
        result = subprocess.run(
            ["/bin/bash", "--noprofile", "--norc", "-n"],
            input=step["run"],
            text=True,
            capture_output=True,
            timeout=5,
            env={"PATH": "/usr/bin:/bin", "BASH_ENV": "/dev/null", "ENV": "/dev/null"},
        )
        assert result.returncode == 0, result.stderr
