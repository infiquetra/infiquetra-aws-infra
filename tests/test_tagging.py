"""Tests for tagging utilities."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_common_tags_valid_environments(env: str) -> None:
    """Test that valid environments return correct tags."""
    result = common_tags(env, "platform", "auth")
    assert result["Environment"] == env
    assert result["Team"] == "platform"
    assert result["Project"] == "auth"
    assert result["ManagedBy"] == "CDK"


def test_common_tags_raises_for_invalid_env() -> None:
    """Test that invalid environment raises ValueError."""
    with pytest.raises(ValueError):
        common_tags("test", "x", "y")


def test_common_tags_normalizes_whitespace() -> None:
    """Test that inputs are normalized by stripping whitespace."""
    result = common_tags("dev  ", " platform ", "auth")
    assert result["Environment"] == "dev"
    assert result["Team"] == "platform"
    assert result["Project"] == "auth"


def test_common_tags_returns_all_required_keys() -> None:
    """Test that result contains all required keys."""
    result = common_tags("dev", "platform", "auth")
    expected_keys = {"Environment", "Team", "Project", "ManagedBy"}
    assert set(result.keys()) == expected_keys
