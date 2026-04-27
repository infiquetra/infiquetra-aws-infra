"""AWS resource naming utilities."""

import re

_VALID_NAME_RE = re.compile(r"^[a-z0-9-]+$")


def resource_name(
    service: str,
    env: str,
    name: str,
    max_len: int = 64,
) -> str:
    """Build a lowercased AWS resource name with ``{service}-{env}-{name}`` format.

    Parameters
    ----------
    service:
        Service name component (e.g. ``"s3"``, ``"lambda"``).
    env:
        Environment component (e.g. ``"dev"``, ``"prod"``).
    name:
        Logical resource name.
    max_len:
        Maximum length of the returned string.  Default 64.

    Returns
    -------
    str
        Lowercased name string no longer than ``max_len``.

    Raises
    ------
    ValueError
        If any component is empty, or contains characters outside
        ``[a-z0-9-]`` after lowercasing.
    """
    if not service:
        raise ValueError("service component is empty")
    if not env:
        raise ValueError("env component is empty")
    if not name:
        raise ValueError("name component is empty")

    service_lower = service.lower()
    env_lower = env.lower()
    name_lower = name.lower()

    for label, value in [
        ("service", service_lower),
        ("env", env_lower),
        ("name", name_lower),
    ]:
        if not _VALID_NAME_RE.fullmatch(value):
            raise ValueError(
                f"{label} contains illegal characters "
                f"(only a-z, 0-9, and hyphens allowed): {value!r}"
            )

    prefix = f"{service_lower}-{env_lower}-"
    candidate = f"{prefix}{name_lower}"

    if len(candidate) <= max_len:
        return candidate

    allowed_name_len = max_len - len(prefix)
    if allowed_name_len < 1:
        raise ValueError(
            f"max_len={max_len} is too small to hold "
            f"prefix {prefix!r} and a non-empty name"
        )

    return f"{prefix}{name_lower[:allowed_name_len]}"
