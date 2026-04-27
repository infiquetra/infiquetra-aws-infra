"""AWS resource naming utilities."""

import re

_VALID_PATTERN = re.compile(r"^[a-z0-9-]+$")


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """Build a standardized AWS resource name in the form ``{service}-{env}-{name}``.

    Components are lowercased before assembly.  Empty components or components
    containing characters outside ``a-z``, ``0-9``, or ``-`` (after lowering)
    raise :class:`ValueError`.  When the full name exceeds *max_len*, only the
    *name* portion is truncated so the ``{service}-{env}-`` prefix is preserved.
    """
    service = service.lower()
    env = env.lower()
    name = name.lower()

    if not service:
        raise ValueError("service must not be empty")
    if not env:
        raise ValueError("env must not be empty")
    if not name:
        raise ValueError("name must not be empty")

    for label, value in (("service", service), ("env", env), ("name", name)):
        if not _VALID_PATTERN.match(value):
            raise ValueError(f"{label} contains illegal characters: {value!r}")

    prefix = f"{service}-{env}-"
    if len(prefix) + len(name) <= max_len:
        return f"{prefix}{name}"

    allowed_name_len = max_len - len(prefix)
    if allowed_name_len <= 0:
        raise ValueError(
            f"max_len={max_len} too small to preserve prefix {prefix!r}"
        )
    return f"{prefix}{name[:allowed_name_len]}"
