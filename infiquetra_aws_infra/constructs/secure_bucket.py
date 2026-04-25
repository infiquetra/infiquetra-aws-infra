from aws_cdk import (
    RemovalPolicy,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct


class SecureBucket(Construct):
    def __init__(self, scope, construct_id, *, bucket_name: str | None = None):
        super().__init__(scope, construct_id)

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
        return self._bucket
