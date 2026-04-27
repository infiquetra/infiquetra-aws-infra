"""SecureBucket CDK construct with encryption, versioning, and
public-access blocking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from constructs import Construct

if TYPE_CHECKING:
    pass

try:
    from infiquetra_aws_infra.naming import resource_name as _resource_name

    _NAMING_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    _NAMING_AVAILABLE = False


class SecureBucket(Construct):
    """S3 bucket with secure defaults: encryption, versioning,
    public-access blocking, and retain deletion policy."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        if bucket_name is not None and _NAMING_AVAILABLE:
            _resource_name("s3", "secure", bucket_name, max_len=73)

        self._bucket = s3.Bucket(
            self,
            "Bucket",
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> s3.Bucket:
        """The underlying S3 bucket resource."""
        return self._bucket
