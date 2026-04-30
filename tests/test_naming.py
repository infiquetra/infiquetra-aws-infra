import pytest
from infiquetra_aws_infra.naming import resource_name

def test_resource_name_happy_path():
    assert resource_name("s3", "dev", "user-data") == "s3-dev-user-data"

def test_resource_name_truncates_name_to_max_len():
    # prefix "lambda-prod-" is 12 chars. max_len 30. name should be 18 chars.
    service = "lambda"
    env = "prod"
    long_name = "a" * 100
    max_len = 30
    result = resource_name(service, env, long_name, max_len=max_len)
    
    assert result.startswith(f"{service}-{env}-")
    assert len(result) == max_len
    # 30 - (6+1+4+1) = 30 - 12 = 18
    assert result == f"lambda-prod-{'a' * 18}"

def test_resource_name_rejects_empty_component():
    with pytest.raises(ValueError, match="Component name cannot be empty"):
        resource_name("s3", "dev", "")
    with pytest.raises(ValueError, match="Component service cannot be empty"):
        resource_name("", "dev", "user-data")
    with pytest.raises(ValueError, match="Component env cannot be empty"):
        resource_name("s3", "", "user-data")

def test_resource_name_rejects_illegal_chars():
    with pytest.raises(ValueError, match="Component name contains illegal characters"):
        resource_name("s3", "dev", "Bad Name!")
    with pytest.raises(ValueError, match="Component service contains illegal characters"):
        resource_name("S3!", "dev", "user-data")
    with pytest.raises(ValueError, match="Component env contains illegal characters"):
        resource_name("s3", "dev@", "user-data")

def test_resource_name_normalizes_case():
    assert resource_name("S3", "Dev", "User-Data") == "s3-dev-user-data"
    assert resource_name("s3", "DEV", "USER-DATA") == "s3-dev-user-data"

def test_resource_name_prefix_too_long():
    # prefix "verylongservice-verylongenv-" is 28 chars.
    # if max_len is 20, it should raise ValueError.
    with pytest.raises(ValueError, match="exceeds or equals max_len"):
        resource_name("verylongservice", "verylongenv", "name", max_len=20)
