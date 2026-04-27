"""Unit tests for SecureBucket CDK construct."""

import pytest
from aws_cdk import App, Stack
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


@pytest.fixture
def template() -> Template:
    """Create CloudFormation template from SecureBucket synth."""
    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "SecureBucket")
    return Template.from_stack(stack)


def test_secure_bucket_uses_s3_managed_encryption(template: Template) -> None:
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


def test_secure_bucket_enables_versioning(template: Template) -> None:
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"VersioningConfiguration": {"Status": "Enabled"}},
    )


def test_secure_bucket_blocks_public_access(template: Template) -> None:
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


def test_secure_bucket_retains_on_delete(template: Template) -> None:
    buckets = template.find_resources("AWS::S3::Bucket")
    assert len(buckets) == 1
    bucket = next(iter(buckets.values()))
    assert bucket.get("DeletionPolicy") == "Retain"
    assert bucket.get("UpdateReplacePolicy") == "Retain"


def test_secure_bucket_exposes_underlying_bucket() -> None:
    app = App()
    stack = Stack(app, "TestStack2")
    secure_bucket = SecureBucket(stack, "SecureBucket2")
    assert secure_bucket.bucket is secure_bucket._bucket
