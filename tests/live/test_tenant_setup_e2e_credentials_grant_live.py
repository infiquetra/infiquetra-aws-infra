"""Live check: tenant-setup's nonprod deploy role reads the consolidated store.

Runs ``simulate-principal-policy`` for the deploy role in the CAMPPS nonprod
account (OD-13, plan issue 164 unit U8). Read-only. Skips unless
``CAMPPS_LIVE_IAM_CHECK=1``; with it set, ``tests/live/conftest.py`` turns any
skip into a failure, and nothing here catches a credential error.

    env CAMPPS_LIVE_IAM_CHECK=1 AWS_PROFILE=campps-nonprod AWS_REGION=us-east-1 \\
        uv run pytest tests/live/test_tenant_setup_e2e_credentials_grant_live.py -q
"""

from __future__ import annotations

import os
from typing import Any

import boto3
import pytest

ACCOUNT_ID = "477152411873"
REGION = "us-east-1"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/campps-tenant-setup-nonprod-gha-deploy-role"
ACTION = "secretsmanager:GetSecretValue"
STORE_SECRET_ID = "campps/web-app/e2e/fixture"  # noqa: S105 - a name, not a value
WORKOS_API_KEY_SECRET_ID = "campps/identity-access/nonprod/workos/api-key"  # noqa: S105
PREVIOUS_STORE_ARN = (
    f"arn:aws:secretsmanager:{REGION}:{ACCOUNT_ID}:secret:"
    "campps/web-app/e2e/fixture-previous-Ab12xy"
)

pytestmark = pytest.mark.skipif(
    os.environ.get("CAMPPS_LIVE_IAM_CHECK") != "1",
    reason="live IAM check; set CAMPPS_LIVE_IAM_CHECK=1 with nonprod credentials",
)


@pytest.fixture(scope="module")
def session() -> Any:
    session = boto3.Session(region_name=REGION)
    account = session.client("sts").get_caller_identity()["Account"]
    assert account == ACCOUNT_ID, f"credentials are for {account}, not {ACCOUNT_ID}"
    return session


def secret_arn(session: Any, secret_id: str) -> str:
    arn: str = session.client("secretsmanager").describe_secret(SecretId=secret_id)[
        "ARN"
    ]
    return arn


def decision(session: Any, resource_arn: str) -> str:
    response = session.client("iam").simulate_principal_policy(
        PolicySourceArn=ROLE_ARN, ActionNames=[ACTION], ResourceArns=[resource_arn]
    )
    results = response["EvaluationResults"]
    assert len(results) == 1, results
    eval_decision: str = results[0]["EvalDecision"]
    return eval_decision


def test_deploy_role_reads_the_consolidated_store(session: Any) -> None:
    store_arn = secret_arn(session, STORE_SECRET_ID)
    assert decision(session, store_arn) == "allowed", store_arn


def test_deploy_role_reads_the_workos_api_key(session: Any) -> None:
    api_key_arn = secret_arn(session, WORKOS_API_KEY_SECRET_ID)
    assert decision(session, api_key_arn) == "allowed", api_key_arn


def test_deploy_role_cannot_read_a_previous_store(session: Any) -> None:
    assert decision(session, PREVIOUS_STORE_ARN) == "implicitDeny"
