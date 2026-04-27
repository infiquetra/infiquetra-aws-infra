"""Tests for SecureBucket CDK construct."""

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def _template_for_bucket(
    bucket_name: str | None = None,
) -> tuple[Template, SecureBucket]:
    app = App()
    stack = Stack(app, "TestStack")
    secure_bucket = SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
    template = Template.from_stack(stack)
    return template, secure_bucket


def test_secure_bucket_applies_secure_defaults() -> None:
    template, _ = _template_for_bucket()

    template.resource_count_is("AWS::S3::Bucket", 1)

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

    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
        },
    )

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

    template.has_resource(
        "AWS::S3::Bucket",
        Match.object_like(
            {
                "DeletionPolicy": "Retain",
                "UpdateReplacePolicy": "Retain",
            },
        ),
    )


def test_secure_bucket_exposes_bucket_and_accepts_bucket_name() -> None:
    template, secure_bucket = _template_for_bucket(bucket_name="my-secure-bucket")

    assert secure_bucket.bucket is not None

    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"BucketName": "my-secure-bucket"},
    )
