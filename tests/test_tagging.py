import pytest

from infiquetra_aws_infra.tagging import common_tags


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_common_tags_accepts_valid_environments(env: str) -> None:
    result = common_tags(env, "platform", "auth")
    assert result["Environment"] == env
    assert result["ManagedBy"] == "CDK"


def test_common_tags_rejects_invalid_environment() -> None:
    with pytest.raises(ValueError, match="Invalid environment"):
        common_tags("test", "x", "y")


def test_common_tags_strips_whitespace() -> None:
    result = common_tags("dev  ", " platform ", "auth")
    assert result["Environment"] == "dev"
    assert result["Team"] == "platform"
    assert result["Project"] == "auth"


def test_common_tags_returns_all_required_keys() -> None:
    result = common_tags("prod", "platform", "auth")
    assert set(result) == {"Environment", "Team", "Project", "ManagedBy"}
