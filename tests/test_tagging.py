"""Tests for the tagging module."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_common_tags_accepts_valid_environments(env: str) -> None:
    """Test that valid environments are accepted and produce expected output."""
    result = common_tags(env, "platform", "auth")
    assert result["Environment"] == env
    assert result["ManagedBy"] == "CDK"


def test_common_tags_rejects_invalid_environment() -> None:
    """Test that invalid environment raises ValueError."""
    with pytest.raises(ValueError, match="Invalid environment"):
        common_tags("test", "x", "y")


def test_common_tags_strips_whitespace_from_inputs() -> None:
    """Test that whitespace is normalized from all inputs."""
    result = common_tags("dev  ", " platform ", "auth")
    expected = {
        "Environment": "dev",
        "Team": "platform",
        "Project": "auth",
        "ManagedBy": "CDK",
    }
    assert result == expected


def test_common_tags_returns_all_required_keys() -> None:
    """Test that all required tag keys are present in the result."""
    result = common_tags("prod", "platform", "billing")
    assert set(result) == {"Environment", "Team", "Project", "ManagedBy"}
