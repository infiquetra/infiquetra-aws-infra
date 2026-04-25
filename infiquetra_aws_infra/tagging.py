def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """
    Generate common tags for AWS resources.

    Args:
        env: The environment (dev, staging, prod).
        team: The team responsible for the resource.
        project: The project name.

    Returns:
        A dictionary of tags.

    Raises:
        ValueError: If the environment is not one of dev, staging, or prod.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    valid_envs = {"dev", "staging", "prod"}
    if normalized_env not in valid_envs:
        msg = f"Invalid environment '{normalized_env}'. Must be one of {valid_envs}"
        raise ValueError(msg)

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
