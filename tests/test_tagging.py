"""Tests for the common_tags helper function."""

import pytest

from infiquetra_aws_infra.tagging import common_tags


class TestCommonTags:
    """Test cases for common_tags."""

    @pytest.mark.parametrize(
        ("env", "team", "project", "expected"),
        [
            (
                "dev",
                "platform",
                "auth",
                {
                    "Environment": "dev",
                    "Team": "platform",
                    "Project": "auth",
                    "ManagedBy": "CDK",
                },
            ),
            (
                "staging",
                "platform",
                "auth",
                {
                    "Environment": "staging",
                    "Team": "platform",
                    "Project": "auth",
                    "ManagedBy": "CDK",
                },
            ),
            (
                "prod",
                "platform",
                "auth",
                {
                    "Environment": "prod",
                    "Team": "platform",
                    "Project": "auth",
                    "ManagedBy": "CDK",
                },
            ),
        ],
    )
    def test_valid_envs(
        self,
        env: str,
        team: str,
        project: str,
        expected: dict[str, str],
    ) -> None:
        """Test that valid environments return the correct tag dictionary."""
        result = common_tags(env, team, project)
        assert result == expected

    def test_invalid_env_raises_valueerror(self) -> None:
        """Test that an invalid environment raises ValueError."""
        with pytest.raises(ValueError):
            common_tags("test", "x", "y")

    def test_whitespace_normalization(self) -> None:
        """Test that whitespace is stripped from all inputs."""
        result = common_tags("dev  ", " platform ", "auth")
        assert result == {
            "Environment": "dev",
            "Team": "platform",
            "Project": "auth",
            "ManagedBy": "CDK",
        }

    def test_all_required_keys_present(self) -> None:
        """Test that all required keys are present in the returned dict."""
        result = common_tags("dev", "platform", "auth")

        # Check all required keys are present
        required_keys = {"Environment", "Team", "Project", "ManagedBy"}
        assert set(result.keys()) == required_keys

        # Check specific values
        assert result["Environment"] == "dev"
        assert result["Team"] == "platform"
        assert result["Project"] == "auth"
        assert result["ManagedBy"] == "CDK"
