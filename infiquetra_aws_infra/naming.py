"""Resource naming utilities for AWS infrastructure."""

import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """Build a consistent AWS resource name from components.

    Args:
        service: The service name component.
        env: The environment component.
        name: The resource name component.
        max_len: Maximum allowed length (default 64).

    Returns:
        A lowercase hyphenated string in format "{service}-{env}-{name}".

    Raises:
        ValueError: If any component is empty, contains illegal characters,
                   or cannot be truncated to fit max_len while preserving
                   the {service}-{env}- prefix.
    """
    # Validate non-empty components
    if not service:
        raise ValueError("service cannot be empty")
    if not env:
        raise ValueError("env cannot be empty")
    if not name:
        raise ValueError("name cannot be empty")

    # Normalize to lowercase
    service = service.lower()
    env = env.lower()
    name = name.lower()

    # Validate characters (only a-z, 0-9, - allowed)
    pattern = re.compile(r"^[a-z0-9-]+$")
    if not pattern.match(service):
        raise ValueError(f"service contains illegal characters: {service}")
    if not pattern.match(env):
        raise ValueError(f"env contains illegal characters: {env}")
    if not pattern.match(name):
        raise ValueError(f"name contains illegal characters: {name}")

    # Build the full name
    full_name = f"{service}-{env}-{name}"

    # Check length and truncate if needed
    if len(full_name) <= max_len:
        return full_name

    # Calculate available space for name component
    prefix = f"{service}-{env}-"
    if len(prefix) >= max_len:
        raise ValueError(
            f"prefix '{prefix}' length {len(prefix)} exceeds max_len {max_len}; "
            "cannot preserve prefix while truncating"
        )

    available = max_len - len(prefix)
    truncated_name = name[:available]

    return f"{prefix}{truncated_name}"
