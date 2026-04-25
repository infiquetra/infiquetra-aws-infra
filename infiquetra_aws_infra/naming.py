"""AWS resource naming helpers."""

import re


def resource_name(service: str, env: str, name: str, max_len: int = 64) -> str:
    """Build a consistent AWS resource name.
    
    Format: "{service}-{env}-{name}" lowercased.
    If length exceeds max_len, truncate the middle component (name) to fit,
    preserving "{service}-{env}-" prefix.
    Reject illegal chars (only a-z 0-9 - allowed in output) — raise ValueError on invalid input chars.
    Reject empty components — raise ValueError.
    
    Args:
        service: AWS service identifier (e.g., 's3', 'lambda')
        env: Environment identifier (e.g., 'dev', 'prod')
        name: Resource name identifier
        max_len: Maximum length of the resulting string (default: 64)
        
    Returns:
        Formatted resource name string
        
    Raises:
        ValueError: If any component is empty or contains invalid characters
    """
    # Normalize inputs to lowercase for validation and output
    service_lower = service.lower()
    env_lower = env.lower()
    name_lower = name.lower()
    
    # Validate that components are not empty after normalization
    if not service_lower:
        raise ValueError("service component cannot be empty")
    if not env_lower:
        raise ValueError("env component cannot be empty")
    if not name_lower:
        raise ValueError("name component cannot be empty")
    
    # Validate that normalized components contain only allowed characters
    # Allowed: a-z, 0-9, and hyphen
    allowed_pattern = r"[a-z0-9-]+"
    
    if not re.fullmatch(allowed_pattern, service_lower):
        raise ValueError(
            f"service component '{service}' contains illegal characters. "
            "Only lowercase letters, numbers, and hyphens are allowed in output."
        )
    if not re.fullmatch(allowed_pattern, env_lower):
        raise ValueError(
            f"env component '{env}' contains illegal characters. "
            "Only lowercase letters, numbers, and hyphens are allowed in output."
        )
    if not re.fullmatch(allowed_pattern, name_lower):
        raise ValueError(
            f"name component '{name}' contains illegal characters. "
            "Only lowercase letters, numbers, and hyphens are allowed in output."
        )
    
    # Build the prefix and check length
    prefix = f"{service_lower}-{env_lower}-"
    full_name = f"{prefix}{name_lower}"
    
    # If within max_len, return as-is
    if len(full_name) <= max_len:
        return full_name
    
    # Calculate remaining budget for name component
    remaining_budget = max_len - len(prefix)
    
    # If prefix alone exceeds max_len, we can't fit even an empty name
    if remaining_budget <= 0:
        raise ValueError(
            f"max_len={max_len} is too small for prefix '{prefix}'. "
            f"Need at least {len(prefix) + 1} characters to accommodate a non-empty name."
        )
    
    # Truncate the name component to fit
    truncated_name = name_lower[:remaining_budget]
    return f"{prefix}{truncated_name}"