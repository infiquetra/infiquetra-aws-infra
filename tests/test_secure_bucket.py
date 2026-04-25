import sys
from unittest.mock import MagicMock

from aws_cdk import App, Stack
from aws_cdk import aws_s3 as s3
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


def test_secure_bucket_defaults():
    """Test that SecureBucket creates a bucket with the correct defaults."""
    # GIVEN
    app = App()
    stack = Stack(app, "TestStack")

    # WHEN
    SecureBucket(stack, "SecureBucket")
    template = Template.from_stack(stack)

    # THEN
    # Should have exactly one S3 bucket
    template.resource_count_is("AWS::S3::Bucket", 1)

    # Should have S3-managed encryption
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketEncryption": {
            "ServerSideEncryptionConfiguration": [
                {
                    "ServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }
            ]
        }
    })

    # Should have versioning enabled
    template.has_resource_properties("AWS::S3::Bucket", {
        "VersioningConfiguration": {
            "Status": "Enabled"
        }
    })

    # Should block all public access
    template.has_resource_properties("AWS::S3::Bucket", {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True
        }
    })

    # Should have RETAIN deletion policy
    resources = template.find_resources("AWS::S3::Bucket")
    bucket_resource_keys = list(resources.keys())
    assert len(bucket_resource_keys) == 1
    bucket_resource = resources[bucket_resource_keys[0]]
    assert bucket_resource.get("DeletionPolicy") == "Retain"
    # UpdateReplacePolicy is typically also Retain when DeletionPolicy is Retain
    assert bucket_resource.get("UpdateReplacePolicy") == "Retain"


def test_secure_bucket_exposes_underlying_bucket():
    """Test that SecureBucket exposes the underlying Bucket instance."""
    # GIVEN
    app = App()
    stack = Stack(app, "TestStack")

    # WHEN
    secure_bucket = SecureBucket(stack, "SecureBucket")

    # THEN
    assert secure_bucket.bucket is not None
    assert isinstance(secure_bucket.bucket, s3.Bucket)


def test_secure_bucket_with_explicit_name():
    """Test that SecureBucket handles explicit bucket names correctly."""
    # GIVEN
    app = App()
    stack = Stack(app, "TestStack")

    # WHEN
    bucket_name = "my-test-bucket"
    SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
    template = Template.from_stack(stack)

    # THEN
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketName": bucket_name
    })


def test_secure_bucket_with_naming_helper():
    """Test that SecureBucket uses naming helper when available."""
    # GIVEN
    app = App()
    stack = Stack(app, "TestStack")

    # Mock the naming module and resource_name function
    mock_naming_module = MagicMock()
    mock_resource_name = MagicMock(return_value="processed-bucket-name")
    mock_naming_module.resource_name = mock_resource_name

    # Temporarily replace the naming module in sys.modules
    original_module = sys.modules.get('infiquetra_aws_infra.naming')
    sys.modules['infiquetra_aws_infra.naming'] = mock_naming_module

    try:
        # WHEN
        bucket_name = "original-bucket-name"
        SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
        template = Template.from_stack(stack)

        # THEN
        # Verify the resource_name function was called with the original bucket name
        mock_resource_name.assert_called_once_with(bucket_name)

        # Verify the processed name is used in the bucket properties
        template.has_resource_properties("AWS::S3::Bucket", {
            "BucketName": "processed-bucket-name"
        })
    finally:
        # Restore original module
        if original_module is not None:
            sys.modules['infiquetra_aws_infra.naming'] = original_module
        else:
            sys.modules.pop('infiquetra_aws_infra.naming', None)


def test_secure_bucket_without_naming_module():
    """Test that SecureBucket falls back to verbatim name when naming module is missing."""
    # GIVEN
    app = App()
    stack = Stack(app, "TestStack")

    # Save original module if it exists
    original_module = sys.modules.get('infiquetra_aws_infra.naming')

    # Remove the naming module if it exists
    if 'infiquetra_aws_infra.naming' in sys.modules:
        del sys.modules['infiquetra_aws_infra.naming']

    try:
        # WHEN
        bucket_name = "fallback-bucket-name"
        SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
        template = Template.from_stack(stack)

        # THEN
        template.has_resource_properties("AWS::S3::Bucket", {
            "BucketName": bucket_name
        })
    finally:
        # Restore original module
        if original_module is not None:
            sys.modules['infiquetra_aws_infra.naming'] = original_module


def test_secure_bucket_without_resource_name_attribute():
    """Test that SecureBucket falls back to verbatim name when resource_name is missing."""
    # GIVEN
    app = App()
    stack = Stack(app, "TestStack")

    # Mock the naming module without resource_name function
    mock_naming_module = MagicMock()
    if hasattr(mock_naming_module, 'resource_name'):
        delattr(mock_naming_module, 'resource_name')

    # Temporarily replace the naming module in sys.modules
    original_module = sys.modules.get('infiquetra_aws_infra.naming')
    sys.modules['infiquetra_aws_infra.naming'] = mock_naming_module

    try:
        # WHEN
        bucket_name = "fallback-bucket-name"
        SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
        template = Template.from_stack(stack)

        # THEN
        template.has_resource_properties("AWS::S3::Bucket", {
            "BucketName": bucket_name
        })
    finally:
        # Restore original module
        if original_module is not None:
            sys.modules['infiquetra_aws_infra.naming'] = original_module
        else:
            sys.modules.pop('infiquetra_aws_infra.naming', None)
