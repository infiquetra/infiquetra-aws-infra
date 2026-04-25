"""Tests for infiquetra_aws_infra.tagging.common_tags."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


class TestCommonTags:
    """Tests for common_tags function."""

    @pytest.mark.parametrize(
        ("env", "team", "project"),
        [
            ("dev", "platform", "auth"),
            ("staging", "backend", "api"),
            ("prod", "frontend", "web"),
        ],
    )
    def test_common_tags_accepts_valid_environments(
        self, env: str, team: str, project: str
    ) -> None:
        """Valid environments (dev, staging, prod) should return correct tags."""
        result = common_tags(env, team, project)

        assert result["Environment"] == env
        assert result["Team"] == team
        assert result["Project"] == project
        assert result["ManagedBy"] == "CDK"

    def test_common_tags_rejects_invalid_environment(self) -> None:
        """Invalid env values should raise ValueError."""
        with pytest.raises(ValueError, match="env must be one of"):
            common_tags("test", "x", "y")

    def test_common_tags_normalizes_whitespace(self) -> None:
        """Inputs with trailing/leading whitespace should be normalized."""
        result = common_tags("dev  ", " platform ", "auth")

        assert result["Environment"] == "dev"
        assert result["Team"] == "platform"
        assert result["Project"] == "auth"

    def test_common_tags_returns_all_required_keys(self) -> None:
        """Returned dict must contain exactly the required keys."""
        result = common_tags("dev", "platform", "auth")

        assert set(result.keys()) == {"Environment", "Team", "Project", "ManagedBy"}
