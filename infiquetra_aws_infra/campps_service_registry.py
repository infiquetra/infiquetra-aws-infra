"""CAMPPS service deployment registry."""

from dataclasses import dataclass
from typing import Literal

DeployEnvironment = Literal["nonprod", "staging", "production"]


@dataclass(frozen=True)
class ServiceRepository:
    """GitHub repository configuration for CAMPPS service deployments."""

    name: str
    repository: str
    environments: tuple[DeployEnvironment, ...] = ("nonprod", "staging", "production")
    deploy_profile: str = "serverless-api"

    def github_subject(self, environment: DeployEnvironment) -> str:
        """Return the exact GitHub Actions OIDC subject for an environment."""
        return f"repo:{self.repository}:environment:{environment}"

    def role_name(self, environment: DeployEnvironment) -> str:
        """Return the workload-account deploy role name for an environment."""
        return f"campps-{self.name}-{environment}-gha-deploy-role"

    def policy_name(self, environment: DeployEnvironment) -> str:
        """Return the deploy managed policy name for an environment."""
        return f"campps-{self.name}-{environment}-gha-deploy-policy"

    def permissions_boundary_name(self, environment: DeployEnvironment) -> str:
        """Return the app role permissions boundary name for an environment."""
        return f"campps-{self.name}-{environment}-permissions-boundary"


CAMPPS_SERVICE_REPOSITORIES: tuple[ServiceRepository, ...] = (
    ServiceRepository(
        name="platform",
        repository="infiquetra/campps-platform",
        deploy_profile="platform-foundation",
    ),
    ServiceRepository(
        name="contracts",
        repository="infiquetra/campps-contracts",
        deploy_profile="codeartifact-publish",
    ),
    ServiceRepository(
        name="identity-access",
        repository="infiquetra/campps-identity-access",
    ),
    ServiceRepository(
        name="tenant-setup",
        repository="infiquetra/campps-tenant-setup",
    ),
    ServiceRepository(
        name="coppa-consent",
        repository="infiquetra/campps-coppa-consent",
    ),
    ServiceRepository(
        name="registration",
        repository="infiquetra/campps-registration",
    ),
    ServiceRepository(
        name="payments",
        repository="infiquetra/campps-payments",
    ),
    ServiceRepository(
        name="health-forms",
        repository="infiquetra/campps-health-forms",
    ),
    ServiceRepository(
        name="activities-achievements",
        repository="infiquetra/campps-activities-achievements",
    ),
    ServiceRepository(
        name="staff-management",
        repository="infiquetra/campps-staff-management",
    ),
    # Provisional: campps-web-app is an empty scaffold today with no settled
    # deploy target. The web-app profile is scoped to the standard static-site
    # pattern (S3 + CloudFront) and MUST be revisited when the real web-app CDK
    # stack lands (it may be Amplify or differ). See KTD3 in
    # docs/plans/2026-06-20-c0-3-aws-infra-service-registry-oidc-plan.md.
    ServiceRepository(
        name="web-app",
        repository="infiquetra/campps-web-app",
        deploy_profile="web-app",
    ),
)
