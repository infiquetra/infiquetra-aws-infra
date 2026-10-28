#!/usr/bin/env python3
"""Synthesize only the existing nonproduction deploy-roles stack."""

from aws_cdk import App, Environment

from infiquetra_aws_infra.campps_deploy_roles_stack import (
    CAMPPS_NONPROD_ACCOUNT_ID,
    CamppsDeployRolesStack,
)

app = App()
CamppsDeployRolesStack(
    app,
    "CamppsNonProdDeployRolesStack",
    target_environment="nonprod",
    env=Environment(account=CAMPPS_NONPROD_ACCOUNT_ID, region="us-east-1"),
    description="GitHub Actions deploy roles for CAMPPS nonprod workload account",
)
app.synth()
