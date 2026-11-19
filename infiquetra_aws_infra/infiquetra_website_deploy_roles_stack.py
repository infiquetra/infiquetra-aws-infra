"""Static website publishing roles for GitHub Actions."""

from typing import Any

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

MANAGEMENT_ACCOUNT_ID = "645166163764"
GITHUB_OIDC_HOST = "token.actions.githubusercontent.com"
GITHUB_SUBJECT_PREFIX = "repo:infiquetra@232245665/infiquetra-website@1366920096"


class InfiquetraWebsiteDeployRolesStack(Stack):
    """Allow main to publish website content within its GitHub environment."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self,
            "GitHubActionsOidcProvider",
            f"arn:aws:iam::{MANAGEMENT_ACCOUNT_ID}:oidc-provider/{GITHUB_OIDC_HOST}",
        )

        for role_name, environment, bucket_stage in (
            ("InfiquetraWebsiteNonprodDeployRole", "nonprod", "nonprod"),
            ("InfiquetraWebsiteDeployRole", "production", "prod"),
        ):
            bucket_arns = [
                f"arn:aws:s3:::{site}-website-{bucket_stage}-{MANAGEMENT_ACCOUNT_ID}"
                for site in ("infiquetra-llc", "infiquetra-software-llc")
            ]
            role = iam.Role(
                self,
                role_name,
                role_name=role_name,
                description=f"GitHub Actions static website publishing ({environment})",
                assumed_by=iam.FederatedPrincipal(
                    federated=provider.open_id_connect_provider_arn,
                    conditions={
                        "StringEquals": {
                            f"{GITHUB_OIDC_HOST}:aud": "sts.amazonaws.com",
                            f"{GITHUB_OIDC_HOST}:sub": (
                                f"{GITHUB_SUBJECT_PREFIX}:environment:{environment}"
                            ),
                            f"{GITHUB_OIDC_HOST}:ref": "refs/heads/main",
                        },
                    },
                    assume_role_action="sts:AssumeRoleWithWebIdentity",
                ),
                inline_policies={
                    "WebsitePublishing": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                actions=["s3:ListBucket"],
                                resources=bucket_arns,
                            ),
                            iam.PolicyStatement(
                                actions=["s3:PutObject", "s3:DeleteObject"],
                                resources=[f"{arn}/*" for arn in bucket_arns],
                            ),
                            iam.PolicyStatement(
                                actions=[
                                    "cloudfront:CreateInvalidation",
                                    "cloudfront:GetInvalidation",
                                ],
                                resources=[
                                    f"arn:aws:cloudfront::{MANAGEMENT_ACCOUNT_ID}:"
                                    "distribution/*"
                                ],
                                conditions={
                                    "StringEquals": {
                                        "aws:ResourceTag/Service": "infiquetra-website",
                                        "aws:ResourceTag/Environment": environment,
                                    },
                                },
                            ),
                        ],
                    ),
                },
            )
            CfnOutput(
                self,
                f"{role_name}Arn",
                value=role.role_arn,
                export_name=f"{role_name}Arn",
                description=f"Website publishing role ARN ({environment})",
            )
