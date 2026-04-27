import pytest
from infiquetra_aws_infra.tagging import common_tags

@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_common_tags_accepts_valid_environments(env):
    tags = common_tags(env, "platform", "auth")
    assert tags["Environment"] == env
    assert tags["Team"] == "platform"
    assert tags["Project"] == "auth"
    assert tags["ManagedBy"] == "CDK"

def test_common_tags_rejects_invalid_environment():
    with pytest.raises(ValueError, match="Invalid environment"):
        common_tags("test", "x", "y")

def test_common_tags_strips_whitespace_from_inputs():
    expected = {
        "Environment": "dev",
        "Team": "platform",
        "Project": "auth",
        "ManagedBy": "CDK",
    }
    assert common_tags("dev  ", " platform ", "auth") == expected

def test_common_tags_returns_all_required_keys():
    tags = common_tags("prod", "platform", "billing")
    assert set(tags.keys()) == {"Environment", "Team", "Project", "ManagedBy"}
