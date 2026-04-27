"""Secure S3 Bucket CDK construct with safe defaults."""

from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from constructs import Construct

# Attempt to import resource_name from naming module
try:
    from infiquetra_aws_infra.naming import resource_name
except ImportError:
    resource_name = None  # type: ignore


def _resolve_bucket_name(bucket_name: str | None) -> str | None:
    """Resolve bucket name, applying naming conventions if available.

    Args:
        bucket_name: Optional bucket name provided by caller.

    Returns:
        Resolved bucket name or None for CDK-generated name.

    Raises:
        ValueError: If resource_name raises ValueError for invalid input.
    """
    if bucket_name is None:
        return None

    if resource_name is not None:
        return resource_name("s3", "secure", bucket_name, max_len=63)

    return bucket_name


class SecureBucket(Construct):
    """CDK construct for a secure S3 bucket with safe defaults.

    Applies S3 managed encryption, versioning, public access blocking,
    and retention policies by default.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        """Initialize SecureBucket.

        Args:
            scope: CDK construct scope.
            construct_id: Unique construct identifier.
            bucket_name: Optional bucket name (validated via naming.resource_name
                if available, otherwise accepted verbatim).
        """
        super().__init__(scope, construct_id)

        resolved_bucket_name = _resolve_bucket_name(bucket_name)

        bucket_kwargs: dict = {
            "encryption": s3.BucketEncryption.S3_MANAGED,
            "versioned": True,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "removal_policy": RemovalPolicy.RETAIN,
        }

        if resolved_bucket_name is not None:
            bucket_kwargs["bucket_name"] = resolved_bucket_name

        self._bucket = s3.Bucket(self, "Bucket", **bucket_kwargs)

    @property
    def bucket(self) -> s3.Bucket:
        """Return the underlying S3 bucket."""
        return self._bucket
