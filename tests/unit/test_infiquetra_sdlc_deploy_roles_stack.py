"""Assertions for the public SDLC publishing roles' trust and permissions."""

from typing import Any

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from infiquetra_aws_infra import infiquetra_sdlc_deploy_roles_stack

MANAGEMENT_ACCOUNT = "645166163764"
REGION = "us-east-1"
OIDC_HOST = "token.actions.githubusercontent.com"
SUBJECT_PREFIX = "repo:infiquetra@232245665/infiquetra-sdlc@1195488988"
DEPLOY_ROLES = (
    (
        "InfiquetraSdlcPublicSiteNonprodDeployRole",
        "nonprod",
        "arn:aws:s3:::infiquetra-sdlc-public-nonprod-645166163764",
    ),
    (
        "InfiquetraSdlcPublicSiteDeployRole",
        "public-sdlc-pages",
        "arn:aws:s3:::infiquetra-sdlc-public-prod-645166163764",
    ),
)


@pytest.fixture(scope="module")
def template() -> Template:
    app = App(analytics_reporting=False)
    stack = infiquetra_sdlc_deploy_roles_stack.InfiquetraSdlcDeployRolesStack(
        app,
        "InfiquetraSdlcDeployRolesStack",
        env=Environment(account=MANAGEMENT_ACCOUNT, region=REGION),
    )
    return Template.from_stack(stack)


def role_properties(template: Template, role_name: str) -> dict[str, Any]:
    roles = template.find_resources(
        "AWS::IAM::Role", {"Properties": {"RoleName": role_name}}
    )
    assert len(roles) == 1, roles
    return dict(next(iter(roles.values()))["Properties"])


@pytest.mark.parametrize(("role_name", "environment", "bucket_arn"), DEPLOY_ROLES)
def test_role_has_only_the_expected_trust_and_permissions(
    template: Template, role_name: str, environment: str, bucket_arn: str
) -> None:
    properties = role_properties(template, role_name)
    subject = f"{SUBJECT_PREFIX}:environment:{environment}"

    assert properties["AssumeRolePolicyDocument"] == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": (
                        f"arn:aws:iam::{MANAGEMENT_ACCOUNT}:oidc-provider/{OIDC_HOST}"
                    ),
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        f"{OIDC_HOST}:aud": "sts.amazonaws.com",
                        f"{OIDC_HOST}:sub": subject,
                        f"{OIDC_HOST}:ref": "refs/heads/main",
                    },
                },
            },
        ],
    }
    assert "ManagedPolicyArns" not in properties
    assert properties["Policies"] == [
        {
            "PolicyName": "SdlcPublicSitePublishing",
            "PolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:ListBucket",
                        "Resource": bucket_arn,
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["s3:PutObject", "s3:DeleteObject"],
                        "Resource": f"{bucket_arn}/*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "cloudfront:CreateInvalidation",
                            "cloudfront:GetInvalidation",
                        ],
                        "Resource": (
                            f"arn:aws:cloudfront::{MANAGEMENT_ACCOUNT}:distribution/*"
                        ),
                        "Condition": {
                            "StringEquals": {
                                "aws:ResourceTag/Service": "infiquetra-sdlc",
                                "aws:ResourceTag/Environment": environment,
                            },
                        },
                    },
                ],
            },
        },
    ]


@pytest.mark.parametrize(
    ("role_name", "environment"), [role[:2] for role in DEPLOY_ROLES]
)
def test_trust_rejects_tokens_outside_the_repo_branch_and_environment(
    template: Template, role_name: str, environment: str
) -> None:
    trust = role_properties(template, role_name)["AssumeRolePolicyDocument"][
        "Statement"
    ]
    conditions = trust[0]["Condition"]["StringEquals"]
    audience_key = f"{OIDC_HOST}:aud"
    subject_key = f"{OIDC_HOST}:sub"
    ref_key = f"{OIDC_HOST}:ref"
    valid_claims = {
        audience_key: "sts.amazonaws.com",
        subject_key: f"{SUBJECT_PREFIX}:environment:{environment}",
        ref_key: "refs/heads/main",
    }
    assert all(valid_claims.get(key) == value for key, value in conditions.items())

    other_environment = "public-sdlc-pages" if environment == "nonprod" else "nonprod"
    rejected_claims = {
        "feature branch": valid_claims | {ref_key: "refs/heads/feature"},
        "pull request": valid_claims | {ref_key: "refs/pull/42/merge"},
        "fork": valid_claims
        | {subject_key: f"repo:fork@42/infiquetra-sdlc@43:environment:{environment}"},
        "subject without numeric IDs": valid_claims
        | {subject_key: f"repo:infiquetra/infiquetra-sdlc:environment:{environment}"},
        "subject without an environment": valid_claims
        | {subject_key: f"{SUBJECT_PREFIX}:ref:refs/heads/main"},
        "different environment": valid_claims
        | {subject_key: f"{SUBJECT_PREFIX}:environment:{other_environment}"},
        "wrong audience": valid_claims
        | {audience_key: "https://github.com/infiquetra"},
        "missing ref": {
            key: value for key, value in valid_claims.items() if key != ref_key
        },
    }
    for case, claims in rejected_claims.items():
        assert any(claims.get(key) != value for key, value in conditions.items()), case


def test_only_two_roles_are_created_and_both_arns_are_exported(
    template: Template,
) -> None:
    resources = template.to_json()["Resources"]
    assert len(resources) == 2
    assert {resource["Type"] for resource in resources.values()} == {"AWS::IAM::Role"}
    logical_ids = {
        resource["Properties"]["RoleName"]: logical_id
        for logical_id, resource in resources.items()
    }

    outputs = template.find_outputs("*")
    assert set(outputs) == {f"{role_name}Arn" for role_name, _, _ in DEPLOY_ROLES}
    for role_name, _, _ in DEPLOY_ROLES:
        output_name = f"{role_name}Arn"
        assert outputs[output_name]["Value"] == {
            "Fn::GetAtt": [logical_ids[role_name], "Arn"],
        }
        assert outputs[output_name]["Export"] == {"Name": output_name}


@pytest.mark.parametrize(
    ("account", "region"),
    [
        pytest.param("111111111111", REGION, id="wrong-account"),
        pytest.param(MANAGEMENT_ACCOUNT, "us-west-2", id="wrong-region"),
    ],
)
def test_stack_rejects_wrong_account_or_region(account: str, region: str) -> None:
    app = App(analytics_reporting=False)
    with pytest.raises(ValueError):
        stack = infiquetra_sdlc_deploy_roles_stack.InfiquetraSdlcDeployRolesStack(
            app,
            "InfiquetraSdlcDeployRolesStack",
            env=Environment(account=account, region=region),
        )
        Template.from_stack(stack)
