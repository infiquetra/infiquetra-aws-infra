import pytest
from aws_cdk import App, Stack, assertions
from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket

@pytest.fixture
def template():
    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "SecureBucket")
    return assertions.Template.from_stack(stack)

def test_secure_bucket_uses_s3_managed_encryption(template):
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

def test_secure_bucket_enables_versioning(template):
    template.has_resource_properties("AWS::S3::Bucket", {
        "VersioningConfiguration": {
            "Status": "Enabled"
        }
    })

def test_secure_bucket_blocks_public_access(template):
    template.has_resource_properties("AWS::S3::Bucket", {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True
        }
    })

def test_secure_bucket_retains_bucket_on_delete(template):
    # DeletionPolicy and UpdateReplacePolicy are at the resource level, not in Properties
    template.has_resource("AWS::S3::Bucket", {
        "DeletionPolicy": "Retain",
        "UpdateReplacePolicy": "Retain"
    })
