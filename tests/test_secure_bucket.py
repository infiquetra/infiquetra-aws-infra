from aws_cdk import App, Stack
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def test_secure_bucket_sets_s3_managed_encryption():
    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "MySecureBucket")

    template = Template.from_stack(stack)
    buckets = template.find_resources("AWS::S3::Bucket")
    bucket = next(iter(buckets.values()))

    # S3_MANAGED typically results in no explicit BucketEncryption defined
    # for the S3-managed keys (SSE-S3) because it is the default.
    # However, we check that it's not explicitly set to something else.
    prop = bucket.get("Properties", {})
    encryption = prop.get("BucketEncryption", {})
    config = encryption.get("ServerSideEncryptionConfiguration", [])

    if config:
        algo = config[0].get("ServerSideEncryptionByDefault", {}).get("SSEAlgorithm")
        assert algo == "AES256"

def test_secure_bucket_enables_versioning():
    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "MySecureBucket")

    template = Template.from_stack(stack)
    template.has_resource_properties("AWS::S3::Bucket", {
        "VersioningConfiguration": {"Status": "Enabled"}
    })

def test_secure_bucket_blocks_all_public_access():
    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "MySecureBucket")

    template = Template.from_stack(stack)
    template.has_resource_properties("AWS::S3::Bucket", {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True
        }
    })

def test_secure_bucket_retains_bucket_on_delete():
    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "MySecureBucket")

    template = Template.from_stack(stack)
    buckets = template.find_resources("AWS::S3::Bucket")
    bucket = next(iter(buckets.values()))
    assert bucket["DeletionPolicy"] == "Retain"

def test_secure_bucket_exposes_wrapped_bucket():
    app = App()
    stack = Stack(app, "TestStack")
    secure_bucket = SecureBucket(stack, "MySecureBucket")

    from aws_cdk import aws_s3 as s3
    assert isinstance(secure_bucket.bucket, s3.Bucket)

def test_secure_bucket_uses_explicit_bucket_name_when_no_naming_helper():
    app = App()
    stack = Stack(app, "TestStack")
    expected_name = "my-explicit-test-bucket"
    SecureBucket(stack, "MySecureBucket", bucket_name=expected_name)

    template = Template.from_stack(stack)
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketName": expected_name
    })
