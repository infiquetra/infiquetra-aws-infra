"""Tests for resource naming utilities."""

import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path() -> None:
    """Test basic happy path with valid inputs."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len() -> None:
    """Test that long names are truncated while preserving prefix."""
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert len(result) == 30
    assert result.startswith("lambda-prod-")
    # Prefix is 12 chars (lambda-prod-), so name gets 18 chars
    assert result == "lambda-prod-" + "a" * 18


def test_resource_name_rejects_empty_component() -> None:
    """Test that empty components raise ValueError."""
    with pytest.raises(ValueError, match="name component cannot be empty"):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_characters() -> None:
    """Test that illegal characters raise ValueError."""
    with pytest.raises(ValueError, match="name contains illegal characters"):
        resource_name("s3", "dev", "Bad Name!")


def test_resource_name_normalizes_case() -> None:
    """Test that mixed-case input is lowercased in output."""
    result = resource_name("S3", "DEV", "User-Data")
    assert result == "s3-dev-user-data"
