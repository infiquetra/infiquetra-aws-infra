"""Tagging utilities for AWS infrastructure."""

# Valid environments for our infrastructure
VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """
    Generate standardized tags for AWS resources.

    Args:
        env: Environment name (must be one of 'dev', 'staging', 'prod')
        team: Team responsible for the resource
        project: Project name

    Returns:
        Dictionary with standardized tags

    Raises:
        ValueError: If env is not one of the valid environments
    """
    # Normalize inputs by stripping whitespace
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    # Validate environment
    if normalized_env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment '{normalized_env}'; "
            f"expected one of: {', '.join(sorted(VALID_ENVIRONMENTS))}"
        )

    # Return standardized tag dictionary
    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
