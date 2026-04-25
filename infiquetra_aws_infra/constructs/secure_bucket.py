from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SecureBucket(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None
    ) -> None:
        super().__init__(scope, construct_id)

        resolved_name = bucket_name
        try:
            import naming
            if hasattr(naming, "resource_name") and callable(naming.resource_name):
                # Helper must return valid data, else fail
                resolved_name = (
                    naming.resource_name(bucket_name) if bucket_name else None
                )
                if bucket_name and not resolved_name:
                    raise ValueError(
                        "naming.resource_name returned empty result"
                    )
            elif hasattr(naming, "resource_name"):
                # Helper exists but isn't callable -> Broken helper case
                raise TypeError("naming.resource_name is present but not callable")
        except ImportError:
            # Helper absent -> use verbatim
            pass

        self._bucket = s3.Bucket(
            self,
            "Bucket",
            bucket_name=resolved_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> s3.Bucket:
        """The underlying S3 Bucket instance."""
        return self._bucket
