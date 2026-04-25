#!/usr/bin/env python3

"""
Secure S3 bucket construct with safe defaults.

This module provides a CDK construct that wraps aws_cdk.aws_s3.Bucket
with security-focused defaults: S3-managed encryption, versioning,
block all public access, and retention on deletion.
"""

from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_s3 as s3
from constructs import Construct


class SecureBucket(Construct):
    """
    A secure S3 bucket construct with safe defaults.

    Provides:
    - Server-side encryption with S3-managed keys (S3_MANAGED)
    - Object versioning enabled
    - Block all public access enabled
    - Bucket retained on stack deletion
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the SecureBucket construct.

        Args:
            scope: The parent construct.
            construct_id: The construct ID.
            bucket_name: Optional bucket name. If None, CDK generates a name.
            **kwargs: Additional construct options.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Attempt to import the repo-local naming helper
        resolved_bucket_name = bucket_name

        try:
            import importlib

            naming_module = importlib.import_module("infiquetra_aws_infra.naming")

            if (
                hasattr(naming_module, "resource_name")
                and callable(naming_module.resource_name)
                and bucket_name is not None
            ):
                resolved_bucket_name = naming_module.resource_name(bucket_name)
        except ModuleNotFoundError:
            # Module doesn't exist - pass bucket_name verbatim
            pass
        except ImportError:
            # Package exists but module doesn't - pass bucket_name verbatim
            pass
        except Exception as exc:
            # Import failed for other reasons - fail loudly
            raise RuntimeError(
                f"Failed to import infiquetra_aws_infra.naming: {exc}"
            ) from exc

        # Create the secure bucket with safe defaults
        self._bucket = s3.Bucket(
            self,
            "SecureBucket",
            bucket_name=resolved_bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

    @property
    def bucket(self) -> s3.Bucket:
        """
        Expose the underlying S3 Bucket instance.

        Returns:
            The wrapped s3.Bucket instance.
        """
        return self._bucket
