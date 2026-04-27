"""Tests for common_tags helper."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


class TestCommonTagsValidEnvironments:
    """Test that valid environments are accepted."""

    @pytest.mark.parametrize("env", ["dev", "staging", "prod"])
    def test_accepts_valid_environments(self, env: str) -> None:
        """common_tags accepts dev, staging, and prod environments."""
        tags = common_tags(env, "platform", "auth")
        assert tags["Environment"] == env
        assert tags["ManagedBy"] == "CDK"


class TestCommonTagsInvalidEnvironment:
    """Test that invalid environments raise ValueError."""

    def test_rejects_invalid_environment(self) -> None:
        """common_tags raises ValueError for invalid environment."""
        with pytest.raises(ValueError, match="Invalid environment"):
            common_tags("test", "x", "y")


class TestCommonTagsWhitespaceNormalization:
    """Test whitespace normalization on inputs."""

    def test_normalizes_whitespace(self) -> None:
        """common_tags strips leading and trailing whitespace."""
        tags = common_tags("dev  ", " platform ", "auth")
        assert tags["Environment"] == "dev"
        assert tags["Team"] == "platform"
        assert tags["Project"] == "auth"


class TestCommonTagsRequiredKeys:
    """Test that all required keys are present."""

    def test_returns_all_required_keys(self) -> None:
        """common_tags returns all required keys."""
        tags = common_tags("dev", "platform", "auth")
        assert set(tags) == {"Environment", "Team", "Project", "ManagedBy"}
