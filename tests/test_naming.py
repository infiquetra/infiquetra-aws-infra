"""Tests for the resource_name function."""

import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path() -> None:
    """Test the basic happy path with valid inputs."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len() -> None:
    """Test that name is truncated when total length exceeds max_len."""
    service = "lambda"
    env = "prod"
    long_name = "a" * 100
    max_len = 30

    result = resource_name(service, env, long_name, max_len=max_len)

    # Verify length is exactly max_len
    assert len(result) == max_len

    # Verify prefix is preserved
    expected_prefix = f"{service}-{env}-"
    assert result.startswith(expected_prefix)


def test_resource_name_rejects_empty_component() -> None:
    """Test that empty components raise ValueError."""
    with pytest.raises(ValueError, match="service cannot be empty"):
        resource_name("", "dev", "name")

    with pytest.raises(ValueError, match="env cannot be empty"):
        resource_name("svc", "", "name")

    with pytest.raises(ValueError, match="name cannot be empty"):
        resource_name("svc", "dev", "")


def test_resource_name_rejects_illegal_chars() -> None:
    """Test that illegal characters raise ValueError."""
    # Uppercase letters (will be normalized to lowercase, but these are OK)
    # Only the actual bad chars: space, punctuation, underscore, etc.
    with pytest.raises(ValueError, match="contains illegal characters"):
        resource_name("s3", "dev", "Bad Name!")

    with pytest.raises(ValueError, match="contains illegal characters"):
        resource_name("s3", "dev", "name_with_underscore")

    with pytest.raises(ValueError, match="contains illegal characters"):
        resource_name("s3", "dev", "name.with.dots")

    with pytest.raises(ValueError, match="contains illegal characters"):
        resource_name("s3", "dev", "name@special")


def test_resource_name_normalizes_case() -> None:
    """Test that inputs are normalized to lowercase."""
    result = resource_name("S3", "PROD", "User-Data")
    assert result == "s3-prod-user-data"
