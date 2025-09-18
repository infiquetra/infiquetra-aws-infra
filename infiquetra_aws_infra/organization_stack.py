#!/usr/bin/env python3

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_organizations as organizations
from constructs import Construct


class OrganizationStack(Stack):
    """
    AWS Organizations stack for Infiquetra LLC business structure.

    Creates the organizational unit structure to reflect:
    - Infiquetra, LLC (Holding Company)
      ├── Infiquetra Media, LLC (Online content, branding, media)
      ├── Infiquetra Apps, LLC (Software product development)
      └── Infiquetra Consulting, LLC (Contracting & consulting services)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Organization root ID - this will be looked up from existing organization
        self.root_id = "r-f3un"  # From audit

        # Create the main business unit OUs
        self.create_organizational_structure()

        # Create Service Control Policies
        self.create_service_control_policies()

        # Output important information
        self.create_outputs()

    def create_organizational_structure(self) -> None:
        """Create the organizational unit structure for Infiquetra business units."""

        # Core OU for shared services (Security, Logging, Shared Services)
        self.core_ou = organizations.CfnOrganizationalUnit(
            self,
            "CoreOU",
            name="Core",
            parent_id=self.root_id,
            tags=[
                cdk.CfnTag(key="Purpose", value="Shared Services"),
                cdk.CfnTag(key="BusinessUnit", value="Core"),
            ],
        )

        # Media OU for Infiquetra Media, LLC
        self.media_ou = organizations.CfnOrganizationalUnit(
            self,
            "MediaOU",
            name="Media",
            parent_id=self.root_id,
            tags=[
                cdk.CfnTag(key="Purpose", value="Online content branding media"),
                cdk.CfnTag(key="BusinessUnit", value="Media"),
                cdk.CfnTag(key="LegalEntity", value="Infiquetra Media LLC"),
            ],
        )

        # Apps OU for Infiquetra Apps, LLC (will include CAMPPS migration)
        self.apps_ou = organizations.CfnOrganizationalUnit(
            self,
            "AppsOU",
            name="Apps",
            parent_id=self.root_id,
            tags=[
                cdk.CfnTag(key="Purpose", value="Software product development"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="LegalEntity", value="Infiquetra Apps LLC"),
            ],
        )

        # Consulting OU for Infiquetra Consulting, LLC
        self.consulting_ou = organizations.CfnOrganizationalUnit(
            self,
            "ConsultingOU",
            name="Consulting",
            parent_id=self.root_id,
            tags=[
                cdk.CfnTag(key="Purpose", value="Contracting and consulting services"),
                cdk.CfnTag(key="BusinessUnit", value="Consulting"),
                cdk.CfnTag(key="LegalEntity", value="Infiquetra Consulting LLC"),
            ],
        )

        # Create sub-OUs for environment separation in Apps OU (for CAMPPS migration)
        self.apps_campps_ou = organizations.CfnOrganizationalUnit(
            self,
            "AppsCamppsOU",
            name="CAMPPS",
            parent_id=self.apps_ou.ref,
            tags=[
                cdk.CfnTag(key="Purpose", value="CAMPPS application workloads"),
                cdk.CfnTag(key="Project", value="CAMPPS"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
            ],
        )

        # Environment-specific OUs under CAMPPS
        self.campps_production_ou = organizations.CfnOrganizationalUnit(
            self,
            "CamppsProductionOU",
            name="Production",
            parent_id=self.apps_campps_ou.ref,
            tags=[
                cdk.CfnTag(key="Environment", value="Production"),
                cdk.CfnTag(key="Project", value="CAMPPS"),
            ],
        )

        self.campps_nonprod_ou = organizations.CfnOrganizationalUnit(
            self,
            "CamppsNonProdOU",
            name="NonProd",
            parent_id=self.apps_campps_ou.ref,
            tags=[
                cdk.CfnTag(key="AccountType", value="NonProduction"),
                cdk.CfnTag(key="Project", value="CAMPPS"),
            ],
        )

    def create_service_control_policies(self) -> None:
        """Create Service Control Policies for governance and security."""

        # Base security policy for all business units
        base_security_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyRootUserActions",
                    "Effect": "Deny",
                    "Principal": {"AWS": "*"},
                    "Action": "*",
                    "Resource": "*",
                    "Condition": {"StringEquals": {"aws:PrincipalType": "Root"}},
                },
                {
                    "Sid": "DenyDeleteLoggingResources",
                    "Effect": "Deny",
                    "Principal": {"AWS": "*"},
                    "Action": [
                        "logs:DeleteLogGroup",
                        "logs:DeleteLogStream",
                        "cloudtrail:DeleteTrail",
                        "cloudtrail:StopLogging",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "RequireMFAForSensitiveActions",
                    "Effect": "Deny",
                    "Principal": {"AWS": "*"},
                    "Action": [
                        "iam:DeleteUser",
                        "iam:DeleteRole",
                        "iam:DeletePolicy",
                        "organizations:*",
                    ],
                    "Resource": "*",
                    "Condition": {
                        "BoolIfExists": {"aws:MultiFactorAuthPresent": "false"}
                    },
                },
            ],
        }

        # Create base security SCP
        self.base_security_scp = organizations.CfnPolicy(
            self,
            "BaseSecuritySCP",
            name="BaseSecurityPolicy",
            description="Base security controls applied to all business units",
            type="SERVICE_CONTROL_POLICY",
            content=base_security_policy,
            target_ids=[
                self.core_ou.ref,
                self.media_ou.ref,
                self.apps_ou.ref,
                self.consulting_ou.ref,
            ],
            tags=[
                cdk.CfnTag(key="PolicyType", value="Security"),
                cdk.CfnTag(key="Scope", value="AllBusinessUnits"),
            ],
        )

        # Cost control policy for development environments
        dev_cost_control_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyExpensiveInstanceTypes",
                    "Effect": "Deny",
                    "Principal": {"AWS": "*"},
                    "Action": "ec2:RunInstances",
                    "Resource": "arn:aws:ec2:*:*:instance/*",
                    "Condition": {
                        "StringNotEquals": {
                            "ec2:InstanceType": [
                                "t3.nano",
                                "t3.micro",
                                "t3.small",
                                "t3.medium",
                                "t4g.nano",
                                "t4g.micro",
                                "t4g.small",
                                "t4g.medium",
                            ]
                        }
                    },
                }
            ],
        }

        # Apply cost control to non-production environments
        self.nonprod_cost_control_scp = organizations.CfnPolicy(
            self,
            "NonProdCostControlSCP",
            name="NonProductionCostControl",
            description="Cost controls for non-production environments",
            type="SERVICE_CONTROL_POLICY",
            content=dev_cost_control_policy,
            target_ids=[self.campps_nonprod_ou.ref],
            tags=[
                cdk.CfnTag(key="PolicyType", value="CostControl"),
                cdk.CfnTag(key="AccountType", value="NonProduction"),
            ],
        )

    def create_outputs(self) -> None:
        """Create CloudFormation outputs for important resources."""

        CfnOutput(
            self,
            "CoreOUId",
            value=self.core_ou.ref,
            description="Core OU ID for shared services",
        )

        CfnOutput(
            self,
            "MediaOUId",
            value=self.media_ou.ref,
            description="Media OU ID for Infiquetra Media LLC",
        )

        CfnOutput(
            self,
            "AppsOUId",
            value=self.apps_ou.ref,
            description="Apps OU ID for Infiquetra Apps LLC",
        )

        CfnOutput(
            self,
            "ConsultingOUId",
            value=self.consulting_ou.ref,
            description="Consulting OU ID for Infiquetra Consulting LLC",
        )

        CfnOutput(
            self,
            "CamppsOUId",
            value=self.apps_campps_ou.ref,
            description="CAMPPS OU ID for migrated CAMPPS accounts",
        )

        CfnOutput(
            self,
            "CamppsProductionOUId",
            value=self.campps_production_ou.ref,
            description="CAMPPS Production OU ID",
        )

        CfnOutput(
            self,
            "CamppsNonProdOUId",
            value=self.campps_nonprod_ou.ref,
            description="CAMPPS NonProd OU ID",
        )

    @property
    def organization_structure(self) -> dict[str, str]:
        """Return the organization structure mapping for use by other stacks."""
        return {
            "core_ou_id": self.core_ou.ref,
            "media_ou_id": self.media_ou.ref,
            "apps_ou_id": self.apps_ou.ref,
            "consulting_ou_id": self.consulting_ou.ref,
            "campps_ou_id": self.apps_campps_ou.ref,
            "campps_production_ou_id": self.campps_production_ou.ref,
            "campps_nonprod_ou_id": self.campps_nonprod_ou.ref,
        }
