"""Tests for the resource_name helper."""

import pytest
from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path():
    """Test happy path resource name generation."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len():
    """Test that name component is truncated to fit max_len."""
    # Service: lambda (5), env: prod (4), prefix: lambda-prod- (12)
    # With max_len=30, we have 18 chars left for name
    long_name = "a" * 30  # This will be truncated to 18 chars
    result = resource_name("lambda", "prod", long_name, max_len=30)
    expected = "lambda-prod-" + "a" * 18
    assert result == expected
    assert len(result) == 30


def test_resource_name_rejects_empty_component():
    """Test that empty components raise ValueError."""
    with pytest.raises(ValueError, match="service component cannot be empty"):
        resource_name("", "dev", "test")
    
    with pytest.raises(ValueError, match="env component cannot be empty"):
        resource_name("s3", "", "test")
    
    with pytest.raises(ValueError, match="name component cannot be empty"):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_chars():
    """Test that illegal characters raise ValueError."""
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "Bad Name!")  # space and exclamation
    
    # Note: Uppercase letters are now normalized to lowercase, so they don't raise ValueError
    # Only truly illegal characters (like punctuation, spaces, etc.) raise ValueError
    
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "test@domain")  # @ symbol
    
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "test.name")  # dot symbol
        
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "test name")  # space


def test_resource_name_normalizes_case():
    """Test that input is normalized to lowercase."""
    result = resource_name("S3", "DEV", "User-Data")
    assert result == "s3-dev-user-data"