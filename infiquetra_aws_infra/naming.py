"""Resource naming utilities for AWS infrastructure."""

import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """Build a consistent resource name with format '{service}-{env}-{name}'.

    Args:
        service: The service identifier (e.g., 's3', 'lambda').
        env: The environment identifier (e.g., 'dev', 'prod').
        name: The resource name component.
        max_len: Maximum allowed length of the full resource name (default: 64).

    Returns:
        A lowercase resource name in the format '{service}-{env}-{name}',
        truncated to max_len if necessary (preserving the prefix).

    Raises:
        ValueError: If any component is empty after normalization,
                    contains illegal characters, or if truncation leaves
                    no room for the name component.
    """
    # Normalize to lowercase
    service_lower = service.lower()
    env_lower = env.lower()
    name_lower = name.lower()

    # Validate non-empty components
    if not service_lower:
        raise ValueError("service component cannot be empty")
    if not env_lower:
        raise ValueError("env component cannot be empty")
    if not name_lower:
        raise ValueError("name component cannot be empty")

    # Validate allowed characters (a-z, 0-9, -)
    allowed_pattern = re.compile(r'^[a-z0-9-]+$')
    if not allowed_pattern.match(service_lower):
        raise ValueError(f"service contains illegal characters: {service!r}")
    if not allowed_pattern.match(env_lower):
        raise ValueError(f"env contains illegal characters: {env!r}")
    if not allowed_pattern.match(name_lower):
        raise ValueError(f"name contains illegal characters: {name!r}")

    # Build the prefix and full name
    prefix = f"{service_lower}-{env_lower}-"
    full_name = f"{prefix}{name_lower}"

    # Check if truncation is needed
    if len(full_name) <= max_len:
        return full_name

    # Calculate available length for name component
    available_for_name = max_len - len(prefix)

    # Fail if no room for name
    if available_for_name < 1:
        raise ValueError(
            f"max_len={max_len} leaves no room for name after prefix {prefix!r}"
        )

    # Truncate only the name component
    truncated_name = name_lower[:available_for_name]
    return f"{prefix}{truncated_name}"
