#!/usr/bin/env python3


from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SecureBucket(Construct):
    """
    A CDK Construct that wraps an S3 Bucket with secure defaults.

    Defaults:
    - Server-side encryption with Amazon S3-managed keys (SSE-S3)
    - Versioning enabled
    - Block all public access
    - Removal policy set to RETAIN (bucket will not be deleted on stack deletion)

    Optionally accepts a bucket name; if provided, the bucket name will be
    validated via the `naming.resource_name` function if available, otherwise
    passed verbatim. If bucket_name is None, CDK will generate a unique name.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
    ) -> None:
        """
        Initialize the SecureBucket construct.

        :param scope: The parent Construct.
        :param construct_id: The identifier for this SecureBucket instance.
        :param bucket_name: Optional bucket name. If None, CDK will generate a unique
          name.
        """
        super().__init__(scope, construct_id)

        bucket_kwargs = {
            "encryption": s3.BucketEncryption.S3_MANAGED,
            "versioned": True,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "removal_policy": RemovalPolicy.RETAIN,
        }

        if bucket_name is not None:
            # If naming.resource_name exists, apply it; otherwise use bucket_name as-is.
            # If validation fails, the exception will propagate.
            try:
                from infiquetra_aws_infra.naming import resource_name
                resolved_name = resource_name(bucket_name)
            except ImportError:
                # naming module not found, use raw bucket_name
                resolved_name = bucket_name

            bucket_kwargs["bucket_name"] = resolved_name

        self._bucket = s3.Bucket(self, "Bucket", **bucket_kwargs)

    @property
    def bucket(self) -> s3.Bucket:
        """
        Property exposing the underlying CDK Bucket instance.

        :return: The wrapped s3.Bucket instance.
        """
        return self._bucket
