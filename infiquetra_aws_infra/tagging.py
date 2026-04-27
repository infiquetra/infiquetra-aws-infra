VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardised AWS resource tags.

    Args:
        env: Deployment environment — must be one of dev, staging, prod.
        team: Owning team name.
        project: Project name.

    Returns:
        A dict with keys Environment, Team, Project, and ManagedBy.

    Raises:
        ValueError: If *env* is not a recognised environment.
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
