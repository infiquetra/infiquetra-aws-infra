"""Tests for infiquetra_aws_infra.naming."""

import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path() -> None:
    """Basic successful case."""
    assert resource_name("s3", "dev", "user-data") == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len() -> None:
    """When name exceeds max_len, truncate only the name component."""
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert result.startswith("lambda-prod-")
    assert len(result) == 30
    # "lambda-prod-" is 12 chars, so 18 'a's for a 30-char total
    assert result == "lambda-prod-aaaaaaaaaaaaaaaaaa"


def test_resource_name_rejects_empty_component() -> None:
    """Empty service, env, or name should raise ValueError."""
    # Empty service
    with pytest.raises(ValueError, match="service"):
        resource_name("", "dev", "user-data")
    
    # Empty env
    with pytest.raises(ValueError, match="env"):
        resource_name("s3", "", "user-data")
    
    # Empty name
    with pytest.raises(ValueError, match="name"):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_chars() -> None:
    """Invalid characters should raise ValueError."""
    # Space in name
    with pytest.raises(ValueError, match="name"):
        resource_name("s3", "dev", "Bad Name!")
    
    # Special char in env
    with pytest.raises(ValueError, match="env"):
        resource_name("s3", "prod!", "user-data")
    
    # Special char in service
    with pytest.raises(ValueError, match="service"):
        resource_name("s3!", "dev", "user-data")


def test_resource_name_normalizes_case() -> None:
    """Mixed/uppercase inputs should normalize to lowercase output."""
    assert resource_name("S3", "DEV", "UserData") == "s3-dev-userdata"


def test_resource_name_prefix_too_long() -> None:
    """When prefix length >= max_len, should raise ValueError."""
    # prefix "averyverylongservice-averyverylongenv-" is 38 chars > 30
    with pytest.raises(ValueError, match="prefix length"):
        resource_name("averyverylongservice", "averyverylongenv", "x", max_len=30)
