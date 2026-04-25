"""Common tagging utilities for AWS resources."""


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardized AWS resource tags.

    Args:
        env: Environment name (must be 'dev', 'staging', or 'prod').
        team: Team name.
        project: Project name.

    Returns:
        Dict with keys: Environment, Team, Project, ManagedBy.

    Raises:
        ValueError: If env is not one of 'dev', 'staging', or 'prod'.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in {"dev", "staging", "prod"}:
        raise ValueError(
            f"env must be one of 'dev', 'staging', or 'prod', got '{normalized_env}'"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
