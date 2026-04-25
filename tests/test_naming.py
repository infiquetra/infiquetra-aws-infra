"""Tests for infiquetra_aws_infra.naming."""

import pytest

from infiquetra_aws_infra.naming import resource_name


class TestResourceName:
    """Test resource_name function."""

    def test_happy_path(self) -> None:
        """Normal case with valid inputs returns lowercased hyphenated name."""
        result = resource_name("s3", "dev", "user-data")
        assert result == "s3-dev-user-data"

    def test_case_normalization(self) -> None:
        """Mixed-case components are lowercased."""
        result = resource_name("S3", "DEV", "USER-DATA")
        assert result == "s3-dev-user-data"

    def test_truncates_name_to_max_len(self) -> None:
        """When total length exceeds max_len, only the name component is truncated."""
        # Name component is 100 chars, prefix "lambda-prod-" is 12 chars,
        # total would be 112, max_len=30 → name truncated to 30-12 = 18 chars.
        long_name = "a" * 100
        result = resource_name("lambda", "prod", long_name, max_len=30)
        expected = "lambda-prod-" + ("a" * 18)
        assert result == expected
        assert len(result) == 30

    def test_truncates_name_to_exact_max_len(self) -> None:
        """When total length equals max_len, no truncation occurs."""
        # Prefix length = len("s3-dev-") = 7, name length = 57, total 64.
        name = "x" * 57
        result = resource_name("s3", "dev", name, max_len=64)
        assert result == "s3-dev-" + name
        assert len(result) == 64

    def test_rejects_empty_component(self) -> None:
        """Empty service, env, or name raises ValueError."""
        with pytest.raises(ValueError, match="service must be a non-empty string"):
            resource_name("", "dev", "user-data")
        with pytest.raises(ValueError, match="env must be a non-empty string"):
            resource_name("s3", "", "user-data")
        with pytest.raises(ValueError, match="name must be a non-empty string"):
            resource_name("s3", "dev", "")

    def test_rejects_empty_string_after_stripping(self) -> None:
        """A string containing only whitespace is considered empty."""
        with pytest.raises(ValueError, match="service must be a non-empty string"):
            resource_name("   ", "dev", "user-data")

    def test_rejects_illegal_chars(self) -> None:
        """Characters outside a-z, 0-9, hyphen raise ValueError."""
        # space
        with pytest.raises(ValueError, match="service contains invalid characters"):
            resource_name("s3 bucket", "dev", "user-data")
        with pytest.raises(ValueError, match="env contains invalid characters"):
            resource_name("s3", "dev prod", "user-data")
        with pytest.raises(ValueError, match="name contains invalid characters"):
            resource_name("s3", "dev", "user_data")

        # underscore
        with pytest.raises(ValueError):
            resource_name("s3", "dev", "user_data")

        # uppercase letters are allowed because they are lowercased first
        # (validation runs after lowercasing)
        result = resource_name("S3", "DEV", "User-Data")
        assert result == "s3-dev-user-data"

    def test_rejects_non_string_input(self) -> None:
        """Non-string components raise ValueError."""
        with pytest.raises(ValueError, match="service must be a non-empty string"):
            resource_name(None, "dev", "user-data")  # type: ignore
        with pytest.raises(ValueError, match="env must be a non-empty string"):
            resource_name("s3", 123, "user-data")  # type: ignore
        with pytest.raises(ValueError, match="name must be a non-empty string"):
            resource_name("s3", "dev", [])

    def test_rejects_invalid_max_len(self) -> None:
        """max_len must be a positive integer."""
        with pytest.raises(ValueError, match="max_len must be a positive integer"):
            resource_name("s3", "dev", "user-data", max_len=0)
        with pytest.raises(ValueError, match="max_len must be a positive integer"):
            resource_name("s3", "dev", "user-data", max_len=-5)

    def test_max_len_too_small_for_prefix_raises(self) -> None:
        """If max_len cannot fit prefix plus one char, raise ValueError."""
        # prefix "lambda-prod-" length = 12
        with pytest.raises(
            ValueError,
            match="max_len=10 is too small to accommodate prefix",
        ):
            resource_name("lambda", "prod", "x", max_len=10)

        # edge case: prefix exactly max_len fails (needs name char)
        with pytest.raises(
            ValueError,
            match="max_len=12 is too small to accommodate prefix",
        ):
            resource_name("lambda", "prod", "x", max_len=12)

    def test_no_truncation_when_within_limit(self) -> None:
        """When total length <= max_len, returns full normalized string."""
        result = resource_name("s3", "dev", "user-data", max_len=100)
        assert result == "s3-dev-user-data"

    def test_truncation_preserves_prefix(self) -> None:
        """Only the name component is truncated, prefix stays unchanged."""
        result = resource_name("lambda", "prod", "my-function-name", max_len=20)
        # prefix "lambda-prod-" length = 12, remaining 8 chars for name
        assert result.startswith("lambda-prod-")
        assert len(result) == 20
        assert result == "lambda-prod-my-funct"

    def test_truncation_edge_case_single_char_name(self) -> None:
        """If max_len allows only one char for name, that char is kept."""
        result = resource_name("s3", "dev", "abcdefg", max_len=len("s3-dev-") + 1)
        assert result == "s3-dev-a"
        assert len(result) == len("s3-dev-") + 1
