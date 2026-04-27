"""Tests for the naming module."""
import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path():
    """Test the happy path for resource_name."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len():
    """Test that resource_name truncates the name component when exceeding max_len."""
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert result.startswith("lambda-prod-")
    assert len(result) == 30
    assert result == "lambda-prod-" + "a" * 18  # 30 - 12 (prefix length) = 18


def test_resource_name_rejects_empty_component():
    """Test that resource_name raises ValueError for empty components."""
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "")

    with pytest.raises(ValueError):
        resource_name("", "dev", "user-data")

    with pytest.raises(ValueError):
        resource_name("s3", "", "user-data")


def test_resource_name_rejects_illegal_chars():
    """Test that resource_name raises ValueError for illegal characters."""
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "Bad Name!")


def test_resource_name_normalizes_case():
    """Test that resource_name normalizes uppercase input to lowercase output."""
    result = resource_name("S3", "Dev", "User-Data")
    assert result == "s3-dev-user-data"
