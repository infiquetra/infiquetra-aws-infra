"""CAMPPS workload-account deploy roles for GitHub Actions."""

from collections.abc import Sequence
from typing import Any

from aws_cdk import ArnFormat, CfnOutput, Duration, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

from infiquetra_aws_infra.campps_service_registry import (
    CAMPPS_SERVICE_REPOSITORIES,
    DeployEnvironment,
    ServiceRepository,
)

CAMPPS_NONPROD_ACCOUNT_ID = "477152411873"
CAMPPS_STAGING_ACCOUNT_ID = "050922968859"
CAMPPS_PROD_ACCOUNT_ID = "431643435299"

GITHUB_OIDC_URL = "https://token.actions.githubusercontent.com"
GITHUB_OIDC_HOST = "token.actions.githubusercontent.com"
GITHUB_OIDC_AUDIENCE = "sts.amazonaws.com"

CODEARTIFACT_DOMAIN = "infiquetra"
CODEARTIFACT_REPOSITORY = "campps"


class CamppsDeployRolesStack(Stack):
    """Create per-service GitHub Actions deploy roles in a CAMPPS account."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        target_environment: DeployEnvironment,
        service_repositories: Sequence[ServiceRepository] = CAMPPS_SERVICE_REPOSITORIES,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        oidc_provider = iam.CfnOIDCProvider(
            self,
            "GitHubActionsOidcProvider",
            url=GITHUB_OIDC_URL,
            client_id_list=[GITHUB_OIDC_AUDIENCE],
        )

        for service_repository in service_repositories:
            if target_environment not in service_repository.environments:
                continue

            deploy_role = self._create_deploy_role(
                oidc_provider=oidc_provider,
                service_repository=service_repository,
                target_environment=target_environment,
            )
            permissions_boundary = self._create_app_permissions_boundary(
                service_repository=service_repository,
                target_environment=target_environment,
            )
            deploy_policies = self._create_deploy_policies(
                service_repository=service_repository,
                target_environment=target_environment,
                permissions_boundary=permissions_boundary,
            )
            for deploy_policy in deploy_policies:
                deploy_role.add_managed_policy(deploy_policy)

            seam_proof_policy = self._create_scope_seam_proof_policy(
                service_repository=service_repository,
                target_environment=target_environment,
            )
            if seam_proof_policy is not None:
                deploy_role.add_managed_policy(seam_proof_policy)

            identity_scope_readback_policy = (
                self._create_e2e_canary_identity_scope_readback_policy(
                    service_repository=service_repository,
                    target_environment=target_environment,
                )
            )
            if identity_scope_readback_policy is not None:
                deploy_role.add_managed_policy(identity_scope_readback_policy)

            CfnOutput(
                self,
                f"{self._logical_id_prefix(service_repository.name)}DeployRoleArn",
                value=deploy_role.role_arn,
                description=(
                    f"Deploy role ARN for {service_repository.repository} "
                    f"{target_environment} deployments"
                ),
            )

    def _create_deploy_role(
        self,
        *,
        oidc_provider: iam.CfnOIDCProvider,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
    ) -> iam.Role:
        return iam.Role(
            self,
            f"{self._logical_id_prefix(service_repository.name)}DeployRole",
            role_name=service_repository.role_name(target_environment),
            assumed_by=iam.FederatedPrincipal(
                federated=oidc_provider.attr_arn,
                conditions={
                    "StringEquals": {
                        f"{GITHUB_OIDC_HOST}:aud": GITHUB_OIDC_AUDIENCE,
                        f"{GITHUB_OIDC_HOST}:sub": service_repository.github_subject(
                            target_environment
                        ),
                    }
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            max_session_duration=Duration.hours(2),
            description=(
                f"GitHub Actions deploy role for {service_repository.repository} "
                f"{target_environment}"
            ),
        )

    def _create_app_permissions_boundary(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
    ) -> iam.ManagedPolicy:
        prefix = f"campps-{service_repository.name}-{target_environment}"
        return iam.ManagedPolicy(
            self,
            f"{self._logical_id_prefix(service_repository.name)}AppPermissionsBoundary",
            managed_policy_name=service_repository.permissions_boundary_name(
                target_environment
            ),
            description=(
                f"Maximum app role permissions for {service_repository.repository} "
                f"{target_environment}"
            ),
            statements=[
                iam.PolicyStatement(
                    actions=["cloudwatch:PutMetricData"],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:BatchGetItem",
                        "dynamodb:BatchWriteItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                        "dynamodb:UpdateItem",
                    ],
                    resources=[
                        self.format_arn(
                            service="dynamodb",
                            resource="table",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    actions=["events:PutEvents"],
                    resources=[
                        self.format_arn(
                            service="events",
                            resource="event-bus",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    actions=[
                        "kms:Decrypt",
                        "kms:DescribeKey",
                        "kms:Encrypt",
                        "kms:GenerateDataKey",
                    ],
                    resources=[
                        self.format_arn(
                            service="kms",
                            resource="key",
                            resource_name="*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:ResourceTag/Service": service_repository.name,
                            "aws:ResourceTag/Environment": target_environment,
                        }
                    },
                ),
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=[
                        self.format_arn(
                            service="logs",
                            resource="log-group",
                            resource_name=f"/aws/lambda/{prefix}-*:log-stream:*",
                            arn_format=ArnFormat.COLON_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[
                        self.format_arn(
                            service="secretsmanager",
                            resource="secret",
                            resource_name=(
                                f"campps/{service_repository.name}/{target_environment}/*"
                            ),
                            arn_format=ArnFormat.COLON_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    actions=[
                        "sqs:ChangeMessageVisibility",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                        "sqs:ReceiveMessage",
                        "sqs:SendMessage",
                    ],
                    resources=[
                        self.format_arn(
                            service="sqs",
                            resource=f"{prefix}-*",
                            arn_format=ArnFormat.NO_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    actions=["ssm:GetParameter", "ssm:GetParameters"],
                    resources=[
                        self.format_arn(
                            service="ssm",
                            resource="parameter",
                            resource_name=(
                                f"campps/{service_repository.name}/{target_environment}/*"
                            ),
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
            ],
        )

    def _create_deploy_policies(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
        permissions_boundary: iam.ManagedPolicy,
    ) -> tuple[iam.ManagedPolicy, ...]:
        """Select the deploy policy builder for the service deploy profile.

        ``serverless-api`` and ``platform-foundation`` each return a split set
        of managed policies to stay under the IAM managed-policy size limit.
        The ``codeartifact-publish`` and ``web-app`` profiles each return a
        single managed policy.

        Every recognized profile is matched explicitly; an unknown profile
        raises rather than falling back to ``serverless-api``, so a typo can
        never silently mint an over-privileged serverless-api role.
        """
        profile = service_repository.deploy_profile
        if profile == "serverless-api":
            return self._create_serverless_api_deploy_policies(
                service_repository=service_repository,
                target_environment=target_environment,
                permissions_boundary=permissions_boundary,
            )
        if profile == "platform-foundation":
            return self._create_platform_foundation_deploy_policies(
                service_repository=service_repository,
                target_environment=target_environment,
                permissions_boundary=permissions_boundary,
            )
        if profile == "codeartifact-publish":
            return (
                self._create_codeartifact_publish_deploy_policy(
                    service_repository=service_repository,
                    target_environment=target_environment,
                    permissions_boundary=permissions_boundary,
                ),
            )
        if profile == "web-app":
            return (
                self._create_web_app_deploy_policy(
                    service_repository=service_repository,
                    target_environment=target_environment,
                    permissions_boundary=permissions_boundary,
                ),
            )
        raise ValueError(f"unknown deploy_profile: {profile!r}")

    def _codeartifact_domain_arn(self) -> str:
        return str(
            self.format_arn(
                service="codeartifact",
                resource="domain",
                resource_name=CODEARTIFACT_DOMAIN,
                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
            )
        )

    def _codeartifact_repository_arn(self) -> str:
        return str(
            self.format_arn(
                service="codeartifact",
                resource="repository",
                resource_name=f"{CODEARTIFACT_DOMAIN}/{CODEARTIFACT_REPOSITORY}",
                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
            )
        )

    def _codeartifact_package_arn(self) -> str:
        return str(
            self.format_arn(
                service="codeartifact",
                resource="package",
                resource_name=f"{CODEARTIFACT_DOMAIN}/{CODEARTIFACT_REPOSITORY}/*",
                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
            )
        )

    def _codeartifact_consume_statements(self) -> list[iam.PolicyStatement]:
        """Read grant so CI ``uv sync`` can pull the pinned campps-contracts dep."""
        return [
            iam.PolicyStatement(
                sid="CodeArtifactConsumeAuth",
                actions=[
                    "codeartifact:GetAuthorizationToken",
                    "codeartifact:GetRepositoryEndpoint",
                ],
                resources=[
                    self._codeartifact_domain_arn(),
                    self._codeartifact_repository_arn(),
                ],
            ),
            iam.PolicyStatement(
                sid="CodeArtifactConsumeRead",
                actions=[
                    "codeartifact:DescribePackageVersion",
                    "codeartifact:GetPackageVersionAsset",
                    "codeartifact:ListPackageVersionAssets",
                    "codeartifact:ReadFromRepository",
                ],
                resources=[
                    self._codeartifact_repository_arn(),
                    self._codeartifact_package_arn(),
                ],
            ),
            iam.PolicyStatement(
                sid="CodeArtifactBearerToken",
                actions=["sts:GetServiceBearerToken"],
                resources=["*"],
            ),
        ]

    def _cdk_bootstrap_role_statements(self) -> list[iam.PolicyStatement]:
        """Allow assuming the CDK modern-bootstrap roles + passing cfn-exec.

        CDK deploys with a restricted GitHub Actions principal by assuming the
        ``cdk-hnb659fds`` bootstrap deploy/file-publishing/image-publishing/
        lookup roles, then handing CloudFormation the bootstrap cfn-exec role.
        Without these grants CDK falls back to acting as the GitHub Actions
        deploy role directly, which then lacks ``iam:PassRole`` on the
        bootstrap cfn-exec role and the deploy fails. Scoped to the
        ``hnb659fds`` qualifier in this account and region only.
        """
        return [
            iam.PolicyStatement(
                sid="CdkBootstrapAssumeRoles",
                actions=["sts:AssumeRole"],
                resources=[
                    f"arn:aws:iam::{self.account}:role/"
                    f"cdk-hnb659fds-*-{self.account}-{self.region}",
                ],
            ),
            iam.PolicyStatement(
                sid="CdkBootstrapPassExecRole",
                actions=["iam:PassRole"],
                resources=[
                    f"arn:aws:iam::{self.account}:role/"
                    f"cdk-hnb659fds-cfn-exec-role-{self.account}-{self.region}",
                ],
            ),
        ]

    def _cloudformation_baseline_statements(
        self,
        *,
        prefix: str,
    ) -> list[iam.PolicyStatement]:
        """CloudFormation + CDK-assets S3 + cdk-bootstrap SSM read baseline."""
        return [
            iam.PolicyStatement(
                sid="CloudFormationDeployments",
                actions=[
                    "cloudformation:CancelUpdateStack",
                    "cloudformation:ContinueUpdateRollback",
                    "cloudformation:CreateChangeSet",
                    "cloudformation:CreateStack",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStackResource",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:DescribeStacks",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:GetTemplate",
                    "cloudformation:GetTemplateSummary",
                    "cloudformation:SetStackPolicy",
                    "cloudformation:UpdateStack",
                ],
                resources=[
                    self.format_arn(
                        service="cloudformation",
                        resource="stack",
                        resource_name=f"{prefix}-*/*",
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    ),
                    self.format_arn(
                        service="cloudformation",
                        resource="changeSet",
                        resource_name="cdk-deploy-change-set/*",
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    ),
                ],
            ),
            iam.PolicyStatement(
                sid="CloudFormationTemplateValidation",
                actions=["cloudformation:ValidateTemplate"],
                resources=["*"],
            ),
            iam.PolicyStatement(
                sid="CdkAssetsBucket",
                actions=[
                    "s3:AbortMultipartUpload",
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:PutObject",
                ],
                resources=[
                    f"arn:aws:s3:::cdk-hnb659fds-assets-{self.account}-{self.region}",
                    f"arn:aws:s3:::cdk-hnb659fds-assets-{self.account}-{self.region}/*",
                ],
            ),
            iam.PolicyStatement(
                sid="CdkBootstrapVersion",
                actions=["ssm:GetParameter"],
                resources=[
                    self.format_arn(
                        service="ssm",
                        resource="parameter",
                        resource_name="cdk-bootstrap/hnb659fds/version",
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    )
                ],
            ),
            *self._cdk_bootstrap_role_statements(),
        ]

    def _create_codeartifact_publish_deploy_policy(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
        permissions_boundary: iam.ManagedPolicy,
    ) -> iam.ManagedPolicy:
        prefix = f"campps-{service_repository.name}-{target_environment}"
        return iam.ManagedPolicy(
            self,
            f"{self._logical_id_prefix(service_repository.name)}DeployPolicy",
            managed_policy_name=service_repository.policy_name(target_environment),
            description=(
                f"CodeArtifact publish deployment permissions for "
                f"{service_repository.repository} {target_environment}"
            ),
            statements=[
                *self._cloudformation_baseline_statements(prefix=prefix),
                *self._codeartifact_consume_statements(),
                iam.PolicyStatement(
                    sid="CodeArtifactPublishAuth",
                    actions=[
                        "codeartifact:GetAuthorizationToken",
                        "sts:GetServiceBearerToken",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    sid="CodeArtifactPublishPackages",
                    actions=["codeartifact:PublishPackageVersion"],
                    resources=[self._codeartifact_package_arn()],
                ),
                iam.PolicyStatement(
                    sid="CodeArtifactPublishReads",
                    actions=[
                        "codeartifact:DescribeDomain",
                        "codeartifact:DescribePackageVersion",
                        "codeartifact:DescribeRepository",
                        "codeartifact:ListPackageVersions",
                        "codeartifact:ListPackages",
                        "codeartifact:ListRepositories",
                        "codeartifact:ReadFromRepository",
                    ],
                    resources=[
                        self._codeartifact_domain_arn(),
                        self._codeartifact_repository_arn(),
                        self._codeartifact_package_arn(),
                    ],
                ),
            ],
        )

    def _create_web_app_deploy_policy(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
        permissions_boundary: iam.ManagedPolicy,
    ) -> iam.ManagedPolicy:
        """Least-privilege static-site (S3 + CloudFront) deploy policy.

        PROVISIONAL (KTD3): ``campps-web-app`` is an empty scaffold today with
        no settled deploy target, so this profile is scoped to the standard
        static-site pattern — the shared CloudFormation + CDK-bootstrap
        baseline, S3 object/bucket ops on the service's own
        ``campps-web-app-<env>-*`` buckets, and CloudFront distribution +
        invalidation + origin-access-control management. It deliberately grants
        **no** Lambda / DynamoDB / API Gateway / EventBridge / SQS / Secrets
        Manager actions. Revisit and tighten when the real web-app CDK stack
        lands (it may be Amplify or differ). See
        docs/plans/2026-06-20-c0-3-aws-infra-service-registry-oidc-plan.md.

        CloudFront create-class actions
        (``CreateDistribution``/``CreateOriginAccessControl``) do not support
        resource-level IAM scoping, so they are granted on ``*``; everything
        that can be scoped is pinned to this account's distributions.
        """
        prefix = f"campps-{service_repository.name}-{target_environment}"
        site_bucket_arn = f"arn:aws:s3:::{prefix}-*"
        distribution_arn = self.format_arn(
            service="cloudfront",
            region="",
            resource="distribution",
            resource_name="*",
            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
        )
        return iam.ManagedPolicy(
            self,
            f"{self._logical_id_prefix(service_repository.name)}DeployPolicy",
            managed_policy_name=service_repository.policy_name(target_environment),
            description=(
                f"Static-site (S3 + CloudFront) deployment permissions for "
                f"{service_repository.repository} {target_environment} "
                f"(provisional)"
            ),
            statements=[
                *self._cloudformation_baseline_statements(prefix=prefix),
                *self._codeartifact_consume_statements(),
                iam.PolicyStatement(
                    sid="StaticSiteBucket",
                    actions=[
                        "s3:CreateBucket",
                        "s3:DeleteObject",
                        "s3:GetBucketLocation",
                        "s3:GetBucketPolicy",
                        "s3:GetBucketWebsite",
                        "s3:GetEncryptionConfiguration",
                        "s3:GetObject",
                        "s3:ListBucket",
                        "s3:PutBucketPolicy",
                        "s3:PutBucketWebsite",
                        "s3:PutEncryptionConfiguration",
                        "s3:PutObject",
                    ],
                    resources=[site_bucket_arn, f"{site_bucket_arn}/*"],
                ),
                iam.PolicyStatement(
                    sid="CloudFrontDistributionManagement",
                    actions=[
                        "cloudfront:CreateInvalidation",
                        "cloudfront:GetDistribution",
                        "cloudfront:GetDistributionConfig",
                        "cloudfront:TagResource",
                        "cloudfront:UntagResource",
                        "cloudfront:UpdateDistribution",
                    ],
                    resources=[distribution_arn],
                ),
                iam.PolicyStatement(
                    sid="CloudFrontCreateAndOriginAccessControl",
                    actions=[
                        "cloudfront:CreateDistribution",
                        "cloudfront:CreateDistributionWithTags",
                        "cloudfront:CreateOriginAccessControl",
                        "cloudfront:GetOriginAccessControl",
                    ],
                    # CloudFront create-class actions have no resource-level
                    # IAM support; "*" is the AWS-documented requirement here.
                    resources=["*"],
                ),
            ],
        )

    def _create_platform_foundation_deploy_policies(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
        permissions_boundary: iam.ManagedPolicy,
    ) -> tuple[iam.ManagedPolicy, ...]:
        """Split platform-foundation grants across core/runtime/data policies.

        The combined platform-foundation document exceeds IAM's 6144-byte
        managed-policy size quota, so the identical set of permissions is
        partitioned into three managed policies, mirroring the
        ``serverless-api`` core/runtime/data split:

        * core: CloudFormation + CDK assets + CodeArtifact consume baseline
        * runtime: EventBridge bus + KMS keys/aliases + SSM platform params
        * data: IAM (bounded roles/policies) + CloudWatch + log groups +
          CodeArtifact domain/repository creation
        """
        prefix = f"campps-{service_repository.name}-{target_environment}"
        scoped_path = f"campps/{service_repository.name}/{target_environment}"
        permissions_boundary_arn = permissions_boundary.managed_policy_arn
        logical_prefix = self._logical_id_prefix(service_repository.name)
        core_policy = iam.ManagedPolicy(
            self,
            f"{logical_prefix}DeployPolicy",
            managed_policy_name=service_repository.policy_name(target_environment),
            description=(
                f"Platform foundation core deployment permissions for "
                f"{service_repository.repository} {target_environment}"
            ),
            statements=[
                *self._cloudformation_baseline_statements(prefix=prefix),
                *self._codeartifact_consume_statements(),
            ],
        )
        runtime_policy = iam.ManagedPolicy(
            self,
            f"{logical_prefix}RuntimeDeployPolicy",
            managed_policy_name=f"{prefix}-gha-runtime-policy",
            description=(
                f"Platform foundation runtime deployment permissions for "
                f"{service_repository.repository} {target_environment}"
            ),
            statements=[
                iam.PolicyStatement(
                    sid="PlatformEventBuses",
                    actions=[
                        "events:CreateEventBus",
                        "events:DeleteEventBus",
                        "events:DescribeEventBus",
                        "events:ListTagsForResource",
                        "events:TagResource",
                        "events:UntagResource",
                    ],
                    resources=[
                        self.format_arn(
                            service="events",
                            resource="event-bus",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformKmsKeyCreation",
                    actions=["kms:CreateKey"],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "aws:RequestTag/Service": service_repository.name,
                            "aws:RequestTag/Environment": target_environment,
                        },
                        "ForAllValues:StringEquals": {
                            "aws:TagKeys": ["Service", "Environment"]
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="PlatformKmsAliases",
                    actions=[
                        "kms:CreateAlias",
                        "kms:DeleteAlias",
                        "kms:UpdateAlias",
                    ],
                    resources=[
                        self.format_arn(
                            service="kms",
                            resource="alias",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformTaggedKmsKeys",
                    actions=[
                        "kms:DescribeKey",
                        "kms:EnableKeyRotation",
                        "kms:GetKeyPolicy",
                        "kms:GetKeyRotationStatus",
                        "kms:ListResourceTags",
                        "kms:PutKeyPolicy",
                        "kms:ScheduleKeyDeletion",
                        "kms:TagResource",
                        "kms:UntagResource",
                    ],
                    resources=[
                        self.format_arn(
                            service="kms",
                            resource="key",
                            resource_name="*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:ResourceTag/Service": service_repository.name,
                            "aws:ResourceTag/Environment": target_environment,
                        }
                    },
                ),
                iam.PolicyStatement(
                    sid="PlatformSsmParameters",
                    actions=[
                        "ssm:AddTagsToResource",
                        "ssm:DeleteParameter",
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath",
                        "ssm:ListTagsForResource",
                        "ssm:PutParameter",
                        "ssm:RemoveTagsFromResource",
                    ],
                    resources=[
                        self.format_arn(
                            service="ssm",
                            resource="parameter",
                            resource_name=f"{scoped_path}/*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformSsmParameterDiscovery",
                    actions=["ssm:DescribeParameters"],
                    resources=["*"],
                    conditions={"StringLike": {"ssm:Name": f"/{scoped_path}/*"}},
                ),
                iam.PolicyStatement(
                    sid="PlatformSsmParameterPathRead",
                    actions=["ssm:GetParametersByPath"],
                    resources=[
                        self.format_arn(
                            service="ssm",
                            resource="parameter",
                            resource_name=scoped_path,
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
            ],
        )
        data_policy = iam.ManagedPolicy(
            self,
            f"{logical_prefix}DataDeployPolicy",
            managed_policy_name=f"{prefix}-gha-data-policy",
            description=(
                f"Platform foundation data and configuration deployment "
                f"permissions for {service_repository.repository} "
                f"{target_environment}"
            ),
            statements=[
                iam.PolicyStatement(
                    sid="PlatformCreateBoundedRoles",
                    actions=["iam:CreateRole"],
                    resources=[
                        self.format_arn(
                            service="iam",
                            region="",
                            resource="role",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                    conditions={
                        "StringEquals": {
                            "iam:PermissionsBoundary": permissions_boundary_arn
                        }
                    },
                ),
                iam.PolicyStatement(
                    sid="PlatformManageRoles",
                    actions=[
                        "iam:DeleteRole",
                        "iam:DeleteRolePolicy",
                        "iam:DetachRolePolicy",
                        "iam:GetRole",
                        "iam:GetRolePolicy",
                        "iam:ListAttachedRolePolicies",
                        "iam:ListRolePolicies",
                        "iam:PutRolePolicy",
                        "iam:TagRole",
                        "iam:UntagRole",
                        "iam:UpdateAssumeRolePolicy",
                        "iam:UpdateRole",
                    ],
                    resources=[
                        self.format_arn(
                            service="iam",
                            region="",
                            resource="role",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformManagePolicies",
                    actions=[
                        "iam:CreatePolicy",
                        "iam:CreatePolicyVersion",
                        "iam:DeletePolicy",
                        "iam:DeletePolicyVersion",
                        "iam:GetPolicy",
                        "iam:GetPolicyVersion",
                        "iam:ListPolicyVersions",
                        "iam:SetDefaultPolicyVersion",
                        "iam:TagPolicy",
                        "iam:UntagPolicy",
                    ],
                    resources=[
                        self.format_arn(
                            service="iam",
                            region="",
                            resource="policy",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformAttachPolicies",
                    actions=["iam:AttachRolePolicy"],
                    resources=[
                        self.format_arn(
                            service="iam",
                            region="",
                            resource="role",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                    conditions={
                        "ArnLike": {
                            "iam:PolicyARN": self.format_arn(
                                service="iam",
                                region="",
                                resource="policy",
                                resource_name=f"{prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        }
                    },
                ),
                iam.PolicyStatement(
                    sid="PlatformCloudWatchDashboards",
                    actions=[
                        "cloudwatch:DeleteDashboards",
                        "cloudwatch:GetDashboard",
                        "cloudwatch:PutDashboard",
                    ],
                    resources=[
                        self.format_arn(
                            service="cloudwatch",
                            region="",
                            resource="dashboard",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformCloudWatchAlarms",
                    actions=[
                        "cloudwatch:DeleteAlarms",
                        "cloudwatch:DescribeAlarms",
                        "cloudwatch:PutMetricAlarm",
                    ],
                    resources=[
                        self.format_arn(
                            service="cloudwatch",
                            resource="alarm",
                            resource_name=f"{prefix}-*",
                            arn_format=ArnFormat.COLON_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformLogGroups",
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:DeleteLogGroup",
                        "logs:DescribeLogGroups",
                        "logs:ListTagsForResource",
                        "logs:PutRetentionPolicy",
                        "logs:TagResource",
                        "logs:UntagResource",
                    ],
                    resources=[
                        self.format_arn(
                            service="logs",
                            resource="log-group",
                            resource_name=f"/campps/{service_repository.name}/"
                            f"{target_environment}-*",
                            arn_format=ArnFormat.COLON_RESOURCE_NAME,
                        ),
                        self.format_arn(
                            service="logs",
                            resource="log-group",
                            resource_name=f"/campps/{service_repository.name}/"
                            f"{target_environment}-*:log-stream:*",
                            arn_format=ArnFormat.COLON_RESOURCE_NAME,
                        ),
                    ],
                ),
                iam.PolicyStatement(
                    sid="PlatformCodeArtifactDomain",
                    actions=[
                        "codeartifact:CreateDomain",
                        "codeartifact:DescribeDomain",
                        "codeartifact:PutDomainPermissionsPolicy",
                    ],
                    resources=[self._codeartifact_domain_arn()],
                ),
                iam.PolicyStatement(
                    sid="PlatformCodeArtifactRepository",
                    actions=[
                        "codeartifact:CreateRepository",
                        "codeartifact:DescribeRepository",
                        "codeartifact:PutRepositoryPermissionsPolicy",
                        "codeartifact:ReadFromRepository",
                    ],
                    resources=[self._codeartifact_repository_arn()],
                ),
            ],
        )
        return (core_policy, runtime_policy, data_policy)

    def _shared_platform_ssm_read_statements(
        self, *, target_environment: DeployEnvironment
    ) -> list[iam.PolicyStatement]:
        """Allow service deploy workflows to read shared platform discovery params."""
        platform_path = f"campps/platform/{target_environment}"
        return [
            iam.PolicyStatement(
                sid="SharedPlatformSsmParameterReads",
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    self.format_arn(
                        service="ssm",
                        resource="parameter",
                        resource_name=f"{platform_path}/*",
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    )
                ],
            ),
            iam.PolicyStatement(
                sid="SharedPlatformSsmParameterPathRead",
                actions=["ssm:GetParametersByPath"],
                resources=[
                    self.format_arn(
                        service="ssm",
                        resource="parameter",
                        resource_name=platform_path,
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    ),
                    self.format_arn(
                        service="ssm",
                        resource="parameter",
                        resource_name=f"{platform_path}/*",
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    ),
                ],
            ),
        ]

    def _create_serverless_api_deploy_policies(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
        permissions_boundary: iam.ManagedPolicy,
    ) -> tuple[iam.ManagedPolicy, ...]:
        prefix = f"campps-{service_repository.name}-{target_environment}"
        app_iam_prefix = f"{prefix}-app"
        permissions_boundary_arn = permissions_boundary.managed_policy_arn
        return (
            iam.ManagedPolicy(
                self,
                f"{self._logical_id_prefix(service_repository.name)}DeployPolicy",
                managed_policy_name=service_repository.policy_name(target_environment),
                description=(
                    f"Core deployment permissions for "
                    f"{service_repository.repository} {target_environment}"
                ),
                statements=[
                    *self._codeartifact_consume_statements(),
                    iam.PolicyStatement(
                        sid="CloudFormationDeployments",
                        actions=[
                            "cloudformation:CancelUpdateStack",
                            "cloudformation:ContinueUpdateRollback",
                            "cloudformation:CreateChangeSet",
                            "cloudformation:CreateStack",
                            "cloudformation:DeleteChangeSet",
                            "cloudformation:DeleteStack",
                            "cloudformation:DescribeChangeSet",
                            "cloudformation:DescribeStackEvents",
                            "cloudformation:DescribeStackResource",
                            "cloudformation:DescribeStackResources",
                            "cloudformation:DescribeStacks",
                            "cloudformation:ExecuteChangeSet",
                            "cloudformation:GetTemplate",
                            "cloudformation:GetTemplateSummary",
                            "cloudformation:SetStackPolicy",
                            "cloudformation:UpdateStack",
                        ],
                        resources=[
                            self.format_arn(
                                service="cloudformation",
                                resource="stack",
                                resource_name=f"{prefix}-*/*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            ),
                            self.format_arn(
                                service="cloudformation",
                                resource="changeSet",
                                resource_name="cdk-deploy-change-set/*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            ),
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="CloudFormationTemplateValidation",
                        actions=["cloudformation:ValidateTemplate"],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        sid="CdkAssetsBucket",
                        actions=[
                            "s3:AbortMultipartUpload",
                            "s3:GetBucketLocation",
                            "s3:GetObject",
                            "s3:ListBucket",
                            "s3:ListBucketMultipartUploads",
                            "s3:PutObject",
                        ],
                        resources=[
                            f"arn:aws:s3:::cdk-hnb659fds-assets-{self.account}-{self.region}",
                            f"arn:aws:s3:::cdk-hnb659fds-assets-{self.account}-{self.region}/*",
                        ],
                    ),
                    *self._cdk_bootstrap_role_statements(),
                    iam.PolicyStatement(
                        sid="CreateBoundedServerlessRoles",
                        actions=["iam:CreateRole"],
                        resources=[
                            self.format_arn(
                                service="iam",
                                region="",
                                resource="role",
                                resource_name=f"{app_iam_prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                        conditions={
                            "StringEquals": {
                                "iam:PermissionsBoundary": permissions_boundary_arn
                            }
                        },
                    ),
                    iam.PolicyStatement(
                        sid="ManageServerlessRoles",
                        actions=[
                            "iam:DeleteRole",
                            "iam:DeleteRolePolicy",
                            "iam:DetachRolePolicy",
                            "iam:GetRole",
                            "iam:GetRolePolicy",
                            "iam:ListAttachedRolePolicies",
                            "iam:ListRolePolicies",
                            "iam:PutRolePolicy",
                            "iam:TagRole",
                            "iam:UntagRole",
                            "iam:UpdateAssumeRolePolicy",
                            "iam:UpdateRole",
                        ],
                        resources=[
                            self.format_arn(
                                service="iam",
                                region="",
                                resource="role",
                                resource_name=f"{app_iam_prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="ManageServerlessPolicies",
                        actions=[
                            "iam:CreatePolicy",
                            "iam:CreatePolicyVersion",
                            "iam:DeletePolicy",
                            "iam:DeletePolicyVersion",
                            "iam:GetPolicy",
                            "iam:GetPolicyVersion",
                            "iam:ListPolicyVersions",
                            "iam:SetDefaultPolicyVersion",
                            "iam:TagPolicy",
                            "iam:UntagPolicy",
                        ],
                        resources=[
                            self.format_arn(
                                service="iam",
                                region="",
                                resource="policy",
                                resource_name=f"{app_iam_prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="AttachServerlessPolicies",
                        actions=["iam:AttachRolePolicy"],
                        resources=[
                            self.format_arn(
                                service="iam",
                                region="",
                                resource="role",
                                resource_name=f"{app_iam_prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                        conditions={
                            "ArnLike": {
                                "iam:PolicyARN": self.format_arn(
                                    service="iam",
                                    region="",
                                    resource="policy",
                                    resource_name=f"{app_iam_prefix}-*",
                                    arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                                )
                            }
                        },
                    ),
                    iam.PolicyStatement(
                        sid="PassServerlessRoles",
                        actions=["iam:PassRole"],
                        resources=[
                            self.format_arn(
                                service="iam",
                                region="",
                                resource="role",
                                resource_name=f"{app_iam_prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                        conditions={
                            "StringEquals": {
                                "iam:PassedToService": [
                                    "apigateway.amazonaws.com",
                                    "cloudformation.amazonaws.com",
                                    "events.amazonaws.com",
                                    "lambda.amazonaws.com",
                                ]
                            }
                        },
                    ),
                ],
            ),
            iam.ManagedPolicy(
                self,
                f"{self._logical_id_prefix(service_repository.name)}RuntimeDeployPolicy",
                managed_policy_name=f"{prefix}-gha-runtime-policy",
                description=(
                    f"Runtime deployment permissions for "
                    f"{service_repository.repository} {target_environment}"
                ),
                statements=[
                    iam.PolicyStatement(
                        sid="LambdaApiRuntimeResources",
                        actions=[
                            "lambda:CreateAlias",
                            "lambda:CreateEventSourceMapping",
                            "lambda:CreateFunction",
                            "lambda:DeleteAlias",
                            "lambda:DeleteEventSourceMapping",
                            "lambda:DeleteFunction",
                            "lambda:GetAlias",
                            "lambda:GetEventSourceMapping",
                            "lambda:GetFunction",
                            "lambda:GetFunctionConfiguration",
                            "lambda:ListAliases",
                            "lambda:ListEventSourceMappings",
                            "lambda:ListTags",
                            "lambda:ListVersionsByFunction",
                            "lambda:PublishVersion",
                            "lambda:RemovePermission",
                            "lambda:TagResource",
                            "lambda:UntagResource",
                            "lambda:UpdateAlias",
                            "lambda:UpdateEventSourceMapping",
                            "lambda:UpdateFunctionCode",
                            "lambda:UpdateFunctionConfiguration",
                        ],
                        resources=[
                            self.format_arn(
                                service="lambda",
                                resource="function",
                                resource_name=f"{prefix}-*",
                                arn_format=ArnFormat.COLON_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="GrantServerlessInvokePermissions",
                        actions=["lambda:AddPermission"],
                        resources=[
                            self.format_arn(
                                service="lambda",
                                resource="function",
                                resource_name=f"{prefix}-*",
                                arn_format=ArnFormat.COLON_RESOURCE_NAME,
                            )
                        ],
                        conditions={
                            "StringEquals": {
                                "lambda:Principal": [
                                    "apigateway.amazonaws.com",
                                    "events.amazonaws.com",
                                ]
                            }
                        },
                    ),
                    iam.PolicyStatement(
                        sid="LambdaLayerReads",
                        actions=["lambda:GetLayerVersion"],
                        resources=[
                            self.format_arn(
                                service="lambda",
                                resource="layer",
                                resource_name="*:*",
                                arn_format=ArnFormat.COLON_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="ApiGatewayReadDeployments",
                        actions=["apigateway:GET"],
                        resources=[
                            self.format_arn(
                                service="apigateway",
                                account="",
                                resource="/restapis",
                                arn_format=ArnFormat.NO_RESOURCE_NAME,
                            ),
                            self.format_arn(
                                service="apigateway",
                                account="",
                                resource="/restapis",
                                resource_name="*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            ),
                            self.format_arn(
                                service="apigateway",
                                account="",
                                resource="/tags",
                                resource_name="*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            ),
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="ApiGatewayCreateDeployments",
                        actions=["apigateway:POST"],
                        resources=[
                            self.format_arn(
                                service="apigateway",
                                account="",
                                resource="/restapis",
                                arn_format=ArnFormat.NO_RESOURCE_NAME,
                            )
                        ],
                        conditions={
                            "StringEquals": {
                                "aws:RequestTag/Service": service_repository.name,
                                "aws:RequestTag/Environment": target_environment,
                            },
                            "ForAllValues:StringEquals": {
                                "aws:TagKeys": ["Service", "Environment"]
                            },
                        },
                    ),
                    iam.PolicyStatement(
                        sid="ApiGatewayWriteDeployments",
                        actions=[
                            "apigateway:DELETE",
                            "apigateway:PATCH",
                            "apigateway:POST",
                            "apigateway:PUT",
                        ],
                        resources=[
                            self.format_arn(
                                service="apigateway",
                                account="",
                                resource="/restapis",
                                resource_name="*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            ),
                            self.format_arn(
                                service="apigateway",
                                account="",
                                resource="/tags",
                                resource_name="*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            ),
                        ],
                        conditions={
                            "StringEquals": {
                                "aws:ResourceTag/Service": service_repository.name,
                                "aws:ResourceTag/Environment": target_environment,
                            }
                        },
                    ),
                    iam.PolicyStatement(
                        sid="DynamoDbTables",
                        actions=[
                            "dynamodb:CreateTable",
                            "dynamodb:DeleteTable",
                            "dynamodb:DescribeContinuousBackups",
                            "dynamodb:DescribeTable",
                            "dynamodb:DescribeTimeToLive",
                            "dynamodb:ListTagsOfResource",
                            "dynamodb:TagResource",
                            "dynamodb:UntagResource",
                            "dynamodb:UpdateContinuousBackups",
                            "dynamodb:UpdateTable",
                            "dynamodb:UpdateTimeToLive",
                        ],
                        resources=[
                            self.format_arn(
                                service="dynamodb",
                                resource="table",
                                resource_name=f"{prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="EventBridgeRules",
                        actions=[
                            "events:DeleteRule",
                            "events:DescribeRule",
                            "events:ListTagsForResource",
                            "events:ListTargetsByRule",
                            "events:PutRule",
                            "events:PutTargets",
                            "events:RemoveTargets",
                            "events:TagResource",
                            "events:UntagResource",
                        ],
                        resources=[
                            self.format_arn(
                                service="events",
                                resource="rule",
                                resource_name=f"{prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="SqsQueues",
                        actions=[
                            "sqs:CreateQueue",
                            "sqs:DeleteQueue",
                            "sqs:GetQueueAttributes",
                            "sqs:GetQueueUrl",
                            "sqs:ListQueueTags",
                            "sqs:SetQueueAttributes",
                            "sqs:TagQueue",
                            "sqs:UntagQueue",
                        ],
                        resources=[
                            self.format_arn(
                                service="sqs",
                                resource=f"{prefix}-*",
                                arn_format=ArnFormat.NO_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="CloudWatchAlarms",
                        actions=[
                            "cloudwatch:DeleteAlarms",
                            "cloudwatch:DescribeAlarms",
                            "cloudwatch:PutMetricAlarm",
                        ],
                        resources=[
                            self.format_arn(
                                service="cloudwatch",
                                resource="alarm",
                                resource_name=f"{prefix}-*",
                                arn_format=ArnFormat.COLON_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="LambdaLogGroups",
                        actions=[
                            "logs:CreateLogGroup",
                            "logs:DeleteLogGroup",
                            "logs:DescribeLogGroups",
                            "logs:ListTagsForResource",
                            "logs:PutRetentionPolicy",
                            "logs:TagResource",
                            "logs:UntagResource",
                        ],
                        resources=[
                            self.format_arn(
                                service="logs",
                                resource="log-group",
                                resource_name=f"/aws/lambda/{prefix}-*",
                                arn_format=ArnFormat.COLON_RESOURCE_NAME,
                            ),
                            self.format_arn(
                                service="logs",
                                resource="log-group",
                                resource_name=f"/aws/lambda/{prefix}-*:log-stream:*",
                                arn_format=ArnFormat.COLON_RESOURCE_NAME,
                            ),
                        ],
                    ),
                ],
            ),
            iam.ManagedPolicy(
                self,
                f"{self._logical_id_prefix(service_repository.name)}DataDeployPolicy",
                managed_policy_name=f"{prefix}-gha-data-policy",
                description=(
                    f"Data and configuration deployment permissions for "
                    f"{service_repository.repository} {target_environment}"
                ),
                statements=[
                    iam.PolicyStatement(
                        sid="KmsKeyCreation",
                        actions=["kms:CreateKey"],
                        resources=["*"],
                        conditions={
                            "StringEquals": {
                                "aws:RequestTag/Service": service_repository.name,
                                "aws:RequestTag/Environment": target_environment,
                            },
                            "ForAllValues:StringEquals": {
                                "aws:TagKeys": ["Service", "Environment"]
                            },
                        },
                    ),
                    iam.PolicyStatement(
                        sid="KmsAliases",
                        actions=[
                            "kms:CreateAlias",
                            "kms:DeleteAlias",
                            "kms:UpdateAlias",
                        ],
                        resources=[
                            self.format_arn(
                                service="kms",
                                resource="alias",
                                resource_name=f"{prefix}-*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="TaggedKmsKeys",
                        actions=[
                            "kms:DescribeKey",
                            "kms:EnableKeyRotation",
                            "kms:GetKeyPolicy",
                            "kms:GetKeyRotationStatus",
                            "kms:ListResourceTags",
                            "kms:PutKeyPolicy",
                            "kms:ScheduleKeyDeletion",
                            "kms:TagResource",
                            "kms:UntagResource",
                        ],
                        resources=[
                            self.format_arn(
                                service="kms",
                                resource="key",
                                resource_name="*",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                        conditions={
                            "StringEquals": {
                                "aws:ResourceTag/Service": service_repository.name,
                                "aws:ResourceTag/Environment": target_environment,
                            }
                        },
                    ),
                    iam.PolicyStatement(
                        sid="SecretsManagerSecrets",
                        actions=[
                            "secretsmanager:CreateSecret",
                            "secretsmanager:DeleteSecret",
                            "secretsmanager:DescribeSecret",
                            "secretsmanager:GetResourcePolicy",
                            "secretsmanager:PutSecretValue",
                            "secretsmanager:TagResource",
                            "secretsmanager:UntagResource",
                            "secretsmanager:UpdateSecret",
                        ],
                        resources=[
                            self.format_arn(
                                service="secretsmanager",
                                resource="secret",
                                resource_name=(
                                    f"campps/{service_repository.name}/{target_environment}/*"
                                ),
                                arn_format=ArnFormat.COLON_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="SsmParameters",
                        actions=[
                            "ssm:AddTagsToResource",
                            "ssm:DeleteParameter",
                            "ssm:GetParameter",
                            "ssm:GetParameters",
                            "ssm:ListTagsForResource",
                            "ssm:PutParameter",
                            "ssm:RemoveTagsFromResource",
                        ],
                        resources=[
                            self.format_arn(
                                service="ssm",
                                resource="parameter",
                                resource_name=(
                                    f"campps/{service_repository.name}/{target_environment}/*"
                                ),
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                    ),
                    *self._shared_platform_ssm_read_statements(
                        target_environment=target_environment
                    ),
                    iam.PolicyStatement(
                        sid="CdkBootstrapVersion",
                        actions=["ssm:GetParameter"],
                        resources=[
                            self.format_arn(
                                service="ssm",
                                resource="parameter",
                                resource_name="cdk-bootstrap/hnb659fds/version",
                                arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        sid="SsmParameterDiscovery",
                        actions=["ssm:DescribeParameters"],
                        resources=["*"],
                        conditions={
                            "StringLike": {
                                "ssm:Name": (
                                    f"/campps/{service_repository.name}/{target_environment}/*"
                                )
                            }
                        },
                    ),
                ],
            ),
        )

    def _create_scope_seam_proof_policy(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
    ) -> iam.ManagedPolicy | None:
        """Cross-service grant for the deploy-gated scope-origination seam proof.

        campps-tenant-setup's nonprod deploy lane runs
        ``tests/integration/test_scope_origination_seam_deployed.py`` (PR #67):
        it emits a real ``CampDefinitionChanged`` to the shared platform bus and
        reads back the ``ResourceScope`` row that identity-access projects,
        proving the producer -> bus -> consumer seam end-to-end against deployed
        infrastructure. The deploy role needs ``events:PutEvents`` on the platform
        bus and ``dynamodb:GetItem`` on identity's table to run that proof.

        Scoped to tenant-setup + nonprod only: the proof runs only in the nonprod
        lane, and granting a staging/production deploy role read access into
        identity's table would be speculative privilege. Extend per environment
        only when those lanes also run the proof.
        """
        if service_repository.name != "tenant-setup" or target_environment != "nonprod":
            return None
        return iam.ManagedPolicy(
            self,
            f"{self._logical_id_prefix(service_repository.name)}ScopeSeamProofPolicy",
            managed_policy_name=(
                f"campps-{service_repository.name}-{target_environment}"
                "-gha-seam-proof-policy"
            ),
            description=(
                "Cross-service deploy-gated scope-origination seam proof grant "
                f"for {service_repository.repository} {target_environment} "
                "(campps-tenant-setup PR #67)"
            ),
            statements=[
                iam.PolicyStatement(
                    sid="ScopeSeamProducerEmit",
                    actions=["events:PutEvents"],
                    resources=[
                        self.format_arn(
                            service="events",
                            resource="event-bus",
                            resource_name=f"campps-platform-{target_environment}",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
                iam.PolicyStatement(
                    sid="ScopeSeamConsumerReadback",
                    actions=["dynamodb:GetItem"],
                    resources=[
                        self.format_arn(
                            service="dynamodb",
                            resource="table",
                            resource_name=f"campps-identity-access-{target_environment}",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
            ],
        )

    def _create_e2e_canary_identity_scope_readback_policy(
        self,
        *,
        service_repository: ServiceRepository,
        target_environment: DeployEnvironment,
    ) -> iam.ManagedPolicy | None:
        """Nonprod-only readback grant for the e2e canary identity-scope proof."""
        if service_repository.name != "e2e-canary" or target_environment != "nonprod":
            return None
        return iam.ManagedPolicy(
            self,
            (
                f"{self._logical_id_prefix(service_repository.name)}"
                "IdentityScopeReadbackPolicy"
            ),
            managed_policy_name=(
                f"campps-{service_repository.name}-{target_environment}"
                "-gha-identity-scope-readback-policy"
            ),
            description=(
                "Identity scope readback grant for "
                f"{service_repository.repository} {target_environment}"
            ),
            statements=[
                iam.PolicyStatement(
                    sid="IdentityScopeReadback",
                    actions=["dynamodb:GetItem"],
                    resources=[
                        self.format_arn(
                            service="dynamodb",
                            resource="table",
                            resource_name=f"campps-identity-access-{target_environment}",
                            arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                        )
                    ],
                ),
            ],
        )

    @staticmethod
    def _logical_id_prefix(service_name: str) -> str:
        return "".join(part.capitalize() for part in service_name.split("-"))
