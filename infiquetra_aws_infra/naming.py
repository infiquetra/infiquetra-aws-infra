"""Resource naming utilities for AWS infrastructure."""

import re

# Precompiled pattern for valid resource name components (a-z, 0-9, hyphen)
_VALID_COMPONENT_PATTERN = re.compile(r"^[a-z0-9-]+$")


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Build a standardized AWS resource name with format {service}-{env}-{name}.

    All components are normalized to lowercase. Output characters are limited
    to a-z, 0-9, and hyphen. If the total length exceeds max_len, only the
    name component is truncated to fit while preserving the service-env prefix.

    Args:
        service: Service identifier (e.g., "s3", "lambda")
        env: Environment identifier (e.g., "dev", "prod")
        name: Resource name within the service
        max_len: Maximum total length (default 64)

    Returns:
        Lowercase resource name string in format {service}-{env}-{name}

    Raises:
        ValueError: If any component is empty or contains illegal characters
            (not a-z, 0-9, or hyphen after normalization)
    """
    # Check for empty components (before normalization)
    if not service:
        raise ValueError("service cannot be empty")
    if not env:
        raise ValueError("env cannot be empty")
    if not name:
        raise ValueError("name cannot be empty")

    # Normalize to lowercase
    normalized_service = service.lower()
    normalized_env = env.lower()
    normalized_name = name.lower()

    # Validate characters in normalized components
    if not _VALID_COMPONENT_PATTERN.match(normalized_service):
        raise ValueError(
            f"service contains illegal characters: {service!r} "
            "(only a-z, 0-9, and hyphen allowed)"
        )
    if not _VALID_COMPONENT_PATTERN.match(normalized_env):
        raise ValueError(
            f"env contains illegal characters: {env!r} "
            "(only a-z, 0-9, and hyphen allowed)"
        )
    if not _VALID_COMPONENT_PATTERN.match(normalized_name):
        raise ValueError(
            f"name contains illegal characters: {name!r} "
            "(only a-z, 0-9, and hyphen allowed)"
        )

    # Build prefix and full name
    prefix = f"{normalized_service}-{normalized_env}-"
    full_name = f"{prefix}{normalized_name}"

    # Check if truncation is needed
    if len(full_name) <= max_len:
        return full_name

    # Truncate only the name component
    available_name_length = max_len - len(prefix)
    if available_name_length <= 0:
        raise ValueError(
            f"max_len={max_len} too short for prefix '{prefix}' "
            f"(need at least {len(prefix) + 1} characters)"
        )

    return f"{prefix}{normalized_name[:available_name_length]}"
