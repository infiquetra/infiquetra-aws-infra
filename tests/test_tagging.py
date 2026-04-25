import pytest
from infiquetra_aws_infra.tagging import common_tags

def test_common_tags_valid_environments():
    for env in ["dev", "staging", "prod"]:
        result = common_tags(env, "platform", "auth")
        assert result == {
            "Environment": env,
            "Team": "platform",
            "Project": "auth",
            "ManagedBy": "CDK",
        }

def test_common_tags_invalid_environment_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        common_tags("test", "x", "y")
    assert "Invalid environment 'test'" in str(excinfo.value)

def test_common_tags_whitespace_normalization():
    result = common_tags("dev  ", " platform ", " auth ")
    assert result == {
        "Environment": "dev",
        "Team": "platform",
        "Project": "auth",
        "ManagedBy": "CDK",
    }

def test_common_tags_all_keys_present():
    result = common_tags("dev", "team", "proj")
    assert set(result.keys()) == {"Environment", "Team", "Project", "ManagedBy"}
    assert result["ManagedBy"] == "CDK"
