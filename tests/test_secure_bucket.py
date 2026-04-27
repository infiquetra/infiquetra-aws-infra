"""Tests for SecureBucket CDK construct."""

import aws_cdk as cdk
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def test_secure_bucket_synthesizes_safe_bucket_defaults() -> None:
    """SecureBucket synthesizes with encryption, versioning, access block, retain."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    secure_bucket = SecureBucket(stack, "SecureBucket")

    assert secure_bucket.bucket is not None

    template = Template.from_stack(stack)

    # Verify encryption (S3_MANAGED -> AES256 in CloudFormation)
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256",
                        },
                    },
                ],
            },
        },
    )

    # Verify versioning enabled
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {
                "Status": "Enabled",
            },
        },
    )

    # Verify block public access
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

    # Verify retain-on-delete policy
    template.has_resource(
        "AWS::S3::Bucket",
        {
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
        },
    )
