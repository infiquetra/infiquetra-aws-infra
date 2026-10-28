"""Prepare, activate, and remove one temporary cross-account CI grant.

This program is invoked only by the manual, reviewed-main workflow. A grant
receipt is uploaded before activation so cleanup can recover even if the runner
dies after IAM accepts the policy-version request.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import boto3
from botocore.exceptions import ClientError

from tools.nonprod_deploy_roles_ci import (
    ACCOUNT,
    MANAGEMENT_ACCOUNT,
    REGION,
    ROLE_NAME,
    GuardError,
    _canonical,
    _digest,
    _run_id,
    check_head,
)

GITHUB_ROLE = "infiquetra-aws-infra-gha-role"
POLICY_NAME = "infiquetra-aws-infra-gha-cdk-policy"
SID = "TemporaryCamppsNonprodRolesCi"
MAX_DURATION = timedelta(hours=2)
SCHEMA = "campps-temporary-nonprod-role-v1"


def _iam_arn(account: str, kind: str, name: str) -> str:
    return f"arn:aws:iam::{account}:{kind}/{name}"


def session_policy(phase: str) -> dict[str, Any]:
    """Limit each phase to one policy and only the writes it needs."""
    writes = {
        "plan": [],
        "grant": ["iam:CreatePolicyVersion"],
        "cleanup": ["iam:SetDefaultPolicyVersion", "iam:DeletePolicyVersion"],
    }
    if phase not in writes:
        raise GuardError("invalid bootstrap phase")
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "iam:GetPolicy",
                    "iam:GetPolicyVersion",
                    "iam:ListPolicyVersions",
                    *writes[phase],
                ],
                "Resource": _iam_arn(MANAGEMENT_ACCOUNT, "policy", POLICY_NAME),
            },
            {
                "Effect": "Allow",
                "Action": [
                    "iam:GetRole",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                ],
                "Resource": _iam_arn(MANAGEMENT_ACCOUNT, "role", GITHUB_ROLE),
            },
        ],
    }


def expected_trust() -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": _iam_arn(
                        MANAGEMENT_ACCOUNT,
                        "oidc-provider",
                        "token.actions.githubusercontent.com",
                    )
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": (
                            "repo:infiquetra/infiquetra-aws-infra:ref:refs/heads/main"
                        ),
                    }
                },
            }
        ],
    }


def _document(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = json.loads(unquote(value))
    if not isinstance(value, dict):
        raise GuardError("IAM returned an invalid policy document")
    return value


def snapshot(iam: Any, sts: Any) -> dict[str, Any]:
    """Read and pin the identity, attachment, policy and every version."""
    identity = sts.get_caller_identity()
    role = iam.get_role(RoleName=GITHUB_ROLE)["Role"]
    role_arn = _iam_arn(MANAGEMENT_ACCOUNT, "role", GITHUB_ROLE)
    policy_arn = _iam_arn(MANAGEMENT_ACCOUNT, "policy", POLICY_NAME)
    principal_prefix = f"arn:aws:sts::{MANAGEMENT_ACCOUNT}:assumed-role/{GITHUB_ROLE}/"
    if (
        identity.get("Account") != MANAGEMENT_ACCOUNT
        or not str(identity.get("Arn", "")).startswith(principal_prefix)
        or role.get("RoleName") != GITHUB_ROLE
        or role.get("Arn") != role_arn
        or role.get("Path") != "/"
        or not str(identity.get("UserId", "")).startswith(f"{role.get('RoleId')}:")
        or not role.get("RoleId")
        or not isinstance(role.get("MaxSessionDuration"), int)
        or not 3600 <= role["MaxSessionDuration"] <= 43200
        or role.get("PermissionsBoundary")
        or _document(role.get("AssumeRolePolicyDocument")) != expected_trust()
    ):
        raise GuardError("management role identity, trust, or boundary changed")

    attached_response = iam.list_attached_role_policies(RoleName=GITHUB_ROLE)
    inline_response = iam.list_role_policies(RoleName=GITHUB_ROLE)
    if attached_response.get("IsTruncated") or inline_response.get("IsTruncated"):
        raise GuardError("role policy inventory was truncated")
    attached = attached_response.get("AttachedPolicies", [])
    if attached != [{"PolicyName": POLICY_NAME, "PolicyArn": policy_arn}]:
        raise GuardError("the management role's attached policies changed")
    if inline_response.get("PolicyNames") != []:
        raise GuardError("the management role has inline policies")

    policy = iam.get_policy(PolicyArn=policy_arn)["Policy"]
    if (
        policy.get("Arn") != policy_arn
        or policy.get("PolicyName") != POLICY_NAME
        or policy.get("Path") != "/"
        or not policy.get("PolicyId")
        or policy.get("AttachmentCount") != 1
        or policy.get("PermissionsBoundaryUsageCount") != 0
    ):
        raise GuardError("managed policy identity or attachments changed")

    listed = iam.list_policy_versions(PolicyArn=policy_arn)
    if listed.get("IsTruncated"):
        raise GuardError("managed policy version inventory was truncated")
    versions = listed.get("Versions", [])
    ids = [item.get("VersionId") for item in versions]
    defaults = [
        item.get("VersionId") for item in versions if item.get("IsDefaultVersion")
    ]
    default = policy.get("DefaultVersionId")
    if (
        not versions
        or len(ids) != len(set(ids))
        or any(
            not isinstance(i, str) or not re.fullmatch(r"v[1-9][0-9]*", i) for i in ids
        )
        or defaults != [default]
    ):
        raise GuardError("managed policy default/version inventory is inconsistent")
    documents = {
        version: _document(
            iam.get_policy_version(PolicyArn=policy_arn, VersionId=version)[
                "PolicyVersion"
            ]["Document"]
        )
        for version in sorted(ids)
    }
    return {
        "role_id": role["RoleId"],
        "role_max_session_duration": role["MaxSessionDuration"],
        "policy_id": policy["PolicyId"],
        "default": default,
        "versions": documents,
    }


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
    ):
        raise GuardError("expiry must be a UTC timestamp in seconds")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise GuardError("invalid UTC timestamp") from exc


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def temporary_policy(original: Mapping[str, Any], expiry: str) -> dict[str, Any]:
    """Append only the reviewed, expiring grant to the original document."""
    _timestamp(expiry)
    result = deepcopy(dict(original))
    statements = result.get("Statement")
    if result.get("Version") != "2012-10-17" or not isinstance(statements, list):
        raise GuardError("baseline policy has an unexpected shape")
    if any(not isinstance(s, dict) or s.get("Sid") == SID for s in statements):
        raise GuardError("baseline contains an invalid or existing temporary statement")
    statements.append(
        {
            "Sid": SID,
            "Effect": "Allow",
            "Action": "sts:AssumeRole",
            "Resource": _iam_arn(ACCOUNT, "role", ROLE_NAME),
            "Condition": {
                "StringLike": {"sts:RoleSessionName": "campps-nonprod-roles-*"},
                "DateLessThan": {"aws:CurrentTime": expiry},
            },
        }
    )
    if len(_canonical(result)) > 6144:
        raise GuardError("temporary policy exceeds the IAM managed policy size limit")
    return result


def _baseline_document(baseline: Mapping[str, Any]) -> dict[str, Any]:
    versions = baseline.get("versions")
    default = baseline.get("default")
    if not isinstance(versions, dict) or default not in versions:
        raise GuardError("receipt does not contain the original default version")
    return _document(versions[default])


def make_plan(
    baseline: dict[str, Any], *, head: str, run_id: str, minutes: int, now: datetime
) -> dict[str, Any]:
    if minutes < 1 or minutes > 120 or len(baseline["versions"]) >= 5:
        raise GuardError("duration or available policy-version slot is invalid")
    expiry = _format_time(now + timedelta(minutes=minutes))
    candidate = temporary_policy(_baseline_document(baseline), expiry)
    return {
        "schema": SCHEMA,
        "head": head,
        "plan_run_id": _run_id(run_id),
        "planned_at": _format_time(now),
        "expires_at": expiry,
        "baseline": baseline,
        "candidate": candidate,
    }


def validate_plan(plan: dict[str, Any], *, now: datetime, require_live: bool) -> None:
    if plan.get("schema") != SCHEMA or not re.fullmatch(
        r"[0-9a-f]{40}", str(plan.get("head", ""))
    ):
        raise GuardError("unexpected receipt schema or head")
    _run_id(str(plan.get("plan_run_id", "")))
    planned_at = _timestamp(plan.get("planned_at"))
    expiry = _timestamp(plan.get("expires_at"))
    if expiry <= planned_at or expiry - planned_at > MAX_DURATION:
        raise GuardError("temporary exception exceeds two hours")
    if require_live and (
        planned_at > now or expiry <= now or expiry - now > MAX_DURATION
    ):
        raise GuardError("the planned exception is expired or not yet valid")
    baseline = plan.get("baseline")
    if not isinstance(baseline, dict) or len(baseline.get("versions", {})) >= 5:
        raise GuardError("invalid baseline or no available version slot")
    if plan.get("candidate") != temporary_policy(
        _baseline_document(baseline), plan["expires_at"]
    ):
        raise GuardError("candidate is not the sole permitted temporary statement")


def prepare_grant(
    plan: dict[str, Any],
    *,
    baseline: dict[str, Any],
    head: str,
    plan_run_id: str,
    plan_digest: str,
    grant_run_id: str,
    now: datetime,
) -> dict[str, Any]:
    validate_plan(plan, now=now, require_live=True)
    if (
        plan["head"] != head
        or plan["plan_run_id"] != _run_id(plan_run_id)
        or not re.fullmatch(r"[0-9a-f]{64}", plan_digest)
        or _digest(plan) != plan_digest
        or plan["baseline"] != baseline
    ):
        raise GuardError("reviewed plan, current head, or policy baseline changed")
    return {
        "schema": SCHEMA,
        "grant_run_id": _run_id(grant_run_id),
        "plan_digest": plan_digest,
        "plan": plan,
    }


def _validate_grant(
    grant: dict[str, Any], *, run_id: str, digest: str, now: datetime, live: bool
) -> dict[str, Any]:
    if (
        grant.get("schema") != SCHEMA
        or grant.get("grant_run_id") != _run_id(run_id)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or _digest(grant) != digest
        or not isinstance(grant.get("plan"), dict)
        or _digest(grant["plan"]) != grant.get("plan_digest")
    ):
        raise GuardError("grant receipt or its review digest changed")
    plan: dict[str, Any] = grant["plan"]
    validate_plan(plan, now=now, require_live=live)
    return plan


def activate(
    iam: Any,
    sts: Any,
    grant: dict[str, Any],
    *,
    head: str,
    run_id: str,
    digest: str,
    now: datetime,
    head_guard: Callable[[], None],
) -> dict[str, Any]:
    plan = _validate_grant(grant, run_id=run_id, digest=digest, now=now, live=True)
    if plan["head"] != head or snapshot(iam, sts) != plan["baseline"]:
        raise GuardError("main or the original policy changed before activation")
    head_guard()
    # Recheck at the write boundary; IAM has no conditional policy-version API.
    if snapshot(iam, sts) != plan["baseline"]:
        raise GuardError("policy changed immediately before activation")
    validate_plan(plan, now=datetime.now(UTC), require_live=True)
    result = iam.create_policy_version(
        PolicyArn=_iam_arn(MANAGEMENT_ACCOUNT, "policy", POLICY_NAME),
        PolicyDocument=_canonical(plan["candidate"]).decode(),
        SetAsDefault=True,
    )["PolicyVersion"]
    version = result.get("VersionId")
    if not isinstance(version, str):
        raise GuardError("activation omitted the version; use the recovery receipt")
    _wait_snapshot(
        iam,
        sts,
        lambda current: (
            current["default"] == version
            and _candidate_version(current, plan) == version
        ),
        "activation was not verified; use the recovery receipt",
    )
    return {
        "schema": SCHEMA,
        "grant_run_id": run_id,
        "grant_digest": digest,
        "original_version": plan["baseline"]["default"],
        "temporary_version": version,
        "temporary_document_digest": _digest(plan["candidate"]),
        "expires_at": plan["expires_at"],
    }


def _candidate_version(current: dict[str, Any], plan: dict[str, Any]) -> str | None:
    baseline = plan["baseline"]
    identity_keys = ("role_id", "role_max_session_duration", "policy_id")
    if {k: current[k] for k in identity_keys} != {
        k: baseline[k] for k in identity_keys
    }:
        raise GuardError("policy or role identity changed")
    old = baseline["versions"]
    versions = current["versions"]
    if any(versions.get(version) != document for version, document in old.items()):
        raise GuardError("an original policy version changed or disappeared")
    added = set(versions) - set(old)
    if len(added) > 1:
        raise GuardError("unrelated policy versions appeared")
    candidate = next(iter(added), None)
    if candidate and versions[candidate] != plan["candidate"]:
        raise GuardError("an unrelated policy version appeared")
    if current["default"] not in {baseline["default"], candidate}:
        raise GuardError("an unrelated policy version became the default")
    return candidate


def _wait_snapshot(
    iam: Any,
    sts: Any,
    predicate: Callable[[dict[str, Any]], bool],
    message: str,
) -> dict[str, Any]:
    """Bounded reads after a write tolerate IAM's eventual consistency."""
    for attempt in range(12):
        try:
            current = snapshot(iam, sts)
            if predicate(current):
                return current
        except (ClientError, GuardError):
            pass
        if attempt < 11:
            time.sleep(1)
    raise GuardError(message)


def cleanup(
    iam: Any,
    sts: Any,
    grant: dict[str, Any],
    *,
    run_id: str,
    digest: str,
    now: datetime,
    head_guard: Callable[[], None],
) -> dict[str, Any]:
    """Restore the original version and remove only the matching temporary version."""
    plan = _validate_grant(grant, run_id=run_id, digest=digest, now=now, live=False)
    policy_arn = _iam_arn(MANAGEMENT_ACCOUNT, "policy", POLICY_NAME)
    current = snapshot(iam, sts)
    candidate = _candidate_version(current, plan)
    original = plan["baseline"]["default"]
    if candidate and current["default"] == candidate:
        head_guard()
        if snapshot(iam, sts) != current:
            raise GuardError("policy changed immediately before restoring the original")
        iam.set_default_policy_version(PolicyArn=policy_arn, VersionId=original)
        current = _wait_snapshot(
            iam,
            sts,
            lambda state: (
                state["default"] == original
                and _candidate_version(state, plan) == candidate
            ),
            "original default restoration could not be verified",
        )
    if candidate:
        head_guard()
        if snapshot(iam, sts) != current:
            raise GuardError(
                "policy changed immediately before removing the temporary version"
            )
        iam.delete_policy_version(PolicyArn=policy_arn, VersionId=candidate)
    _wait_snapshot(
        iam,
        sts,
        lambda state: state == plan["baseline"],
        "cleanup did not restore the exact recorded policy baseline",
    )
    return {
        "schema": SCHEMA,
        "grant_run_id": run_id,
        "grant_digest": digest,
        "original_version": original,
        "removed_temporary_version": candidate,
        "baseline_digest": _digest(plan["baseline"]),
    }


def _read(path: Path) -> dict[str, Any]:
    return _document(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value) + b"\n")
    digest = _digest(value)
    print(f"{path.name} SHA-256: {digest}")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"receipt_digest={digest}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open(
            "a", encoding="utf-8"
        ) as summary:
            summary.write(f"`{path.name}` SHA-256: `{digest}`\n")


def main() -> None:
    command = sys.argv[1:]
    if command == ["identity"]:
        policy = _canonical(session_policy(os.environ.get("PHASE", ""))).decode()
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"policy={policy}\n")
        return
    if len(command) != 1 or command[0] not in {
        "plan",
        "prepare",
        "activate",
        "cleanup",
    }:
        raise GuardError("expected identity, plan, prepare, activate, or cleanup")
    head = os.environ.get("EXPECTED_HEAD", "")

    def head_guard() -> None:
        check_head(head, os.environ)

    head_guard()
    iam = boto3.Session(region_name=REGION).client("iam")
    sts = boto3.Session(region_name=REGION).client("sts")
    root = Path(os.environ["RUNNER_TEMP"]) / "campps-role-bootstrap"
    run_id = _run_id(os.environ.get("GITHUB_RUN_ID", ""))
    now = datetime.now(UTC)
    if command == ["plan"]:
        duration = os.environ.get("DURATION_MINUTES", "")
        if not re.fullmatch(r"[1-9][0-9]{0,2}", duration):
            raise GuardError("duration must be a whole number of minutes")
        result = make_plan(
            snapshot(iam, sts), head=head, run_id=run_id, minutes=int(duration), now=now
        )
        _save(root / "plan.json", result)
    elif command == ["prepare"]:
        result = prepare_grant(
            _read(root / "download" / "plan.json"),
            baseline=snapshot(iam, sts),
            head=head,
            plan_run_id=os.environ.get("RECEIPT_RUN_ID", ""),
            plan_digest=os.environ.get("RECEIPT_DIGEST", ""),
            grant_run_id=run_id,
            now=now,
        )
        _save(root / "grant.json", result)
    elif command == ["activate"]:
        result = activate(
            iam,
            sts,
            _read(root / "grant.json"),
            head=head,
            run_id=run_id,
            digest=os.environ.get("PREPARED_DIGEST", ""),
            now=now,
            head_guard=head_guard,
        )
        _save(root / "activation.json", result)
    else:
        result = cleanup(
            iam,
            sts,
            _read(root / "download" / "grant.json"),
            run_id=os.environ.get("RECEIPT_RUN_ID", ""),
            digest=os.environ.get("RECEIPT_DIGEST", ""),
            now=now,
            head_guard=head_guard,
        )
        _save(root / "cleanup.json", result)


if __name__ == "__main__":
    try:
        main()
    except (GuardError, KeyError, ValueError, OSError) as exc:
        print(f"Bootstrap guard failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
