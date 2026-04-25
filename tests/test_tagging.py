#!/usr/bin/env python3
"""Tests for infiquetra_aws_infra.tagging.common_tags()."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


class TestCommonTags:
    """Tests for common_tags helper."""

    @pytest.mark.parametrize(
        "env",
        ["dev", "staging", "prod"],
    )
    def test_common_tags_valid_envs(self, env: str) -> None:
        """Test that valid environments are accepted."""
        result = common_tags(env, "platform", "auth")

        assert result["Environment"] == env
        assert result["Team"] == "platform"
        assert result["Project"] == "auth"
        assert result["ManagedBy"] == "CDK"

    def test_common_tags_invalid_env_raises_value_error(self) -> None:
        """Test that invalid environments raise ValueError."""
        with pytest.raises(ValueError, match=r"env must be one of.*got 'test'"):
            common_tags("test", "platform", "auth")

    def test_common_tags_normalizes_whitespace(self) -> None:
        """Test that whitespace is stripped from inputs."""
        result = common_tags("dev  ", " platform ", "auth  ")

        assert result["Environment"] == "dev"
        assert result["Team"] == "platform"
        assert result["Project"] == "auth"

    def test_common_tags_returns_all_required_keys(self) -> None:
        """Test that the returned dict contains all required keys."""
        result = common_tags("dev", "platform", "auth")

        assert set(result.keys()) == {"Environment", "Team", "Project", "ManagedBy"}
        assert result["ManagedBy"] == "CDK"
