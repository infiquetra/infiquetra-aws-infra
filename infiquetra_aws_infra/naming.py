def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Generate a standardized AWS resource name with format "{service}-{env}-{name}".

    Args:
        service: Service identifier (e.g., "s3", "lambda")
        env: Environment identifier (e.g., "dev", "prod")
        name: Resource name identifier
        max_len: Maximum allowed length for the full name (default: 64)

    Returns:
        str: Formatted resource name in lowercase

    Raises:
        ValueError: If any component is empty or contains illegal characters
    """
    # Normalize components to lowercase
    service_part = service.lower()
    env_part = env.lower()
    name_part = name.lower()

    # Validate components
    for component, component_name in [
        (service_part, "service"),
        (env_part, "env"),
        (name_part, "name")
    ]:
        if not component:
            raise ValueError(f"{component_name} component cannot be empty")
        if not all((c >= 'a' and c <= 'z') or (c >= '0' and c <= '9') or c == '-' for c in component):
            raise ValueError(
                f"{component_name} component contains illegal characters "
                f"(only a-z, 0-9, - allowed)"
            )

    # Build the candidate name
    candidate = f"{service_part}-{env_part}-{name_part}"

    # If within max_len, return as-is
    if len(candidate) <= max_len:
        return candidate

    # Calculate prefix length
    prefix = f"{service_part}-{env_part}-"
    prefix_len = len(prefix)

    # Check if prefix alone exceeds max_len
    if prefix_len >= max_len:
        raise ValueError(f"Prefix '{prefix}' exceeds max_len {max_len}")

    # Calculate remaining capacity for name part
    remaining_capacity = max_len - prefix_len

    # If no capacity left for name, raise error
    if remaining_capacity <= 0:
        raise ValueError(
            f"No capacity left for name component after prefix '{prefix}'"
        )

    # Truncate name part to fit
    truncated_name = name_part[:remaining_capacity]
    return prefix + truncated_name
