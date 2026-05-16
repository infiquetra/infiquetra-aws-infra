#!/usr/bin/env python3
"""CDK app for bootstrapping CAMPPS workload-account deploy roles."""

from aws_cdk import App, Environment
from dotenv import load_dotenv

from infiquetra_aws_infra.campps_deploy_roles_stack import (
    CAMPPS_NONPROD_ACCOUNT_ID,
    CAMPPS_PROD_ACCOUNT_ID,
    CAMPPS_STAGING_ACCOUNT_ID,
    CamppsDeployRolesStack,
)

load_dotenv()

app = App()

CamppsDeployRolesStack(
    app,
    "CamppsNonProdDeployRolesStack",
    target_environment="nonprod",
    env=Environment(account=CAMPPS_NONPROD_ACCOUNT_ID, region="us-east-1"),
    description="GitHub Actions deploy roles for CAMPPS nonprod workload account",
)

CamppsDeployRolesStack(
    app,
    "CamppsStagingDeployRolesStack",
    target_environment="staging",
    env=Environment(account=CAMPPS_STAGING_ACCOUNT_ID, region="us-east-1"),
    description="GitHub Actions deploy roles for CAMPPS staging workload account",
)

CamppsDeployRolesStack(
    app,
    "CamppsProductionDeployRolesStack",
    target_environment="production",
    env=Environment(account=CAMPPS_PROD_ACCOUNT_ID, region="us-east-1"),
    description="GitHub Actions deploy roles for CAMPPS production workload account",
)

app.synth()
