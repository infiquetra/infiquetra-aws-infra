"""Resource naming utilities for AWS infrastructure."""
import re

# Module-level compiled regex for legal normalized components
VALID_COMPONENT_RE = re.compile(r"^[a-z0-9-]+$")


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """Build a consistent AWS resource name.

    Args:
        service: The service/component name
        env: The environment name
        name: The specific resource name
        max_len: Maximum length of the resulting name (default: 64)

    Returns:
        A formatted resource name: "{service}-{env}-{name}" lowercased

    Raises:
        ValueError: If any component is empty or contains illegal characters
        (only a-z, 0-9, and - are allowed after normalization)
    """
    # Check for empty components before normalization
    if not service:
        raise ValueError("service component cannot be empty")
    if not env:
        raise ValueError("env component cannot be empty")
    if not name:
        raise ValueError("name component cannot be empty")

    # Normalize to lowercase
    normalized_service = service.lower()
    normalized_env = env.lower()
    normalized_name = name.lower()

    # Validate each component against the regex
    if not VALID_COMPONENT_RE.match(normalized_service):
        raise ValueError(
            f"service component contains illegal characters: {normalized_service!r}"
        )
    if not VALID_COMPONENT_RE.match(normalized_env):
        raise ValueError(
            f"env component contains illegal characters: {normalized_env!r}"
        )
    if not VALID_COMPONENT_RE.match(normalized_name):
        raise ValueError(
            f"name component contains illegal characters: {normalized_name!r}"
        )

    # Build the prefix and full resource name
    prefix = f"{normalized_service}-{normalized_env}-"
    candidate = f"{prefix}{normalized_name}"

    # If within max_len, return as-is
    if len(candidate) <= max_len:
        return candidate

    # Truncate the name component to fit within max_len
    available_name_len = max_len - len(prefix)

    if available_name_len <= 0:
        raise ValueError(
            f"Cannot fit required prefix '{prefix}' within max_len={max_len}"
        )

    return f"{prefix}{normalized_name[:available_name_len]}"
