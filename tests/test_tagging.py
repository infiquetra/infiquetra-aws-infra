"""Tests for infiquetra_aws_infra.tagging."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_common_tags_accepts_valid_environments(env: str) -> None:
    tags = common_tags(env, "platform", "auth")
    assert tags["Environment"] == env
    assert tags["ManagedBy"] == "CDK"


def test_common_tags_rejects_invalid_environment() -> None:
    with pytest.raises(ValueError, match="Invalid environment"):
        common_tags("test", "x", "y")


def test_common_tags_strips_input_whitespace() -> None:
    tags = common_tags("dev  ", " platform ", "auth")
    assert tags["Environment"] == "dev"
    assert tags["Team"] == "platform"
    assert tags["Project"] == "auth"


def test_common_tags_returns_all_expected_keys() -> None:
    tags = common_tags("dev", "platform", "auth")
    assert set(tags) == {"Environment", "Team", "Project", "ManagedBy"}
