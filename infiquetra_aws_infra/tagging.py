"""Tagging utilities for standardized resource tagging."""


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Generate common AWS resource tags.

    Args:
        env: Environment name. Must be one of: dev, staging, prod.
        team: Team name.
        project: Project name.

    Returns:
        Dict with standardized tag keys: Environment, Team, Project, ManagedBy.

    Raises:
        ValueError: If env is not one of the allowed values.
    """
    # Normalize inputs by stripping whitespace
    env_normalized = env.strip()
    team_normalized = team.strip()
    project_normalized = project.strip()

    # Validate environment
    allowed_envs = {"dev", "staging", "prod"}
    if env_normalized not in allowed_envs:
        raise ValueError(
            f"Invalid env '{env_normalized}'. Must be one of: {allowed_envs}"
        )

    # Build and return the tag dictionary
    return {
        "Environment": env_normalized,
        "Team": team_normalized,
        "Project": project_normalized,
        "ManagedBy": "CDK",
    }
