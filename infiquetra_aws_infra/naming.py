"""Naming utilities for AWS resources."""

import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Build a consistent AWS resource name.

    Format: "{service}-{env}-{name}" lowercased.

    Args:
        service: The service name (e.g., "s3", "lambda").
        env: The environment (e.g., "dev", "prod").
        name: The resource name component.
        max_len: Maximum length for the resulting name (default: 64).

    Returns:
        The formatted resource name.

    Raises:
        ValueError: If any component is empty or contains illegal characters.

    """
    # Step 1: Lowercase and validate all components
    normalized_service = service.lower()
    normalized_env = env.lower()
    normalized_name = name.lower()

    # Step 2: Validate non-empty
    if not normalized_service:
        raise ValueError(f"service component cannot be empty: {service!r}")
    if not normalized_env:
        raise ValueError(f"env component cannot be empty: {env!r}")
    if not normalized_name:
        raise ValueError(f"name component cannot be empty: {name!r}")

    # Step 3: Validate allowed characters (a-z, 0-9, -)
    allowed_pattern = re.compile(r"^[a-z0-9-]+$")

    if not allowed_pattern.match(normalized_service):
        raise ValueError(
            f"service component contains illegal characters: {service!r} "
            f"(only a-z, 0-9, - allowed)"
        )
    if not allowed_pattern.match(normalized_env):
        raise ValueError(
            f"env component contains illegal characters: {env!r} "
            f"(only a-z, 0-9, - allowed)"
        )
    if not allowed_pattern.match(normalized_name):
        raise ValueError(
            f"name component contains illegal characters: {name!r} "
            f"(only a-z, 0-9, - allowed)"
        )

    # Step 4: Build prefix and check length
    prefix = f"{normalized_service}-{normalized_env}-"
    remaining_budget = max_len - len(prefix)

    if remaining_budget < 1:
        raise ValueError(
            f"max_len ({max_len}) too small to accommodate prefix "
            f"'{prefix}' ({len(prefix)} chars)"
        )

    full_name = prefix + normalized_name

    if len(full_name) <= max_len:
        return full_name

    # Truncate only the name component to fit
    return prefix + normalized_name[:remaining_budget]
