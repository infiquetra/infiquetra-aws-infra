#!/usr/bin/env python3
import os
import aws_cdk as cdk
from dotenv import load_dotenv

from infiquetra_organizations.organization_stack import OrganizationStack
from infiquetra_organizations.sso_stack import SSOStack

# Load environment variables
load_dotenv()

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "us-east-1")
)

# Create the main organization stack
organization_stack = OrganizationStack(
    app, 
    "InfiquetraOrganizationStack",
    env=env,
    description="AWS Organizations structure for Infiquetra LLC"
)

# Create the SSO stack
sso_stack = SSOStack(
    app,
    "InfiquetraSSOStack",
    env=env,
    description="AWS SSO configuration for Infiquetra LLC",
    # Make SSO stack depend on organization stack
    organization_stack=organization_stack
)

app.synth()