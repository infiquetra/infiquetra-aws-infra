"""Standardized resource tagging for CDK infrastructure."""

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """
    Return a standardized CDK resource tagging dictionary.

    Args:
        env: Environment identifier, must be one of "dev", "staging", "prod".
        team: Team name (will be stripped).
        project: Project name (will be stripped).

    Returns:
        dict[str, str] with keys Environment, Team, Project, ManagedBy.

    Raises:
        ValueError: If env is not one of VALID_ENVIRONMENTS.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in VALID_ENVIRONMENTS:
        envs = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise ValueError(f"Invalid environment {env!r}; expected one of: {envs}")

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
