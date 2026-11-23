"""Static public site publishing roles for GitHub Actions."""

from typing import Any

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

MANAGEMENT_ACCOUNT_ID = "645166163764"
MANAGEMENT_REGION = "us-east-1"
GITHUB_OIDC_HOST = "token.actions.githubusercontent.com"
# GitHub includes these numeric IDs with the repository's use_immutable_subject
# setting enabled. This trust uses the repository setting, not an org template.
GITHUB_SUBJECT_PREFIX = "repo:infiquetra@232245665/infiquetra-sdlc@1195488988"


class InfiquetraSdlcDeployRolesStack(Stack):
    """Allow main to publish the public site within its GitHub environment."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if self.account != MANAGEMENT_ACCOUNT_ID or self.region != MANAGEMENT_REGION:
            raise ValueError(
                f"{type(self).__name__} requires account {MANAGEMENT_ACCOUNT_ID} "
                f"and region {MANAGEMENT_REGION}"
            )

        provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self,
            "GitHubActionsOidcProvider",
            f"arn:aws:iam::{MANAGEMENT_ACCOUNT_ID}:oidc-provider/{GITHUB_OIDC_HOST}",
        )

        for role_name, environment, bucket_stage in (
            ("InfiquetraSdlcPublicSiteNonprodDeployRole", "nonprod", "nonprod"),
            ("InfiquetraSdlcPublicSiteDeployRole", "public-sdlc-pages", "prod"),
        ):
            bucket_arn = (
                f"arn:aws:s3:::infiquetra-sdlc-public-{bucket_stage}-"
                f"{MANAGEMENT_ACCOUNT_ID}"
            )
            role = iam.Role(
                self,
                role_name,
                role_name=role_name,
                description=(
                    f"GitHub Actions public SDLC site publishing ({environment})"
                ),
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
                    "SdlcPublicSitePublishing": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                actions=["s3:ListBucket"],
                                resources=[bucket_arn],
                            ),
                            iam.PolicyStatement(
                                actions=["s3:PutObject", "s3:DeleteObject"],
                                resources=[f"{bucket_arn}/*"],
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
                                        "aws:ResourceTag/Service": "infiquetra-sdlc",
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
                description=f"Public SDLC site publishing role ARN ({environment})",
            )
