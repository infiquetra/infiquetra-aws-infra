import sys
from unittest.mock import MagicMock

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_s3 as s3
from aws_cdk.assertions import Template

from infiquetra_aws_infra.constructs.secure_bucket import SecureBucket


class TestSecureBucket:
    @pytest.fixture
    def app(self) -> App:
        return App()

    @pytest.fixture
    def stack(self, app: App) -> Stack:
        return Stack(app, "TestStack")

    def test_secure_bucket_sets_secure_defaults(self, stack: Stack) -> None:
        SecureBucket(stack, "SecureBucket")
        template = Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                    ]
                },
                "VersioningConfiguration": {"Status": "Enabled"},
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    def test_secure_bucket_sets_retain_policies(self, stack: Stack) -> None:
        SecureBucket(stack, "SecureBucket")
        template = Template.from_stack(stack)

        template.has_resource(
            "AWS::S3::Bucket",
            {
                "DeletionPolicy": "Retain",
                "UpdateReplacePolicy": "Retain",
            },
        )

    def test_secure_bucket_uses_bucket_name_verbatim_without_naming_helper(
        self, stack: Stack
    ) -> None:
        # Ensure naming helper is not in sys.modules for this test
        if "infiquetra_aws_infra.naming" in sys.modules:
            del sys.modules["infiquetra_aws_infra.naming"]

        bucket_name = "verbatim-bucket-name"
        SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
        template = Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::S3::Bucket",
            {"BucketName": bucket_name},
        )

    def test_secure_bucket_uses_naming_resource_name_when_available(
        self, stack: Stack
    ) -> None:
        # Mock the naming module
        mock_naming = MagicMock()
        mock_naming.resource_name = MagicMock(return_value="transformed-bucket-name")
        sys.modules["infiquetra_aws_infra.naming"] = mock_naming

        try:
            bucket_name = "original-bucket-name"
            SecureBucket(stack, "SecureBucket", bucket_name=bucket_name)
            template = Template.from_stack(stack)

            template.has_resource_properties(
                "AWS::S3::Bucket",
                {"BucketName": "transformed-bucket-name"},
            )
            mock_naming.resource_name.assert_called_once_with(bucket_name)
        finally:
            if "infiquetra_aws_infra.naming" in sys.modules:
                del sys.modules["infiquetra_aws_infra.naming"]

    def test_secure_bucket_exposes_wrapped_bucket(self, stack: Stack) -> None:
        sb = SecureBucket(stack, "SecureBucket")
        assert isinstance(sb.bucket, s3.Bucket)
        assert sb.bucket.node.id == "Bucket"
