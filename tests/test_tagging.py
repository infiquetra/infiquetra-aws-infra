"""Tests for infiquetra_aws_infra.tagging."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


class TestCommonTags:
    """Test suite for common_tags function."""

    @pytest.mark.parametrize(
        "environment",
        ["dev", "staging", "prod"],
    )
    def test_common_tags_accepts_valid_environments(
        self,
        environment: str,
    ) -> None:
        """Test that valid environments are accepted."""
        result = common_tags(environment, "platform", "auth")

        assert result["Environment"] == environment
        assert result["ManagedBy"] == "CDK"

    def test_common_tags_rejects_invalid_environment(self) -> None:
        """Test that invalid environments raise ValueError."""
        with pytest.raises(ValueError):
            common_tags("test", "x", "y")

    def test_common_tags_strips_whitespace(self) -> None:
        """Test that whitespace is stripped from all inputs."""
        result = common_tags("dev  ", " platform ", "auth")

        assert result["Environment"] == "dev"
        assert result["Team"] == "platform"
        assert result["Project"] == "auth"

    def test_common_tags_returns_all_required_keys(self) -> None:
        """Test that all required keys are present in the result."""
        result = common_tags("dev", "platform", "auth")

        assert set(result.keys()) == {"Environment", "Team", "Project", "ManagedBy"}
