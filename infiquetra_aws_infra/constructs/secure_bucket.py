from __future__ import annotations

from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SecureBucket(Construct):
    """An S3 bucket with secure defaults: SSE-S3 encryption, versioning,
    public access blocking, and RETAIN deletion policy.

    Optionally accepts a *bucket_name*; if the project provides a
    ``infiquetra_aws_infra.naming.resource_name()`` helper it will be
    called automatically.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        final_bucket_name = bucket_name
        if bucket_name is not None:
            try:
                from infiquetra_aws_infra import naming  # type: ignore[attr-defined]
            except ImportError:
                naming = None

            if naming is not None and hasattr(naming, "resource_name") and callable(
                naming.resource_name
            ):
                final_bucket_name = naming.resource_name(bucket_name)

        self._bucket = s3.Bucket(
            self,
            "Bucket",
            bucket_name=final_bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> s3.Bucket:
        """The underlying S3 Bucket resource."""
        return self._bucket
