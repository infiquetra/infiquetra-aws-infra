#!/usr/bin/env python3

"""
Unit tests for the SecureBucket construct.

Tests encryption, versioning, block-public-access, and deletion policy
via synthesized CloudFormation template, plus direct construct API tests.
"""

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_s3 as s3
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


class TestSecureBucket:
    """Test cases for SecureBucket construct."""

    @pytest.fixture
    def app(self) -> App:
        """Create CDK App for testing."""
        return App()

    @pytest.fixture
    def stack(self, app: App) -> Stack:
        """Create a minimal test stack with SecureBucket."""
        stack = Stack(app, "TestSecureBucketStack")
        SecureBucket(stack, "SecureBucket")
        return stack

    @pytest.fixture
    def template(self, stack: Stack) -> Template:
        """Create CloudFormation template for testing."""
        return Template.from_stack(stack)

    def test_secure_bucket_exposes_wrapped_bucket(self, stack: Stack) -> None:
        """Test that .bucket property exposes the underlying S3 Bucket."""
        # Find the SecureBucket construct
        constructs = stack.node.children
        secure_bucket = None
        for c in constructs:
            if isinstance(c, SecureBucket):
                secure_bucket = c
                break

        assert secure_bucket is not None, "SecureBucket construct not found in stack"
        assert isinstance(secure_bucket.bucket, s3.Bucket), (
            ".bucket should return an s3.Bucket instance"
        )

    def test_secure_bucket_enables_s3_managed_encryption(
        self,
        template: Template,
    ) -> None:
        """Test that bucket is configured with S3-managed encryption."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}},
                    ],
                },
            },
        )

    def test_secure_bucket_enables_versioning(self, template: Template) -> None:
        """Test that versioning is enabled on the bucket."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {"VersioningConfiguration": {"Status": "Enabled"}},
        )

    def test_secure_bucket_blocks_all_public_access(self, template: Template) -> None:
        """Test that all four block-public-access flags are enabled."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    def test_secure_bucket_retains_bucket_on_delete(self, template: Template) -> None:
        """Test that bucket is retained on stack deletion."""
        resources = template.find_resources("AWS::S3::Bucket")
        bucket_resource = next(iter(resources.values()))

        # Check resource-level deletion policies
        assert bucket_resource.get("DeletionPolicy") == "Retain", (
            "DeletionPolicy should be Retain"
        )
        assert bucket_resource.get("UpdateReplacePolicy") == "Retain", (
            "UpdateReplacePolicy should be Retain"
        )

    def test_secure_bucket_uses_verbatim_bucket_name_when_naming_helper_unavailable(
        self,
        app: App,
    ) -> None:
        """Test verbatim bucket_name when naming helper is unavailable."""
        # Temporarily hide the naming module to simulate unavailability
        import sys
        original_modules = dict(sys.modules)
        sys.modules.pop("infiquetra_aws_infra.naming", None)

        try:
            stack = Stack(app, "TestVerbatimName")
            bucket_name = "my-secure-test-bucket"
            SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)

            template = Template.from_stack(stack)
            template.has_resource_properties(
                "AWS::S3::Bucket",
                {"BucketName": bucket_name},
            )
        finally:
            sys.modules.clear()
            sys.modules.update(original_modules)

    def test_secure_bucket_uses_validated_bucket_name_when_naming_resource_name_exists(
        self,
        app: App,
    ) -> None:
        """Test bucket name validation via monkeypatched naming.resource_name."""
        import sys
        from types import SimpleNamespace

        # Create a stub naming module with resource_name
        stub_naming = SimpleNamespace(resource_name=lambda name: f"valid-{name}")

        original_modules = dict(sys.modules)
        sys.modules["infiquetra_aws_infra"] = SimpleNamespace(naming=stub_naming)
        sys.modules["infiquetra_aws_infra.naming"] = stub_naming

        try:
            stack = Stack(app, "TestValidatedName")
            bucket_name = "test-bucket"
            SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)

            template = Template.from_stack(stack)
            template.has_resource_properties(
                "AWS::S3::Bucket",
                {"BucketName": "valid-test-bucket"},
            )
        finally:
            sys.modules.clear()
            sys.modules.update(original_modules)
