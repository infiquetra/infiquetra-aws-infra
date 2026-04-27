import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path():
    """Test the basic happy path case."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len():
    """Test that the name component is truncated when total length exceeds max_len."""
    # Create a long name that would make the full name exceed 30 characters
    long_name = "a" * 100
    result = resource_name("lambda", "prod", long_name, max_len=30)

    # Should be exactly 30 characters long
    assert len(result) == 30
    # Should preserve the prefix
    assert result.startswith("lambda-prod-")
    # Should have the truncated name portion
    expected_name_part = "a" * (30 - len("lambda-prod-"))
    assert result == f"lambda-prod-{expected_name_part}"


def test_resource_name_rejects_empty_component():
    """Test that empty components raise ValueError."""
    with pytest.raises(ValueError, match="service component cannot be empty"):
        resource_name("", "dev", "user-data")

    with pytest.raises(ValueError, match="env component cannot be empty"):
        resource_name("s3", "", "user-data")

    with pytest.raises(ValueError, match="name component cannot be empty"):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_chars():
    """Test that illegal characters raise ValueError."""
    with pytest.raises(ValueError, match="contains illegal characters"):
        resource_name("s3", "dev", "Bad Name!")

    with pytest.raises(ValueError, match="contains illegal characters"):
        resource_name("S3 Service!", "dev", "user-data")

    with pytest.raises(ValueError, match="contains illegal characters"):
        resource_name("s3", "dev_env", "user-data")


def test_resource_name_normalizes_case():
    """Test that uppercase characters are normalized to lowercase."""
    result = resource_name("S3", "Dev", "User-Data")
    assert result == "s3-dev-user-data"


def test_resource_name_prefix_exceeds_max_len():
    """Test the edge case where the prefix exceeds max_len."""
    with pytest.raises(ValueError, match="no room for name component"):
        # The prefix "very-long-service-name-development-" is 37 characters
        # Asking for max_len=30 means there's no room for any name
        resource_name(
            "very-long-service-name", "development", "anything", max_len=30
        )
