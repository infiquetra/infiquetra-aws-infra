import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """
    Builds a consistent AWS resource name.
    Format: {service}-{env}-{name}
    """
    # Normalize to lowercase
    service = service.lower()
    env = env.lower()
    name = name.lower()

    # Validate components: non-empty and allowed characters [a-z0-9-]+
    pattern = re.compile(r"^[a-z0-9-]+$")

    for component, label in [(service, "service"), (env, "env"), (name, "name")]:
        if not component:
            raise ValueError(f"Component {label} cannot be empty")
        if not pattern.match(component):
            msg = f"Component {label} contains illegal characters: {component}"
            raise ValueError(msg)

    prefix = f"{service}-{env}-"
    full_name = f"{prefix}{name}"

    if len(full_name) <= max_len:
        return full_name

    # Truncate name component to fit max_len, preserving prefix
    if len(prefix) >= max_len:
        msg = f"Prefix '{prefix}' exceeds or equals max_len {max_len}"
        raise ValueError(f"{msg}, no room for name component")

    allowed_name_len = max_len - len(prefix)
    truncated_name = name[:allowed_name_len]

    return f"{prefix}{truncated_name}"
