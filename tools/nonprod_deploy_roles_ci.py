"""Plan or apply the reviewed nonproduction deploy-role change set in CI.

The workflow is manual, main-only, and runs this guard immediately before every
write. It accepts only the four resources introduced by infrastructure PR 178.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3

ACCOUNT = "477152411873"
MANAGEMENT_ACCOUNT = "645166163764"
REGION = "us-east-1"
STACK = "CamppsNonProdDeployRolesStack"
ROLE_NAME = "org-admin"
EXECUTION_ROLE_NAME = f"cdk-hnb659fds-cfn-exec-role-{ACCOUNT}-{REGION}"
BUCKET = f"cdk-hnb659fds-assets-{ACCOUNT}-{REGION}"
OBJECT_PREFIX = "campps-nonprod-deploy-roles-ci/"
CHANGESET_PREFIX = "campps-nonprod-roles-ci-"
REPO = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO / "cdk.out" / f"{STACK}.template.json"
ROLE_POLICIES = {
    "CoppaConsentDeployRoleB2456F4F": "CoppaConsentHorizonProofPolicyD615C2A4",
    "TenantSetupDeployRole5914AC60": "TenantFixtureRepairPolicyD1012943",
}
ROLE_IDS = frozenset(ROLE_POLICIES)
POLICY_IDS = frozenset(ROLE_POLICIES.values())
EXPECTED_RESOURCE_IDS = ROLE_IDS | POLICY_IDS
EXPECTED_PARAMETERS = frozenset({"BootstrapVersion"})


class GuardError(RuntimeError):
    """A safety condition failed before an update could be executed."""


def _arn(service: str, resource: str, *, region: str = REGION) -> str:
    return f"arn:aws:{service}:{region}:{ACCOUNT}:{resource}"


def session_policy() -> dict[str, Any]:
    """Restrict the existing nonprod administrator session to this operation."""
    stack = _arn("cloudformation", f"stack/{STACK}/*")
    execution_role = _arn("iam", f"role/{EXECUTION_ROLE_NAME}", region="")
    template_url = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{OBJECT_PREFIX}*"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "cloudformation:DescribeStacks",
                    "cloudformation:GetTemplate",
                    # The receipt checks the exact prefixed name before execute.
                    "cloudformation:DescribeChangeSet",
                ],
                "Resource": stack,
            },
            {
                "Effect": "Allow",
                "Action": "cloudformation:CreateChangeSet",
                "Resource": stack,
                "Condition": {
                    "StringLike": {
                        "cloudformation:ChangeSetName": f"{CHANGESET_PREFIX}*",
                        "cloudformation:TemplateUrl": template_url,
                    },
                    "StringEquals": {"cloudformation:RoleArn": execution_role},
                },
            },
            {
                "Effect": "Allow",
                "Action": [
                    "cloudformation:ExecuteChangeSet",
                ],
                "Resource": stack,
                "Condition": {
                    "StringLike": {
                        "cloudformation:ChangeSetName": [
                            f"{CHANGESET_PREFIX}*",
                            _arn("cloudformation", f"changeSet/{CHANGESET_PREFIX}*/*"),
                        ]
                    }
                },
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": f"arn:aws:s3:::{BUCKET}/{OBJECT_PREFIX}*",
            },
            {
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": execution_role,
                "Condition": {
                    "StringEquals": {
                        "iam:PassedToService": "cloudformation.amazonaws.com"
                    }
                },
            },
        ],
    }


def required_management_grant() -> dict[str, Any]:
    """The existing management role lacks this exact cross-account grant."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": _arn("iam", f"role/{ROLE_NAME}", region=""),
                "Condition": {
                    "StringLike": {"sts:RoleSessionName": "campps-nonprod-roles-*"}
                },
            }
        ],
    }


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _document(value: Any) -> dict[str, Any]:
    result = json.loads(value) if isinstance(value, str) else value
    if not isinstance(result, dict):
        raise GuardError("CloudFormation returned an invalid template")
    return result


def preserve_deployed_cdk_metadata(
    deployed: Mapping[str, Any], synthesized: Mapping[str, Any]
) -> dict[str, Any]:
    """Keep the existing analytics-only metadata so it is not a fifth change."""
    old = deployed.get("Resources", {}).get("CDKMetadata")
    new = synthesized.get("Resources", {}).get("CDKMetadata")
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise GuardError("CDK metadata resource is missing")
    if old.get("Type") != "AWS::CDK::Metadata" or new.get("Type") != old["Type"]:
        raise GuardError("CDK metadata resource type changed")
    old_props, new_props = old.get("Properties"), new.get("Properties")
    if not isinstance(old_props, dict) or not isinstance(new_props, dict):
        raise GuardError("CDK metadata properties are invalid")
    if (
        {k: v for k, v in old.items() if k != "Properties"}
        != {k: v for k, v in new.items() if k != "Properties"}
        or {k: v for k, v in old_props.items() if k != "Analytics"}
        != {k: v for k, v in new_props.items() if k != "Analytics"}
        or not isinstance(old_props.get("Analytics"), str)
        or not isinstance(new_props.get("Analytics"), str)
    ):
        raise GuardError("CDK metadata changed beyond its analytics value")
    result = deepcopy(dict(synthesized))
    result["Resources"]["CDKMetadata"] = deepcopy(old)
    return result


def validate_template_changes(
    deployed: Mapping[str, Any], proposed: Mapping[str, Any]
) -> frozenset[str]:
    """Reject unrelated template changes, removals and role modifications."""
    if {k: v for k, v in deployed.items() if k != "Resources"} != {
        k: v for k, v in proposed.items() if k != "Resources"
    }:
        raise GuardError("top-level template content changed")
    old = deployed.get("Resources")
    new = proposed.get("Resources")
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise GuardError("template resources are missing")
    changed = frozenset(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
    if changed != EXPECTED_RESOURCE_IDS:
        raise GuardError(f"unexpected changed resources: {sorted(changed)}")
    for role_id, policy_id in ROLE_POLICIES.items():
        before, after = old.get(role_id), new.get(role_id)
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise GuardError("an existing deploy role is missing")
        if (
            before.get("Type") != "AWS::IAM::Role"
            or after.get("Type") != before["Type"]
        ):
            raise GuardError("unexpected deploy role type")
        if {k: v for k, v in before.items() if k != "Properties"} != {
            k: v for k, v in after.items() if k != "Properties"
        }:
            raise GuardError("deploy role metadata changed")
        before_props, after_props = (
            before.get("Properties", {}),
            after.get("Properties", {}),
        )
        if {k: v for k, v in before_props.items() if k != "ManagedPolicyArns"} != {
            k: v for k, v in after_props.items() if k != "ManagedPolicyArns"
        }:
            raise GuardError("deploy role properties other than its attachment changed")
        old_attachments = before_props.get("ManagedPolicyArns", [])
        new_attachments = after_props.get("ManagedPolicyArns", [])
        if (
            not isinstance(old_attachments, list)
            or not isinstance(new_attachments, list)
            or {"Ref": policy_id} in old_attachments
            or new_attachments.count({"Ref": policy_id}) != 1
            or [entry for entry in new_attachments if entry != {"Ref": policy_id}]
            != old_attachments
        ):
            raise GuardError(
                "deploy role attachments differ from the reviewed addition"
            )
    for policy_id in POLICY_IDS:
        item = new.get(policy_id)
        if (
            policy_id in old
            or not isinstance(item, dict)
            or item.get("Type") != "AWS::IAM::ManagedPolicy"
        ):
            raise GuardError("expected a new managed policy")
    return changed


def validate_changeset(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Require exactly two attachments and two new policies without replacement."""
    if (
        response.get("Status") != "CREATE_COMPLETE"
        or response.get("ExecutionStatus") != "AVAILABLE"
    ):
        raise GuardError("change set is not ready to execute")
    if response.get("NextToken"):
        raise GuardError("change set contains more than one page")
    changes = response.get("Changes")
    if not isinstance(changes, list) or len(changes) != 4:
        raise GuardError("change set does not contain exactly four resources")
    rows: list[dict[str, Any]] = []
    for change in changes:
        if not isinstance(change, dict) or change.get("Type") != "Resource":
            raise GuardError("unexpected change set entry")
        row = change.get("ResourceChange")
        if not isinstance(row, dict):
            raise GuardError("invalid change set resource")
        logical_id = row.get("LogicalResourceId")
        if logical_id in ROLE_IDS:
            if (
                row.get("Action") != "Modify"
                or row.get("ResourceType") != "AWS::IAM::Role"
                or row.get("Replacement") != "False"
            ):
                raise GuardError("role change is not an in-place modification")
        elif logical_id in POLICY_IDS:
            if (
                row.get("Action") != "Add"
                or row.get("ResourceType") != "AWS::IAM::ManagedPolicy"
            ):
                raise GuardError("managed policy change is not an addition")
        else:
            raise GuardError("change set includes an unrelated resource")
        rows.append(dict(row))
    if {row["LogicalResourceId"] for row in rows} != EXPECTED_RESOURCE_IDS:
        raise GuardError("change set has duplicate or missing resources")
    return sorted(rows, key=lambda row: str(row["LogicalResourceId"]))


def _checkout_head() -> str:
    """GitHub's SHA checkout must be detached at exactly the reviewed commit."""
    return (REPO / ".git" / "HEAD").read_text(encoding="utf-8").strip()


def _remote_main(token: str) -> str:
    """Read main from the fixed GitHub API endpoint without logging the token."""
    if not token:
        raise GuardError("repository read token is unavailable")
    connection = http.client.HTTPSConnection("api.github.com", timeout=10)
    try:
        connection.request(
            "GET",
            "/repos/infiquetra/infiquetra-aws-infra/git/ref/heads/main",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "campps-nonprod-deploy-roles-ci",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise GuardError("cannot read current remote main")
        data = json.loads(response.read())
        if (
            data.get("ref") != "refs/heads/main"
            or data.get("object", {}).get("type") != "commit"
        ):
            raise GuardError("remote main did not resolve to a commit")
        return str(data["object"]["sha"])
    finally:
        connection.close()


def check_head(expected: str, environ: Mapping[str, str]) -> None:
    """Require the manual dispatch, checkout, input and current remote main to agree."""
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise GuardError("expected head must be a full lowercase commit SHA")
    if (
        environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise GuardError("only a manual dispatch from main is permitted")
    if environ.get("GITHUB_SHA") != expected or _checkout_head() != expected:
        raise GuardError("dispatch or checkout does not match the reviewed head")
    if _remote_main(environ.get("GITHUB_TOKEN", "")) != expected:
        raise GuardError("remote main has moved since the reviewed head")


def check_nonprod(sts: Any, region: str | None) -> None:
    """Verify the target credentials before accessing any nonprod resources."""
    if region != REGION:
        raise GuardError("credentials or region are not nonproduction")
    identity = sts.get_caller_identity()
    arn = str(identity.get("Arn", ""))
    prefix = f"arn:aws:sts::{ACCOUNT}:assumed-role/{ROLE_NAME}/"
    session_name = arn.removeprefix(prefix)
    if (
        identity.get("Account") != ACCOUNT
        or not arn.startswith(prefix)
        or not re.fullmatch(r"[A-Za-z0-9+=,.@_-]{2,64}", session_name)
    ):
        raise GuardError("credentials or region are not nonproduction")


def _stack(cfn: Any, sts: Any, region: str) -> dict[str, Any]:
    check_nonprod(sts, region)
    stacks = cfn.describe_stacks(StackName=STACK).get("Stacks", [])
    if len(stacks) != 1:
        raise GuardError("the exact target stack was not found")
    stack = stacks[0]
    if (
        stack.get("StackName") != STACK
        or not str(stack.get("StackId", "")).startswith(
            _arn("cloudformation", f"stack/{STACK}/")
        )
        or stack.get("RoleARN") != _arn("iam", f"role/{EXECUTION_ROLE_NAME}", region="")
        or stack.get("StackStatus")
        not in {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}
    ):
        raise GuardError("target stack identity, status, or execution role changed")
    return dict(stack)


def _run_id(value: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]{0,19}", value):
        raise GuardError("plan run ID must be numeric")
    return value


def _receipt(
    cfn: Any,
    *,
    stack: Mapping[str, Any],
    name: str,
    head: str,
    proposed: dict[str, Any],
    deployed: dict[str, Any],
    synthesized_hash: str,
) -> dict[str, Any]:
    response = cfn.describe_change_set(StackName=STACK, ChangeSetName=name)
    rows = validate_changeset(response)
    template_hash = _digest(proposed)
    if (
        response.get("StackId") != stack["StackId"]
        or response.get("StackName") != STACK
        or response.get("ChangeSetName") != name
        or response.get("Description") != f"head={head};template={template_hash}"
        or response.get("Capabilities") != ["CAPABILITY_NAMED_IAM"]
        or response.get("IncludeNestedStacks", False)
        or response.get("ImportExistingResources", False)
        or response.get("ParentChangeSetId")
        or response.get("RootChangeSetId")
        or response.get("Tags", []) != stack.get("Tags", [])
        or response.get("NotificationARNs", []) != stack.get("NotificationARNs", [])
        or response.get("RollbackConfiguration", {})
        != stack.get("RollbackConfiguration", {})
    ):
        raise GuardError("change set does not match the reviewed stack or revision")
    old_parameters = stack.get("Parameters", [])
    next_parameters = response.get("Parameters", [])
    if not isinstance(old_parameters, list) or not isinstance(next_parameters, list):
        raise GuardError("invalid change set parameters")

    def parameter_values(values: list[Any]) -> dict[str, tuple[Any, Any]]:
        return {
            item["ParameterKey"]: (
                item.get("ParameterValue"),
                item.get("ResolvedValue"),
            )
            for item in values
        }

    if parameter_values(old_parameters) != parameter_values(next_parameters):
        raise GuardError("change set would change a stack parameter")
    actual = _document(
        cfn.get_template(StackName=STACK, ChangeSetName=name, TemplateStage="Original")[
            "TemplateBody"
        ]
    )
    if actual != proposed:
        raise GuardError("change set template differs from the synthesized template")
    return {
        "account": ACCOUNT,
        "region": REGION,
        "stack": STACK,
        "stack_id": stack["StackId"],
        "head": head,
        "change_set_name": name,
        "change_set_id": response["ChangeSetId"],
        "template_sha256": template_hash,
        "synthesized_template_sha256": synthesized_hash,
        "previous_template_sha256": _digest(deployed),
        "parameters_sha256": _digest(parameter_values(old_parameters)),
        "changes": rows,
    }


def plan(
    cfn: Any,
    s3: Any,
    sts: Any,
    *,
    head: str,
    run_id: str,
    proposed: dict[str, Any],
    head_guard: Callable[[], None],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create, inspect and return one bounded nonproduction change set."""
    run_id = _run_id(run_id)
    head_guard()
    stack = _stack(cfn, sts, REGION)
    deployed = _document(
        cfn.get_template(StackName=STACK, TemplateStage="Original")["TemplateBody"]
    )
    synthesized_hash = _digest(proposed)
    proposed = preserve_deployed_cdk_metadata(deployed, proposed)
    validate_template_changes(deployed, proposed)
    parameters = proposed.get("Parameters", {})
    if not isinstance(parameters, dict) or set(parameters) != EXPECTED_PARAMETERS:
        raise GuardError("invalid template parameters")
    current_parameters = stack.get("Parameters", [])
    if not isinstance(current_parameters, list) or {
        item.get("ParameterKey") for item in current_parameters
    } != set(parameters):
        raise GuardError("stack parameters differ from the reviewed template")
    template_hash = _digest(proposed)
    key = f"{OBJECT_PREFIX}{run_id}/{template_hash}.json"
    head_guard()
    s3.put_object(
        Bucket=BUCKET, Key=key, Body=_canonical(proposed), ServerSideEncryption="AES256"
    )
    name = f"{CHANGESET_PREFIX}{run_id}"
    head_guard()
    created = cfn.create_change_set(
        StackName=STACK,
        ChangeSetName=name,
        ChangeSetType="UPDATE",
        Description=f"head={head};template={template_hash}",
        TemplateURL=f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{quote(key)}",
        Parameters=[
            {"ParameterKey": parameter, "UsePreviousValue": True}
            for parameter in sorted(parameters)
        ],
        Capabilities=["CAPABILITY_NAMED_IAM"],
        RoleARN=stack["RoleARN"],
    )
    cfn.get_waiter("change_set_create_complete").wait(
        StackName=STACK, ChangeSetName=name
    )
    head_guard()
    receipt = _receipt(
        cfn,
        stack=stack,
        name=name,
        head=head,
        proposed=proposed,
        deployed=deployed,
        synthesized_hash=synthesized_hash,
    )
    if (
        not isinstance(created, dict)
        or created.get("Id") != receipt["change_set_id"]
        or created.get("StackId") != stack["StackId"]
    ):
        raise GuardError("created change set identity differs from the reviewed plan")
    return receipt, proposed


def apply(
    cfn: Any,
    sts: Any,
    *,
    head: str,
    plan_run_id: str,
    reviewed_digest: str,
    proposed: dict[str, Any],
    head_guard: Callable[[], None],
) -> dict[str, Any]:
    """Execute only the previously reviewed, still-current change set."""
    name = f"{CHANGESET_PREFIX}{_run_id(plan_run_id)}"
    if not re.fullmatch(r"[0-9a-f]{64}", reviewed_digest):
        raise GuardError("reviewed plan digest must be a SHA-256")
    head_guard()
    stack = _stack(cfn, sts, REGION)
    deployed = _document(
        cfn.get_template(StackName=STACK, TemplateStage="Original")["TemplateBody"]
    )
    synthesized_hash = _digest(proposed)
    proposed = preserve_deployed_cdk_metadata(deployed, proposed)
    validate_template_changes(deployed, proposed)
    receipt = _receipt(
        cfn,
        stack=stack,
        name=name,
        head=head,
        proposed=proposed,
        deployed=deployed,
        synthesized_hash=synthesized_hash,
    )
    if _digest(receipt) != reviewed_digest:
        raise GuardError("current change set differs from the reviewed plan")
    head_guard()
    _stack(cfn, sts, REGION)
    cfn.execute_change_set(StackName=STACK, ChangeSetName=name)
    cfn.get_waiter("stack_update_complete").wait(StackName=STACK)
    after = _document(
        cfn.get_template(StackName=STACK, TemplateStage="Original")["TemplateBody"]
    )
    if after != proposed:
        raise GuardError("updated stack template differs from the reviewed template")
    return receipt


def main() -> int:
    command = sys.argv[1:] if len(sys.argv) > 1 else []
    if command == ["check"]:
        check_head(os.environ.get("EXPECTED_HEAD", ""), os.environ)
        return 0
    if command == ["identity"]:
        output = Path(os.environ["GITHUB_OUTPUT"])
        with output.open("a", encoding="utf-8") as stream:
            stream.write(f"role={_arn('iam', f'role/{ROLE_NAME}', region='')}\n")
            stream.write(f"policy={_canonical(session_policy()).decode()}\n")
            stream.write(
                f"management_policy={_canonical(required_management_grant()).decode()}\n"
            )
        return 0
    if command == ["check-management"]:
        identity = boto3.Session(region_name=REGION).client("sts").get_caller_identity()
        principal = str(identity.get("Arn", "")).split(":", 5)[-1]
        if identity.get("Account") != MANAGEMENT_ACCOUNT or not principal.startswith(
            "assumed-role/infiquetra-aws-infra-gha-role/"
        ):
            raise GuardError("unexpected management GitHub identity")
        return 0
    if command == ["check-nonprod"]:
        required = {
            "AWS_REGION": REGION,
            "AWS_DEFAULT_REGION": REGION,
            "CDK_DEFAULT_REGION": REGION,
            "CDK_DEFAULT_ACCOUNT": ACCOUNT,
        }
        if any(os.environ.get(key) != value for key, value in required.items()):
            raise GuardError("credentials or region are not nonproduction")
        session = boto3.Session()
        check_nonprod(session.client("sts"), session.region_name)
        return 0
    if command != ["run"]:
        raise GuardError(
            "expected check, identity, check-management, check-nonprod or run"
        )
    expected = os.environ.get("EXPECTED_HEAD", "")
    guard = lambda: check_head(expected, os.environ)  # noqa: E731
    guard()
    session = boto3.Session(region_name=REGION)
    cfn, sts = session.client("cloudformation"), session.client("sts")
    proposed = _document(TEMPLATE_PATH.read_text(encoding="utf-8"))
    phase = os.environ.get("PHASE", "")
    if phase == "plan":
        result, effective_template = plan(
            cfn,
            session.client("s3"),
            sts,
            head=expected,
            run_id=os.environ.get("GITHUB_RUN_ID", ""),
            proposed=proposed,
            head_guard=guard,
        )
        (REPO / "cdk.out" / "nonprod-role-effective-template.json").write_text(
            json.dumps(effective_template, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    elif phase == "apply":
        result = apply(
            cfn,
            sts,
            head=expected,
            plan_run_id=os.environ.get("PLAN_RUN_ID", ""),
            reviewed_digest=os.environ.get("PLAN_DIGEST", ""),
            proposed=proposed,
            head_guard=guard,
        )
    else:
        raise GuardError("phase must be plan or apply")
    receipt = {**result, "review_digest_sha256": _digest(result)}
    evidence = REPO / "cdk.out" / "nonprod-role-plan.json"
    evidence.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"review digest: {receipt['review_digest_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GuardError as error:
        print(f"refused: {error}", file=sys.stderr)
        sys.exit(1)
