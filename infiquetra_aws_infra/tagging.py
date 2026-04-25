"""Common tagging utilities for AWS resources."""


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardized AWS resource tags for the given environment.

    Args:
        env: The environment name (must be 'dev', 'staging', or 'prod').
        team: The team name responsible for the resource.
        project: The project name for the resource.

    Returns:
        A dictionary with the keys: Environment, Team, Project, and
        ManagedBy.

    Raises:
        ValueError: If env is not one of 'dev', 'staging', or 'prod'.
    """
    # Normalize inputs by stripping leading/trailing whitespace
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    # Validate environment
    if normalized_env not in ("dev", "staging", "prod"):
        raise ValueError(
            f"env must be one of 'dev', 'staging', or 'prod', got "
            f"'{normalized_env}'"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
