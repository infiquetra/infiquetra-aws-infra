ALLOWED_ENVIRONMENTS = {"dev", "staging", "prod"}

def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """
    Returns a standardized dictionary of tags for AWS resources.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in ALLOWED_ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment: expected one of "
            f"dev, staging, prod; got {normalized_env!r}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
