"""Read-only AWS monitoring roles for the home-lab Forge workflow."""

from typing import Any

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

from infiquetra_aws_infra.campps_deploy_roles_stack import (
    CAMPPS_NONPROD_ACCOUNT_ID,
    CAMPPS_PROD_ACCOUNT_ID,
    CAMPPS_STAGING_ACCOUNT_ID,
)

MANAGEMENT_ROLE_NAME = "infiquetra-heimdall-monitoring-management-role"
WORKLOAD_ROLE_NAME = "infiquetra-heimdall-monitoring-workload-role"
GITHUB_OIDC_HOST = "token.actions.githubusercontent.com"
GITHUB_SUBJECT = "repo:infiquetra/home-lab:ref:refs/heads/main"
GITHUB_AUDIENCE = "sts.amazonaws.com"

WORKLOAD_ACCOUNTS = {
    "nonprod": CAMPPS_NONPROD_ACCOUNT_ID,
    "staging": CAMPPS_STAGING_ACCOUNT_ID,
    "prod": CAMPPS_PROD_ACCOUNT_ID,
}


class HeimdallMonitoringManagementStack(Stack):
    """GitHub OIDC entry role for cost, alarms, and named workload roles."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        provider_arn = (
            f"arn:{self.partition}:iam::{self.account}:oidc-provider/{GITHUB_OIDC_HOST}"
        )
        workload_role_arns = [
            f"arn:{self.partition}:iam::{account_id}:role/{WORKLOAD_ROLE_NAME}"
            for account_id in WORKLOAD_ACCOUNTS.values()
        ]
        role = iam.Role(
            self,
            "HeimdallMonitoringManagementRole",
            role_name=MANAGEMENT_ROLE_NAME,
            assumed_by=iam.FederatedPrincipal(
                provider_arn,
                conditions={
                    "StringEquals": {
                        f"{GITHUB_OIDC_HOST}:aud": GITHUB_AUDIENCE,
                        f"{GITHUB_OIDC_HOST}:sub": GITHUB_SUBJECT,
                    }
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            max_session_duration=Duration.hours(1),
            description="Read-only cost and alarm monitoring for home-lab Forge",
        )
        role.add_to_policy(
            iam.PolicyStatement(actions=["ce:GetCostAndUsage"], resources=["*"])
        )
        role.add_to_policy(
            iam.PolicyStatement(actions=["cloudwatch:DescribeAlarms"], resources=["*"])
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["sts:AssumeRole"], resources=workload_role_arns
            )
        )

        CfnOutput(
            self,
            "MonitoringManagementRoleArn",
            value=role.role_arn,
            description="GitHub Actions management monitoring role ARN",
        )


class HeimdallMonitoringWorkloadStack(Stack):
    """Alarm reader in one workload account, trusted only by management."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        management_account_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        management_role_arn = (
            f"arn:{self.partition}:iam::{management_account_id}:"
            f"role/{MANAGEMENT_ROLE_NAME}"
        )
        role = iam.Role(
            self,
            "HeimdallMonitoringWorkloadRole",
            role_name=WORKLOAD_ROLE_NAME,
            assumed_by=iam.ArnPrincipal(management_role_arn),
            max_session_duration=Duration.hours(1),
            description="Read-only CloudWatch alarm monitoring for home-lab Forge",
        )
        role.add_to_policy(
            iam.PolicyStatement(actions=["cloudwatch:DescribeAlarms"], resources=["*"])
        )
        if self.account == CAMPPS_NONPROD_ACCOUNT_ID:
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["freetier:GetFreeTierUsage"], resources=["*"]
                )
            )

        CfnOutput(
            self,
            "MonitoringWorkloadRoleArn",
            value=role.role_arn,
            description="Workload CloudWatch alarm reader role ARN",
        )
