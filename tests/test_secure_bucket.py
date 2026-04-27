import pytest
from aws_cdk import App, Stack
from aws_cdk.assertions import Template
from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket

def _template_for(bucket_name: str | None = None) -> Template:
    app = App()
    stack = Stack(app, "TestStack")
    SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
    return Template.from_stack(stack)

def test_secure_bucket_applies_encryption_versioning_and_public_access_block():
    template = _template_for()
    
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketEncryption": {
            "ServerSideEncryptionConfiguration": [
                {
                    "ServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }
            ]
        },
        "VersioningConfiguration": {
            "Status": "Enabled"
        },
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True
        }
    })

def test_secure_bucket_uses_retain_removal_policy():
    template = _template_for()
    resources = template.to_json()["Resources"]
    
    # Find the S3 Bucket resource
    buckets = [res for res in resources.values() if res["Type"] == "AWS::S3::Bucket"]
    
    if len(buckets) != 1:
        pytest.fail(f"Expected exactly 1 S3 Bucket resource, found {len(buckets)}")
    
    bucket = buckets[0]
    assert bucket.get("DeletionPolicy") == "Retain"
    assert bucket.get("UpdateReplacePolicy") == "Retain"

def test_secure_bucket_uses_explicit_bucket_name_when_provided():
    bucket_name = "s3-secure-user-data"
    template = _template_for(bucket_name=bucket_name)
    
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketName": bucket_name
    })
