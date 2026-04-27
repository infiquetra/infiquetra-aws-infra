"""Tagging utilities for AWS infrastructure resources."""

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Generate standardized tags for AWS resources.

    Args:
        env: Environment name (dev, staging, or prod).
        team: Team responsible for the resource.
        project: Project name for the resource.

    Returns:
        Dictionary containing standardized tags.

    Raises:
        ValueError: If env is not one of dev, staging, or prod.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment '{normalized_env}'; "
            f"expected one of: {', '.join(sorted(VALID_ENVIRONMENTS))}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
