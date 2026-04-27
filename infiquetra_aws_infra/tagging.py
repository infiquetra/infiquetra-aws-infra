"""Standardized resource tagging utilities for AWS CDK stacks."""

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardized AWS resource tags.

    Args:
        env: Environment name. Must be one of "dev", "staging", or "prod".
        team: Team name.
        project: Project name.

    Returns:
        Dictionary with Environment, Team, Project, and ManagedBy keys.

    Raises:
        ValueError: If env is not a valid environment.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in VALID_ENVIRONMENTS:
        valid_envs = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise ValueError(
            f"Invalid environment '{normalized_env}'; expected one of: {valid_envs}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
