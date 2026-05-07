"""Standardized resource tagging helper for CDK stacks."""

_ALLOWED_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return a standard set of resource tags.

    Args:
        env: Deployment environment — must be "dev", "staging", or "prod".
        team: Owning team name (whitespace trimmed).
        project: Project name (whitespace trimmed).

    Returns:
        A dict with Environment, Team, Project, and ManagedBy keys.

    Raises:
        ValueError: If *env* is not one of the allowed environments.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in _ALLOWED_ENVIRONMENTS:
        allowed = ", ".join(sorted(_ALLOWED_ENVIRONMENTS))
        raise ValueError(
            f"Invalid environment for common tags: "
            f"expected one of {allowed}; got '{normalized_env}'"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
