"""Assertions for the website publish roles' trust and permission boundaries."""

from typing import Any

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from infiquetra_aws_infra.infiquetra_website_deploy_roles_stack import (
    InfiquetraWebsiteDeployRolesStack,
)

OIDC_HOST = "token.actions.githubusercontent.com"
SUBJECT_PREFIX = "repo:infiquetra@232245665/infiquetra-website@1366920096"
DEPLOY_ROLES = (
    (
        "InfiquetraWebsiteNonprodDeployRole",
        "nonprod",
        [
            "arn:aws:s3:::infiquetra-llc-website-nonprod-645166163764",
            "arn:aws:s3:::infiquetra-software-llc-website-nonprod-645166163764",
        ],
    ),
    (
        "InfiquetraWebsiteDeployRole",
        "production",
        [
            "arn:aws:s3:::infiquetra-llc-website-prod-645166163764",
            "arn:aws:s3:::infiquetra-software-llc-website-prod-645166163764",
        ],
    ),
)


@pytest.fixture(scope="module")
def template() -> Template:
    app = App(analytics_reporting=False)
    stack = InfiquetraWebsiteDeployRolesStack(
        app,
        "InfiquetraWebsiteDeployRolesStack",
        env=Environment(account="645166163764", region="us-east-1"),
    )
    return Template.from_stack(stack)


def role_properties(template: Template, role_name: str) -> dict[str, Any]:
    roles = template.find_resources(
        "AWS::IAM::Role", {"Properties": {"RoleName": role_name}}
    )
    assert len(roles) == 1, roles
    return dict(next(iter(roles.values()))["Properties"])


@pytest.mark.parametrize(("role_name", "environment", "bucket_arns"), DEPLOY_ROLES)
def test_role_has_only_the_expected_trust_and_permissions(
    template: Template, role_name: str, environment: str, bucket_arns: list[str]
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
                        "arn:aws:iam::645166163764:"
                        "oidc-provider/token.actions.githubusercontent.com"
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
            "PolicyName": "WebsitePublishing",
            "PolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:ListBucket",
                        "Resource": bucket_arns,
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["s3:PutObject", "s3:DeleteObject"],
                        "Resource": [f"{arn}/*" for arn in bucket_arns],
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "cloudfront:CreateInvalidation",
                            "cloudfront:GetInvalidation",
                        ],
                        "Resource": "arn:aws:cloudfront::645166163764:distribution/*",
                        "Condition": {
                            "StringEquals": {
                                "aws:ResourceTag/Service": "infiquetra-website",
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
    valid_claims = {
        f"{OIDC_HOST}:aud": "sts.amazonaws.com",
        f"{OIDC_HOST}:sub": f"{SUBJECT_PREFIX}:environment:{environment}",
        f"{OIDC_HOST}:ref": "refs/heads/main",
    }
    assert all(valid_claims.get(key) == value for key, value in conditions.items())

    opposite_environment = "production" if environment == "nonprod" else "nonprod"
    for rejected_claims in (
        valid_claims | {f"{OIDC_HOST}:ref": "refs/heads/feature"},
        valid_claims | {f"{OIDC_HOST}:ref": "refs/pull/42/merge"},
        valid_claims
        | {
            f"{OIDC_HOST}:sub": (
                f"repo:fork@42/infiquetra-website@43:environment:{environment}"
            )
        },
        valid_claims | {f"{OIDC_HOST}:sub": f"{SUBJECT_PREFIX}:ref:refs/heads/main"},
        valid_claims
        | {f"{OIDC_HOST}:sub": f"{SUBJECT_PREFIX}:environment:{opposite_environment}"},
        valid_claims | {f"{OIDC_HOST}:aud": "https://github.com/infiquetra"},
        {
            key: value
            for key, value in valid_claims.items()
            if key != f"{OIDC_HOST}:ref"
        },
    ):
        assert any(
            rejected_claims.get(key) != value for key, value in conditions.items()
        )


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
