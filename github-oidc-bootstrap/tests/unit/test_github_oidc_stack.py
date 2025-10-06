"""
Unit tests for GitHub OIDC Stack.

Tests the CDK stack creation, IAM policies, and OIDC provider configuration.
"""

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from github_oidc_bootstrap.github_oidc_stack import GitHubOIDCStack


class TestGitHubOIDCStack:
    """Test cases for GitHubOIDCStack."""

    @pytest.fixture
    def app(self) -> App:
        """Create CDK App for testing."""
        return App()

    @pytest.fixture
    def stack(self, app: App) -> GitHubOIDCStack:
        """Create GitHubOIDCStack for testing."""
        return GitHubOIDCStack(
            app,
            "TestGitHubOIDCStack",
            env=Environment(account="123456789012", region="us-east-1"),
        )

    @pytest.fixture
    def template(self, stack: GitHubOIDCStack) -> Template:
        """Create CloudFormation template for testing."""
        return Template.from_stack(stack)

    def test_stack_creation(self, stack: GitHubOIDCStack) -> None:
        """Test that the stack can be created without errors."""
        assert stack is not None
        assert stack.stack_name == "TestGitHubOIDCStack"

    def test_oidc_provider_creation(self, template: Template) -> None:
        """Test that OIDC provider is created with correct configuration."""
        # CDK creates OIDC providers as custom resources
        template.has_resource_properties(
            "Custom::AWSCDKOpenIdConnectProvider",
            {
                "Url": "https://token.actions.githubusercontent.com",
                "ClientIDList": ["sts.amazonaws.com"],
                "ThumbprintList": [
                    "6938fd4d98bab03faadb97b34396831e3780aea1",
                    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
                ],
            },
        )

    def test_iam_role_creation(self, template: Template) -> None:
        """Test that IAM role is created with appropriate configuration."""
        template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "RoleName": "infiquetra-aws-infra-gha-role",
                "Description": "Role for GitHub Actions to deploy CDK stacks from infiquetra-aws-infra",
                "MaxSessionDuration": 43200,  # 12 hours in seconds
            },
        )

    def test_iam_role_trust_policy(self, template: Template) -> None:
        """Test that IAM role has correct trust policy."""
        # Get the GitHub Actions role (not the custom resource provider role)
        roles = template.find_resources("AWS::IAM::Role")
        github_role = None
        for _role_name, role_resource in roles.items():
            role_name_prop = role_resource["Properties"].get("RoleName")
            if role_name_prop == "infiquetra-aws-infra-gha-role":
                github_role = role_resource
                break

        assert github_role is not None, "infiquetra-aws-infra-gha-role not found"
        assume_role_policy = github_role["Properties"]["AssumeRolePolicyDocument"]

        # Verify the trust policy structure
        assert assume_role_policy["Version"] == "2012-10-17"
        assert len(assume_role_policy["Statement"]) == 1

        statement = assume_role_policy["Statement"][0]
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"

        # Verify conditions
        conditions = statement["Condition"]
        assert "StringEquals" in conditions
        assert "StringLike" in conditions

        # Check specific conditions
        string_equals = conditions["StringEquals"]
        assert (
            string_equals["token.actions.githubusercontent.com:aud"]
            == "sts.amazonaws.com"
        )
        assert (
            string_equals["token.actions.githubusercontent.com:repository"]
            == "infiquetra/infiquetra-aws-infra"
        )

        string_like = conditions["StringLike"]
        expected_subs = [
            "repo:infiquetra/infiquetra-aws-infra:ref:refs/heads/main",
            "repo:infiquetra/infiquetra-aws-infra:ref:refs/heads/develop",
            "repo:infiquetra/infiquetra-aws-infra:pull_request:refs/heads/main",
        ]
        assert string_like["token.actions.githubusercontent.com:sub"] == expected_subs

        expected_actors = ["infiquetra/*", "github-actions[bot]"]
        assert (
            string_like["token.actions.githubusercontent.com:actor"] == expected_actors
        )

    def test_iam_policy_creation(self, template: Template) -> None:
        """Test that IAM policy is created and attached to role."""
        template.resource_count_is("AWS::IAM::Policy", 1)

        # Verify policy is attached to the role
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyName": "infiquetra-aws-infra-gha-deployment-policy",
            },
        )

    def test_iam_policy_permissions_scope(self, template: Template) -> None:
        """Test that IAM policy has appropriately scoped permissions."""
        policies = template.find_resources("AWS::IAM::Policy")
        policy_resource = next(iter(policies.values()))
        policy_document = policy_resource["Properties"]["PolicyDocument"]

        statements = policy_document["Statement"]

        # Verify CloudFormation permissions are scoped
        cf_statements = [
            s
            for s in statements
            if any(
                action.startswith("cloudformation:") for action in s.get("Action", [])
            )
        ]
        assert len(cf_statements) >= 1

        # Check that some statements have resource restrictions
        scoped_statements = [s for s in statements if s.get("Resource") != ["*"]]
        assert len(scoped_statements) > 0, (
            "Some IAM statements should have scoped resources"
        )

    def test_cloudformation_outputs(self, template: Template) -> None:
        """Test that required CloudFormation outputs are created."""
        template.has_output("GitHubActionsRoleArn", {})
        template.has_output("GitHubOIDCProviderArn", {})

    def test_resource_naming_conventions(self, template: Template) -> None:
        """Test that resources follow naming conventions."""
        # Check that role name follows convention
        template.has_resource_properties(
            "AWS::IAM::Role",
            {"RoleName": "infiquetra-aws-infra-gha-role"},
        )

        # Check that policy name follows convention
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {"PolicyName": "infiquetra-aws-infra-gha-deployment-policy"},
        )

    def test_no_overly_permissive_policies(self, template: Template) -> None:
        """Test that no policies grant wildcard permissions to sensitive actions."""
        policies = template.find_resources("AWS::IAM::Policy")
        policy_resource = next(iter(policies.values()))
        policy_document = policy_resource["Properties"]["PolicyDocument"]

        statements = policy_document["Statement"]

        # Check for dangerous wildcard combinations
        for statement in statements:
            actions = statement.get("Action", [])
            resources = statement.get("Resource", [])

            # If resource is wildcard, actions should not include dangerous wildcards
            if resources == ["*"]:
                dangerous_wildcards = [
                    "iam:*",
                    "s3:*",
                    "cloudformation:*",
                    "organizations:*",
                    "sso:*",
                    "sso-admin:*",
                    "identitystore:*",
                    "cloudtrail:*",
                ]
                for action in actions:
                    assert action not in dangerous_wildcards, (
                        f"Found dangerous wildcard action: {action}"
                    )

    def test_session_duration_limit(self, template: Template) -> None:
        """Test that IAM role has appropriate session duration limit."""
        template.has_resource_properties(
            "AWS::IAM::Role",
            {"MaxSessionDuration": 43200},  # 12 hours maximum
        )

    def test_minimal_required_permissions(self, template: Template) -> None:
        """Test that policy includes minimal required permissions for CDK."""
        policies = template.find_resources("AWS::IAM::Policy")
        policy_resource = next(iter(policies.values()))
        policy_document = policy_resource["Properties"]["PolicyDocument"]

        statements = policy_document["Statement"]
        all_actions = []
        for statement in statements:
            all_actions.extend(statement.get("Action", []))

        # Verify essential CDK permissions are present
        essential_actions = [
            "sts:GetCallerIdentity",
            "cloudformation:DescribeStacks",
            "s3:GetObject",
            "s3:PutObject",
        ]

        for action in essential_actions:
            assert action in all_actions, f"Missing essential action: {action}"
