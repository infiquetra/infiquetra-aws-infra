#!/usr/bin/env python3
"""Isolated CDK app for the management account's website publishing roles."""

from aws_cdk import App, Environment

from infiquetra_aws_infra.infiquetra_website_deploy_roles_stack import (
    MANAGEMENT_ACCOUNT_ID,
    InfiquetraWebsiteDeployRolesStack,
)

app = App()
InfiquetraWebsiteDeployRolesStack(
    app,
    "InfiquetraWebsiteDeployRolesStack",
    env=Environment(account=MANAGEMENT_ACCOUNT_ID, region="us-east-1"),
    description="GitHub Actions publishing roles for the Infiquetra websites",
)
app.synth()
