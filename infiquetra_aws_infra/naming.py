import re

# Allowed characters pattern: only lowercase letters, digits, and hyphens
_ALLOWED_CHARS_PATTERN = re.compile(r"^[a-z0-9-]+$")


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Generate a standardized resource name for AWS resources.

    Args:
        service: Service name (e.g., "s3", "lambda")
        env: Environment name (e.g., "dev", "prod")
        name: Resource name (e.g., "user-data")
        max_len: Maximum length of the resulting name (default: 64)

    Returns:
        Formatted resource name in the format "{service}-{env}-{name}" (lowercased)

    Raises:
        ValueError: If any component is empty or contains illegal characters
    """
    # Validate components are not empty
    if not service:
        raise ValueError("service component cannot be empty")
    if not env:
        raise ValueError("env component cannot be empty")
    if not name:
        raise ValueError("name component cannot be empty")

    # Normalize to lowercase
    service_lower = service.lower()
    env_lower = env.lower()
    name_lower = name.lower()

    # Validate components contain only allowed characters
    if not _ALLOWED_CHARS_PATTERN.match(service_lower):
        raise ValueError(
            f"service '{service}' contains illegal characters "
            "(only a-z, 0-9, - allowed)"
        )
    if not _ALLOWED_CHARS_PATTERN.match(env_lower):
        raise ValueError(
            f"env '{env}' contains illegal characters "
            "(only a-z, 0-9, - allowed)"
        )
    if not _ALLOWED_CHARS_PATTERN.match(name_lower):
        raise ValueError(
            f"name '{name}' contains illegal characters "
            "(only a-z, 0-9, - allowed)"
        )

    # Build the full name
    prefix = f"{service_lower}-{env_lower}-"
    full_name = f"{prefix}{name_lower}"

    # If within limit, return as-is
    if len(full_name) <= max_len:
        return full_name

    # Truncate name component to fit within max_len
    available_name_len = max_len - len(prefix)

    # If no room for name, that's an error
    if available_name_len <= 0:
        raise ValueError(
            f"service and env ('{prefix}') exceed max_len={max_len}, "
            "no room for name component"
        )

    # Truncate name to fit
    truncated_name = name_lower[:available_name_len]
    return f"{prefix}{truncated_name}"
