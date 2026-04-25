import pytest
from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path():
    """Test happy path case."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_component_to_max_len():
    """Test that long names are truncated to fit max_len."""
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    expected_prefix = "lambda-prod-"
    assert result.startswith(expected_prefix)
    assert len(result) == 30


def test_resource_name_rejects_empty_component():
    """Test that empty components raise ValueError."""
    with pytest.raises(ValueError, match="name component cannot be empty"):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_characters():
    """Test that illegal characters raise ValueError."""
    with pytest.raises(ValueError, match="name component contains illegal characters"):
        resource_name("s3", "dev", "Bad Name!")


def test_resource_name_normalizes_case_to_lowercase():
    """Test that uppercase inputs are normalized to lowercase."""
    result = resource_name("S3", "DEV", "USER-DATA")
    assert result == "s3-dev-user-data"


def test_resource_name_rejects_empty_service():
    """Test that empty service component raises ValueError."""
    with pytest.raises(ValueError, match="service component cannot be empty"):
        resource_name("", "dev", "user-data")


def test_resource_name_rejects_empty_env():
    """Test that empty env component raises ValueError."""
    with pytest.raises(ValueError, match="env component cannot be empty"):
        resource_name("s3", "", "user-data")


def test_resource_name_prefix_exceeds_max_len():
    """Test that prefix exceeding max_len raises ValueError."""
    with pytest.raises(ValueError, match="Prefix .* exceeds max_len"):
        resource_name("very-long-service-name", "very-long-env-name", "short", max_len=10)