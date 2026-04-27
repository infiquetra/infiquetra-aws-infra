_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    for label, value in (("service", service), ("env", env), ("name", name)):
        if value == "":
            raise ValueError(f"resource_name component '{label}' must not be empty")
        lower = value.lower()
        if any(ch not in _ALLOWED_CHARS for ch in lower):
            raise ValueError(
                f"resource_name component '{label}' "
                f"contains illegal characters: '{value}'"
            )

    service_lower = service.lower()
    env_lower = env.lower()
    name_lower = name.lower()

    prefix = f"{service_lower}-{env_lower}-"
    candidate = f"{prefix}{name_lower}"
    if len(candidate) <= max_len:
        return candidate

    available_name_len = max_len - len(prefix)
    if available_name_len <= 0:
        raise ValueError(f"max_len {max_len} is too small for prefix '{prefix}'")

    return f"{prefix}{name_lower[:available_name_len]}"
