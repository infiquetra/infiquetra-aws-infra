from __future__ import annotations

from aws_cdk import RemovalPolicy
from aws_cdk.aws_s3 import BlockPublicAccess, Bucket, BucketEncryption
from constructs import Construct


class SecureBucket(Construct):
    """A CDK Construct that wraps an S3 Bucket with secure defaults.

    Defaults:
        encryption: S3_MANAGED (AES-256)
        versioned: True
        block_public_access: BLOCK_ALL
        removal_policy: RETAIN
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        if bucket_name is not None:
            _validate_bucket_name(bucket_name)

        self._bucket = Bucket(
            self,
            "Bucket",
            bucket_name=bucket_name,
            encryption=BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> Bucket:
        """The underlying S3 Bucket."""
        return self._bucket


def _validate_bucket_name(bucket_name: str) -> None:
    """Validate a bucket name using the project's naming helper if available.

    If the helper cannot be imported the name is accepted verbatim.
    If the helper is imported and raises ValueError the exception
    propagates.
    """
    try:
        from infiquetra_aws_infra.naming import resource_name

        resource_name("s3", "secure", bucket_name, max_len=73)
    except ImportError:
        pass
    except ModuleNotFoundError:
        pass
