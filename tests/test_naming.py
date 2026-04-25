import pytest
from infiquetra_aws_infra.naming import resource_name

def test_resource_name_happy_path():
    assert resource_name("s3", "dev", "user-data") == "s3-dev-user-data"

def test_resource_name_truncates_name_to_max_len():
    # prefix "lambda-prod-" is 12 chars. max_len 30. name should be 18 chars.
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert len(result) == 30
    assert result.startswith("lambda-prod-")
    assert result == "lambda-prod-" + "a" * 18

def test_resource_name_rejects_empty_component():
    with pytest.raises(ValueError, match="must be non-empty"):
        resource_name("", "dev", "user-data")
    with pytest.raises(ValueError, match="must be non-empty"):
        resource_name("s3", "", "user-data")
    with pytest.raises(ValueError, match="must be non-empty"):
        resource_name("s3", "dev", "")

def test_resource_name_rejects_illegal_chars():
    with pytest.raises(ValueError, match="only contain lowercase letters, numbers, and hyphens"):
        resource_name("s3", "dev", "Bad Name!")
    with pytest.raises(ValueError, match="only contain lowercase letters, numbers, and hyphens"):
        resource_name("S3_Service", "dev", "user-data")

def test_resource_name_normalizes_case():
    assert resource_name("S3", "DEV", "USER-DATA") == "s3-dev-user-data"
    assert resource_name("S3", "Dev", "uSeR-DaTa") == "s3-dev-user-data"

def test_resource_name_prefix_too_long():
    # prefix "longservice-production-" is 23 chars. max_len 20.
    with pytest.raises(ValueError, match="too short to accommodate the prefix"):
        resource_name("longservice", "production", "test", max_len=20)
    # prefix "s3-dev-" is 7 chars. max_len 7.
    with pytest.raises(ValueError, match="too short to accommodate the prefix"):
        resource_name("s3", "dev", "test", max_len=7)
