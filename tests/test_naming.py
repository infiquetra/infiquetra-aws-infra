import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path() -> None:
    assert resource_name("s3", "dev", "user-data") == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len() -> None:
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert len(result) == 30
    assert result.startswith("lambda-prod-")
    # prefix length = len("lambda-prod-") = 12, available = 30-12 = 18
    assert result == "lambda-prod-" + "a" * 18


def test_resource_name_rejects_empty_component() -> None:
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "")
    with pytest.raises(ValueError):
        resource_name("", "dev", "user-data")
    with pytest.raises(ValueError):
        resource_name("s3", "", "user-data")


def test_resource_name_rejects_illegal_chars() -> None:
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "Bad Name!")
    # additional illegal char examples
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "bad_name!")
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "bad@name")


def test_resource_name_normalizes_case() -> None:
    assert resource_name("S3", "Dev", "User-Data") == "s3-dev-user-data"
    # additional case normalization test
    assert resource_name("LAMBDA", "PROD", "API-GATEWAY") == "lambda-prod-api-gateway"
