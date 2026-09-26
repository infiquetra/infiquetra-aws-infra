#!/usr/bin/env python3
"""Isolated CDK app for home-lab Forge monitoring IAM roles."""

import os

from aws_cdk import App, Environment
from dotenv import load_dotenv

from infiquetra_aws_infra.heimdall_monitoring_stack import (
    WORKLOAD_ACCOUNTS,
    HeimdallMonitoringManagementStack,
    HeimdallMonitoringWorkloadStack,
)

load_dotenv()

management_account_id = os.getenv("HEIMDALL_MONITORING_MANAGEMENT_ACCOUNT_ID")
if not management_account_id:
    management_account_id = os.getenv("CDK_DEFAULT_ACCOUNT", "")
if not (management_account_id.isdecimal() and len(management_account_id) == 12):
    raise ValueError("A 12-digit management account ID is required")
if management_account_id in WORKLOAD_ACCOUNTS.values():
    raise ValueError("Management and workload accounts must be distinct")
if len(set(WORKLOAD_ACCOUNTS.values())) != len(WORKLOAD_ACCOUNTS):
    raise ValueError("Each workload monitoring stack needs a distinct account")

region = os.getenv("CDK_DEFAULT_REGION", "us-east-1")
app = App()

HeimdallMonitoringManagementStack(
    app,
    "HeimdallMonitoringManagementStack",
    env=Environment(account=management_account_id, region=region),
)
for environment, account_id in WORKLOAD_ACCOUNTS.items():
    HeimdallMonitoringWorkloadStack(
        app,
        f"HeimdallMonitoring{environment.capitalize()}Stack",
        management_account_id=management_account_id,
        env=Environment(account=account_id, region=region),
    )

app.synth()
