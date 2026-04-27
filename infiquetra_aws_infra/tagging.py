ALLOWED_ENVIRONMENTS = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    env = env.strip()
    team = team.strip()
    project = project.strip()

    if env not in ALLOWED_ENVIRONMENTS:
        expected = ", ".join(sorted(ALLOWED_ENVIRONMENTS))
        raise ValueError(
            f"Invalid environment '{env}'; expected one of: {expected}"
        )

    return {
        "Environment": env,
        "Team": team,
        "Project": project,
        "ManagedBy": "CDK",
    }
