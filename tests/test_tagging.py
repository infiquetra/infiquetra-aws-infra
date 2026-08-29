"""Tests for tagging helpers."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_common_tags_accepts_valid_environments(env: str) -> None:
    """Valid environments produce a tag dict with correct values."""
    tags = common_tags(env, "platform", "auth")
    assert tags["Environment"] == env
    assert tags["Team"] == "platform"
    assert tags["Project"] == "auth"
    assert tags["ManagedBy"] == "CDK"


def test_common_tags_rejects_invalid_environment() -> None:
    """Non-dev/staging/prod env raises ValueError."""
    with pytest.raises(ValueError, match="Invalid env"):
        common_tags("test", "x", "y")


def test_common_tags_strips_whitespace_from_inputs() -> None:
    """Input strings are normalized via strip()."""
    tags = common_tags("dev  ", " platform ", "auth")
    assert tags["Environment"] == "dev"
    assert tags["Team"] == "platform"
    assert tags["Project"] == "auth"


def test_common_tags_returns_all_required_keys() -> None:
    """Returned dict has exactly Environment, Team, Project, ManagedBy."""
    tags = common_tags("prod", "sre", "platform")
    assert set(tags.keys()) == {"Environment", "Team", "Project", "ManagedBy"}
