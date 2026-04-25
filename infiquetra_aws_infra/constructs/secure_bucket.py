"""SecureBucket CDK construct with secure defaults."""

from aws_cdk import RemovalPolicy
from aws_cdk.aws_s3 import BlockPublicAccess, Bucket, BucketEncryption
from constructs import Construct


class SecureBucket(Construct):
    """S3 bucket wrapper with encryption, versioning, and public-access
    blocking.

    Encryption: S3-managed (AES-256 server-side).
    Versioning: enabled.
    Public access: fully blocked.
    Removal policy: retain on delete.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        # No naming helper exists in this repo; bucket_name
        # is passed verbatim to the underlying Bucket.
        bucket_kwargs: dict = {
            "encryption": BucketEncryption.S3_MANAGED,
            "versioned": True,
            "block_public_access": BlockPublicAccess.BLOCK_ALL,
            "removal_policy": RemovalPolicy.RETAIN,
        }
        if bucket_name is not None:
            bucket_kwargs["bucket_name"] = bucket_name

        self._bucket = Bucket(self, "Bucket", **bucket_kwargs)

    @property
    def bucket(self) -> Bucket:
        """The underlying aws_cdk.aws_s3.Bucket instance."""
        return self._bucket
