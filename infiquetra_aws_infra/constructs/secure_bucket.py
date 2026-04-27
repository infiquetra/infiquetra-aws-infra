"""SecureBucket CDK construct with safe S3 defaults."""

from aws_cdk import RemovalPolicy
from aws_cdk.aws_s3 import BlockPublicAccess, Bucket, BucketEncryption
from constructs import Construct


class SecureBucket(Construct):
    """S3 Bucket with encryption, versioning, public-access blocking, retain policy."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        validated_bucket_name = bucket_name

        # Optional validation via naming.resource_name if available
        try:
            from infiquetra_aws_infra.naming import resource_name

            if bucket_name is not None:
                resource_name("s3", "bucket", bucket_name, max_len=63)
        except ImportError:
            pass

        self._bucket = Bucket(
            self,
            "Bucket",
            bucket_name=validated_bucket_name,
            encryption=BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> Bucket:
        """Expose the underlying S3 Bucket resource."""
        return self._bucket
