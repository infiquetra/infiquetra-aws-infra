"""Tests for SecureBucket CDK construct."""

from aws_cdk import App, Stack
from aws_cdk.assertions import Template
from aws_cdk.aws_s3 import Bucket

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def _make_stack_and_template(
    bucket_name: str | None = None,
) -> tuple[Stack, Template]:
    """Create a minimal stack with SecureBucket and return (stack, template)."""
    app = App()
    stack = Stack(app, "TestStack")
    kwargs: dict = {}
    if bucket_name is not None:
        kwargs["bucket_name"] = bucket_name
    SecureBucket(stack, "TestBucket", **kwargs)
    return stack, Template.from_stack(stack)


def _find_bucket_resource(template: Template) -> dict:
    """Find the single AWS::S3::Bucket resource in the template."""
    buckets = template.find_resources("AWS::S3::Bucket")
    assert len(buckets) == 1, f"Expected 1 bucket, found {len(buckets)}"
    return next(iter(buckets.values()))


def test_secure_bucket_uses_s3_managed_encryption() -> None:
    """SecureBucket must use S3-managed server-side encryption."""
    _, template = _make_stack_and_template()
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            }
        },
    )


def test_secure_bucket_enables_versioning() -> None:
    """SecureBucket must have versioning enabled."""
    _, template = _make_stack_and_template()
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"VersioningConfiguration": {"Status": "Enabled"}},
    )


def test_secure_bucket_blocks_all_public_access() -> None:
    """SecureBucket must block all public access."""
    _, template = _make_stack_and_template()
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
    """SecureBucket must have DeletionPolicy=Retain on the bucket."""
    _, template = _make_stack_and_template()
    bucket_resource = _find_bucket_resource(template)
    assert bucket_resource.get("DeletionPolicy") == "Retain", (
        f"Expected DeletionPolicy=Retain, "
        f"got {bucket_resource.get('DeletionPolicy')}"
    )


def test_secure_bucket_exposes_wrapped_bucket() -> None:
    """SecureBucket.bucket must return the underlying Bucket instance."""
    app = App()
    stack = Stack(app, "TestStack")
    secure = SecureBucket(stack, "TestBucket")
    assert isinstance(secure.bucket, Bucket)


def test_secure_bucket_uses_verbatim_bucket_name_when_naming_helper_absent() -> None:
    """When no naming helper exists, bucket_name is passed verbatim."""
    _, template = _make_stack_and_template(bucket_name="my-exact-bucket-name")
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"BucketName": "my-exact-bucket-name"},
    )
