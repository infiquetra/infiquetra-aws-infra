#!/usr/bin/env python3
"""Tests for the resource_name naming utility."""

import pytest

from infiquetra_aws_infra.naming import resource_name


def test_resource_name_happy_path() -> None:
    """Happy-path test: simple lowercase and hyphen formatting."""
    result = resource_name("s3", "dev", "user-data")
    assert result == "s3-dev-user-data"


def test_resource_name_truncates_name_to_max_len() -> None:
    """Length limit triggers truncation of only the name component."""
    long_name = "a" * 100
    result = resource_name("lambda", "prod", long_name, max_len=30)
    # prefix = "lambda-prod-" (12 chars)
    # remaining = 30 - 12 = 18 chars for name
    assert result.startswith("lambda-prod-")
    assert len(result) == 30
    assert result == "lambda-prod-" + ("a" * 18)


def test_resource_name_truncates_name_exact_fit() -> None:
    """Exactly fits max_len."""
    # full "s3-dev-mybucket" length = 15
    result = resource_name("s3", "dev", "mybucket", max_len=15)
    assert result == "s3-dev-mybucket"
    assert len(result) == 15


def test_resource_name_rejects_empty_component() -> None:
    """Empty service, env, or name raises ValueError."""
    with pytest.raises(ValueError, match="must be non-empty"):
        resource_name("", "dev", "something")
    with pytest.raises(ValueError, match="must be non-empty"):
        resource_name("s3", "", "something")
    with pytest.raises(ValueError, match="must be non-empty"):
        resource_name("s3", "dev", "")


def test_resource_name_rejects_illegal_characters() -> None:
    """Invalid characters raise ValueError."""
    # uppercase letters are ok (they get lowercased), but punctuation is not
    with pytest.raises(ValueError, match="contains invalid characters"):
        resource_name("s3", "dev", "Bad Name!")
    with pytest.raises(ValueError, match="contains invalid characters"):
        resource_name("s3", "dev", "bucket@example")
    with pytest.raises(ValueError, match="contains invalid characters"):
        resource_name("s3", "de_v", "bucket")  # underscore invalid
    with pytest.raises(ValueError, match="contains invalid characters"):
        resource_name("s3!", "dev", "bucket")


def test_resource_name_normalizes_case() -> None:
    """Uppercase input is lowercased."""
    result = resource_name("S3", "DEV", "USER-DATA")
    assert result == "s3-dev-user-data"
    # uppercase letters are allowed in input because they become lowercase
    result2 = resource_name("Lambda", "Prod", "MyFunction")
    assert result2 == "lambda-prod-myfunction"


def test_resource_name_rejects_max_len_with_no_room_for_name() -> None:
    """max_len too small to fit prefix raises ValueError."""
    # prefix "s3-dev-" = 7 chars, max_len=6 -> error
    with pytest.raises(
        ValueError,
        match="max_len=6 is too small to fit prefix 's3-dev-'",
    ):
        resource_name("s3", "dev", "anything", max_len=6)

    # exactly equal length also raises because we need at least one char for name
    with pytest.raises(
        ValueError,
        match="max_len=7 is too small to fit prefix 's3-dev-'",
    ):
        resource_name("s3", "dev", "anything", max_len=7)


def test_resource_name_edge_cases() -> None:
    """Edge cases: single-character components, allowed characters."""
    result = resource_name("a", "b", "c")
    assert result == "a-b-c"

    result = resource_name("service", "env", "123-numbers")
    assert result == "service-env-123-numbers"

    # hyphen allowed in all positions
    result = resource_name("my-service", "dev-env", "resource-name")
    assert result == "my-service-dev-env-resource-name"

    # max_len truncates hyphenated name correctly
    result = resource_name("svc", "env", "a-b-c-d", max_len=10)
    # prefix = "svc-env-" (8 chars), remaining = 2 chars for name -> "a-"
    assert result == "svc-env-a-"
    assert len(result) == 10


def test_resource_name_default_max_len() -> None:
    """Default max_len=64 works."""
    name = "x" * 50
    result = resource_name("s", "e", name)
    # prefix "s-e-" = 4 chars, total length = 4 + 50 = 54 <= 64
    assert result == f"s-e-{name}"
    assert len(result) == 54
    # should not truncate