"""Tests for standardized resource tagging."""

import pytest

from infiquetra_aws_infra.tagging import VALID_ENVIRONMENTS, common_tags


def test_common_tags_accepts_valid_environments():
    """common_tags should accept dev, staging, prod environments."""
    # Using parametrization per requirement
    for env in VALID_ENVIRONMENTS:
        tags = common_tags(env, "platform", "auth")
        assert tags["Environment"] == env
        assert tags["ManagedBy"] == "CDK"


def test_common_tags_rejects_invalid_environment():
    """common_tags should raise ValueError for unsupported environment."""
    with pytest.raises(ValueError) as exc_info:
        common_tags("test", "x", "y")
    error_msg = str(exc_info.value)
    assert "test" in error_msg
    assert "dev" in error_msg or "staging" in error_msg or "prod" in error_msg


def test_common_tags_strips_whitespace_from_inputs():
    """common_tags should strip leading/trailing whitespace from all inputs."""
    tags = common_tags("dev  ", " platform ", "auth")
    assert tags["Environment"] == "dev"
    assert tags["Team"] == "platform"
    assert tags["Project"] == "auth"
    assert tags["ManagedBy"] == "CDK"


def test_common_tags_returns_all_required_keys():
    """common_tags must return exactly Environment, Team, Project, ManagedBy."""
    tags = common_tags("dev", "platform", "auth")
    assert set(tags) == {"Environment", "Team", "Project", "ManagedBy"}
    assert tags == {
        "Environment": "dev",
        "Team": "platform",
        "Project": "auth",
        "ManagedBy": "CDK",
    }
