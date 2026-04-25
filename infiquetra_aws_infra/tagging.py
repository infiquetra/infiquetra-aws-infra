"""Common tagging utilities for AWS resource tagging."""


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardized tags for AWS resources.

    Args:
        env: Environment name (must be 'dev', 'staging', or 'prod').
        team: Team name responsible for the resource.
        project: Project identifier.

    Returns:
        Dict with keys: Environment, Team, Project, ManagedBy.

    Raises:
        ValueError: If env is not one of the allowed values.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    valid_envs = {"dev", "staging", "prod"}
    if normalized_env not in valid_envs:
        raise ValueError(
            f"Invalid environment '{normalized_env}'. "
            f"Must be one of: {', '.join(sorted(valid_envs))}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
