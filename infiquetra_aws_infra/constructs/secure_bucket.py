#!/usr/bin/env python3

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SecureBucket(Construct):
    """
    Secure S3 Bucket construct with encryption and versioning enabled.

    Wraps aws_cdk.aws_s3.Bucket with safe defaults:
    - S3-managed encryption (AES256)
    - Versioning enabled
    - All block public access flags enabled
    - Retains bucket on stack deletion or replacement
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Apply secure defaults to the underlying S3 bucket
        self._bucket = s3.Bucket(
            self,
            "Bucket",
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> s3.Bucket:
        """Return the underlying S3 Bucket instance."""
        return self._bucket
