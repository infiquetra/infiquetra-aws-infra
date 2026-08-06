import aws_cdk as cdk
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def test_secure_bucket_sse_s3_encryption() -> None:
    """SecureBucket must use AES256 (SSE-S3) encryption by default."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    SecureBucket(stack, "TestBucket")
    template = Template.from_stack(stack)

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


def test_secure_bucket_versioning_enabled() -> None:
    """SecureBucket must have versioning enabled by default."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    SecureBucket(stack, "TestBucket")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"VersioningConfiguration": {"Status": "Enabled"}},
    )


def test_secure_bucket_blocks_all_public_access() -> None:
    """SecureBucket must block all public access."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    SecureBucket(stack, "TestBucket")
    template = Template.from_stack(stack)

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


def test_secure_bucket_retain_deletion_policy() -> None:
    """SecureBucket must use RETAIN for both deletion and update-replace policies."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    SecureBucket(stack, "TestBucket")
    template = Template.from_stack(stack)

    # DeletionPolicy / UpdateReplacePolicy are top-level CFN keys, not
    # inside Properties, so we match the full resource shape.
    template.has_resource(
        "AWS::S3::Bucket",
        {
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
        },
    )


def test_secure_bucket_creates_exactly_one_bucket() -> None:
    """SecureBucket creates exactly one S3 bucket (no extras)."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    SecureBucket(stack, "TestBucket")
    template = Template.from_stack(stack)

    template.resource_count_is("AWS::S3::Bucket", 1)


def test_secure_bucket_exposes_bucket_property() -> None:
    """Exposes the underlying Bucket via the ``.bucket`` property."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    sb = SecureBucket(stack, "TestBucket")

    assert sb.bucket is not None
    assert isinstance(sb.bucket, cdk.aws_s3.Bucket)


def test_secure_bucket_with_explicit_name() -> None:
    """When a bucket_name is provided it must not crash."""
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    SecureBucket(stack, "TestBucket", bucket_name="my-bucket")

    template = Template.from_stack(stack)
    # The construct should still synth to exactly one bucket
    template.resource_count_is("AWS::S3::Bucket", 1)
