from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def _template_for_bucket(
    bucket_name: str | None = None,
) -> tuple[Template, SecureBucket]:
    """Helper to create a SecureBucket and return its synth template + construct."""
    app = App()
    stack = Stack(app, "TestStack")
    bucket_construct = SecureBucket(
        stack, "SecureBucket", bucket_name=bucket_name
    )
    return Template.from_stack(stack), bucket_construct


def test_secure_bucket_applies_secure_defaults() -> None:
    """Verify the synthesized bucket has all secure defaults applied."""
    template, _ = _template_for_bucket()

    # Exactly one S3 bucket resource
    template.resource_count_is("AWS::S3::Bucket", 1)

    # S3-managed encryption (AES-256)
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

    # Versioning enabled
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"VersioningConfiguration": {"Status": "Enabled"}},
    )

    # Block public access — all four booleans set to True
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

    # Retain deletion policy and update-replace policy
    template.has_resource(
        "AWS::S3::Bucket",
        Match.object_like(
            {
                "DeletionPolicy": "Retain",
                "UpdateReplacePolicy": "Retain",
            }
        ),
    )


def test_secure_bucket_exposes_bucket_and_accepts_bucket_name() -> None:
    """Verify the .bucket property and optional bucket_name pass-through."""
    template, secure_bucket = _template_for_bucket(
        bucket_name="my-secure-bucket"
    )

    # The construct exposes a non-None bucket property
    assert secure_bucket.bucket is not None

    # The custom bucket name is passed through to the synthesized BucketName
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {"BucketName": "my-secure-bucket"},
    )
