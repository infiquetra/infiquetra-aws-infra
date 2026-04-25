import pytest  # type: ignore

from infiquetra_aws_infra.tagging import common_tags


def test_common_tags_returns_expected_values_for_valid_envs() -> None:
    for env in ["dev", "staging", "prod"]:
        tags = common_tags(env, "platform", "auth")
        assert tags["Environment"] == env
        assert tags["Team"] == "platform"
        assert tags["Project"] == "auth"
        assert tags["ManagedBy"] == "CDK"

def test_common_tags_raises_value_error_for_invalid_env() -> None:
    with pytest.raises(ValueError, match="Invalid environment 'test'"):
        common_tags("test", "x", "y")

def test_common_tags_strips_whitespace_from_inputs() -> None:
    tags = common_tags("dev  ", " platform ", "auth")
    assert tags["Environment"] == "dev"
    assert tags["Team"] == "platform"
    assert tags["Project"] == "auth"

def test_common_tags_includes_all_required_keys() -> None:
    tags = common_tags("prod", "infra", "networking")
    expected_keys = {"Environment", "Team", "Project", "ManagedBy"}
    assert set(tags.keys()) == expected_keys
    assert tags["ManagedBy"] == "CDK"
