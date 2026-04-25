def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """
    Generates a standardized set of resource tags.

    Args:
        env: The deployment environment (must be 'dev', 'staging', or 'prod').
        team: The team responsible for the resource.
        project: The project the resource belongs to.

    Returns:
        A dictionary containing the standardized tags.

    Raises:
        ValueError: If the provided environment is not one of the allowed values.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    allowed_envs = {"dev", "staging", "prod"}
    if normalized_env not in allowed_envs:
        raise ValueError(
            f"Invalid environment '{normalized_env}'. Must be one of {allowed_envs}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
