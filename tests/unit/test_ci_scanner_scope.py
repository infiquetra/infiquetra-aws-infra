"""Independent scope controls; fixture plans are not real scanner receipts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from test_ci_scanners import (
    VERSIONS,
    _fixture_scope,
    _report,
    _targets,
    _write,
)

from tools import ci_scanners as scanners


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    _targets(tmp_path)
    (tmp_path / "sample.py").write_text("print(1)\n")
    (tmp_path / "second.py").write_text("print(2)\n")
    (tmp_path / "pyproject.toml").write_text("[tool.bandit]\n")
    return tmp_path


@pytest.mark.parametrize("tool", ["bandit", "semgrep"])
@pytest.mark.parametrize(
    "damage", ["partial", "extra", "duplicate", "invalid", "missing"]
)
def test_consistent_partial_or_invalid_target_inventory_fails(
    source: Path, tool: str, damage: str
) -> None:
    report = _report(tool)
    scope = _fixture_scope(tool)
    scope["targets"] = ["sample.py", "second.py"]
    if tool == "semgrep":
        report["paths"]["scanned"] = ["sample.py", "second.py"]
    else:
        metrics = report["metrics"]
        metrics["./second.py"] = copy.deepcopy(metrics["./sample.py"])
        metrics["_totals"]["loc"] = 2

    def validate() -> scanners.Counts:
        if tool == "semgrep":
            return scanners._semgrep(report, VERSIONS[tool], scope)
        return scanners._bandit(report, scope)

    assert validate().scanned == 2
    paths = {
        "partial": ["sample.py"],
        "extra": ["sample.py", "second.py", "extra.py"],
        "duplicate": ["sample.py", "./sample.py", "second.py"],
        "invalid": ["sample.py", "../second.py"],
        "missing": [],
    }[damage]
    if tool == "semgrep":
        report["paths"]["scanned"] = paths
    else:
        metric = copy.deepcopy(report["metrics"]["./sample.py"])
        report["metrics"] = {p: copy.deepcopy(metric) for p in paths}
        report["metrics"]["_totals"] = copy.deepcopy(metric)
        report["metrics"]["_totals"]["loc"] = len(paths)
    with pytest.raises(scanners.ScanError):
        validate()


@pytest.mark.parametrize("tool", ["bandit", "semgrep"])
def test_planner_scope_allows_ignored_and_unsupported_files(
    source: Path, tool: str
) -> None:
    # Presence alone is not applicability. A real planner may ignore tests or
    # files without rules for their language; never require a static file count.
    (source / "not-applicable.unhandled").write_text("not code\n")
    scope = _fixture_scope(tool)
    report = _report(tool)
    result = (
        scanners._bandit(report, scope)
        if tool == "bandit"
        else scanners._semgrep(report, VERSIONS[tool], scope)
    )
    assert result.scanned == 1


@pytest.mark.parametrize("tool", list(VERSIONS))
@pytest.mark.parametrize(
    "damage", ["missing", "version", "argv", "root", "source", "plan-only"]
)
def test_planning_evidence_must_bind_actual_invocation_and_source(
    source: Path, tool: str, damage: str
) -> None:
    _write(tool, _report(tool))
    plan = scanners._scope_path(tool)
    value = json.loads(plan.read_text())
    if damage == "missing":
        plan.unlink()
    else:
        if damage == "version":
            value["version"] = "0.0.0"
        if damage == "argv":
            value["argv"] = ["--exclude", "*"]
        if damage == "root":
            value["root"] = "/different-source"
        if damage == "plan-only":
            value["mode"] = "plan"
        if damage == "source":
            value["target_sha256"][value["targets"][0]] = "0" * 64
        plan.write_text(json.dumps(value))
    with pytest.raises(scanners.ScanError):
        scanners.validate_report(tool, 0, VERSIONS[tool])


@pytest.mark.parametrize(
    "damage", ["partial", "duplicate", "extra", "invalid", "state", "error"]
)
def test_checkov_consistent_resource_count_does_not_prove_checks_complete(
    source: Path, damage: str
) -> None:
    report = _report("checkov", 1)
    scope = _fixture_scope("checkov", 1)
    assert scanners._checkov(report, VERSIONS["checkov"], scope).findings == 1
    if damage == "partial":
        report["results"]["passed_checks"] = []
        report["summary"]["passed"] = 0
    elif damage == "duplicate":
        report["results"]["passed_checks"] *= 2
        report["summary"]["passed"] = 2
    elif damage == "extra":
        report["results"]["passed_checks"][0]["resource"] = "AWS::S3::Bucket.Other"
    elif damage == "invalid":
        report["results"]["passed_checks"][0]["file_path"] = "/../Sample.template.json"
    elif damage == "state":
        scope["evaluations"][0][3] = "FAILED"
    else:
        scope["evaluation_errors"] = [scope["checks"][0]]
    with pytest.raises(scanners.ScanError):
        scanners._checkov(report, VERSIONS["checkov"], scope)


def test_checkov_keeps_legitimate_unknown_explicit_and_requires_its_execution(
    source: Path,
) -> None:
    report = _report("checkov")
    scope = _fixture_scope("checkov")
    identity = ["Sample.template.json", "AWS::S3::Bucket.Sample", "CKV_AWS_2"]
    scope["checks"].append(identity)
    with pytest.raises(scanners.ScanError, match="registry execution"):
        scanners._checkov(report, VERSIONS["checkov"], scope)
    scope["evaluations"].append([*identity, "UNKNOWN"])
    assert scanners._checkov(report, VERSIONS["checkov"], scope).findings == 0
    scope["evaluation_errors"].append(identity)
    with pytest.raises(scanners.ScanError, match="execution errors"):
        scanners._checkov(report, VERSIONS["checkov"], scope)


def test_checkov_resources_without_registered_checks_do_not_need_fabricated_records(
    source: Path,
) -> None:
    path = source / "cdk.out/Sample.template.json"
    value = json.loads(path.read_text())
    value["Resources"]["Unsupported"] = {
        "Type": "AWS::Organizations::OrganizationalUnit"
    }
    path.write_text(json.dumps(value))
    scope = _fixture_scope("checkov")
    scope["resources"].append(
        ["Sample.template.json", "AWS::Organizations::OrganizationalUnit.Unsupported"]
    )
    report = _report("checkov")
    report["summary"]["resource_count"] = 2
    result = scanners._checkov(report, VERSIONS["checkov"], scope)
    assert result == scanners.Counts(0, 2)
