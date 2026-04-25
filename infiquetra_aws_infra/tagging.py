"""Standardized resource tagging helpers for AWS CDK stacks."""


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """
    Return a standardized tag dict for AWS resources.

    Args:
        env: Deployment environment. Must be one of "dev", "staging", "prod".
        team: Team responsible for the resource.
        project: Project name.

    Returns:
        Dict with keys: Environment, Team, Project, ManagedBy.

    Raises:
        ValueError: If env is not one of "dev", "staging", "prod".
    """
    env_norm = env.strip()
    team_norm = team.strip()
    project_norm = project.strip()

    valid_envs = {"dev", "staging", "prod"}
    if env_norm not in valid_envs:
        raise ValueError(
            f"Invalid env {env_norm!r}: must be one of {sorted(valid_envs)}"
        )

    return {
        "Environment": env_norm,
        "Team": team_norm,
        "Project": project_norm,
        "ManagedBy": "CDK",
    }
