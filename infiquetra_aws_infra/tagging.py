"""Standardized AWS resource tagging helpers."""

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return a standardized tag dictionary for AWS resources.

    Args:
        env: Environment name, must be one of: dev, staging, prod.
        team: Team responsible for the resource.
        project: Project name.

    Returns:
        dict with keys: Environment, Team, Project, ManagedBy (always "CDK").

    Raises:
        ValueError: if env is not one of the valid environments.
    """
    env = env.strip()
    team = team.strip()
    project = project.strip()

    if env not in VALID_ENVIRONMENTS:
        allowed = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise ValueError(f"Invalid environment '{env}'; expected one of: {allowed}")

    return {
        "Environment": env,
        "Team": team,
        "Project": project,
        "ManagedBy": "CDK",
    }
