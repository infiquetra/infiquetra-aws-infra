"""Safety and recovery tests for the temporary management policy exception."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from tools import nonprod_role_bootstrap_ci as bootstrap
from tools.nonprod_deploy_roles_ci import GuardError, _digest

HEAD = "a" * 40
ROLE_ID = "AROATESTONLY"
POLICY_ID = "ANPATESTONLY"
ORIGINAL: dict[str, Any] = {
    "Version": "2012-10-17",
    "Statement": [
        {"Sid": "Existing", "Effect": "Allow", "Action": "iam:GetRole", "Resource": "*"}
    ],
}


class FakeSts:
    def get_caller_identity(self) -> dict[str, str]:
        return {
            "Account": bootstrap.MANAGEMENT_ACCOUNT,
            "Arn": (
                f"arn:aws:sts::{bootstrap.MANAGEMENT_ACCOUNT}:"
                f"assumed-role/{bootstrap.GITHUB_ROLE}/test"
            ),
            "UserId": f"{ROLE_ID}:test",
        }


class FakeIam:
    def __init__(self) -> None:
        self.role: dict[str, Any] = {
            "RoleName": bootstrap.GITHUB_ROLE,
            "Arn": bootstrap._iam_arn(
                bootstrap.MANAGEMENT_ACCOUNT, "role", bootstrap.GITHUB_ROLE
            ),
            "RoleId": ROLE_ID,
            "Path": "/",
            "MaxSessionDuration": 43200,
            "AssumeRolePolicyDocument": bootstrap.expected_trust(),
        }
        self.policy = {
            "PolicyName": bootstrap.POLICY_NAME,
            "Arn": bootstrap._iam_arn(
                bootstrap.MANAGEMENT_ACCOUNT, "policy", bootstrap.POLICY_NAME
            ),
            "PolicyId": POLICY_ID,
            "Path": "/",
            "AttachmentCount": 1,
            "PermissionsBoundaryUsageCount": 0,
        }
        self.attached = [
            {"PolicyName": bootstrap.POLICY_NAME, "PolicyArn": self.policy["Arn"]}
        ]
        self.inline: list[str] = []
        self.versions: dict[str, dict[str, Any]] = {"v2": deepcopy(ORIGINAL)}
        self.default = "v2"
        self.writes: list[tuple[str, str]] = []

    def get_role(self, **_: Any) -> dict[str, Any]:
        return {"Role": deepcopy(self.role)}

    def list_attached_role_policies(self, **_: Any) -> dict[str, Any]:
        return {"AttachedPolicies": deepcopy(self.attached)}

    def list_role_policies(self, **_: Any) -> dict[str, Any]:
        return {"PolicyNames": deepcopy(self.inline)}

    def get_policy(self, **_: Any) -> dict[str, Any]:
        return {"Policy": {**deepcopy(self.policy), "DefaultVersionId": self.default}}

    def list_policy_versions(self, **_: Any) -> dict[str, Any]:
        return {
            "Versions": [
                {"VersionId": version, "IsDefaultVersion": version == self.default}
                for version in self.versions
            ]
        }

    def get_policy_version(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "PolicyVersion": {"Document": deepcopy(self.versions[kwargs["VersionId"]])}
        }

    def create_policy_version(self, **kwargs: Any) -> dict[str, Any]:
        version = "v3"
        self.versions[version] = json.loads(kwargs["PolicyDocument"])
        if kwargs["SetAsDefault"]:
            self.default = version
        self.writes.append(("create", version))
        return {
            "PolicyVersion": {
                "VersionId": version,
                "IsDefaultVersion": kwargs["SetAsDefault"],
            }
        }

    def set_default_policy_version(self, **kwargs: Any) -> None:
        self.default = kwargs["VersionId"]
        self.writes.append(("default", self.default))

    def delete_policy_version(self, **kwargs: Any) -> None:
        version = kwargs["VersionId"]
        assert version != self.default
        del self.versions[version]
        self.writes.append(("delete", version))


def setup() -> tuple[FakeIam, FakeSts, dict[str, Any], dict[str, Any], datetime]:
    iam, sts = FakeIam(), FakeSts()
    now = datetime.now(UTC).replace(microsecond=0)
    baseline = bootstrap.snapshot(iam, sts)
    plan = bootstrap.make_plan(baseline, head=HEAD, run_id="12", minutes=120, now=now)
    grant = bootstrap.prepare_grant(
        plan,
        baseline=baseline,
        head=HEAD,
        plan_run_id="12",
        plan_digest=_digest(plan),
        grant_run_id="34",
        now=now,
    )
    return iam, sts, plan, grant, now


def activate(
    iam: FakeIam, sts: FakeSts, grant: dict[str, Any], now: datetime
) -> dict[str, Any]:
    return bootstrap.activate(
        iam,
        sts,
        grant,
        head=HEAD,
        run_id="34",
        digest=_digest(grant),
        now=now,
        head_guard=lambda: None,
    )


def cleanup(
    iam: FakeIam, sts: FakeSts, grant: dict[str, Any], now: datetime
) -> dict[str, Any]:
    return bootstrap.cleanup(
        iam,
        sts,
        grant,
        run_id="34",
        digest=_digest(grant),
        now=now,
        head_guard=lambda: None,
    )


@pytest.mark.parametrize(
    ("phase", "writes"),
    [
        ("plan", set()),
        ("grant", {"iam:CreatePolicyVersion"}),
        ("cleanup", {"iam:SetDefaultPolicyVersion", "iam:DeletePolicyVersion"}),
    ],
)
def test_session_can_modify_only_the_existing_policy_and_read_only_its_role(
    phase: str, writes: set[str]
) -> None:
    policy, role = bootstrap.session_policy(phase)["Statement"]
    assert policy["Resource"] == bootstrap._iam_arn(
        bootstrap.MANAGEMENT_ACCOUNT, "policy", bootstrap.POLICY_NAME
    )
    assert (
        set(policy["Action"])
        == {
            "iam:GetPolicy",
            "iam:GetPolicyVersion",
            "iam:ListPolicyVersions",
        }
        | writes
    )
    assert role["Resource"] == bootstrap._iam_arn(
        bootstrap.MANAGEMENT_ACCOUNT, "role", bootstrap.GITHUB_ROLE
    )
    assert set(role["Action"]) == {
        "iam:GetRole",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
    }


def test_unknown_phase_cannot_prepare_a_session() -> None:
    with pytest.raises(GuardError):
        bootstrap.session_policy("other")


def test_plan_adds_only_exact_time_limited_statement() -> None:
    _, _, plan, _, now = setup()
    assert bootstrap._timestamp(plan["expires_at"]) == now + timedelta(hours=2)
    assert plan["candidate"]["Statement"][:-1] == ORIGINAL["Statement"]
    assert plan["candidate"]["Statement"][-1] == {
        "Sid": bootstrap.SID,
        "Effect": "Allow",
        "Action": "sts:AssumeRole",
        "Resource": bootstrap._iam_arn(bootstrap.ACCOUNT, "role", bootstrap.ROLE_NAME),
        "Condition": {
            "StringLike": {"sts:RoleSessionName": "campps-nonprod-roles-*"},
            "DateLessThan": {"aws:CurrentTime": plan["expires_at"]},
        },
    }


@pytest.mark.parametrize("duration", [0, 121, 999])
def test_plan_rejects_out_of_range_duration(duration: int) -> None:
    iam, sts, _, _, now = setup()
    with pytest.raises(GuardError):
        bootstrap.make_plan(
            bootstrap.snapshot(iam, sts),
            head=HEAD,
            run_id="12",
            minutes=duration,
            now=now,
        )


def test_grant_and_cleanup_restore_exact_original_and_are_retryable() -> None:
    iam, sts, plan, grant, now = setup()
    activation = activate(iam, sts, grant, now)
    assert activation["original_version"] == "v2"
    assert activation["temporary_version"] == "v3"
    assert iam.versions["v3"] == plan["candidate"]
    result = cleanup(iam, sts, grant, now + timedelta(hours=3))
    assert result["removed_temporary_version"] == "v3"
    assert iam.default == "v2"
    assert iam.versions == {"v2": ORIGINAL}
    assert iam.writes == [("create", "v3"), ("default", "v2"), ("delete", "v3")]
    assert cleanup(iam, sts, grant, now)["removed_temporary_version"] is None
    assert len(iam.writes) == 3


def test_cleanup_recovers_when_activation_receipt_was_lost() -> None:
    iam, sts, plan, grant, now = setup()
    iam.versions["v3"] = deepcopy(plan["candidate"])
    iam.default = "v3"
    assert cleanup(iam, sts, grant, now)["removed_temporary_version"] == "v3"
    assert iam.versions == {"v2": ORIGINAL}


def test_recovery_receipt_handles_a_write_that_never_happened() -> None:
    iam, sts, _, grant, now = setup()
    assert cleanup(iam, sts, grant, now)["removed_temporary_version"] is None
    assert iam.writes == []


def test_cleanup_retries_after_original_was_restored_but_delete_failed() -> None:
    iam, sts, plan, grant, now = setup()
    iam.versions["v3"] = deepcopy(plan["candidate"])
    assert cleanup(iam, sts, grant, now)["removed_temporary_version"] == "v3"
    assert iam.writes == [("delete", "v3")]


def test_eventual_consistency_is_retried_without_another_write(
    monkeypatch: Any,
) -> None:
    iam, sts, _, _, _ = setup()
    expected = bootstrap.snapshot(iam, sts)
    calls = 0

    def stale_reads(_iam: Any, _sts: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise GuardError("IAM has not converged")
        return expected

    monkeypatch.setattr(bootstrap, "snapshot", stale_reads)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    assert (
        bootstrap._wait_snapshot(iam, sts, lambda state: state == expected, "failed")
        == expected
    )
    assert calls == 3
    assert iam.writes == []


@pytest.mark.parametrize(
    "drift",
    ["document", "attachment", "trust", "boundary", "role_id", "duration", "inline"],
)
def test_changed_identity_or_baseline_fails_before_grant(drift: str) -> None:
    iam, sts, _, grant, now = setup()
    if drift == "document":
        iam.versions["v2"]["Statement"][0]["Action"] = "iam:DeleteRole"
    elif drift == "attachment":
        iam.policy["AttachmentCount"] = 2
    elif drift == "trust":
        iam.role["AssumeRolePolicyDocument"]["Statement"][0]["Condition"] = {}
    elif drift == "boundary":
        iam.role["PermissionsBoundary"] = {"PermissionsBoundaryArn": "unexpected"}
    elif drift == "role_id":
        iam.role["RoleId"] = "different"
    elif drift == "duration":
        iam.role["MaxSessionDuration"] = 3600
    else:
        iam.inline.append("unexpected")
    with pytest.raises(GuardError):
        activate(iam, sts, grant, now)
    assert iam.writes == []


@pytest.mark.parametrize(
    "drift", ["document", "extra_version", "different_default", "policy_id"]
)
def test_cleanup_refuses_unrelated_policy_changes(drift: str) -> None:
    iam, sts, plan, grant, now = setup()
    iam.versions["v3"] = deepcopy(plan["candidate"])
    iam.default = "v3"
    if drift == "document":
        iam.versions["v2"]["Statement"][0]["Action"] = "iam:DeleteRole"
    elif drift == "extra_version":
        iam.versions["v4"] = deepcopy(ORIGINAL)
    elif drift == "different_default":
        iam.versions["v4"] = deepcopy(ORIGINAL)
        iam.default = "v4"
    else:
        iam.policy["PolicyId"] = "different"
    with pytest.raises(GuardError):
        cleanup(iam, sts, grant, now)
    assert iam.writes == []


def test_changed_receipt_head_or_expiry_refuses_grant() -> None:
    iam, sts, plan, grant, now = setup()
    with pytest.raises(GuardError):
        bootstrap.prepare_grant(
            plan,
            baseline=bootstrap.snapshot(iam, sts),
            head="b" * 40,
            plan_run_id="12",
            plan_digest=_digest(plan),
            grant_run_id="34",
            now=now,
        )
    with pytest.raises(GuardError):
        bootstrap.activate(
            iam,
            sts,
            grant,
            head=HEAD,
            run_id="34",
            digest="0" * 64,
            now=now,
            head_guard=lambda: None,
        )
    with pytest.raises(GuardError):
        bootstrap.activate(
            iam,
            sts,
            grant,
            head=HEAD,
            run_id="34",
            digest=_digest(grant),
            now=now + timedelta(hours=2),
            head_guard=lambda: None,
        )
    assert iam.writes == []


def test_tampered_candidate_is_rejected_even_with_a_matching_digest() -> None:
    iam, sts, plan, _, now = setup()
    plan["candidate"]["Statement"][-1]["Action"] = "sts:*"
    with pytest.raises(GuardError):
        bootstrap.prepare_grant(
            plan,
            baseline=bootstrap.snapshot(iam, sts),
            head=HEAD,
            plan_run_id="12",
            plan_digest=_digest(plan),
            grant_run_id="34",
            now=now,
        )
    assert iam.writes == []


def test_mutation_between_initial_check_and_write_is_refused() -> None:
    iam, sts, _, grant, now = setup()

    def concurrent_change() -> None:
        iam.versions["v2"]["Statement"][0]["Action"] = "iam:DeleteRole"

    with pytest.raises(GuardError):
        bootstrap.activate(
            iam,
            sts,
            grant,
            head=HEAD,
            run_id="34",
            digest=_digest(grant),
            now=now,
            head_guard=concurrent_change,
        )
    assert iam.writes == []


def test_workflow_is_manual_current_main_and_saves_recovery_before_write() -> None:
    root = Path(__file__).parents[2]
    workflow = yaml.safe_load(
        (root / ".github/workflows/bootstrap-campps-nonprod-roles.yml").read_text()
    )
    assert set(workflow[True]) == {"workflow_dispatch"}
    job = workflow["jobs"]["bootstrap"]
    assert "refs/heads/main" in job["if"]
    assert job["permissions"] == {
        "actions": "read",
        "contents": "read",
        "id-token": "write",
    }
    names = [step.get("name", "") for step in job["steps"]]
    assert names.index("Preserve the recovery receipt before activation") < names.index(
        "Activate only the reviewed temporary policy"
    )
    assert names.index("Download the reviewed recovery receipt") < names.index(
        "Restore and verify the recorded policy baseline"
    )
    assert job["env"]["AWS_REGION"] == "us-east-1"
    assert workflow["concurrency"]["group"] == "campps-nonprod-deploy-roles"
