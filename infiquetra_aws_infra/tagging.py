"""Tagging helpers for standardized AWS resource tagging.

Provides a single function, ``common_tags``, that returns a consistent
dictionary of tags for CDK-deployed resources.
"""

VALID_ENVIRONMENTS: set[str] = {"dev", "staging", "prod"}


def common_tags(env: str, team: str, project: str) -> dict[str, str]:
    """Return a standard set of AWS resource tags.

    Parameters
    ----------
    env : str
        Deployment environment. Must be one of ``"dev"``, ``"staging"``,
        or ``"prod"`` (whitespace-normalized before validation).
    team : str
        Team that owns the resource (whitespace-normalized).
    project : str
        Project the resource belongs to (whitespace-normalized).

    Returns
    -------
    dict[str, str]
        Dictionary with keys ``Environment``, ``Team``, ``Project``,
        and ``ManagedBy``.

    Raises
    ------
    ValueError
        If *env* is not one of the allowed values after normalization.
    """
    normalized_env = env.strip()
    normalized_team = team.strip()
    normalized_project = project.strip()

    if normalized_env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment: expected one of"
            f" {sorted(VALID_ENVIRONMENTS)}, got {normalized_env!r}"
        )

    return {
        "Environment": normalized_env,
        "Team": normalized_team,
        "Project": normalized_project,
        "ManagedBy": "CDK",
    }
