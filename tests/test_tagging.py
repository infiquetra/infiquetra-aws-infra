"""Tests for infiquetra_aws_infra.tagging.common_tags."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


def test_common_tags_accepts_valid_environments() -> None:
    """Exercise all three allowed env values: dev, staging, prod."""
    for env in ("dev", "staging", "prod"):
        tags = common_tags(env, "platform", "auth")
        assert tags["Environment"] == env
        assert tags["Team"] == "platform"
        assert tags["Project"] == "auth"
        assert tags["ManagedBy"] == "CDK"


def test_common_tags_rejects_invalid_environment() -> None:
    """Pass an invalid environment and expect ValueError."""
    with pytest.raises(ValueError, match="Invalid environment"):
        common_tags("test", "x", "y")


def test_common_tags_strips_whitespace_from_inputs() -> None:
    """Leading and trailing whitespace is normalized on all inputs."""
    tags = common_tags("dev  ", "  platform ", "auth")
    assert tags["Environment"] == "dev"
    assert tags["Team"] == "platform"
    assert tags["Project"] == "auth"


def test_common_tags_returns_all_required_keys() -> None:
    """The returned dict has exactly the expected keys and values."""
    tags = common_tags("dev", "platform", "auth")
    assert set(tags) == {"Environment", "Team", "Project", "ManagedBy"}
    assert tags == {
        "Environment": "dev",
        "Team": "platform",
        "Project": "auth",
        "ManagedBy": "CDK",
    }
