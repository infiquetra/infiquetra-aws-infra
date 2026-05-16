"""Unit tests for CAMPPS service deploy role generation."""

import json
from collections.abc import Iterable
from typing import Any

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from infiquetra_aws_infra.campps_deploy_roles_stack import CamppsDeployRolesStack
from infiquetra_aws_infra.campps_service_registry import (
    CAMPPS_SERVICE_REPOSITORIES,
    DeployEnvironment,
    ServiceRepository,
)

DEPLOY_ENVIRONMENTS: tuple[DeployEnvironment, ...] = (
    "nonprod",
    "staging",
    "production",
)


def synth_template(target_environment: DeployEnvironment = "nonprod") -> Template:
    return synth_template_for_repositories(
        ServiceRepository(
            name="tenant-setup",
            repository="infiquetra/campps-tenant-setup-service",
        ),
        target_environment=target_environment,
    )


def synth_template_for_repositories(
    *service_repositories: ServiceRepository,
    target_environment: DeployEnvironment = "nonprod",
) -> Template:
    app = App()
    stack = CamppsDeployRolesStack(
        app,
        "TestCamppsDeployRolesStack",
        target_environment=target_environment,
        service_repositories=service_repositories,
        env=Environment(account="477152411873", region="us-east-1"),
    )
    return Template.from_stack(stack)


def find_deploy_role(template: Template, role_name: str) -> dict[str, Any]:
    roles = template.find_resources("AWS::IAM::Role")
    matching_roles = [
        role
        for role in roles.values()
        if role.get("Properties", {}).get("RoleName") == role_name
    ]

    assert len(matching_roles) == 1, roles
    return dict(matching_roles[0])


def get_assume_role_statement(role: dict[str, Any]) -> dict[str, Any]:
    statements = role["Properties"]["AssumeRolePolicyDocument"]["Statement"]

    assert len(statements) == 1, statements
    assert statements[0].get("Action") == "sts:AssumeRoleWithWebIdentity"
    return dict(statements[0])


def assert_deploy_role_trust(
    template: Template,
    *,
    role_name: str,
    target_environment: str,
) -> None:
    role = find_deploy_role(template, role_name)
    statement = get_assume_role_statement(role)

    assert statement["Effect"] == "Allow"
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"

    string_equals = statement["Condition"]["StringEquals"]
    assert (
        string_equals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    )
    assert string_equals["token.actions.githubusercontent.com:sub"] == (
        f"repo:infiquetra/campps-tenant-setup-service:environment:{target_environment}"
    )

    principal = statement["Principal"]
    assert "Federated" in principal


def normalize_actions(actions: Any) -> Iterable[str]:
    if isinstance(actions, str):
        return (actions,)

    if isinstance(actions, Iterable):
        return tuple(actions)

    return ()


def normalize_resources(resources: Any) -> Iterable[str]:
    if isinstance(resources, str):
        return (resources,)

    if isinstance(resources, Iterable):
        return tuple(resources)

    return ()


def policy_documents(template: Template) -> Iterable[dict[str, Any]]:
    managed_policies = template.find_resources("AWS::IAM::ManagedPolicy")
    for policy in managed_policies.values():
        yield policy["Properties"]["PolicyDocument"]

    roles = template.find_resources("AWS::IAM::Role")
    for role in roles.values():
        for policy in role.get("Properties", {}).get("Policies", []):
            yield policy["PolicyDocument"]

    policies = template.find_resources("AWS::IAM::Policy")
    for policy in policies.values():
        yield policy["Properties"]["PolicyDocument"]


def managed_policy_document_sizes(template: Template) -> dict[str, int]:
    managed_policies = template.find_resources("AWS::IAM::ManagedPolicy")
    return {
        policy["Properties"].get("ManagedPolicyName", logical_id): len(
            json.dumps(
                policy["Properties"]["PolicyDocument"],
                separators=(",", ":"),
            )
        )
        for logical_id, policy in managed_policies.items()
    }


def test_default_registry_includes_tenant_setup_service() -> None:
    assert (
        ServiceRepository(
            name="tenant-setup",
            repository="infiquetra/campps-tenant-setup-service",
            environments=("nonprod", "staging", "production"),
        ),
    ) == CAMPPS_SERVICE_REPOSITORIES


def test_deploy_role_uses_service_and_environment_name() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-tenant-setup-nonprod-gha-deploy-role"},
    )


def test_managed_policy_documents_fit_iam_size_limit() -> None:
    policy_sizes: dict[str, dict[str, int]] = {}

    for environment in DEPLOY_ENVIRONMENTS:
        template = synth_template(target_environment=environment)
        policy_sizes[environment] = managed_policy_document_sizes(template)

    violations = {
        environment: {
            policy_name: size
            for policy_name, size in environment_sizes.items()
            if size > 6144
        }
        for environment, environment_sizes in policy_sizes.items()
    }

    assert not any(violations.values()), violations


def test_deploy_role_trust_is_exact_repo_and_environment() -> None:
    template = synth_template()

    assert_deploy_role_trust(
        template,
        role_name="campps-tenant-setup-nonprod-gha-deploy-role",
        target_environment="nonprod",
    )


def test_production_role_uses_production_environment_subject() -> None:
    template = synth_template(target_environment="production")

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-tenant-setup-production-gha-deploy-role"},
    )
    assert_deploy_role_trust(
        template,
        role_name="campps-tenant-setup-production-gha-deploy-role",
        target_environment="production",
    )


def test_staging_role_uses_staging_environment_subject() -> None:
    template = synth_template(target_environment="staging")

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-tenant-setup-staging-gha-deploy-role"},
    )
    assert_deploy_role_trust(
        template,
        role_name="campps-tenant-setup-staging-gha-deploy-role",
        target_environment="staging",
    )


def test_deploy_policy_includes_scoped_cdk_change_set_access() -> None:
    template = synth_template()
    change_set_statements: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            resources = statement.get("Resource", [])
            if "cdk-deploy-change-set/*" not in str(resources):
                continue

            change_set_statements.append(statement)
            if any(resource == "*" for resource in normalize_resources(resources)):
                violations.append(statement)

    assert change_set_statements
    assert not violations, violations


def test_deploy_policy_excludes_organization_and_sso_actions() -> None:
    template = synth_template()
    forbidden_service_prefixes = ("organizations", "sso", "sso-admin", "identitystore")
    forbidden_actions: list[str] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            assert "NotAction" not in statement, statement

            for action in normalize_actions(statement.get("Action", [])):
                normalized_action = action.strip().lower()
                service_prefix = normalized_action.split(":", maxsplit=1)[0]
                uses_forbidden_service = service_prefix in forbidden_service_prefixes
                if "*" in normalized_action or uses_forbidden_service:
                    forbidden_actions.append(action)

    assert not forbidden_actions, forbidden_actions


def test_sensitive_mutating_actions_do_not_use_unscoped_wildcard_resources() -> None:
    template = synth_template()
    sensitive_services = {
        "cloudformation",
        "dynamodb",
        "events",
        "iam",
        "kms",
        "lambda",
        "logs",
        "s3",
        "secretsmanager",
        "sqs",
        "ssm",
    }
    read_only_verbs = (
        "describe",
        "get",
        "list",
    )
    wildcard_resource_allowlist = {
        "cloudformation:validatetemplate": False,
        "kms:createkey": True,
        "ssm:describeparameters": True,
    }
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            resources = tuple(normalize_resources(statement.get("Resource", [])))
            if "*" not in resources:
                continue

            conditions = statement.get("Condition", {})
            for action in normalize_actions(statement.get("Action", [])):
                normalized_action = action.strip().lower()
                service_prefix, action_name = normalized_action.split(":", maxsplit=1)
                writes_account_metric_namespace = (
                    normalized_action == "cloudwatch:putmetricdata"
                )
                is_sensitive_mutating_action = (
                    service_prefix in sensitive_services
                    and not action_name.startswith(read_only_verbs)
                    and not writes_account_metric_namespace
                )
                if not is_sensitive_mutating_action:
                    continue

                requires_condition = wildcard_resource_allowlist.get(normalized_action)
                if requires_condition is None:
                    violations.append({"action": action, "statement": statement})
                    continue

                if requires_condition and not conditions:
                    violations.append({"action": action, "statement": statement})

    assert not violations, violations


def test_cdk_assets_access_is_pinned_to_workload_bootstrap_bucket() -> None:
    template = synth_template()
    bucket_management_actions = {
        "s3:createbucket",
        "s3:deleteobject",
        "s3:putbucketencryption",
        "s3:putbucketpolicy",
        "s3:putbucketpublicaccessblock",
        "s3:putbucketversioning",
    }
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if normalized_actions & bucket_management_actions:
                violations.append(statement)
                continue

            if any(action.startswith("s3:") for action in normalized_actions):
                resources = tuple(normalize_resources(statement.get("Resource", [])))
                broad_resources = {"*", "arn:aws:s3:::cdk-*"}
                if any(resource in broad_resources for resource in resources):
                    violations.append(statement)

    assert not violations, violations


def test_api_gateway_write_actions_are_tag_constrained() -> None:
    template = synth_template()
    api_gateway_write_actions = {
        "apigateway:delete",
        "apigateway:patch",
        "apigateway:post",
        "apigateway:put",
    }
    create_statements: list[dict[str, Any]] = []
    steady_state_statements: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if normalized_actions.isdisjoint(api_gateway_write_actions):
                continue

            conditions = statement.get("Condition", {})
            string_equals = conditions.get("StringEquals", {})
            if string_equals == {
                "aws:RequestTag/Service": "tenant-setup",
                "aws:RequestTag/Environment": "nonprod",
            }:
                create_statements.append(statement)
                if conditions.get("ForAllValues:StringEquals") != {
                    "aws:TagKeys": ["Service", "Environment"]
                }:
                    violations.append(statement)
                if "/restapis" not in str(statement.get("Resource")):
                    violations.append(statement)
                continue

            if string_equals == {
                "aws:ResourceTag/Service": "tenant-setup",
                "aws:ResourceTag/Environment": "nonprod",
            }:
                steady_state_statements.append(statement)
                continue

            violations.append(statement)

    assert create_statements
    assert steady_state_statements
    assert not violations, violations


def test_api_gateway_reads_include_rest_api_collection() -> None:
    template = synth_template()
    read_statements: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if normalized_actions == {"apigateway:get"}:
                read_statements.append(statement)

    assert read_statements
    assert any(
        "/restapis" in str(statement.get("Resource")) for statement in read_statements
    )


def test_app_permissions_boundary_is_created_for_service_roles() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::ManagedPolicy",
        {"ManagedPolicyName": ("campps-tenant-setup-nonprod-permissions-boundary")},
    )


def test_iam_mutation_cannot_target_deploy_identity_resources() -> None:
    template = synth_template()
    deploy_identity_fragments = (
        "campps-tenant-setup-nonprod-gha-deploy-role",
        "campps-tenant-setup-nonprod-gha-deploy-policy",
        "campps-tenant-setup-nonprod-permissions-boundary",
    )
    iam_mutation_actions = {
        "iam:attachrolepolicy",
        "iam:createpolicyversion",
        "iam:putrolepolicy",
        "iam:setdefaultpolicyversion",
        "iam:updateassumerolepolicy",
    }
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if normalized_actions.isdisjoint(iam_mutation_actions):
                continue

            for resource in normalize_resources(statement.get("Resource", [])):
                if any(fragment in resource for fragment in deploy_identity_fragments):
                    violations.append({"resource": resource, "statement": statement})

    assert not violations, violations


def test_app_roles_require_permissions_boundary() -> None:
    template = synth_template()
    create_role_statements: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if "iam:createrole" in normalized_actions:
                create_role_statements.append(statement)

    assert create_role_statements
    for statement in create_role_statements:
        assert statement["Resource"] == {
            "Fn::Join": [
                "",
                [
                    "arn:",
                    {"Ref": "AWS::Partition"},
                    ":iam::477152411873:role/campps-tenant-setup-nonprod-app-*",
                ],
            ]
        }
        boundary_condition = statement["Condition"]["StringEquals"][
            "iam:PermissionsBoundary"
        ]
        assert boundary_condition == {
            "Ref": next(
                logical_id
                for logical_id, policy in template.find_resources(
                    "AWS::IAM::ManagedPolicy"
                ).items()
                if policy["Properties"].get("ManagedPolicyName")
                == "campps-tenant-setup-nonprod-permissions-boundary"
            )
        }


def test_only_create_role_uses_permissions_boundary_condition() -> None:
    template = synth_template()
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            condition = statement.get("Condition", {})
            if "iam:PermissionsBoundary" not in condition.get("StringEquals", {}):
                continue

            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if normalized_actions != {"iam:createrole"}:
                violations.append(statement)

    assert not violations, violations


def test_attach_role_policy_is_limited_to_service_app_policies() -> None:
    template = synth_template()
    attach_policy_statements: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if "iam:attachrolepolicy" in normalized_actions:
                attach_policy_statements.append(statement)

    assert attach_policy_statements
    for statement in attach_policy_statements:
        assert statement["Condition"]["ArnLike"]["iam:PolicyARN"] == {
            "Fn::Join": [
                "",
                [
                    "arn:",
                    {"Ref": "AWS::Partition"},
                    ":iam::477152411873:policy/campps-tenant-setup-nonprod-app-*",
                ],
            ]
        }


def test_pass_role_is_scoped_to_serverless_services() -> None:
    template = synth_template()
    pass_role_statements: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if "iam:passrole" in normalized_actions:
                pass_role_statements.append(statement)

    assert pass_role_statements
    for statement in pass_role_statements:
        resources = tuple(normalize_resources(statement.get("Resource", [])))
        assert "*" not in resources
        assert all("-gha-deploy-" not in resource for resource in resources)
        assert all("permissions-boundary" not in resource for resource in resources)
        assert statement["Condition"]["StringEquals"]["iam:PassedToService"] == [
            "apigateway.amazonaws.com",
            "cloudformation.amazonaws.com",
            "events.amazonaws.com",
            "lambda.amazonaws.com",
        ]


def test_lambda_permission_grants_are_limited_to_serverless_principals() -> None:
    template = synth_template()
    grant_statements: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if "lambda:addpermission" not in normalized_actions:
                continue

            grant_statements.append(statement)
            if statement["Condition"]["StringEquals"].get("lambda:Principal") != [
                "apigateway.amazonaws.com",
                "events.amazonaws.com",
            ]:
                violations.append(statement)

    assert grant_statements
    assert not violations, violations


def test_cdk_bootstrap_version_read_is_scoped_to_bootstrap_parameter() -> None:
    template = synth_template()
    bootstrap_statements: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized_actions = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            resource = statement.get("Resource", [])
            if "cdk-bootstrap/hnb659fds/version" not in str(resource):
                continue

            bootstrap_statements.append(statement)
            if normalized_actions != {"ssm:getparameter"}:
                violations.append(statement)
            if resource == "*":
                violations.append(statement)

    assert bootstrap_statements
    assert not violations, violations


def test_stack_creates_oidc_provider_for_workload_account() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::OIDCProvider",
        {
            "Url": "https://token.actions.githubusercontent.com",
            "ClientIdList": ["sts.amazonaws.com"],
        },
    )
