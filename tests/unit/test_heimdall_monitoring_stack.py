"""Trust and permission boundaries for Forge AWS monitoring roles."""

from typing import Any

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from infiquetra_aws_infra.heimdall_monitoring_stack import (
    GITHUB_AUDIENCE,
    GITHUB_SUBJECT,
    MANAGEMENT_ROLE_NAME,
    WORKLOAD_ACCOUNTS,
    WORKLOAD_ROLE_NAME,
    HeimdallMonitoringManagementStack,
    HeimdallMonitoringWorkloadStack,
)

MANAGEMENT_ACCOUNT_ID = "645166163764"


def _resources(template: Template, resource_type: str) -> list[dict[str, Any]]:
    found = template.find_resources(resource_type)
    return [dict(resource) for resource in found.values()]


def _local_arn(value: Any) -> str:
    """Resolve only the AWS partition token emitted by the local CDK template."""
    if isinstance(value, str):
        return value
    separator, parts = value["Fn::Join"]
    return str(
        separator.join(
            "aws" if part == {"Ref": "AWS::Partition"} else part for part in parts
        )
    )


def _action_resources(statements: list[dict[str, Any]]) -> set[tuple[str, str]]:
    pairs = set()
    for statement in statements:
        assert statement["Effect"] == "Allow"
        actions = statement["Action"]
        resources = statement["Resource"]
        for action in actions if isinstance(actions, list) else [actions]:
            for resource in resources if isinstance(resources, list) else [resources]:
                pairs.add((action, _local_arn(resource)))
    return pairs


def _management_template() -> Template:
    stack = HeimdallMonitoringManagementStack(
        App(),
        "TestMonitoringManagementStack",
        env=Environment(account=MANAGEMENT_ACCOUNT_ID, region="us-east-1"),
    )
    return Template.from_stack(stack)


def _workload_template(account_id: str) -> Template:
    stack = HeimdallMonitoringWorkloadStack(
        App(),
        "TestMonitoringWorkloadStack",
        management_account_id=MANAGEMENT_ACCOUNT_ID,
        env=Environment(account=account_id, region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_management_role_reuses_provider_and_trusts_exact_home_lab_main() -> None:
    template = _management_template()
    role = _resources(template, "AWS::IAM::Role")[0]["Properties"]

    assert role["RoleName"] == MANAGEMENT_ROLE_NAME
    assert role["MaxSessionDuration"] == 3600
    trust = role["AssumeRolePolicyDocument"]["Statement"]
    assert len(trust) == 1
    assert trust[0]["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert trust[0]["Effect"] == "Allow"
    assert trust[0]["Condition"] == {
        "StringEquals": {
            "token.actions.githubusercontent.com:aud": GITHUB_AUDIENCE,
            "token.actions.githubusercontent.com:sub": GITHUB_SUBJECT,
        }
    }
    assert _local_arn(trust[0]["Principal"]["Federated"]) == (
        f"arn:aws:iam::{MANAGEMENT_ACCOUNT_ID}:"
        "oidc-provider/token.actions.githubusercontent.com"
    )
    template.resource_count_is("AWS::IAM::OIDCProvider", 0)
    template.resource_count_is("AWS::IAM::AccessKey", 0)


def test_management_permissions_only_read_and_assume_named_workload_roles() -> None:
    template = _management_template()
    policies = _resources(template, "AWS::IAM::Policy")
    assert len(policies) == 1
    statements = policies[0]["Properties"]["PolicyDocument"]["Statement"]

    assert _action_resources(statements) == {
        ("ce:GetCostAndUsage", "*"),
        ("cloudwatch:DescribeAlarms", "*"),
        *{
            (
                "sts:AssumeRole",
                f"arn:aws:iam::{account_id}:role/{WORKLOAD_ROLE_NAME}",
            )
            for account_id in WORKLOAD_ACCOUNTS.values()
        },
    }


def test_each_workload_role_trusts_only_management_and_reads_alarms() -> None:
    assert len(set(WORKLOAD_ACCOUNTS.values())) == len(WORKLOAD_ACCOUNTS)

    for account_id in WORKLOAD_ACCOUNTS.values():
        template = _workload_template(account_id)
        role = _resources(template, "AWS::IAM::Role")[0]["Properties"]
        policies = _resources(template, "AWS::IAM::Policy")

        assert role["RoleName"] == WORKLOAD_ROLE_NAME
        assert role["MaxSessionDuration"] == 3600
        trust = role["AssumeRolePolicyDocument"]["Statement"]
        assert len(trust) == 1
        assert trust[0]["Action"] == "sts:AssumeRole"
        assert trust[0]["Effect"] == "Allow"
        assert _local_arn(trust[0]["Principal"]["AWS"]) == (
            f"arn:aws:iam::{MANAGEMENT_ACCOUNT_ID}:role/{MANAGEMENT_ROLE_NAME}"
        )
        assert len(policies) == 1
        statements = policies[0]["Properties"]["PolicyDocument"]["Statement"]
        expected = {("cloudwatch:DescribeAlarms", "*")}
        if account_id == WORKLOAD_ACCOUNTS["nonprod"]:
            expected.add(("freetier:GetFreeTierUsage", "*"))
        assert _action_resources(statements) == expected
        template.resource_count_is("AWS::IAM::OIDCProvider", 0)
        template.resource_count_is("AWS::IAM::AccessKey", 0)
