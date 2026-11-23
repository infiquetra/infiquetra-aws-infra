#!/usr/bin/env python3
"""Isolated CDK app for the public SDLC site's publishing roles."""

from aws_cdk import App, Environment

from infiquetra_aws_infra.infiquetra_sdlc_deploy_roles_stack import (
    MANAGEMENT_ACCOUNT_ID,
    MANAGEMENT_REGION,
    InfiquetraSdlcDeployRolesStack,
)

app = App(analytics_reporting=False)
InfiquetraSdlcDeployRolesStack(
    app,
    "InfiquetraSdlcDeployRolesStack",
    env=Environment(account=MANAGEMENT_ACCOUNT_ID, region=MANAGEMENT_REGION),
    description="GitHub Actions publishing roles for the public Infiquetra SDLC site",
)
app.synth()
