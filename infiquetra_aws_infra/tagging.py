VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardized resource tags for AWS infrastructure.

    Args:
        env: Environment name (dev, staging, prod).
        team: Team name.
        project: Project name.

    Returns:
        Dictionary with keys: Environment, Team, Project, ManagedBy.

    Raises:
        ValueError: If environment is not one of the valid values.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in VALID_ENVIRONMENTS:
        allowed = "', '".join(sorted(VALID_ENVIRONMENTS))
        msg = f"Invalid env: expected [{allowed}], got '{normalized_env}'"
        raise ValueError(msg)

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
