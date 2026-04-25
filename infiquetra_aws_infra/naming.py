"""
AWS resource naming utilities.
"""

import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Build a consistent AWS resource name in the format "{service}-{env}-{name}".

    All components are lowercased. Only lowercase letters (a-z), digits (0-9),
    and hyphens are allowed in the output; any other characters cause a
    ValueError.

    Empty components raise ValueError.

    If the total length exceeds max_len, the name component is truncated to fit,
    preserving the "{service}-{env}-" prefix. If max_len is too small to leave
    at least one character for the name component, ValueError is raised.

    Args:
        service: Service identifier (e.g., "s3", "lambda")
        env: Environment identifier (e.g., "dev", "prod")
        name: Resource name component (e.g., "user-data")
        max_len: Maximum total length (default 64)

    Returns:
        Lowercased, validated resource name.

    Raises:
        ValueError: if any component is empty, contains invalid characters after
                   lowercasing, or max_len is too small to accommodate at least
                   one character for the name component after the prefix.
    """
    # Validate inputs are non-empty strings (including whitespace-only)
    if not isinstance(service, str) or not service.strip():
        raise ValueError("service must be a non-empty string")
    if not isinstance(env, str) or not env.strip():
        raise ValueError("env must be a non-empty string")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(max_len, int) or max_len <= 0:
        raise ValueError("max_len must be a positive integer")

    # Normalize to lowercase
    service_lower = service.lower()
    env_lower = env.lower()
    name_lower = name.lower()

    # Validate characters after normalization
    # Allowed characters: a-z, 0-9, hyphen
    allowed_pattern = re.compile(r"^[a-z0-9-]+$")
    if not allowed_pattern.match(service_lower):
        raise ValueError(
            f"service contains invalid characters after lowercasing: {service_lower}"
        )
    if not allowed_pattern.match(env_lower):
        raise ValueError(
            f"env contains invalid characters after lowercasing: {env_lower}"
        )
    if not allowed_pattern.match(name_lower):
        raise ValueError(
            f"name contains invalid characters after lowercasing: {name_lower}"
        )

    # Compute prefix length
    prefix = f"{service_lower}-{env_lower}-"
    prefix_len = len(prefix)
    # Ensure we can fit at least one character for the name component
    if max_len < prefix_len + 1:
        raise ValueError(
            f"max_len={max_len} is too small to accommodate prefix "
            f"'{prefix}' (length {prefix_len}) plus at least one character"
        )

    # Check if truncation needed
    full_len = prefix_len + len(name_lower)
    if full_len <= max_len:
        return prefix + name_lower

    # Truncate only the name component
    truncated_name = name_lower[: max_len - prefix_len]
    return prefix + truncated_name
