"""Secure S3 bucket construct with safe defaults."""

from aws_cdk import RemovalPolicy
from aws_cdk.aws_s3 import BlockPublicAccess, Bucket, BucketEncryption
from constructs import Construct


def _resolve_bucket_name(bucket_name: str | None) -> str | None:
    """Normalize bucket name via naming.resource_name if available."""
    if bucket_name is None:
        return None
    try:
        from infiquetra_aws_infra import naming
    except ModuleNotFoundError:
        return bucket_name
    if hasattr(naming, "resource_name") and callable(naming.resource_name):
        return naming.resource_name(bucket_name)
    return bucket_name


class SecureBucket(Construct):
    """CDK construct wrapping S3 Bucket with secure defaults."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        self._bucket = Bucket(
            self,
            "Bucket",
            bucket_name=_resolve_bucket_name(bucket_name),
            encryption=BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> Bucket:
        """Return the underlying S3 Bucket resource."""
        return self._bucket
