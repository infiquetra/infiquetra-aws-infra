"""Unit tests for the GitHub OIDC bootstrap stack."""

from collections.abc import Iterable

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from github_oidc_bootstrap.github_oidc_stack import GitHubOIDCStack


def synth_template() -> Template:
    app = App()
    stack = GitHubOIDCStack(
        app,
        "TestGitHubOIDCStack",
        env=Environment(account="123456789012", region="us-east-1"),
    )
    return Template.from_stack(stack)


def find_deploy_role(template: Template) -> dict:
    roles = template.find_resources("AWS::IAM::Role")
    for role in roles.values():
        if role["Properties"].get("RoleName") == "infiquetra-aws-infra-gha-role":
            return dict(role)
    raise AssertionError("infiquetra-aws-infra-gha-role not found")


def find_deploy_role_logical_id(template: Template) -> str:
    roles = template.find_resources("AWS::IAM::Role")
    for logical_id, role in roles.items():
        if role["Properties"].get("RoleName") == "infiquetra-aws-infra-gha-role":
            return logical_id
    raise AssertionError("infiquetra-aws-infra-gha-role not found")


def managed_policy_names(template: Template) -> set[str]:
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    return {
        policy["Properties"]["ManagedPolicyName"]
        for policy in policies.values()
        if "ManagedPolicyName" in policy["Properties"]
    }


def find_managed_policy_logical_id(template: Template, policy_name: str) -> str:
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    for logical_id, policy in policies.items():
        if policy["Properties"].get("ManagedPolicyName") == policy_name:
            return logical_id
    raise AssertionError(f"{policy_name} not found")


def normalize_actions(actions: str | Iterable[str] | None) -> tuple[str, ...]:
    if actions is None:
        return ()
    if isinstance(actions, str):
        return (actions.strip().lower(),)
    return tuple(action.strip().lower() for action in actions)


def find_github_oidc_provider_logical_ids(template: Template) -> set[str]:
    oidc_provider_resources = {
        **template.find_resources("AWS::IAM::OIDCProvider"),
        **template.find_resources("Custom::AWSCDKOpenIdConnectProvider"),
    }

    return {
        logical_id
        for logical_id, provider in oidc_provider_resources.items()
        if provider["Properties"].get("Url")
        == "https://token.actions.githubusercontent.com"
    }


def is_github_oidc_provider_reference(
    federated_principal: str | dict,
    oidc_provider_logical_ids: set[str],
) -> bool:
    if isinstance(federated_principal, str):
        return "token.actions.githubusercontent.com" in federated_principal

    if federated_principal.get("Ref") in oidc_provider_logical_ids:
        return True

    get_att = federated_principal.get("Fn::GetAtt")
    return isinstance(get_att, list) and get_att[0] in oidc_provider_logical_ids


def test_oidc_provider_creation() -> None:
    template = synth_template()

    template.has_resource_properties(
        "Custom::AWSCDKOpenIdConnectProvider",
        {
            "Url": "https://token.actions.githubusercontent.com",
            "ClientIDList": ["sts.amazonaws.com"],
        },
    )


def test_management_role_trust_is_repo_and_main_scoped() -> None:
    template = synth_template()
    deploy_role = find_deploy_role(template)
    oidc_provider_logical_ids = find_github_oidc_provider_logical_ids(template)
    statements = deploy_role["Properties"]["AssumeRolePolicyDocument"]["Statement"]

    assert len(statements) == 1
    statement = statements[0]
    assert statement["Effect"] == "Allow"
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert is_github_oidc_provider_reference(
        statement["Principal"]["Federated"], oidc_provider_logical_ids
    )
    assert statement["Condition"] == {
        "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": "repo:infiquetra/infiquetra-aws-infra:ref:refs/heads/main",
        }
    }


def test_management_role_has_only_foundation_deploy_policy() -> None:
    template = synth_template()
    deploy_role = find_deploy_role(template)
    policy_logical_id = find_managed_policy_logical_id(
        template, "infiquetra-aws-infra-gha-cdk-policy"
    )

    assert managed_policy_names(template) == {"infiquetra-aws-infra-gha-cdk-policy"}
    assert "Policies" not in deploy_role["Properties"]
    assert deploy_role["Properties"].get("ManagedPolicyArns") == [
        {"Ref": policy_logical_id}
    ]


def test_no_inline_policy_resources_attach_to_management_role() -> None:
    template = synth_template()
    deploy_role_logical_id = find_deploy_role_logical_id(template)
    inline_policies = template.find_resources("AWS::IAM::Policy")

    for policy in inline_policies.values():
        assert {"Ref": deploy_role_logical_id} not in policy["Properties"].get(
            "Roles", []
        )
        assert "infiquetra-aws-infra-gha-role" not in policy["Properties"].get(
            "Roles", []
        )


def test_management_role_policy_does_not_include_workload_admin_actions() -> None:
    workload_admin_services = {
        "lambda",
        "apigateway",
        "apigatewayv2",
        "dynamodb",
        "events",
        "route53",
    }
    template = synth_template()
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    policy_documents = [
        policy["Properties"]["PolicyDocument"] for policy in policies.values()
    ]

    for document in policy_documents:
        for statement in document["Statement"]:
            assert "NotAction" not in statement

    actions = {
        action
        for document in policy_documents
        for statement in document["Statement"]
        for action in normalize_actions(statement.get("Action"))
    }

    assert "*" not in actions
    assert not any(
        action.split(":", maxsplit=1)[0] in workload_admin_services
        for action in actions
    )
