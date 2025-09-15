#!/usr/bin/env python3
"""
GitHub OIDC Bootstrap CDK App

This CDK application creates the necessary GitHub OIDC provider and IAM role
for the infiquetra/infiquetra-organizations repository to deploy CDK stacks
in the primary Infiquetra AWS account (645166163764).
"""

import os

import aws_cdk as cdk
from dotenv import load_dotenv

from github_oidc_bootstrap.github_oidc_stack import GitHubOIDCStack

# Load environment variables
load_dotenv()

app = cdk.App()

# Account configuration from environment or CDK context
PRIMARY_ACCOUNT = os.environ.get(
    "CDK_DEFAULT_ACCOUNT", app.node.try_get_context("account")
)
DEFAULT_REGION = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")

if not PRIMARY_ACCOUNT:
    raise ValueError(
        "Account ID must be provided via CDK_DEFAULT_ACCOUNT environment variable "
        "or 'account' context parameter"
    )

env = cdk.Environment(
    account=PRIMARY_ACCOUNT,
    region=DEFAULT_REGION,
)

# Create the GitHub OIDC stack
github_oidc_stack = GitHubOIDCStack(
    app,
    "GitHubOIDCBootstrap",
    env=env,
    description="GitHub OIDC provider and roles for infiquetra-organizations repository",
)

# Add tags for resource management
cdk.Tags.of(app).add("Project", "Infiquetra Organizations")
cdk.Tags.of(app).add("Environment", "Bootstrap")
cdk.Tags.of(app).add("ManagedBy", "CDK")

app.synth()
