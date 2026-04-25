#!/usr/bin/env python3
"""Naming utilities for AWS resource naming conventions."""

import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Build a consistent AWS resource name in the format
    '{service}-{env}-{name}', lowercased.

    Args:
        service: Service identifier (e.g., 's3', 'lambda').
        env: Environment identifier (e.g., 'dev', 'prod').
        name: Resource-specific name (e.g., 'user-data').
        max_len: Maximum total length of the returned name. Defaults to 64.

    Returns:
        Lowercase string '{service}-{env}-{name}', truncated at max_len by
        shortening only the `name` component.

    Raises:
        ValueError: If any component is empty, contains characters outside
            [a-z0-9-] after lowercasing, or if max_len leaves no room for
            the `name` component after the '{service}-{env}-' prefix.
    """
    # Validate inputs
    if not service or not env or not name:
        raise ValueError("service, env, and name must be non-empty strings")

    # Lowercase each component for validation and formatting
    service_lower = service.lower()
    env_lower = env.lower()
    name_lower = name.lower()

    # Validate characters (only a-z, 0-9, hyphen allowed)
    allowed_pattern = re.compile(r"^[a-z0-9-]+$")
    if not allowed_pattern.match(service_lower):
        raise ValueError(f"service contains invalid characters: {service!r}")
    if not allowed_pattern.match(env_lower):
        raise ValueError(f"env contains invalid characters: {env!r}")
    if not allowed_pattern.match(name_lower):
        raise ValueError(f"name contains invalid characters: {name!r}")

    # Build prefix 'service-env-' and check length constraints
    prefix = f"{service_lower}-{env_lower}-"
    prefix_len = len(prefix)

    if prefix_len >= max_len:
        raise ValueError(
            f"max_len={max_len} is too small to fit prefix '{prefix}' "
            f"(length {prefix_len})"
        )

    remaining = max_len - prefix_len
    # remaining is guaranteed >=1 here
    truncated_name = name_lower[:remaining]
    return prefix + truncated_name
