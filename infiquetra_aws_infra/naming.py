import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Build a consistent AWS resource name formatted as "{service}-{env}-{name}".

    All components must be non-empty and contain only alphanumeric characters
    or hyphens after lowercasing. The output is guaranteed to be lowercase.

    If the combined length exceeds `max_len`, only the `name` component is
    truncated to fit while preserving the mandatory "{service}-{env}-" prefix.

    Args:
        service: Service identifier (e.g., "s3", "lambda").
        env: Environment identifier (e.g., "dev", "prod").
        name: Resource-specific name.
        max_len: Maximum total length (default 64).

    Returns:
        Lowercased resource name in the format "{service}-{env}-{name}".

    Raises:
        ValueError: If any component is empty after normalization,
            contains characters other than a-z, 0-9 or hyphen,
            or the prefix alone exceeds `max_len`.
    """
    # Normalize to lowercase
    service_norm = service.lower()
    env_norm = env.lower()
    name_norm = name.lower()

    # Validate each component
    allowed_pattern = re.compile(r"[a-z0-9-]+")
    for component, label in [
        (service_norm, "service"),
        (env_norm, "env"),
        (name_norm, "name"),
    ]:
        if not component:
            raise ValueError(f"{label} cannot be empty")
        if not allowed_pattern.fullmatch(component):
            raise ValueError(
                f"{label} contains invalid characters after lowercasing: "
                f"only a-z, 0-9 and hyphen allowed, got {component!r}"
            )

    # Build the name
    prefix = f"{service_norm}-{env_norm}-"
    if len(prefix) > max_len:
        raise ValueError(
            f"prefix '{prefix}' length {len(prefix)} exceeds max_len={max_len}; "
            f"cannot construct a valid name"
        )

    full = f"{prefix}{name_norm}"
    if len(full) <= max_len:
        return full

    available = max_len - len(prefix)
    if available < 0:
        # Already handled above, but kept for clarity
        raise ValueError(
            f"prefix '{prefix}' length {len(prefix)} exceeds max_len={max_len}"
        )

    truncated_name = name_norm[:available]
    return f"{prefix}{truncated_name}"
