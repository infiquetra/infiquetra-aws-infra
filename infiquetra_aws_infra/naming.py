"""AWS resource naming utilities."""

import re

# Regex pattern for valid AWS resource names: lowercase letters, digits, hyphens
pattern = re.compile(r"^[a-z0-9-]+$")


def resource_name(
    service: str, env: str, name: str, max_len: int = 64
) -> str:
    """Build a consistent AWS resource name.

    Format: "{service}-{env}-{name}" with all components lowercased.
    If length exceeds max_len, truncate only the name component to fit,
    preserving the "{service}-{env}-" prefix.

    Args:
        service: Service name (e.g., "s3", "lambda")
        env: Environment name (e.g., "dev", "prod")
        name: Resource name
        max_len: Maximum length of the returned name (default: 64)

    Returns:
        Valid AWS resource name string

    Raises:
        ValueError: If any component is empty, contains invalid characters,
                   or if the prefix length exceeds max_len making the contract
                   impossible to satisfy.
    """
    # Normalize to lowercase
    service = service.lower()
    env = env.lower()
    name = name.lower()

    # Validate components are non-empty
    for component, label in [(service, "service"), (env, "env"), (name, "name")]:
        if not component:
            raise ValueError(f"{label} component must be non-empty")

    # Validate components contain only allowed characters
    for component, label in [(service, "service"), (env, "env"), (name, "name")]:
        if not pattern.match(component):
            raise ValueError(
                f"{label} component contains invalid characters: "
                "must be lowercase letters, digits, or hyphens only"
            )

    # Build the full name
    prefix = f"{service}-{env}-"
    full_name = f"{prefix}{name}"

    # Check if we meet the length requirements
    if len(full_name) <= max_len:
        return full_name

    # Need to truncate - check if it's possible while preserving prefix
    if len(prefix) >= max_len:
        raise ValueError(
            "prefix length ("
            f"{len(prefix)})"
            f" exceeds max_len ({max_len}); cannot satisfy "
            "the contract of preserving "
            f"'{prefix}'"
            f" and returning <= {max_len} characters"
        )

    # Truncate only the name component
    max_name_len = max_len - len(prefix)
    truncated_name = name[:max_name_len]
    return f"{prefix}{truncated_name}"
