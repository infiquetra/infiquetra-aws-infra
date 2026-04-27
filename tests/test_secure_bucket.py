#!/usr/bin/env python3

from aws_cdk import Stack
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def _template_for_secure_bucket(bucket_name: str | None = None) -> Template:
    """Helper to synth a SecureBucket and return its CloudFormation template."""
    from aws_cdk import App

    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
    return Template.from_stack(stack)


def test_secure_bucket_enables_s3_managed_encryption() -> None:
    """SecureBucket should default to SSE-S3 encryption."""
    template = _template_for_secure_bucket()

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
    """SecureBucket should have versioning enabled."""
    template = _template_for_secure_bucket()

    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"VersioningConfiguration": {"Status": "Enabled"}},
    )


def test_secure_bucket_blocks_public_access() -> None:
    """SecureBucket should block all public access."""
    template = _template_for_secure_bucket()

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
    """SecureBucket should have a DeletionPolicy of Retain."""
    template = _template_for_secure_bucket()
    resources = template.to_json()["Resources"]

    # Find the S3 bucket resource (should be exactly one)
    bucket_resources = [
        (logical_id, resource)
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::S3::Bucket"
    ]
    assert len(bucket_resources) == 1, (
        f"Expected exactly one S3 bucket, got {len(bucket_resources)}"
    )
    _logical_id, bucket_resource = bucket_resources[0]

    # Check the DeletionPolicy
    assert bucket_resource.get("DeletionPolicy") == "Retain", (
        f"Expected DeletionPolicy 'Retain', got {bucket_resource.get('DeletionPolicy')}"
    )


def test_secure_bucket_without_bucket_name_generates_name() -> None:
    """If bucket_name is None, CDK should generate a name."""
    template = _template_for_secure_bucket(bucket_name=None)
    # Should not have a BucketName property
    resources = template.to_json()["Resources"]
    bucket_resources = [
        (logical_id, resource)
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::S3::Bucket"
    ]
    assert len(bucket_resources) == 1
    _logical_id, bucket_resource = bucket_resources[0]
    # CDK-generated names are not present as BucketName property
    assert "BucketName" not in bucket_resource.get("Properties", {})


def test_secure_bucket_with_bucket_name_sets_name() -> None:
    """If bucket_name is provided, it should appear as BucketName."""
    template = _template_for_secure_bucket(bucket_name="my-test-bucket")
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"BucketName": "my-test-bucket"},
    )
