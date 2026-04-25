"""Tests for the naming module."""

import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path():
    """Test basic happy path with valid inputs."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_length():
    """Test that long names are truncated to fit max_len while preserving prefix."""
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    expected = "lambda-prod-" + "a" * 18  # 30 - 12 (prefix) = 18
    assert len(result) == 30
    assert result == expected
    assert result.startswith("lambda-prod-")


def test_resource_name_rejects_empty_component():
    """Test that empty service, env, or name components raise ValueError."""
    with pytest.raises(ValueError, match="service component cannot be empty"):
        resource_name("", "dev", "data")

    with pytest.raises(ValueError, match="env component cannot be empty"):
        resource_name("s3", "", "data")

    with pytest.raises(ValueError, match="name component cannot be empty"):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_characters():
    """Test that components with illegal characters raise ValueError."""
    with pytest.raises(ValueError, match="illegal characters"):
        resource_name("s3", "dev", "Bad Name!")

    with pytest.raises(ValueError, match="illegal characters"):
        resource_name("s3", "dev", "space here")

    with pytest.raises(ValueError, match="illegal characters"):
        resource_name("s3@", "dev", "name")

    with pytest.raises(ValueError, match="illegal characters"):
        resource_name("s3", "dev#", "name")


def test_resource_name_normalizes_case():
    """Test that uppercase inputs are lowercased in output."""
    result = resource_name("S3", "DEV", "USER-DATA")
    assert result == "s3-dev-user-data"

    result = resource_name("Lambda", "Prod", "MyFunction")
    assert result == "lambda-prod-myfunction"
