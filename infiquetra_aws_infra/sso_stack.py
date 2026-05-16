#!/usr/bin/env python3

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnCondition, CfnOutput, CfnParameter, Fn, Stack
from aws_cdk import aws_sso as sso
from constructs import Construct

from .organization_stack import OrganizationStack

MANAGEMENT_ACCOUNT_ID = "645166163764"
CAMPPS_DEV_ACCOUNT_ID = "477152411873"
CAMPPS_PROD_ACCOUNT_ID = "431643435299"


class SSOStack(Stack):
    """
    AWS SSO (Identity Center) stack for Infiquetra LLC business structure.

    Creates permission sets and access patterns for:
    - Core services (Security, Logging, Shared Services)
    - Media business unit (Infiquetra Media, LLC)
    - Apps business unit (Infiquetra Apps, LLC)
    - Consulting business unit (Infiquetra Consulting, LLC)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        organization_stack: OrganizationStack,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.organization_stack = organization_stack

        # SSO Instance ARN from audit
        self.sso_instance_arn = "arn:aws:sso:::instance/ssoins-7223f05fc9da6e24"

        # Create permission sets for different roles and business units
        self.create_permission_sets()

        # Create optional SSO account assignments
        self.create_assignment_parameters()
        self.create_account_assignments()

        # Create outputs
        self.create_outputs()

    def create_permission_sets(self) -> None:
        """Create permission sets for role-based access across business units."""

        # Core Administrator - Full access for core infrastructure management
        self.core_admin_permission_set = sso.CfnPermissionSet(
            self,
            "CoreAdminPermissionSet",
            name="CoreAdministrator",
            description="Full administrative access for core infrastructure",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policies=["arn:aws:iam::aws:policy/AdministratorAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="CoreAdministrator"),
                cdk.CfnTag(key="BusinessUnit", value="Core"),
                cdk.CfnTag(key="AccessLevel", value="Full"),
            ],
        )

        # Security Auditor - Read-only access for security auditing
        self.security_auditor_permission_set = sso.CfnPermissionSet(
            self,
            "SecurityAuditorPermissionSet",
            name="SecurityAuditor",
            description="Read-only access for security auditing and compliance",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policies=[
                "arn:aws:iam::aws:policy/SecurityAudit",
                "arn:aws:iam::aws:policy/ReadOnlyAccess",
            ],
            tags=[
                cdk.CfnTag(key="Role", value="SecurityAuditor"),
                cdk.CfnTag(key="BusinessUnit", value="Core"),
                cdk.CfnTag(key="AccessLevel", value="ReadOnly"),
            ],
        )

        # Billing Manager - Billing and cost management access
        self.billing_manager_permission_set = sso.CfnPermissionSet(
            self,
            "BillingManagerPermissionSet",
            name="BillingManager",
            description="Billing and cost management access",
            instance_arn=self.sso_instance_arn,
            session_duration="PT12H",  # 12 hours
            managed_policies=["arn:aws:iam::aws:policy/job-function/Billing"],
            tags=[
                cdk.CfnTag(key="Role", value="BillingManager"),
                cdk.CfnTag(key="BusinessUnit", value="Core"),
                cdk.CfnTag(key="AccessLevel", value="Billing"),
            ],
        )

        # Media Developer - Development access for media workloads
        self.media_developer_permission_set = sso.CfnPermissionSet(
            self,
            "MediaDeveloperPermissionSet",
            name="MediaDeveloper",
            description="Development access for media content and branding workloads",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policies=["arn:aws:iam::aws:policy/PowerUserAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Media"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser"),
            ],
        )

        # Media Admin - Administrative access for media business unit
        self.media_admin_permission_set = sso.CfnPermissionSet(
            self,
            "MediaAdminPermissionSet",
            name="MediaAdministrator",
            description="Administrative access for Infiquetra Media, LLC resources",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policies=["arn:aws:iam::aws:policy/AdministratorAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="Administrator"),
                cdk.CfnTag(key="BusinessUnit", value="Media"),
                cdk.CfnTag(key="AccessLevel", value="Full"),
            ],
        )

        # Apps Developer - Development access for software products
        self.apps_developer_permission_set = sso.CfnPermissionSet(
            self,
            "AppsDeveloperPermissionSet",
            name="AppsDeveloper",
            description="Development access for software product development",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policies=["arn:aws:iam::aws:policy/PowerUserAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser"),
            ],
        )

        # Apps Admin - Administrative access for apps business unit
        self.apps_admin_permission_set = sso.CfnPermissionSet(
            self,
            "AppsAdminPermissionSet",
            name="AppsAdministrator",
            description="Administrative access for Infiquetra Apps, LLC resources",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policies=["arn:aws:iam::aws:policy/AdministratorAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="Administrator"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="AccessLevel", value="Full"),
            ],
        )

        # CAMPPS Developer - Specific access for CAMPPS workloads
        self.campps_developer_permission_set = sso.CfnPermissionSet(
            self,
            "CamppsDeveloperPermissionSet",
            name="CAMPPSDeveloper",
            description="Development access for CAMPPS application workloads",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policies=["arn:aws:iam::aws:policy/PowerUserAccess"],
            inline_policy=self.create_campps_developer_policy(),
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="Project", value="CAMPPS"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser"),
            ],
        )

        # CAMPPS Production Break-Glass Admin - Emergency production access
        self.campps_prod_breakglass_permission_set = sso.CfnPermissionSet(
            self,
            "CamppsProductionBreakGlassAdministratorPermissionSet",
            name="CAMPPSProductionBreakGlassAdministrator",
            description=(
                "Emergency administrative access for CAMPPS production workloads"
            ),
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policies=["arn:aws:iam::aws:policy/AdministratorAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="BreakGlassAdministrator"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="Project", value="CAMPPS"),
                cdk.CfnTag(key="Environment", value="Production"),
                cdk.CfnTag(key="AccessLevel", value="Full"),
            ],
        )

        # Consulting Developer - Development access for consulting projects
        self.consulting_developer_permission_set = sso.CfnPermissionSet(
            self,
            "ConsultingDeveloperPermissionSet",
            name="ConsultingDeveloper",
            description="Development access for consulting and contracting projects",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policies=["arn:aws:iam::aws:policy/PowerUserAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Consulting"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser"),
            ],
        )

        # Consulting Admin - Administrative access for consulting business unit
        self.consulting_admin_permission_set = sso.CfnPermissionSet(
            self,
            "ConsultingAdminPermissionSet",
            name="ConsultingAdministrator",
            description="Administrative access for Infiquetra Consulting, LLC",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policies=["arn:aws:iam::aws:policy/AdministratorAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="Administrator"),
                cdk.CfnTag(key="BusinessUnit", value="Consulting"),
                cdk.CfnTag(key="AccessLevel", value="Full"),
            ],
        )

        # Read-Only Access - For contractors and temporary access
        self.readonly_permission_set = sso.CfnPermissionSet(
            self,
            "ReadOnlyPermissionSet",
            name="ReadOnlyAccess",
            description="Read-only access for contractors and temporary users",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policies=["arn:aws:iam::aws:policy/ReadOnlyAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="ReadOnly"),
                cdk.CfnTag(key="AccessLevel", value="ReadOnly"),
            ],
        )

    def create_assignment_parameters(self) -> None:
        """Create optional group ID parameters for SSO assignments."""

        self.infiquetra_admins_group_id = CfnParameter(
            self,
            "InfiquetraAdminsGroupId",
            type="String",
            default="",
            description=(
                "Optional Identity Center group ID for Infiquetra administrators"
            ),
        )
        self.campps_developers_group_id = CfnParameter(
            self,
            "CamppsDevelopersGroupId",
            type="String",
            default="",
            description="Optional Identity Center group ID for CAMPPS developers",
        )
        self.campps_prod_readonly_group_id = CfnParameter(
            self,
            "CamppsProdReadOnlyGroupId",
            type="String",
            default="",
            description=(
                "Optional Identity Center group ID for CAMPPS production read-only "
                "access"
            ),
        )
        self.campps_prod_breakglass_admins_group_id = CfnParameter(
            self,
            "CamppsProdBreakGlassAdminsGroupId",
            type="String",
            default="",
            description=(
                "Optional Identity Center group ID for CAMPPS production break-glass "
                "administrators"
            ),
        )

        self.infiquetra_admins_group_id_provided = self.create_group_id_condition(
            "InfiquetraAdminsGroupIdProvided",
            self.infiquetra_admins_group_id,
        )
        self.campps_developers_group_id_provided = self.create_group_id_condition(
            "CamppsDevelopersGroupIdProvided",
            self.campps_developers_group_id,
        )
        self.campps_prod_readonly_group_id_provided = self.create_group_id_condition(
            "CamppsProdReadOnlyGroupIdProvided",
            self.campps_prod_readonly_group_id,
        )
        self.campps_prod_breakglass_admins_group_id_provided = (
            self.create_group_id_condition(
                "CamppsProdBreakGlassAdminsGroupIdProvided",
                self.campps_prod_breakglass_admins_group_id,
            )
        )

    def create_group_id_condition(
        self,
        condition_id: str,
        group_id_parameter: CfnParameter,
    ) -> CfnCondition:
        """Create condition for checking whether a group ID parameter was supplied."""

        return CfnCondition(
            self,
            condition_id,
            expression=Fn.condition_not(
                Fn.condition_equals(group_id_parameter.value_as_string, "")
            ),
        )

    def create_account_assignments(self) -> None:
        """Create optional SSO account assignments for configured groups."""

        assignments = [
            (
                "InfiquetraAdminsManagementAssignment",
                self.infiquetra_admins_group_id,
                MANAGEMENT_ACCOUNT_ID,
                self.core_admin_permission_set.attr_permission_set_arn,
                self.infiquetra_admins_group_id_provided,
            ),
            (
                "CamppsDevelopersDevAssignment",
                self.campps_developers_group_id,
                CAMPPS_DEV_ACCOUNT_ID,
                self.campps_developer_permission_set.attr_permission_set_arn,
                self.campps_developers_group_id_provided,
            ),
            (
                "CamppsDevelopersStagingAssignment",
                self.campps_developers_group_id,
                self.organization_stack.campps_staging_account.attr_account_id,
                self.campps_developer_permission_set.attr_permission_set_arn,
                self.campps_developers_group_id_provided,
            ),
            (
                "CamppsProdReadOnlyAssignment",
                self.campps_prod_readonly_group_id,
                CAMPPS_PROD_ACCOUNT_ID,
                self.readonly_permission_set.attr_permission_set_arn,
                self.campps_prod_readonly_group_id_provided,
            ),
            (
                "CamppsProdBreakGlassAdminAssignment",
                self.campps_prod_breakglass_admins_group_id,
                CAMPPS_PROD_ACCOUNT_ID,
                self.campps_prod_breakglass_permission_set.attr_permission_set_arn,
                self.campps_prod_breakglass_admins_group_id_provided,
            ),
        ]

        for (
            assignment_id,
            group_id,
            account_id,
            permission_set_arn,
            condition,
        ) in assignments:
            assignment = sso.CfnAssignment(
                self,
                assignment_id,
                instance_arn=self.sso_instance_arn,
                permission_set_arn=permission_set_arn,
                principal_id=group_id.value_as_string,
                principal_type="GROUP",
                target_id=account_id,
                target_type="AWS_ACCOUNT",
            )
            assignment.cfn_options.condition = condition

    def create_campps_developer_policy(self) -> dict:
        """Create inline policy for CAMPPS developers."""

        campps_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "CamppsResourceAccess",
                    "Effect": "Allow",
                    "Action": [
                        "s3:*",
                        "dynamodb:*",
                        "lambda:*",
                        "apigateway:*",
                        "cloudformation:*",
                        "cloudwatch:*",
                        "logs:*",
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringLike": {
                            "aws:RequestedRegion": ["us-east-1", "us-west-2"]
                        }
                    },
                },
                {
                    "Sid": "CamppsTaggedResourceAccess",
                    "Effect": "Allow",
                    "Action": "*",
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {"aws:ResourceTag/Project": "CAMPPS"}
                    },
                },
            ],
        }

        return campps_policy

    def create_outputs(self) -> None:
        """Create CloudFormation outputs for permission sets."""

        CfnOutput(
            self,
            "CoreAdminPermissionSetArn",
            value=self.core_admin_permission_set.attr_permission_set_arn,
            description="Core Administrator Permission Set ARN",
        )

        CfnOutput(
            self,
            "SecurityAuditorPermissionSetArn",
            value=self.security_auditor_permission_set.attr_permission_set_arn,
            description="Security Auditor Permission Set ARN",
        )

        CfnOutput(
            self,
            "BillingManagerPermissionSetArn",
            value=self.billing_manager_permission_set.attr_permission_set_arn,
            description="Billing Manager Permission Set ARN",
        )

        CfnOutput(
            self,
            "MediaDeveloperPermissionSetArn",
            value=self.media_developer_permission_set.attr_permission_set_arn,
            description="Media Developer Permission Set ARN",
        )

        CfnOutput(
            self,
            "MediaAdminPermissionSetArn",
            value=self.media_admin_permission_set.attr_permission_set_arn,
            description="Media Administrator Permission Set ARN",
        )

        CfnOutput(
            self,
            "AppsDeveloperPermissionSetArn",
            value=self.apps_developer_permission_set.attr_permission_set_arn,
            description="Apps Developer Permission Set ARN",
        )

        CfnOutput(
            self,
            "AppsAdminPermissionSetArn",
            value=self.apps_admin_permission_set.attr_permission_set_arn,
            description="Apps Administrator Permission Set ARN",
        )

        CfnOutput(
            self,
            "CamppsDeveloperPermissionSetArn",
            value=self.campps_developer_permission_set.attr_permission_set_arn,
            description="CAMPPS Developer Permission Set ARN",
        )

        CfnOutput(
            self,
            "CamppsProdBreakGlassPermissionSetArn",
            value=self.campps_prod_breakglass_permission_set.attr_permission_set_arn,
            description="CAMPPS Production Break-Glass Permission Set ARN",
        )

        CfnOutput(
            self,
            "ConsultingDeveloperPermissionSetArn",
            value=self.consulting_developer_permission_set.attr_permission_set_arn,
            description="Consulting Developer Permission Set ARN",
        )

        CfnOutput(
            self,
            "ConsultingAdminPermissionSetArn",
            value=self.consulting_admin_permission_set.attr_permission_set_arn,
            description="Consulting Administrator Permission Set ARN",
        )

        CfnOutput(
            self,
            "ReadOnlyPermissionSetArn",
            value=self.readonly_permission_set.attr_permission_set_arn,
            description="Read-Only Permission Set ARN",
        )

    @property
    def permission_sets(self) -> dict[str, str]:
        """Return permission set ARNs for use by other resources."""
        return {
            "core_admin": self.core_admin_permission_set.attr_permission_set_arn,
            "security_auditor": (
                self.security_auditor_permission_set.attr_permission_set_arn
            ),
            "billing_manager": (
                self.billing_manager_permission_set.attr_permission_set_arn
            ),
            "media_developer": (
                self.media_developer_permission_set.attr_permission_set_arn
            ),
            "media_admin": self.media_admin_permission_set.attr_permission_set_arn,
            "apps_developer": (
                self.apps_developer_permission_set.attr_permission_set_arn
            ),
            "apps_admin": self.apps_admin_permission_set.attr_permission_set_arn,
            "campps_developer": (
                self.campps_developer_permission_set.attr_permission_set_arn
            ),
            "campps_prod_breakglass": (
                self.campps_prod_breakglass_permission_set.attr_permission_set_arn
            ),
            "consulting_developer": (
                self.consulting_developer_permission_set.attr_permission_set_arn
            ),
            "consulting_admin": (
                self.consulting_admin_permission_set.attr_permission_set_arn
            ),
            "readonly": self.readonly_permission_set.attr_permission_set_arn,
        }
