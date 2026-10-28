"""The CI deploy guard permits only the reviewed nonproduction role changes."""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import boto3
import pytest
import yaml  # type: ignore[import-untyped]
from botocore.stub import Stubber

from tools import nonprod_deploy_roles_ci as guard


def test_management_bootstrap_source_has_no_persistent_assume_grant() -> None:
    source = (
        Path(__file__).parents[2]
        / "github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py"
    ).read_text()
    literals = {
        node.value.lower()
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "sts:assumerole" not in literals


def _templates() -> tuple[dict[str, Any], dict[str, Any]]:
    old: dict[str, Any] = {
        "Resources": {
            role: {
                "Type": "AWS::IAM::Role",
                "Properties": {"ManagedPolicyArns": ["existing"], "RoleName": role},
            }
            for role in guard.ROLE_IDS
        },
        "Parameters": {"BootstrapVersion": {"Type": "String"}},
        "Outputs": {"unchanged": {"Value": "same"}},
    }
    old["Resources"]["CDKMetadata"] = {
        "Type": "AWS::CDK::Metadata",
        "Properties": {"Analytics": "deployed"},
    }
    proposed = deepcopy(old)
    for role, policy in guard.ROLE_POLICIES.items():
        proposed["Resources"][role]["Properties"]["ManagedPolicyArns"].append(
            {"Ref": policy}
        )
    for policy in guard.POLICY_IDS:
        proposed["Resources"][policy] = {
            "Type": "AWS::IAM::ManagedPolicy",
            "Properties": {"ManagedPolicyName": policy},
        }
    return old, proposed


def test_exact_four_resource_changes_are_accepted() -> None:
    old, proposed = _templates()
    assert guard.validate_template_changes(old, proposed) == guard.EXPECTED_RESOURCE_IDS


def test_new_attachment_can_be_inserted_without_reordering_existing_ones() -> None:
    old, proposed = _templates()
    role = next(iter(guard.ROLE_IDS))
    attachments = proposed["Resources"][role]["Properties"]["ManagedPolicyArns"]
    attachments.insert(0, attachments.pop())
    assert guard.validate_template_changes(old, proposed) == guard.EXPECTED_RESOURCE_IDS


def test_analytics_only_change_is_pinned_to_deployed_value() -> None:
    old, synthesized = _templates()
    synthesized["Resources"]["CDKMetadata"]["Properties"]["Analytics"] = "new"
    with pytest.raises(guard.GuardError):
        guard.validate_template_changes(old, synthesized)
    effective = guard.preserve_deployed_cdk_metadata(old, synthesized)
    assert effective["Resources"]["CDKMetadata"] == old["Resources"]["CDKMetadata"]
    assert (
        guard.validate_template_changes(old, effective) == guard.EXPECTED_RESOURCE_IDS
    )
    assert synthesized["Resources"]["CDKMetadata"]["Properties"]["Analytics"] == "new"


def test_other_metadata_changes_are_refused() -> None:
    old, synthesized = _templates()
    synthesized["Resources"]["CDKMetadata"]["Properties"]["Unexpected"] = "changed"
    with pytest.raises(guard.GuardError):
        guard.preserve_deployed_cdk_metadata(old, synthesized)


@pytest.mark.parametrize("change", ["role_trust", "extra_resource", "output"])
def test_other_template_changes_are_refused(change: str) -> None:
    old, proposed = _templates()
    if change == "role_trust":
        proposed["Resources"][next(iter(guard.ROLE_IDS))]["Properties"][
            "AssumeRolePolicyDocument"
        ] = {"unsafe": True}
    elif change == "extra_resource":
        proposed["Resources"]["Unrelated"] = {"Type": "AWS::S3::Bucket"}
    else:
        proposed["Outputs"]["unchanged"]["Value"] = "modified"
    with pytest.raises(guard.GuardError):
        guard.validate_template_changes(old, proposed)


def _changes() -> list[dict[str, Any]]:
    return [
        {
            "Type": "Resource",
            "ResourceChange": {
                "LogicalResourceId": logical_id,
                "Action": "Modify" if logical_id in guard.ROLE_IDS else "Add",
                "ResourceType": "AWS::IAM::Role"
                if logical_id in guard.ROLE_IDS
                else "AWS::IAM::ManagedPolicy",
                **({"Replacement": "False"} if logical_id in guard.ROLE_IDS else {}),
            },
        }
        for logical_id in sorted(guard.EXPECTED_RESOURCE_IDS)
    ]


class _Waiter:
    def __init__(self, action: Any = None) -> None:
        self.action = action

    def wait(self, **_: Any) -> None:
        if self.action:
            self.action()


class _Sts:
    def __init__(self, account: str = guard.ACCOUNT) -> None:
        self.account = account

    def get_caller_identity(self) -> dict[str, str]:
        return {
            "Account": self.account,
            "Arn": guard._arn(
                "sts", f"assumed-role/{guard.ROLE_NAME}/synthetic", region=""
            ),
        }


@pytest.mark.parametrize(
    ("account", "arn", "region", "allowed"),
    [
        (
            guard.ACCOUNT,
            f"arn:aws:sts::{guard.ACCOUNT}:assumed-role/org-admin/campps-nonprod-roles-123",
            guard.REGION,
            True,
        ),
        (
            guard.MANAGEMENT_ACCOUNT,
            f"arn:aws:sts::{guard.MANAGEMENT_ACCOUNT}:assumed-role/infiquetra-aws-infra-gha-role/run",
            guard.REGION,
            False,
        ),
        (
            guard.ACCOUNT,
            f"arn:aws:sts::{guard.ACCOUNT}:assumed-role/other-role/run",
            guard.REGION,
            False,
        ),
        (
            guard.ACCOUNT,
            f"arn:aws:sts::{guard.ACCOUNT}:assumed-role/org-admin-extra/run",
            guard.REGION,
            False,
        ),
        (
            guard.ACCOUNT,
            f"arn:aws:sts::{guard.ACCOUNT}:assumed-role/org-admin/",
            guard.REGION,
            False,
        ),
        (
            guard.ACCOUNT,
            f"arn:aws:sts::{guard.MANAGEMENT_ACCOUNT}:assumed-role/org-admin/run",
            guard.REGION,
            False,
        ),
        (
            guard.ACCOUNT,
            f"arn:aws:sts::{guard.ACCOUNT}:assumed-role/org-admin/run",
            "us-west-2",
            False,
        ),
    ],
)
def test_nonprod_identity_accepts_only_exact_account_role_and_region(
    account: str, arn: str, region: str, allowed: bool
) -> None:
    class Sts:
        def get_caller_identity(self) -> dict[str, str]:
            return {"Account": account, "Arn": arn}

    if allowed:
        guard.check_nonprod(Sts(), region)
    else:
        with pytest.raises(guard.GuardError, match="not nonproduction"):
            guard.check_nonprod(Sts(), region)


def test_check_nonprod_command_checks_environment_before_any_resource_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Session:
        region_name = guard.REGION

        def client(self, name: str) -> Any:
            calls.append(name)
            assert name == "sts"
            return _Sts()

    for name, value in {
        "AWS_REGION": guard.REGION,
        "AWS_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_ACCOUNT": guard.ACCOUNT,
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(guard.boto3, "Session", Session)
    monkeypatch.setattr(guard.sys, "argv", ["guard", "check-nonprod"])
    assert guard.main() == 0
    assert calls == ["sts"]


@pytest.mark.parametrize(
    ("account", "arn"),
    [
        (
            guard.MANAGEMENT_ACCOUNT,
            f"arn:aws:sts::{guard.MANAGEMENT_ACCOUNT}:assumed-role/infiquetra-aws-infra-gha-role/run",
        ),
        (guard.ACCOUNT, f"arn:aws:sts::{guard.ACCOUNT}:assumed-role/other-role/run"),
    ],
)
def test_check_nonprod_command_rejects_source_or_wrong_target_role(
    monkeypatch: pytest.MonkeyPatch, account: str, arn: str
) -> None:
    calls: list[str] = []

    class Sts:
        def get_caller_identity(self) -> dict[str, str]:
            return {"Account": account, "Arn": arn}

    class Session:
        region_name = guard.REGION

        def client(self, name: str) -> Sts:
            calls.append(name)
            assert name == "sts"
            return Sts()

    for name, value in {
        "AWS_REGION": guard.REGION,
        "AWS_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_ACCOUNT": guard.ACCOUNT,
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(guard.boto3, "Session", Session)
    monkeypatch.setattr(guard.sys, "argv", ["guard", "check-nonprod"])
    with pytest.raises(guard.GuardError, match="not nonproduction"):
        guard.main()
    assert calls == ["sts"]


def test_check_nonprod_command_rejects_wrong_session_region_before_sts_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Sts:
        def get_caller_identity(self) -> Any:
            pytest.fail("wrong session region must fail before an AWS request")

    class Session:
        region_name = "us-west-2"

        def client(self, name: str) -> Sts:
            assert name == "sts"
            return Sts()

    for name, value in {
        "AWS_REGION": guard.REGION,
        "AWS_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_ACCOUNT": guard.ACCOUNT,
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(guard.boto3, "Session", Session)
    monkeypatch.setattr(guard.sys, "argv", ["guard", "check-nonprod"])
    with pytest.raises(guard.GuardError, match="not nonproduction"):
        guard.main()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AWS_REGION", "us-west-2"),
        ("AWS_DEFAULT_REGION", ""),
        ("CDK_DEFAULT_REGION", "us-west-2"),
        ("CDK_DEFAULT_ACCOUNT", guard.MANAGEMENT_ACCOUNT),
    ],
)
def test_check_nonprod_command_rejects_wrong_environment(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    for name, expected in {
        "AWS_REGION": guard.REGION,
        "AWS_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_REGION": guard.REGION,
        "CDK_DEFAULT_ACCOUNT": guard.ACCOUNT,
    }.items():
        monkeypatch.setenv(name, expected)
    monkeypatch.setenv(key, value)
    monkeypatch.setattr(guard.sys, "argv", ["guard", "check-nonprod"])
    with pytest.raises(guard.GuardError, match="not nonproduction"):
        guard.main()


class _S3:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.puts.append(kwargs)


class _CloudFormation:
    def __init__(self, old: dict[str, Any], proposed: dict[str, Any]) -> None:
        self.old, self.proposed = old, proposed
        self.stack_id = guard._arn("cloudformation", f"stack/{guard.STACK}/synthetic")
        self.role = guard._arn("iam", f"role/{guard.EXECUTION_ROLE_NAME}", region="")
        self.plan_request: dict[str, Any] | None = None
        self.changes = _changes()
        self.executions: list[dict[str, Any]] = []

    def describe_stacks(self, **_: Any) -> dict[str, Any]:
        return {
            "Stacks": [
                {
                    "StackName": guard.STACK,
                    "StackId": self.stack_id,
                    "RoleARN": self.role,
                    "StackStatus": "UPDATE_COMPLETE",
                    "Parameters": [
                        {
                            "ParameterKey": "BootstrapVersion",
                            "ParameterValue": "synthetic",
                        }
                    ],
                }
            ]
        }

    def get_template(self, **kwargs: Any) -> dict[str, Any]:
        value = self.proposed if kwargs.get("ChangeSetName") else self.old
        return {"TemplateBody": value}

    def create_change_set(self, **kwargs: Any) -> dict[str, str]:
        self.plan_request = kwargs
        return {"Id": "synthetic-change-set-id", "StackId": self.stack_id}

    def describe_change_set(self, **_: Any) -> dict[str, Any]:
        assert self.plan_request is not None
        return {
            "Status": "CREATE_COMPLETE",
            "ExecutionStatus": "AVAILABLE",
            "StackId": self.stack_id,
            "StackName": guard.STACK,
            "ChangeSetName": self.plan_request["ChangeSetName"],
            "Description": self.plan_request["Description"],
            "Capabilities": ["CAPABILITY_NAMED_IAM"],
            "Parameters": [
                {"ParameterKey": "BootstrapVersion", "ParameterValue": "synthetic"}
            ],
            "ChangeSetId": "synthetic-change-set-id",
            "Changes": deepcopy(self.changes),
        }

    def execute_change_set(self, **kwargs: Any) -> None:
        self.executions.append(kwargs)

    def get_waiter(self, name: str) -> _Waiter:
        if name == "stack_update_complete":
            return _Waiter(lambda: setattr(self, "old", self.proposed))
        assert name == "change_set_create_complete"
        return _Waiter()


def _plan() -> tuple[_CloudFormation, _S3, dict[str, Any]]:
    old, proposed = _templates()
    cfn, s3 = _CloudFormation(old, proposed), _S3()
    receipt, effective = guard.plan(
        cfn,
        s3,
        _Sts(),
        head="a" * 40,
        run_id="1234",
        proposed=proposed,
        head_guard=lambda: None,
    )
    assert effective == proposed
    return cfn, s3, receipt


def test_plan_and_reviewed_apply_are_bound_to_one_nonproduction_change_set() -> None:
    cfn, s3, receipt = _plan()
    assert len(s3.puts) == 1
    assert s3.puts[0]["Bucket"] == guard.BUCKET
    assert s3.puts[0]["Key"].startswith(guard.OBJECT_PREFIX)
    assert s3.puts[0]["ServerSideEncryption"] == "AES256"
    assert cfn.plan_request is not None
    assert cfn.plan_request["StackName"] == guard.STACK
    assert cfn.plan_request["RoleARN"] == cfn.role
    assert cfn.plan_request["Parameters"] == [
        {"ParameterKey": "BootstrapVersion", "UsePreviousValue": True}
    ]
    result = guard.apply(
        cfn,
        _Sts(),
        head="a" * 40,
        plan_run_id="1234",
        reviewed_digest=guard._digest(receipt),
        proposed=cfn.proposed,
        head_guard=lambda: None,
    )
    assert result == receipt
    assert cfn.executions == [
        {"StackName": guard.STACK, "ChangeSetName": f"{guard.CHANGESET_PREFIX}1234"}
    ]


@pytest.mark.parametrize(
    "mutation", ["extra", "replacement", "wrong_type", "changed_template", "digest"]
)
def test_apply_refuses_unreviewed_or_unsafe_change_sets(mutation: str) -> None:
    cfn, _, receipt = _plan()
    digest = guard._digest(receipt)
    if mutation == "extra":
        cfn.changes.append(deepcopy(cfn.changes[0]))
    elif mutation == "replacement":
        next(
            c["ResourceChange"]
            for c in cfn.changes
            if c["ResourceChange"]["LogicalResourceId"] in guard.ROLE_IDS
        )["Replacement"] = "True"
    elif mutation == "wrong_type":
        cfn.changes[0]["ResourceChange"]["ResourceType"] = "AWS::S3::Bucket"
    elif mutation == "changed_template":
        cfn.proposed = deepcopy(cfn.proposed)
        cfn.proposed["Outputs"]["unchanged"]["Value"] = "tampered"
    else:
        digest = "f" * 64
    with pytest.raises(guard.GuardError):
        guard.apply(
            cfn,
            _Sts(),
            head="a" * 40,
            plan_run_id="1234",
            reviewed_digest=digest,
            proposed=_templates()[1],
            head_guard=lambda: None,
        )
    assert not cfn.executions


def test_apply_refuses_if_main_moves_before_execution() -> None:
    cfn, _, receipt = _plan()
    calls = 0

    def check() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise guard.GuardError("main moved")

    with pytest.raises(guard.GuardError, match="main moved"):
        guard.apply(
            cfn,
            _Sts(),
            head="a" * 40,
            plan_run_id="1234",
            reviewed_digest=guard._digest(receipt),
            proposed=cfn.proposed,
            head_guard=check,
        )
    assert not cfn.executions


@pytest.mark.parametrize("mutation", ["parameters", "tags", "nested", "name", "prefix"])
def test_apply_refuses_unreviewed_stack_configuration(mutation: str) -> None:
    cfn, _, receipt = _plan()
    describe = cfn.describe_change_set

    def changed(**kwargs: Any) -> dict[str, Any]:
        response = describe(**kwargs)
        if mutation == "parameters":
            response["Parameters"][0]["ParameterValue"] = "changed"
        elif mutation == "tags":
            response["Tags"] = [{"Key": "unexpected", "Value": "changed"}]
        elif mutation == "name":
            response["ChangeSetName"] = f"{guard.CHANGESET_PREFIX}9999"
        elif mutation == "prefix":
            response["ChangeSetName"] = "other-change-set"
        else:
            response["IncludeNestedStacks"] = True
        return response

    cfn.describe_change_set = changed  # type: ignore[method-assign]
    with pytest.raises(guard.GuardError):
        guard.apply(
            cfn,
            _Sts(),
            head="a" * 40,
            plan_run_id="1234",
            reviewed_digest=guard._digest(receipt),
            proposed=cfn.proposed,
            head_guard=lambda: None,
        )
    assert not cfn.executions


def test_wrong_account_refused_before_any_plan_write() -> None:
    old, proposed = _templates()
    cfn, s3 = _CloudFormation(old, proposed), _S3()
    with pytest.raises(guard.GuardError, match="not nonproduction"):
        guard.plan(
            cfn,
            s3,
            _Sts("000000000000"),
            head="a" * 40,
            run_id="1234",
            proposed=proposed,
            head_guard=lambda: None,
        )
    assert not s3.puts and cfn.plan_request is None


@pytest.mark.parametrize("invalid", ["", "0", "-1", "1;echo bad", "9" * 21])
def test_plan_run_id_is_bounded_numeric(invalid: str) -> None:
    with pytest.raises(guard.GuardError):
        guard._run_id(invalid)


@pytest.mark.parametrize("failure", ["ref", "event", "input", "checkout", "remote"])
def test_head_guard_refuses_stale_or_untrusted_invocations(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    expected = "a" * 40
    env = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": expected,
    }
    if failure == "ref":
        env["GITHUB_REF"] = "refs/heads/feature"
    elif failure == "event":
        env["GITHUB_EVENT_NAME"] = "pull_request"
    elif failure == "input":
        env["GITHUB_SHA"] = "b" * 40

    monkeypatch.setattr(
        guard, "_checkout_head", lambda: "b" * 40 if failure == "checkout" else expected
    )
    monkeypatch.setattr(
        guard, "_remote_main", lambda _: "b" * 40 if failure == "remote" else expected
    )
    with pytest.raises(guard.GuardError):
        guard.check_head(expected, env)


def test_head_guard_accepts_only_matching_current_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = "a" * 40
    env = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": expected,
    }
    monkeypatch.setattr(guard, "_checkout_head", lambda: expected)
    monkeypatch.setattr(guard, "_remote_main", lambda _: expected)
    guard.check_head(expected, env)


def test_remote_main_is_read_from_the_fixed_github_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status = 200

        def read(self) -> bytes:
            return json.dumps(
                {
                    "ref": "refs/heads/main",
                    "object": {"type": "commit", "sha": "a" * 40},
                }
            ).encode()

    class Connection:
        def __init__(self, host: str, timeout: int) -> None:
            assert host == "api.github.com" and timeout == 10

        def request(self, method: str, path: str, headers: dict[str, str]) -> None:
            assert method == "GET"
            assert path == "/repos/infiquetra/infiquetra-aws-infra/git/ref/heads/main"
            assert headers["Authorization"] == "Bearer synthetic-token"

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(guard.http.client, "HTTPSConnection", Connection)
    assert guard._remote_main("synthetic-token") == "a" * 40


def test_remote_main_fails_closed_without_a_token() -> None:
    with pytest.raises(guard.GuardError, match="token is unavailable"):
        guard._remote_main("")


def test_session_and_missing_management_grant_name_only_nonprod_resources() -> None:
    grant = guard.required_management_grant()["Statement"]
    assert len(grant) == 1 and grant[0]["Action"] == "sts:AssumeRole"
    assert grant[0]["Resource"] == guard._arn(
        "iam", f"role/{guard.ROLE_NAME}", region=""
    )
    assert grant[0]["Condition"] == {
        "StringLike": {"sts:RoleSessionName": "campps-nonprod-roles-*"}
    }
    text = json.dumps(guard.session_policy(), separators=(",", ":"))
    assert len(text) < 2048
    assert guard.STACK in text and guard.BUCKET in text and guard.ACCOUNT in text
    assert "staging" not in text.lower() and "production" not in text.lower()
    assert (
        "cloudformation:DeleteStack" not in text and "iam:AttachRolePolicy" not in text
    )


def test_changeset_session_policy_keeps_create_and_target_stack_bounded() -> None:
    statements = guard.session_policy()["Statement"]
    create = next(
        s for s in statements if s["Action"] == "cloudformation:CreateChangeSet"
    )
    assert create == {
        "Effect": "Allow",
        "Action": "cloudformation:CreateChangeSet",
        "Resource": guard._arn("cloudformation", f"stack/{guard.STACK}/*"),
        "Condition": {
            "StringLike": {
                "cloudformation:ChangeSetName": f"{guard.CHANGESET_PREFIX}*",
                "cloudformation:TemplateUrl": (
                    f"https://{guard.BUCKET}.s3.{guard.REGION}.amazonaws.com/"
                    f"{guard.OBJECT_PREFIX}*"
                ),
            },
            "StringEquals": {
                "cloudformation:RoleArn": guard._arn(
                    "iam", f"role/{guard.EXECUTION_ROLE_NAME}", region=""
                )
            },
        },
    }
    describe = next(
        s
        for s in statements
        if isinstance(s["Action"], list)
        and "cloudformation:DescribeChangeSet" in s["Action"]
    )
    assert describe == {
        "Effect": "Allow",
        "Action": [
            "cloudformation:DescribeStacks",
            "cloudformation:GetTemplate",
            "cloudformation:DescribeChangeSet",
        ],
        "Resource": guard._arn("cloudformation", f"stack/{guard.STACK}/*"),
    }
    execute = next(
        s
        for s in statements
        if isinstance(s["Action"], list)
        and "cloudformation:ExecuteChangeSet" in s["Action"]
    )
    assert execute == {
        "Effect": "Allow",
        "Action": [
            "cloudformation:ExecuteChangeSet",
        ],
        "Resource": guard._arn("cloudformation", f"stack/{guard.STACK}/*"),
        "Condition": {
            "StringLike": {
                "cloudformation:ChangeSetName": [
                    f"{guard.CHANGESET_PREFIX}*",
                    guard._arn(
                        "cloudformation", f"changeSet/{guard.CHANGESET_PREFIX}*/*"
                    ),
                ]
            }
        },
    }


@pytest.mark.parametrize(
    ("resource", "condition_value", "allowed"),
    [
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            None,
            True,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"{guard.CHANGESET_PREFIX}1234",
            True,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:changeSet/{guard.CHANGESET_PREFIX}1234/id",
            True,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            "other-change-set",
            True,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/OtherStack/id",
            None,
            False,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:000000000000:stack/{guard.STACK}/id",
            None,
            False,
        ),
        (
            f"arn:aws:cloudformation:us-west-2:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            None,
            False,
        ),
    ],
)
def test_describe_change_set_is_readable_only_on_the_exact_stack(
    resource: str, condition_value: str | None, allowed: bool
) -> None:
    """Model missing or unexpected condition context without AWS calls."""
    statement = next(
        s
        for s in guard.session_policy()["Statement"]
        if "cloudformation:DescribeChangeSet" in s["Action"]
    )
    patterns = (
        statement.get("Condition", {})
        .get("StringLike", {})
        .get("cloudformation:ChangeSetName")
    )
    if isinstance(patterns, str):
        patterns = [patterns]
    condition_matches = patterns is None or (
        condition_value is not None
        and any(fnmatchcase(condition_value, pattern) for pattern in patterns)
    )
    result = fnmatchcase(resource, statement["Resource"]) and condition_matches
    assert result is allowed


@pytest.mark.parametrize("action", ["ExecuteChangeSet"])
@pytest.mark.parametrize(
    ("resource", "condition_value", "allowed"),
    [
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"{guard.CHANGESET_PREFIX}1234",
            True,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:changeSet/{guard.CHANGESET_PREFIX}1234/uuid",
            True,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            "other-change-set",
            False,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:changeSet/other-123/uuid",
            False,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"arn:aws:cloudformation:{guard.REGION}:000000000000:changeSet/{guard.CHANGESET_PREFIX}1234/uuid",
            False,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"arn:aws:cloudformation:us-west-2:{guard.ACCOUNT}:changeSet/{guard.CHANGESET_PREFIX}1234/uuid",
            False,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/OtherStack/id",
            f"{guard.CHANGESET_PREFIX}1234",
            False,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:000000000000:stack/{guard.STACK}/id",
            f"{guard.CHANGESET_PREFIX}1234",
            False,
        ),
        (
            f"arn:aws:cloudformation:us-west-2:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            f"{guard.CHANGESET_PREFIX}1234",
            False,
        ),
        (
            f"arn:aws:cloudformation:{guard.REGION}:{guard.ACCOUNT}:stack/{guard.STACK}/id",
            "",
            False,
        ),
    ],
)
def test_local_changeset_policy_simulation(
    action: str, resource: str, condition_value: str, allowed: bool
) -> None:
    """Simulate the single StringLike/resource allow; no AWS calls are made."""
    statements = guard.session_policy()["Statement"]
    statement = next(
        s
        for s in statements
        if isinstance(s["Action"], list) and f"cloudformation:{action}" in s["Action"]
    )
    patterns = statement["Condition"]["StringLike"]["cloudformation:ChangeSetName"]
    patterns = [patterns] if isinstance(patterns, str) else patterns
    result = fnmatchcase(resource, statement["Resource"]) and any(
        fnmatchcase(condition_value, pattern) for pattern in patterns
    )
    assert result is allowed


@pytest.mark.parametrize("representation", ["name", "arn"])
def test_pinned_cloudformation_waiter_and_execute_accept_both_request_forms(
    representation: str,
) -> None:
    name = f"{guard.CHANGESET_PREFIX}1234"
    change = (
        name
        if representation == "name"
        else guard._arn("cloudformation", f"changeSet/{name}/synthetic-id")
    )
    client = boto3.client(
        "cloudformation",
        region_name=guard.REGION,
        aws_access_key_id="synthetic",
        aws_secret_access_key="synthetic",
    )
    expected = {"StackName": guard.STACK, "ChangeSetName": change}
    with Stubber(client) as stub:
        stub.add_response(
            "describe_change_set", {"Status": "CREATE_COMPLETE"}, expected
        )
        client.get_waiter("change_set_create_complete").wait(
            StackName=guard.STACK,
            ChangeSetName=change,
            WaiterConfig={"Delay": 0, "MaxAttempts": 1},
        )
        stub.add_response("execute_change_set", {}, expected)
        client.execute_change_set(StackName=guard.STACK, ChangeSetName=change)
        stub.assert_no_pending_responses()


def test_management_workflow_excludes_only_this_path_when_all_files_match() -> None:
    workflow = yaml.safe_load(
        (
            Path(__file__).parents[2] / ".github/workflows/deploy-infrastructure.yml"
        ).read_text()
    )
    ignored = set(workflow[True]["push"]["paths-ignore"])
    pr178_files = {
        "infiquetra_aws_infra/campps_deploy_roles_stack.py",
        "tests/unit/test_campps_deploy_roles_stack.py",
        "docs/engineering-journal/LEARNINGS.md",
    }
    ci_files = {
        ".github/workflows/deploy-infrastructure.yml",
        ".github/workflows/pull-request-validation.yml",
        ".github/workflows/deploy-campps-nonprod-roles.yml",
        ".github/workflows/bootstrap-campps-nonprod-roles.yml",
        "app_campps_nonprod_roles_ci.py",
        "tools/__init__.py",
        "tools/nonprod_deploy_roles_ci.py",
        "tools/nonprod_role_bootstrap_ci.py",
        "tests/unit/test_nonprod_deploy_roles_ci.py",
        "tests/unit/test_nonprod_role_bootstrap_ci.py",
    }
    assert pr178_files <= ignored and ci_files <= ignored
    assert {
        ".github/workflows/deploy-campps-nonprod-roles.yml",
        "tools/nonprod_deploy_roles_ci.py",
        "tests/unit/test_nonprod_deploy_roles_ci.py",
        "docs/engineering-journal/LEARNINGS.md",
    } <= ignored
    assert "infiquetra_aws_infra/organization_stack.py" not in ignored
    assert "infiquetra_aws_infra/sso_stack.py" not in ignored
    assert "app.py" not in ignored


def test_deploy_workflow_is_manual_main_only_and_uses_restricted_session() -> None:
    workflow = yaml.safe_load(
        (
            Path(__file__).parents[2]
            / ".github/workflows/deploy-campps-nonprod-roles.yml"
        ).read_text()
    )
    assert set(workflow[True]) == {"workflow_dispatch"}
    job = workflow["jobs"]["deploy"]
    assert "refs/heads/main" in job["if"]
    steps = job["steps"]
    run = [step.get("run", "") for step in steps]
    check_index = next(
        i
        for i, command in enumerate(run)
        if "tools/nonprod_deploy_roles_ci.py check" in command
    )
    assert check_index < next(
        i
        for i, step in enumerate(steps)
        if "aws-actions/configure-aws-credentials" in step.get("uses", "")
    )
    guarded = [
        command
        for command in run
        if any(
            line.strip()
            in {
                "uv run python tools/nonprod_deploy_roles_ci.py check",
                "uv run python tools/nonprod_deploy_roles_ci.py run",
            }
            for line in command.splitlines()
        )
    ]
    assert len(guarded) == 2 and all(
        "git status --porcelain" in command for command in guarded
    )
    credentials = [
        step
        for step in steps
        if "aws-actions/configure-aws-credentials" in step.get("uses", "")
    ]
    assert len(credentials) == 2
    assert (
        credentials[0]["with"]["role-to-assume"] == "${{ secrets.AWS_DEPLOY_ROLE_ARN }}"
    )
    assert credentials[0]["with"]["inline-session-policy"] == (
        "${{ steps.identity.outputs.management_policy }}"
    )
    assert credentials[1]["with"]["role-chaining"] is True
    assert credentials[1]["with"]["role-skip-session-tagging"] is True
    assert (
        credentials[1]["with"]["role-session-name"]
        == "campps-nonprod-roles-${{ github.run_id }}"
    )
    assert (
        credentials[1]["with"]["inline-session-policy"]
        == "${{ steps.identity.outputs.policy }}"
    )
    assert credentials[1]["with"]["allowed-account-ids"] == (
        f"{guard.MANAGEMENT_ACCOUNT},{guard.ACCOUNT}"
    )
    chain_index = steps.index(credentials[1])
    assert steps[chain_index + 1]["run"] == (
        "uv run python tools/nonprod_deploy_roles_ci.py check-nonprod"
    )
    assert "synth --app" in steps[chain_index + 2]["run"]


def test_pinned_action_precheck_requires_source_and_target_account_ids() -> None:
    """Bounded stand-in for v5.1.0's pre-assume allowed-account validation."""
    workflow = yaml.safe_load(
        (
            Path(__file__).parents[2]
            / ".github/workflows/deploy-campps-nonprod-roles.yml"
        ).read_text()
    )
    steps = workflow["jobs"]["deploy"]["steps"]
    action = next(step for step in steps if step.get("with", {}).get("role-chaining"))
    current = action["with"]["allowed-account-ids"]

    def precheck(source: str, allowed: str) -> bool:
        return source in {value.strip() for value in allowed.split(",")}

    # v5.1 validates current source credentials before the target role is assumed.
    assert not precheck(guard.MANAGEMENT_ACCOUNT, guard.ACCOUNT)
    assert precheck(guard.MANAGEMENT_ACCOUNT, current)
    assert precheck(guard.ACCOUNT, current)
    assert not precheck("000000000000", current)


def test_pr_validation_runs_the_guard_without_aws_credentials() -> None:
    workflow = yaml.safe_load(
        (
            Path(__file__).parents[2] / ".github/workflows/pull-request-validation.yml"
        ).read_text()
    )
    job = workflow["jobs"]["nonprod-role-ci-guards"]
    assert job["permissions"] == {"contents": "read"}
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "tests/unit/test_nonprod_deploy_roles_ci.py" in commands
    assert "github-oidc-bootstrap/tests/unit/test_github_oidc_stack.py" in commands
    assert "app_campps_nonprod_roles_ci.py" in commands
    assert "CamppsNonProdDeployRolesStack" in commands
    assert "nonprod-role-ci-guards" in workflow["jobs"]["validation-summary"]["needs"]
