from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SecureBucket(Construct):
    """
    A secure S3 bucket construct with sensible defaults.
    """

    def __init__(
        self, scope: Construct, construct_id: str, *, bucket_name: str | None = None
    ) -> None:
        super().__init__(scope, construct_id)

        resolved_name = bucket_name
        if bucket_name is not None:
            try:
                import infiquetra_aws_infra.naming as naming

                if hasattr(naming, "resource_name"):
                    helper = naming.resource_name
                    if callable(helper):
                        resolved_name = helper(bucket_name)
                        if not isinstance(resolved_name, str):
                            msg = (
                                f"resource_name returned non-string: "
                                f"{type(resolved_name)}"
                            )
                            raise TypeError(msg)
            except ImportError:
                # Helper module not available, fallback to verbatim
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
        """Returns the underlying S3 bucket resource."""
        return self._bucket
