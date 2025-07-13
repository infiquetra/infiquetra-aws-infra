#!/usr/bin/env python3

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_sso as sso,
    aws_iam as iam,
    CfnOutput,
    Tags
)
from constructs import Construct
from typing import Dict, List, Optional
from .organization_stack import OrganizationStack


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
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.organization_stack = organization_stack
        
        # SSO Instance ARN from audit
        self.sso_instance_arn = "arn:aws:sso:::instance/ssoins-7223f05fc9da6e24"
        
        # Create permission sets for different roles and business units
        self.create_permission_sets()
        
        # Create outputs
        self.create_outputs()

    def create_permission_sets(self) -> None:
        """Create permission sets for role-based access across business units."""
        
        # Core Administrator - Full access for core infrastructure management
        self.core_admin_permission_set = sso.CfnPermissionSet(
            self, "CoreAdminPermissionSet",
            name="CoreAdministrator",
            description="Full administrative access for core infrastructure and security",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AdministratorAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="CoreAdministrator"),
                cdk.CfnTag(key="BusinessUnit", value="Core"),
                cdk.CfnTag(key="AccessLevel", value="Full")
            ]
        )
        
        # Security Auditor - Read-only access for security auditing
        self.security_auditor_permission_set = sso.CfnPermissionSet(
            self, "SecurityAuditorPermissionSet", 
            name="SecurityAuditor",
            description="Read-only access for security auditing and compliance",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/SecurityAudit",
                "arn:aws:iam::aws:policy/ReadOnlyAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="SecurityAuditor"),
                cdk.CfnTag(key="BusinessUnit", value="Core"),
                cdk.CfnTag(key="AccessLevel", value="ReadOnly")
            ]
        )
        
        # Billing Manager - Billing and cost management access
        self.billing_manager_permission_set = sso.CfnPermissionSet(
            self, "BillingManagerPermissionSet",
            name="BillingManager", 
            description="Billing and cost management access",
            instance_arn=self.sso_instance_arn,
            session_duration="PT12H",  # 12 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/job-function/Billing"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="BillingManager"),
                cdk.CfnTag(key="BusinessUnit", value="Core"),
                cdk.CfnTag(key="AccessLevel", value="Billing")
            ]
        )
        
        # Media Developer - Development access for media workloads
        self.media_developer_permission_set = sso.CfnPermissionSet(
            self, "MediaDeveloperPermissionSet",
            name="MediaDeveloper",
            description="Development access for media content and branding workloads",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/PowerUserAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Media"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser")
            ]
        )
        
        # Media Admin - Administrative access for media business unit
        self.media_admin_permission_set = sso.CfnPermissionSet(
            self, "MediaAdminPermissionSet",
            name="MediaAdministrator",
            description="Administrative access for Infiquetra Media, LLC resources",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AdministratorAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="Administrator"),
                cdk.CfnTag(key="BusinessUnit", value="Media"),
                cdk.CfnTag(key="AccessLevel", value="Full")
            ]
        )
        
        # Apps Developer - Development access for software products
        self.apps_developer_permission_set = sso.CfnPermissionSet(
            self, "AppsDeveloperPermissionSet",
            name="AppsDeveloper",
            description="Development access for software product development",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/PowerUserAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser")
            ]
        )
        
        # Apps Admin - Administrative access for apps business unit  
        self.apps_admin_permission_set = sso.CfnPermissionSet(
            self, "AppsAdminPermissionSet",
            name="AppsAdministrator",
            description="Administrative access for Infiquetra Apps, LLC resources",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AdministratorAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="Administrator"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="AccessLevel", value="Full")
            ]
        )
        
        # CAMPPS Developer - Specific access for CAMPPS workloads
        self.campps_developer_permission_set = sso.CfnPermissionSet(
            self, "CamppsDeveloperPermissionSet",
            name="CamppssDeveloper",
            description="Development access for CAMPPS application workloads",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/PowerUserAccess"
            ],
            inline_policy=self.create_campps_developer_policy(),
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="Project", value="CAMPPS"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser")
            ]
        )
        
        # Consulting Developer - Development access for consulting projects
        self.consulting_developer_permission_set = sso.CfnPermissionSet(
            self, "ConsultingDeveloperPermissionSet",
            name="ConsultingDeveloper",
            description="Development access for consulting and contracting projects",
            instance_arn=self.sso_instance_arn,
            session_duration="PT8H",  # 8 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/PowerUserAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="Developer"),
                cdk.CfnTag(key="BusinessUnit", value="Consulting"),
                cdk.CfnTag(key="AccessLevel", value="PowerUser")
            ]
        )
        
        # Consulting Admin - Administrative access for consulting business unit
        self.consulting_admin_permission_set = sso.CfnPermissionSet(
            self, "ConsultingAdminPermissionSet",
            name="ConsultingAdministrator",
            description="Administrative access for Infiquetra Consulting, LLC resources",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AdministratorAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="Administrator"),
                cdk.CfnTag(key="BusinessUnit", value="Consulting"),
                cdk.CfnTag(key="AccessLevel", value="Full")
            ]
        )
        
        # Read-Only Access - For contractors and temporary access
        self.readonly_permission_set = sso.CfnPermissionSet(
            self, "ReadOnlyPermissionSet",
            name="ReadOnlyAccess",
            description="Read-only access for contractors and temporary users",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",  # 4 hours
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/ReadOnlyAccess"
            ],
            tags=[
                cdk.CfnTag(key="Role", value="ReadOnly"),
                cdk.CfnTag(key="AccessLevel", value="ReadOnly")
            ]
        )

    def create_campps_developer_policy(self) -> str:
        """Create inline policy for CAMPPS developers with specific CAMPPS resource access."""
        
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
                        "logs:*"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringLike": {
                            "aws:RequestedRegion": ["us-east-1", "us-west-2"]
                        }
                    }
                },
                {
                    "Sid": "CamppsTaggedResourceAccess",
                    "Effect": "Allow", 
                    "Action": "*",
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "aws:ResourceTag/Project": "CAMPPS"
                        }
                    }
                }
            ]
        }
        
        return campps_policy

    def create_outputs(self) -> None:
        """Create CloudFormation outputs for permission sets."""
        
        CfnOutput(self, "CoreAdminPermissionSetArn",
                 value=self.core_admin_permission_set.attr_permission_set_arn,
                 description="Core Administrator Permission Set ARN")
        
        CfnOutput(self, "SecurityAuditorPermissionSetArn", 
                 value=self.security_auditor_permission_set.attr_permission_set_arn,
                 description="Security Auditor Permission Set ARN")
        
        CfnOutput(self, "BillingManagerPermissionSetArn",
                 value=self.billing_manager_permission_set.attr_permission_set_arn,
                 description="Billing Manager Permission Set ARN")
        
        CfnOutput(self, "MediaDeveloperPermissionSetArn",
                 value=self.media_developer_permission_set.attr_permission_set_arn,
                 description="Media Developer Permission Set ARN")
        
        CfnOutput(self, "MediaAdminPermissionSetArn",
                 value=self.media_admin_permission_set.attr_permission_set_arn,
                 description="Media Administrator Permission Set ARN")
        
        CfnOutput(self, "AppsDeveloperPermissionSetArn",
                 value=self.apps_developer_permission_set.attr_permission_set_arn,
                 description="Apps Developer Permission Set ARN")
        
        CfnOutput(self, "AppsAdminPermissionSetArn",
                 value=self.apps_admin_permission_set.attr_permission_set_arn,
                 description="Apps Administrator Permission Set ARN")
        
        CfnOutput(self, "CamppsDeveloperPermissionSetArn",
                 value=self.campps_developer_permission_set.attr_permission_set_arn,
                 description="CAMPPS Developer Permission Set ARN")
        
        CfnOutput(self, "ConsultingDeveloperPermissionSetArn",
                 value=self.consulting_developer_permission_set.attr_permission_set_arn,
                 description="Consulting Developer Permission Set ARN")
        
        CfnOutput(self, "ConsultingAdminPermissionSetArn",
                 value=self.consulting_admin_permission_set.attr_permission_set_arn,
                 description="Consulting Administrator Permission Set ARN")
        
        CfnOutput(self, "ReadOnlyPermissionSetArn",
                 value=self.readonly_permission_set.attr_permission_set_arn,
                 description="Read-Only Permission Set ARN")

    @property
    def permission_sets(self) -> Dict[str, str]:
        """Return permission set ARNs for use by other resources."""
        return {
            "core_admin": self.core_admin_permission_set.attr_permission_set_arn,
            "security_auditor": self.security_auditor_permission_set.attr_permission_set_arn,
            "billing_manager": self.billing_manager_permission_set.attr_permission_set_arn,
            "media_developer": self.media_developer_permission_set.attr_permission_set_arn,
            "media_admin": self.media_admin_permission_set.attr_permission_set_arn,
            "apps_developer": self.apps_developer_permission_set.attr_permission_set_arn,
            "apps_admin": self.apps_admin_permission_set.attr_permission_set_arn,
            "campps_developer": self.campps_developer_permission_set.attr_permission_set_arn,
            "consulting_developer": self.consulting_developer_permission_set.attr_permission_set_arn,
            "consulting_admin": self.consulting_admin_permission_set.attr_permission_set_arn,
            "readonly": self.readonly_permission_set.attr_permission_set_arn
        }