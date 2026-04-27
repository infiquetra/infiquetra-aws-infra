from aws_cdk import RemovalPolicy
from aws_cdk.aws_s3 import BlockPublicAccess, Bucket, BucketEncryption
from constructs import Construct


class SecureBucket(Construct):
    """
    CDK construct that wraps an S3 Bucket with secure defaults.
    """

    def __init__(
        self, scope: Construct, construct_id: str, *, bucket_name: str | None = None
    ) -> None:
        super().__init__(scope, construct_id)

        # Optional validation via naming.resource_name if available
        if bucket_name is not None:
            try:
                from infiquetra_aws_infra.naming import resource_name

                # Validation probe: ensure the bucket name is valid for 's3' service
                # If it raises ValueError or returns non-string/empty, it fails
                validated_name = resource_name("s3", "secure", bucket_name, max_len=63)
                if not validated_name or not isinstance(validated_name, str):
                    raise ValueError(f"Invalid bucket name provided: {bucket_name}")
            except ImportError:
                # If naming.resource_name is unavailable, accept verbatim
                pass
            except ValueError as e:
                # Re-raise validation errors to fail the constructor
                raise e

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
        """Exposes the underlying S3 Bucket."""
        return self._bucket
