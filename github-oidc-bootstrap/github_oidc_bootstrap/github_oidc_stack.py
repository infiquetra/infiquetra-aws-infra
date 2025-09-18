"""
GitHub OIDC Bootstrap Stack

This stack creates:
1. GitHub OIDC Identity Provider
2. IAM Role for GitHub Actions with appropriate trust policy
3. Permissions for CDK deployments in the organizations repository

The role created here will be used by GitHub Actions to deploy the main
infiquetra-organizations CDK stacks.
"""

import os
from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Stack,
)
from aws_cdk import aws_iam as iam
from constructs import Construct


class GitHubOIDCStack(Stack):
    """Stack for GitHub OIDC provider and deployment role."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        github_owner: str | None = None,
        repo_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Repository configuration with environment variable fallbacks
        self.github_owner = github_owner or os.environ.get("GITHUB_OWNER", "infiquetra")
        self.repo_name = repo_name or os.environ.get(
            "GITHUB_REPO", "infiquetra-aws-infra"
        )
        self.repo_full_name = f"{self.github_owner}/{self.repo_name}"

        # Validate configuration
        self._validate_configuration()

        # Create GitHub OIDC Identity Provider
        github_oidc_provider = self._create_oidc_provider()

        # Create IAM role for GitHub Actions
        github_actions_role = self._create_github_actions_role(
            github_oidc_provider, self.repo_full_name
        )

        # Create managed policies for serverless deployments
        cdk_deployment_policy = self._create_cdk_deployment_policy()
        serverless_policy = self._create_serverless_policy()
        event_driven_policy = self._create_event_driven_policy()
        edge_services_policy = self._create_edge_services_policy()
        data_analytics_policy = self._create_data_analytics_policy()
        security_policy = self._create_security_policy()
        infrastructure_policy = self._create_infrastructure_policy()

        # Attach all managed policies to role
        github_actions_role.add_managed_policy(cdk_deployment_policy)
        github_actions_role.add_managed_policy(serverless_policy)
        github_actions_role.add_managed_policy(event_driven_policy)
        github_actions_role.add_managed_policy(edge_services_policy)
        github_actions_role.add_managed_policy(data_analytics_policy)
        github_actions_role.add_managed_policy(security_policy)
        github_actions_role.add_managed_policy(infrastructure_policy)

        # Output the role ARN for use in GitHub Actions
        CfnOutput(
            self,
            "GitHubActionsRoleArn",
            value=github_actions_role.role_arn,
            description="ARN of the IAM role for GitHub Actions deployments",
            export_name="GitHubActionsRoleArn",
        )

        # Output the OIDC provider ARN for reference
        CfnOutput(
            self,
            "GitHubOIDCProviderArn",
            value=github_oidc_provider.open_id_connect_provider_arn,
            description="ARN of the GitHub OIDC Identity Provider",
            export_name="GitHubOIDCProviderArn",
        )

        # Apply comprehensive resource tagging
        self._apply_resource_tags()

    def _create_oidc_provider(self) -> iam.OpenIdConnectProvider:
        """Create GitHub OIDC Identity Provider."""
        return iam.OpenIdConnectProvider(
            self,
            "GitHubOIDCProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
            # As of 2025, AWS no longer requires thumbprints for GitHub OIDC
            # Using placeholder value as CDK still requires at least one thumbprint
            thumbprints=[
                "1111111111111111111111111111111111111111",
            ],
        )

    def _create_github_actions_role(
        self, oidc_provider: iam.OpenIdConnectProvider, repo_full_name: str
    ) -> iam.Role:
        """Create IAM role for GitHub Actions with appropriate trust policy."""

        # Create FederatedPrincipal with conditions for GitHub OIDC

        return iam.Role(
            self,
            "GitHubActionsDeployRole",
            role_name="infiquetra-aws-infra-gha-role",
            description="Role for GitHub Actions to deploy CDK stacks from infiquetra-aws-infra",
            assumed_by=iam.FederatedPrincipal(
                oidc_provider.open_id_connect_provider_arn,
                {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        #                        "token.actions.githubusercontent.com:sub": f"repo:{repo_full_name}:*",
                        "token.actions.githubusercontent.com:sub": "repo:infiquetra/*",
                    },
                },
                "sts:AssumeRoleWithWebIdentity",
            ),
            max_session_duration=cdk.Duration.hours(12),
        )

    def _create_cdk_deployment_policy(self) -> iam.ManagedPolicy:
        """Create policy with permissions needed for CDK deployments."""

        # Get account ID for resource-specific policies
        account_id = cdk.Aws.ACCOUNT_ID
        region = cdk.Aws.REGION

        # Scoped permissions for CDK deployments, Organizations, and SSO
        policy_statements = [
            # CloudFormation permissions - scoped to CDK stacks
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudformation:CreateStack",
                    "cloudformation:UpdateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:GetTemplate",
                    "cloudformation:ListStacks",
                    "cloudformation:ValidateTemplate",
                    "cloudformation:CreateChangeSet",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:ListChangeSets",
                    "cloudformation:GetStackPolicy",
                    "cloudformation:SetStackPolicy",
                ],
                resources=[
                    f"arn:aws:cloudformation:{region}:{account_id}:stack/CDKToolkit/*",
                    f"arn:aws:cloudformation:{region}:{account_id}:stack/*-Organizations-*/*",
                    f"arn:aws:cloudformation:{region}:{account_id}:stack/*-SSO-*/*",
                    f"arn:aws:cloudformation:{region}:{account_id}:stack/*/*",
                ],
            ),
            # Allow listing stacks and getting templates globally for CDK operations
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudformation:ListStacks",
                    "cloudformation:DescribeStacks",
                ],
                resources=["*"],
            ),
            # IAM permissions - scoped to CDK and organization roles
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:PassRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:ListRolePolicies",
                    "iam:ListAttachedRolePolicies",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:UpdateRole",
                    "iam:UpdateAssumeRolePolicy",
                ],
                resources=[
                    f"arn:aws:iam::{account_id}:role/cdk-*",
                    f"arn:aws:iam::{account_id}:role/*-Organizations-*",
                    f"arn:aws:iam::{account_id}:role/*-SSO-*",
                    f"arn:aws:iam::{account_id}:role/AWSControlTower*",
                    f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole",
                    f"arn:aws:iam::{account_id}:role/infiquetra-*",
                    f"arn:aws:iam::{account_id}:role/Lambda*",
                    f"arn:aws:iam::{account_id}:role/aws-service-role/*",
                ],
            ),
            # IAM policy management for CDK stacks
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreatePolicy",
                    "iam:DeletePolicy",
                    "iam:GetPolicy",
                    "iam:GetPolicyVersion",
                    "iam:ListPolicyVersions",
                    "iam:CreatePolicyVersion",
                    "iam:DeletePolicyVersion",
                    "iam:SetDefaultPolicyVersion",
                    "iam:TagPolicy",
                    "iam:UntagPolicy",
                ],
                resources=[
                    f"arn:aws:iam::{account_id}:policy/cdk-*",
                    f"arn:aws:iam::{account_id}:policy/*-Organizations-*",
                    f"arn:aws:iam::{account_id}:policy/*-SSO-*",
                    f"arn:aws:iam::{account_id}:policy/infiquetra-*",
                    f"arn:aws:iam::{account_id}:policy/Lambda*",
                    f"arn:aws:iam::{account_id}:policy/AWSLambda*",
                ],
            ),
            # Read-only IAM permissions for discovery
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:ListRoles",
                    "iam:ListPolicies",
                    "iam:GetUser",
                    "iam:GetAccountSummary",
                ],
                resources=["*"],
            ),
            # S3 permissions - scoped to CDK asset buckets and organization buckets
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:GetBucketLocation",
                    "s3:GetBucketPolicy",
                    "s3:PutBucketPolicy",
                    "s3:DeleteBucketPolicy",
                    "s3:ListBucket",
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:PutBucketVersioning",
                    "s3:PutEncryptionConfiguration",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:PutBucketNotification",
                    "s3:PutBucketLogging",
                    "s3:PutBucketCORS",
                    "s3:PutBucketWebsite",
                    "s3:PutBucketTagging",
                    "s3:PutObjectAcl",
                    "s3:GetBucketAcl",
                    "s3:PutBucketAcl",
                    "s3:GetObjectVersion",
                    "s3:DeleteObjectVersion",
                    "s3:PutLifecycleConfiguration",
                    "s3:GetBucketVersioning",
                    "s3:GetBucketNotification",
                    "s3:GetBucketCORS",
                    "s3:GetBucketWebsite",
                    "s3:GetBucketTagging",
                ],
                resources=[
                    f"arn:aws:s3:::cdk-*-assets-{account_id}-{region}",
                    f"arn:aws:s3:::cdk-*-assets-{account_id}-{region}/*",
                    "arn:aws:s3:::infiquetra-*",
                    "arn:aws:s3:::infiquetra-*/*",
                ],
            ),
            # SSM permissions for CDK context - scoped to CDK parameters
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:PutParameter",
                    "ssm:DeleteParameter",
                ],
                resources=[
                    f"arn:aws:ssm:{region}:{account_id}:parameter/cdk-bootstrap/*",
                    f"arn:aws:ssm:{region}:{account_id}:parameter/infiquetra/*",
                ],
            ),
            # AWS Organizations permissions - read-only with specific write permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "organizations:DescribeOrganization",
                    "organizations:DescribeAccount",
                    "organizations:ListAccounts",
                    "organizations:ListRoots",
                    "organizations:ListOrganizationalUnitsForParent",
                    "organizations:ListChildren",
                    "organizations:DescribeOrganizationalUnit",
                    "organizations:ListPolicies",
                    "organizations:DescribePolicy",
                    "organizations:ListTargetsForPolicy",
                ],
                resources=["*"],
            ),
            # Organizations write permissions - for account and OU management
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "organizations:CreateAccount",
                    "organizations:CreateOrganizationalUnit",
                    "organizations:UpdateOrganizationalUnit",
                    "organizations:MoveAccount",
                    "organizations:TagResource",
                    "organizations:UntagResource",
                    "organizations:AttachPolicy",
                    "organizations:DetachPolicy",
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "aws:RequestedRegion": "us-east-1"  # Organizations is global but API calls must be in us-east-1
                    }
                },
            ),
            # AWS SSO read permissions - scoped to specific operations
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sso:ListInstances",
                    "sso:DescribeInstance",
                    "sso:ListPermissionSets",
                    "sso:DescribePermissionSet",
                    "sso:GetInlinePolicyForPermissionSet",
                    "sso:ListManagedPoliciesInPermissionSet",
                    "sso:ListAccountsForProvisionedPermissionSet",
                    "sso:ListPermissionSetProvisioningStatus",
                    "sso:DescribePermissionSetProvisioningStatus",
                ],
                resources=["*"],
            ),
            # SSO write permissions for permission set management
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sso:CreatePermissionSet",
                    "sso:UpdatePermissionSet",
                    "sso:DeletePermissionSet",
                    "sso:PutInlinePolicyInPermissionSet",
                    "sso:DeleteInlinePolicyFromPermissionSet",
                    "sso:AttachManagedPolicyToPermissionSet",
                    "sso:DetachManagedPolicyFromPermissionSet",
                    "sso:ProvisionPermissionSet",
                    "sso:CreateAccountAssignment",
                    "sso:DeleteAccountAssignment",
                    "sso:TagResource",
                    "sso:UntagResource",
                ],
                resources=["*"],
            ),
            # Identity Store read permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "identitystore:ListUsers",
                    "identitystore:DescribeUser",
                    "identitystore:ListGroups",
                    "identitystore:DescribeGroup",
                    "identitystore:ListGroupMemberships",
                    "identitystore:GetGroupMembershipId",
                    "identitystore:IsMemberInGroups",
                ],
                resources=["*"],
            ),
            # CloudTrail permissions - read-only for compliance
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudtrail:DescribeTrails",
                    "cloudtrail:GetTrailStatus",
                    "cloudtrail:LookupEvents",
                ],
                resources=["*"],
            ),
            # Additional services with minimal required permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:GenerateDataKey",
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "sts:GetCallerIdentity",
                ],
                resources=["*"],
            ),
        ]

        return iam.ManagedPolicy(
            self,
            "CDKDeploymentPolicy",
            managed_policy_name="infiquetra-aws-infra-gha-cdk-policy",
            description="CDK, Organizations, and SSO deployment permissions",
            document=iam.PolicyDocument(statements=policy_statements),
        )

    def _create_serverless_policy(self) -> iam.ManagedPolicy:
        """Create policy for core serverless services (Lambda, API Gateway, DynamoDB)."""
        policy_statements = [
            # Lambda permissions - comprehensive serverless deployment
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:*"],
                resources=["*"],
            ),
            # API Gateway permissions - for REST and HTTP APIs
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["apigateway:*", "apigatewayv2:*"],
                resources=["*"],
            ),
            # DynamoDB permissions - for NoSQL database operations
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:*"],
                resources=["*"],
            ),
        ]

        return iam.ManagedPolicy(
            self,
            "ServerlessPolicy",
            managed_policy_name="infiquetra-aws-infra-gha-serverless-policy",
            description="Core serverless services: Lambda, API Gateway, DynamoDB",
            document=iam.PolicyDocument(statements=policy_statements),
        )

    def _create_event_driven_policy(self) -> iam.ManagedPolicy:
        """Create policy for event-driven services (EventBridge, Step Functions, SNS, SQS)."""
        policy_statements = [
            # EventBridge permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:*"],
                resources=["*"],
            ),
            # Step Functions permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:*"],
                resources=["*"],
            ),
            # SNS/SQS permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:*", "sqs:*"],
                resources=["*"],
            ),
        ]

        return iam.ManagedPolicy(
            self,
            "EventDrivenPolicy",
            managed_policy_name="infiquetra-aws-infra-gha-event-driven-policy",
            description="Event-driven services: EventBridge, Step Functions, SNS, SQS",
            document=iam.PolicyDocument(statements=policy_statements),
        )

    def _create_edge_services_policy(self) -> iam.ManagedPolicy:
        """Create policy for edge services (CloudFront, WAF, Route53)."""
        policy_statements = [
            # CloudFront permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudfront:*"],
                resources=["*"],
            ),
            # WAF permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["wafv2:*"],
                resources=["*"],
            ),
            # Route53 permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["route53:*", "route53resolver:*"],
                resources=["*"],
            ),
        ]

        return iam.ManagedPolicy(
            self,
            "EdgeServicesPolicy",
            managed_policy_name="infiquetra-aws-infra-gha-edge-services-policy",
            description="Edge services: CloudFront, WAF, Route53",
            document=iam.PolicyDocument(statements=policy_statements),
        )

    def _create_data_analytics_policy(self) -> iam.ManagedPolicy:
        """Create policy for data analytics services (Athena, Glue, Kinesis)."""
        policy_statements = [
            # Athena permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["athena:*"],
                resources=["*"],
            ),
            # Glue permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["glue:*"],
                resources=["*"],
            ),
            # Kinesis permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["kinesis:*", "firehose:*", "kinesisanalytics:*"],
                resources=["*"],
            ),
        ]

        return iam.ManagedPolicy(
            self,
            "DataAnalyticsPolicy",
            managed_policy_name="infiquetra-aws-infra-gha-data-analytics-policy",
            description="Data analytics services: Athena, Glue, Kinesis",
            document=iam.PolicyDocument(statements=policy_statements),
        )

    def _create_security_policy(self) -> iam.ManagedPolicy:
        """Create policy for security services (Cognito, Secrets Manager, KMS, X-Ray)."""
        policy_statements = [
            # Cognito permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cognito-idp:*", "cognito-identity:*"],
                resources=["*"],
            ),
            # Secrets Manager permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:*"],
                resources=["*"],
            ),
            # KMS permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["kms:*"],
                resources=["*"],
            ),
            # X-Ray permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["xray:*"],
                resources=["*"],
            ),
        ]

        return iam.ManagedPolicy(
            self,
            "SecurityPolicy",
            managed_policy_name="infiquetra-aws-infra-gha-security-policy",
            description="Security services: Cognito, Secrets Manager, KMS, X-Ray",
            document=iam.PolicyDocument(statements=policy_statements),
        )

    def _create_infrastructure_policy(self) -> iam.ManagedPolicy:
        """Create policy for infrastructure services (EC2/VPC, ECR, AppSync, CloudWatch)."""
        policy_statements = [
            # EC2/VPC permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ec2:*"],
                resources=["*"],
            ),
            # ECR permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecr:*"],
                resources=["*"],
            ),
            # AppSync permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["appsync:*"],
                resources=["*"],
            ),
            # Enhanced CloudWatch permissions
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:*",
                    "cloudwatch:*",
                    "synthetics:*",
                    "applicationinsights:*",
                ],
                resources=["*"],
            ),
        ]

        return iam.ManagedPolicy(
            self,
            "InfrastructurePolicy",
            managed_policy_name="infiquetra-aws-infra-gha-infrastructure-policy",
            description="Infrastructure services: EC2/VPC, ECR, AppSync, CloudWatch",
            document=iam.PolicyDocument(statements=policy_statements),
        )

    def _validate_configuration(self) -> None:
        """Validate stack configuration parameters."""
        if not self.github_owner:
            raise ValueError("GitHub owner must be specified")

        if not self.repo_name:
            raise ValueError("Repository name must be specified")

        if "/" in self.github_owner:
            raise ValueError("GitHub owner cannot contain forward slashes")

        if "/" in self.repo_name:
            raise ValueError("Repository name cannot contain forward slashes")

        # Validate that we have a valid AWS environment
        if not self.account:
            raise ValueError(
                "AWS account ID must be specified in the stack environment"
            )

        if not self.region:
            raise ValueError("AWS region must be specified in the stack environment")

        # Log configuration for debugging (using annotations instead of add_info which doesn't exist)
        self.node.add_metadata("repository", self.repo_full_name)
        self.node.add_metadata("target_account", self.account)
        self.node.add_metadata("target_region", self.region)

    def _apply_resource_tags(self) -> None:
        """Apply comprehensive tagging strategy to all resources."""
        tags = {
            "Project": "Infiquetra Organizations",
            "Environment": "Bootstrap",
            "ManagedBy": "CDK",
            "Component": "GitHub OIDC",
            "Repository": self.repo_full_name,
            "Owner": self.github_owner,
            "Purpose": "CI/CD Authentication",
            "SecurityLevel": "High",
            "CostCenter": "Infrastructure",
            "CreatedBy": "GitHubOIDCStack",
        }

        for key, value in tags.items():
            cdk.Tags.of(self).add(key, value)
