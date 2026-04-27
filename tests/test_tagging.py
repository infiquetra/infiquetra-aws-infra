"""Tests for the tagging module."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


def test_common_tags_accepts_valid_environments():
    """Test that common_tags accepts valid environments."""
    for env in ["dev", "staging", "prod"]:
        result = common_tags(env, "platform", "auth")
        assert result["Environment"] == env
        assert result["Team"] == "platform"
        assert result["Project"] == "auth"
        assert result["ManagedBy"] == "CDK"


def test_common_tags_rejects_invalid_environment():
    """Test that common_tags raises ValueError for invalid environments."""
    with pytest.raises(ValueError, match="Invalid environment"):
        common_tags("test", "x", "y")


def test_common_tags_strips_input_whitespace():
    """Test that common_tags strips whitespace from inputs."""
    result = common_tags("dev  ", " platform ", "auth")
    assert result["Environment"] == "dev"
    assert result["Team"] == "platform"
    assert result["Project"] == "auth"
    assert result["ManagedBy"] == "CDK"


def test_common_tags_includes_required_keys():
    """Test that common_tags includes all required keys."""
    result = common_tags("dev", "platform", "auth")
    assert set(result.keys()) == {"Environment", "Team", "Project", "ManagedBy"}