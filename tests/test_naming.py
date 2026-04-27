"""Tests for resource naming utilities."""

import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path():
    """Happy path: valid components produce expected name."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_component_to_max_len():
    """Name truncation: only name component is truncated when too long."""
    # prefix = "lambda-prod-" (12 chars), name = "a" * 18 (to fit 30 total)
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert result.startswith("lambda-prod-")
    assert len(result) == 30
    assert result == "lambda-prod-" + "a" * 18


def test_resource_name_rejects_empty_components():
    """Empty component rejection: ValueError for any empty component."""
    with pytest.raises(ValueError, match="name cannot be empty"):
        resource_name("s3", "dev", "")

    with pytest.raises(ValueError, match="service cannot be empty"):
        resource_name("", "dev", "user-data")

    with pytest.raises(ValueError, match="env cannot be empty"):
        resource_name("s3", "", "user-data")


def test_resource_name_rejects_illegal_chars():
    """Illegal char rejection: ValueError for invalid characters."""
    with pytest.raises(ValueError, match="name contains illegal characters"):
        resource_name("s3", "dev", "Bad Name!")

    with pytest.raises(ValueError, match="service contains illegal characters"):
        resource_name("my service", "dev", "user-data")


def test_resource_name_normalizes_case():
    """Case normalization: uppercase letters are normalized to lowercase."""
    result = resource_name("S3", "Dev", "User-Data")
    assert result == "s3-dev-user-data"
