#!/usr/bin/env python3

"""Common tagging helper for AWS resources."""

from typing import Final

VALID_ENVIRONMENTS: Final[set[str]] = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return standardized tags for AWS resources.

    Args:
        env: The environment (dev, staging, or prod).
        team: The team name.
        project: The project name.

    Returns:
        A dict with keys: Environment, Team, Project, ManagedBy.

    Raises:
        ValueError: If env is not one of the valid environments.
    """
    normalized_env: str = env.strip()
    normalized_team: str = team.strip()
    normalized_project: str = project.strip()

    if normalized_env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"env must be one of {sorted(VALID_ENVIRONMENTS)}, got {normalized_env!r}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
