from aws_cdk import RemovalPolicy
from aws_cdk.aws_s3 import BlockPublicAccess, Bucket, BucketEncryption
from constructs import Construct


class SecureBucket(Construct):
    """A secure S3 bucket construct with sensible defaults."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None
    ):
        """
        Initialize a SecureBucket construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            bucket_name: Optional bucket name, validated via naming helper if available
        """
        super().__init__(scope, construct_id)

        # Process bucket name with optional naming helper
        processed_bucket_name = None
        if bucket_name is not None:
            try:
                # Try to import the naming helper
                from infiquetra_aws_infra.naming import resource_name
                processed_bucket_name = resource_name(bucket_name)
            except ImportError:
                # If the naming module doesn't exist or resource_name is not available,
                # use the bucket name verbatim
                processed_bucket_name = bucket_name
            except AttributeError:
                # If resource_name doesn't exist in the naming module, use verbatim
                processed_bucket_name = bucket_name

        # Create the underlying bucket with secure defaults
        self._bucket = Bucket(
            self,
            "Bucket",
            bucket_name=processed_bucket_name,
            encryption=BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN
        )

    @property
    def bucket(self) -> Bucket:
        """Returns the underlying S3 Bucket instance."""
        return self._bucket
