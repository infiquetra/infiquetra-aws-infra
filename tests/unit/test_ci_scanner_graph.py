"""Graph ledger/report integrity controls; these are synthetic transport data.

Qualification also exercises the actual pinned SDK workers and a native graph
fixture outside this suite, without adding Checkov to project dependencies.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_ci_scanners import VERSIONS, _fixture_scope, _report, _targets

from tools import ci_scanner_plan as planner
from tools import ci_scanners as scanners


@pytest.fixture(autouse=True)
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _targets(tmp_path)
    Path("pyproject.toml").write_text("[tool.bandit]\n")


def graph_fixture(state: str) -> tuple[dict[str, Any], dict[str, Any]]:
    report, scope = _report("checkov"), _fixture_scope("checkov")
    rule = "CKV2_FIXTURE_1"
    scope["graph_registries"] = [[rule]]
    graph = scope["graph"]
    graph["batches"] = [
        {
            key: [rule]
            for key in ("registered", "selected", "started", "completed", "returned")
        }
    ]
    graph["batches"][0]["errors"] = []
    graph["returned_rule_ids"] = [rule]
    graph["evaluations"] = [[*scope["resources"][0], rule, state]]
    row = copy.deepcopy(report["results"]["passed_checks"][0])
    row.update(check_id=rule, check_result={"result": state})
    report["results"][state.lower() + "_checks"].append(row)
    report["summary"][state.lower()] += 1
    return report, scope


@pytest.mark.parametrize("state", ["PASSED", "FAILED", "SKIPPED"])
@pytest.mark.parametrize(
    "damage",
    [
        "phase",
        "results",
        "registry",
        "batch",
        "worker-start",
        "worker-completion",
        "worker-return",
        "worker-error",
        "phase-error",
        "duplicate-worker",
        "filtered",
        "missing",
        "extra",
        "duplicate",
        "state",
        "unknown",
        "duplicate-outcome",
    ],
)
def test_graph_requires_actual_execution_and_exact_report(
    state: str,
    damage: str,
) -> None:
    report, scope = graph_fixture(state)
    assert scanners._checkov(report, VERSIONS["checkov"], scope).findings == int(
        state == "FAILED"
    )
    graph = scope["graph"]
    batch = graph["batches"][0]
    rows = report["results"][state.lower() + "_checks"]
    if damage == "phase":
        graph["completed"] = False
    elif damage == "results":
        graph["results_observed"] = False
    elif damage == "registry":
        scope["graph_registries"].append(["CKV2_MISSING"])
    elif damage == "batch":
        graph["batches"] = []
    elif damage.startswith("worker-"):
        key = {
            "start": "started",
            "completion": "completed",
            "return": "returned",
            "error": "errors",
        }[damage[7:]]
        batch[key] = [["CKV2_FIXTURE_1", "RuntimeError"]] if key == "errors" else []
    elif damage == "phase-error":
        graph["errors"] = ["RuntimeError"]
    elif damage == "duplicate-worker":
        batch["completed"] *= 2
    elif damage == "filtered":
        graph["returned_rule_ids"] = []
    elif damage == "missing":
        rows.pop()
        report["summary"][state.lower()] -= 1
    elif damage == "extra":
        row = copy.deepcopy(rows[-1])
        row["check_id"] = "CKV2_UNEXECUTED"
        rows.append(row)
        report["summary"][state.lower()] += 1
    elif damage == "duplicate":
        rows.append(copy.deepcopy(rows[-1]))
        report["summary"][state.lower()] += 1
    elif damage == "state":
        other = "FAILED" if state != "FAILED" else "PASSED"
        row = rows.pop()
        row["check_result"]["result"] = other
        report["results"][other.lower() + "_checks"].append(row)
        report["summary"][state.lower()] -= 1
        report["summary"][other.lower()] += 1
    elif damage == "unknown":
        graph["evaluations"][0][3] = "UNKNOWN"
    else:
        graph["evaluations"] *= 2
    with pytest.raises(scanners.ScanError):
        scanners._checkov(report, VERSIONS["checkov"], scope)


@pytest.mark.parametrize("selected", [False, True])
def test_native_filtered_or_empty_graph_results_need_no_invented_records(
    selected: bool,
) -> None:
    report, scope = graph_fixture("PASSED")
    scope["graph"]["evaluations"] = []
    report["results"]["passed_checks"].pop()
    report["summary"]["passed"] -= 1
    if not selected:
        for key in ("selected", "started", "completed", "returned"):
            scope["graph"]["batches"][0][key] = []
        scope["graph"]["returned_rule_ids"] = []
    assert scanners._checkov(report, VERSIONS["checkov"], scope).findings == 0


def unknown_fixture(
    rule: str,
    kind: str,
    properties: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report, scope = _report("checkov"), _fixture_scope("checkov")
    resource = {"Type": kind, "Properties": properties}
    Path("cdk.out/Sample.template.json").write_text(
        json.dumps({"Resources": {"Sample": resource}})
    )
    name = kind + ".Sample"
    scope["resources"][0][1] = name
    scope["checks"][0][1] = name
    scope["evaluations"][0][1] = name
    report["results"]["passed_checks"][0]["resource"] = name
    identity = ["Sample.template.json", name, rule]
    scope["checks"].append(identity)
    scope["evaluations"].append([*identity, "UNKNOWN"])
    scope["unknown_context"] = [
        {"target": identity, "shape": planner.unknown_context(resource)}
    ]
    return report, scope


@pytest.mark.parametrize("rule", ["CKV_AWS_62", "CKV_AWS_63"])
@pytest.mark.parametrize(
    "kind", ["AWS::IAM::User", "AWS::IAM::Role", "AWS::IAM::Group"]
)
@pytest.mark.parametrize("properties", [{"UserName": "sample"}, {"Policies": []}])
def test_unknown_requires_source_and_native_context_nonapplicability(
    rule: str,
    kind: str,
    properties: Any,
) -> None:
    report, scope = unknown_fixture(rule, kind, properties)
    assert scanners._checkov(report, VERSIONS["checkov"], scope).findings == 0
    scope["unknown_context"] = []
    with pytest.raises(scanners.ScanError, match="missing source/context proof"):
        scanners._checkov(report, VERSIONS["checkov"], scope)


@pytest.mark.parametrize("rule", ["CKV_AWS_62", "CKV_AWS_63"])
@pytest.mark.parametrize(
    "properties",
    [
        {"Policies": ["unassessable"]},
        {"Policies": {}},
        {"Policies": ""},
        {"Policies": None},
        {"PolicyDocument": {}},
        [],
        None,
    ],
)
def test_malformed_unknown_cannot_become_an_advisory_success(
    rule: str,
    properties: Any,
) -> None:
    report, scope = unknown_fixture(rule, "AWS::IAM::User", properties)
    with pytest.raises(scanners.ScanError, match="unassessable"):
        scanners._checkov(report, VERSIONS["checkov"], scope)


@pytest.mark.parametrize(
    "damage", ["other-rule", "policy-resource", "context", "duplicate"]
)
def test_unknown_check_identity_and_evaluated_context_are_required(damage: str) -> None:
    rule = "CKV_AWS_999" if damage == "other-rule" else "CKV_AWS_62"
    kind = "AWS::IAM::Policy" if damage == "policy-resource" else "AWS::IAM::User"
    report, scope = unknown_fixture(rule, kind, {})
    if damage == "context":
        scope["unknown_context"][0]["shape"] = [True, True, False, False]
    elif damage == "duplicate":
        scope["unknown_context"] *= 2
    with pytest.raises(scanners.ScanError):
        scanners._checkov(report, VERSIONS["checkov"], scope)
