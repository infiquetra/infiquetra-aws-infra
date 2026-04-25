#!/usr/bin/env python3
"""
Unit tests for SecureBucket construct.

Tests encryption, versioning, block public access, and deletion policy.
"""

import aws_cdk as cdk
import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket, s3


class TestSecureBucket:
    """Test cases for SecureBucket construct."""

    @pytest.fixture
    def app(self) -> App:
        """Create CDK App for testing."""
        return App()

    @pytest.fixture
    def stack(self, app: App) -> cdk.Stack:
        """Create a test stack with SecureBucket."""
        return cdk.Stack(
            app,
            "TestSecureBucketStack",
            env=Environment(account="123456789012", region="us-east-1"),
        )

    @pytest.fixture
    def template(self, stack: cdk.Stack) -> Template:
        """Create CloudFormation template for testing."""
        SecureBucket(stack, "TestSecureBucket", bucket_name=None)
        return Template.from_stack(stack)

    def test_secure_bucket_applies_secure_defaults(self, template: Template) -> None:
        """Test that the bucket has secure defaults.

        Verifies encryption, versioning, and block public access settings.
        """
        # Check encryption: S3-managed encryptionAES256)
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                    ]
                },
                "VersioningConfiguration": {"Status": "Enabled"},
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    def test_secure_bucket_retains_bucket_on_delete_or_replace(
        self, template: Template
    ) -> None:
        """Test that the bucket is retained on deletion or replacement."""
        # Get the bucket resource
        buckets = template.find_resources("AWS::S3::Bucket")
        assert len(buckets) >= 1, "No S3 bucket found in template"

        # Check DeletionPolicy and UpdateReplacePolicy
        for _bucket_name, bucket_resource in buckets.items():
            deletion_policy = bucket_resource.get("DeletionPolicy")
            update_replace_policy = bucket_resource.get("UpdateReplacePolicy")

            # Verify both policies are set to Retain
            assert deletion_policy == "Retain", (
                f"DeletionPolicy should be Retain, got {deletion_policy}"
            )
            assert update_replace_policy == "Retain", (
                f"UpdateReplacePolicy should be Retain, got {update_replace_policy}"
            )

    def test_secure_bucket_exposes_underlying_bucket(self, app: App) -> None:
        """Test that the .bucket property exposes the underlying Bucket instance."""
        # Create stack and construct
        test_stack = cdk.Stack(app, "TestExposeBucket")
        construct = SecureBucket(test_stack, "TestExposeBucketConstruct")

        # Verify .bucket returns the underlying S3 Bucket
        assert construct.bucket is not None
        assert isinstance(construct.bucket, s3.Bucket)

    def test_secure_bucket_uses_explicit_bucket_name_verbatim(
        self, app: App
    ) -> None:
        """Test that an explicit bucket name is passed through verbatim."""
        test_stack = cdk.Stack(
            app,
            "TestExplicitBucketNameStack",
            env=Environment(account="123456789012", region="us-east-1"),
        )
        explicit_name = "my-secure-bucket-12345"
        SecureBucket(test_stack, "TestExplicitBucketName", bucket_name=explicit_name)

        # Synthesize and verify bucket name in template
        template = Template.from_stack(test_stack)
        buckets = template.find_resources("AWS::S3::Bucket")
        assert len(buckets) >= 1, "No S3 bucket found in template"

        for _bucket_name, bucket_resource in buckets.items():
            props = bucket_resource.get("Properties", {})
            assert props.get("BucketName") == explicit_name, (
                f"BucketName should be {explicit_name}, got {props.get('BucketName')}"
            )
