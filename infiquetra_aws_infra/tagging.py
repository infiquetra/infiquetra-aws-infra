"""Helpers for standardized AWS resource tags."""

_VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardized AWS resource tags.

    Args:
        env: Deployment environment — must be one of dev, staging, prod.
        team: Owning team name.
        project: Project name.

    Returns:
        Dict with Environment, Team, Project, and ManagedBy keys.

    Raises:
        ValueError: If env is not a recognized environment.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in _VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment '{normalized_env}': "
            f"expected one of {', '.join(sorted(_VALID_ENVIRONMENTS))}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
