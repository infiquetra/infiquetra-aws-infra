import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Builds a consistent AWS resource name in the format {service}-{env}-{name}.

    Args:
        service: The AWS service name.
        env: The environment name.
        name: The specific resource name.
        max_len: Maximum allowed length of the final string.

    Returns:
        A lowercased, validated, and potentially truncated resource name.

    Raises:
        ValueError: If any component is empty, contains illegal characters,
                    or if max_len is too short to fit the required prefix.
    """
    service = service.lower()
    env = env.lower()
    name = name.lower()

    if not service or not env or not name:
        raise ValueError("All components (service, env, name) must be non-empty")

    pattern = re.compile(r"^[a-z0-9-]+$")
    if not all(pattern.match(c) for c in (service, env, name)):
        raise ValueError(
            "Components must only contain lowercase letters, numbers, and hyphens"
        )

    prefix = f"{service}-{env}-"
    full_name = f"{prefix}{name}"

    if len(full_name) <= max_len:
        return full_name

    if len(prefix) >= max_len:
        raise ValueError(
            f"max_len {max_len} is too short to accommodate the prefix '{prefix}'"
        )

    allowed_name_len = max_len - len(prefix)
    return f"{prefix}{name[:allowed_name_len]}"
