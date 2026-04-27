import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path():
    assert resource_name("s3", "dev", "user-data") == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len():
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert len(result) == 30
    assert result.startswith("lambda-prod-")
    assert result == "lambda-prod-" + "a" * (30 - len("lambda-prod-"))


def test_resource_name_rejects_empty_component():
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_chars():
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "Bad Name!")


def test_resource_name_normalizes_case():
    assert resource_name("S3", "DEV", "User-Data") == "s3-dev-user-data"
