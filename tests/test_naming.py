import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path() -> None:
    assert resource_name("s3", "dev", "user-data") == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len() -> None:
    result = resource_name("lambda", "prod", "a" * 100, max_len=30)
    assert len(result) == 30
    assert result.startswith("lambda-prod-")
    assert result == "lambda-prod-" + "a" * (30 - len("lambda-prod-"))


@pytest.mark.parametrize(
    "service,env,name",
    [("", "dev", "x"), ("s3", "", "x"), ("s3", "dev", "")],
)
def test_resource_name_rejects_empty_component(
    service: str, env: str, name: str
) -> None:
    with pytest.raises(ValueError):
        resource_name(service, env, name)


def test_resource_name_rejects_illegal_chars() -> None:
    with pytest.raises(ValueError):
        resource_name("s3", "dev", "Bad Name!")


def test_resource_name_lowercases_components() -> None:
    assert resource_name("S3", "Dev", "User-Data") == "s3-dev-user-data"
