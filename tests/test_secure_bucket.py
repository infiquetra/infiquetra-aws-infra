"""Tests for SecureBucket CDK construct."""

import aws_cdk as cdk
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def _synth_secure_bucket_template(bucket_name: str | None = None) -> Template:
    """Create and return a CDK template for SecureBucket testing."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
    return Template.from_stack(stack)


def test_secure_bucket_enables_s3_managed_encryption() -> None:
    """Verify S3 managed encryption is enabled."""
    template = _synth_secure_bucket_template()
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            }
        },
    )


def test_secure_bucket_enables_versioning() -> None:
    """Verify versioning is enabled."""
    template = _synth_secure_bucket_template()
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"VersioningConfiguration": {"Status": "Enabled"}},
    )


def test_secure_bucket_blocks_all_public_access() -> None:
    """Verify all public access is blocked."""
    template = _synth_secure_bucket_template()
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )


def test_secure_bucket_retains_bucket_on_delete() -> None:
    """Verify bucket has retain deletion policy."""
    template = _synth_secure_bucket_template()
    template.has_resource(
        "AWS::S3::Bucket",
        {"DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"},
    )


def test_secure_bucket_exposes_underlying_bucket() -> None:
    """Verify the underlying bucket is accessible via .bucket property."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    secure_bucket = SecureBucket(stack, "SecureBucket")
    assert secure_bucket.bucket is secure_bucket._bucket
