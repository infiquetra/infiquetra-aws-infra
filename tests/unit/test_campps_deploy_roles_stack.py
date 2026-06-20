"""Unit tests for CAMPPS service deploy role generation."""

import json
from collections.abc import Iterable
from typing import Any

import pytest
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
            name="identity-access",
            repository="infiquetra/campps-identity-access",
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
        f"repo:infiquetra/campps-identity-access:environment:{target_environment}"
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


# The canonical CAMPPS deployable set, grounded in campps-context-library
# phase-1a-build-program.md (KTD1): 10 serverless-api backends + the web-app
# frontend. Membership equality is asserted exactly so adding/removing a
# service is a deliberate, reviewed change.
CANONICAL_SERVICE_REPOSITORIES: tuple[ServiceRepository, ...] = (
    ServiceRepository(
        name="platform",
        repository="infiquetra/campps-platform",
        deploy_profile="platform-foundation",
    ),
    ServiceRepository(
        name="contracts",
        repository="infiquetra/campps-contracts",
        deploy_profile="codeartifact-publish",
    ),
    ServiceRepository(
        name="identity-access",
        repository="infiquetra/campps-identity-access",
    ),
    ServiceRepository(
        name="tenant-setup",
        repository="infiquetra/campps-tenant-setup",
    ),
    ServiceRepository(
        name="coppa-consent",
        repository="infiquetra/campps-coppa-consent",
    ),
    ServiceRepository(
        name="registration",
        repository="infiquetra/campps-registration",
    ),
    ServiceRepository(
        name="payments",
        repository="infiquetra/campps-payments",
    ),
    ServiceRepository(
        name="health-forms",
        repository="infiquetra/campps-health-forms",
    ),
    ServiceRepository(
        name="activities-achievements",
        repository="infiquetra/campps-activities-achievements",
    ),
    ServiceRepository(
        name="staff-management",
        repository="infiquetra/campps-staff-management",
    ),
    ServiceRepository(
        name="web-app",
        repository="infiquetra/campps-web-app",
        deploy_profile="web-app",
    ),
)

# The 10 deployable backends are all serverless-api except the two
# special-profile services (platform, contracts).
EXPECTED_SERVERLESS_API_BACKENDS = frozenset(
    {
        "identity-access",
        "tenant-setup",
        "coppa-consent",
        "registration",
        "payments",
        "health-forms",
        "activities-achievements",
        "staff-management",
    }
)


def test_registry_membership_equals_canonical_set() -> None:
    assert CAMPPS_SERVICE_REPOSITORIES == CANONICAL_SERVICE_REPOSITORIES


def test_registry_has_ten_backends_plus_web_app() -> None:
    backends = [
        service
        for service in CAMPPS_SERVICE_REPOSITORIES
        if service.deploy_profile != "web-app"
    ]
    web_apps = [
        service
        for service in CAMPPS_SERVICE_REPOSITORIES
        if service.deploy_profile == "web-app"
    ]

    assert len(backends) == 10, [service.name for service in backends]
    assert [service.name for service in web_apps] == ["web-app"]


def test_every_service_repository_targets_all_three_environments() -> None:
    for service in CAMPPS_SERVICE_REPOSITORIES:
        assert service.environments == ("nonprod", "staging", "production"), service


def test_serverless_api_backends_use_default_profile() -> None:
    serverless_backends = {
        service.name
        for service in CAMPPS_SERVICE_REPOSITORIES
        if service.deploy_profile == "serverless-api"
    }
    assert serverless_backends == EXPECTED_SERVERLESS_API_BACKENDS


def test_deploy_role_uses_service_and_environment_name() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-identity-access-nonprod-gha-deploy-role"},
    )


PROFILE_REPRESENTATIVE_REPOSITORIES: tuple[ServiceRepository, ...] = (
    ServiceRepository(
        name="identity-access",
        repository="infiquetra/campps-identity-access",
    ),
    ServiceRepository(
        name="platform",
        repository="infiquetra/campps-platform",
        deploy_profile="platform-foundation",
    ),
    ServiceRepository(
        name="contracts",
        repository="infiquetra/campps-contracts",
        deploy_profile="codeartifact-publish",
    ),
)

IAM_MANAGED_POLICY_SIZE_LIMIT = 6144


def test_managed_policy_documents_fit_iam_size_limit() -> None:
    policy_sizes: dict[str, dict[str, int]] = {}

    for repository in PROFILE_REPRESENTATIVE_REPOSITORIES:
        for environment in DEPLOY_ENVIRONMENTS:
            template = synth_template_for_repositories(
                repository, target_environment=environment
            )
            key = f"{repository.deploy_profile}/{environment}"
            policy_sizes[key] = managed_policy_document_sizes(template)

    violations = {
        key: {
            policy_name: size
            for policy_name, size in environment_sizes.items()
            if size > IAM_MANAGED_POLICY_SIZE_LIMIT
        }
        for key, environment_sizes in policy_sizes.items()
    }

    assert not any(violations.values()), violations


def test_deploy_role_trust_is_exact_repo_and_environment() -> None:
    template = synth_template()

    assert_deploy_role_trust(
        template,
        role_name="campps-identity-access-nonprod-gha-deploy-role",
        target_environment="nonprod",
    )


def test_production_role_uses_production_environment_subject() -> None:
    template = synth_template(target_environment="production")

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-identity-access-production-gha-deploy-role"},
    )
    assert_deploy_role_trust(
        template,
        role_name="campps-identity-access-production-gha-deploy-role",
        target_environment="production",
    )


def test_staging_role_uses_staging_environment_subject() -> None:
    template = synth_template(target_environment="staging")

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-identity-access-staging-gha-deploy-role"},
    )
    assert_deploy_role_trust(
        template,
        role_name="campps-identity-access-staging-gha-deploy-role",
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
                "aws:RequestTag/Service": "identity-access",
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
                "aws:ResourceTag/Service": "identity-access",
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
        {"ManagedPolicyName": ("campps-identity-access-nonprod-permissions-boundary")},
    )


def test_iam_mutation_cannot_target_deploy_identity_resources() -> None:
    template = synth_template()
    deploy_identity_fragments = (
        "campps-identity-access-nonprod-gha-deploy-role",
        "campps-identity-access-nonprod-gha-deploy-policy",
        "campps-identity-access-nonprod-permissions-boundary",
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
                    ":iam::477152411873:role/campps-identity-access-nonprod-app-*",
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
                == "campps-identity-access-nonprod-permissions-boundary"
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
                    ":iam::477152411873:policy/campps-identity-access-nonprod-app-*",
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
            if statement.get("Sid") == "CdkBootstrapPassExecRole":
                continue
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


def collect_actions(template: Template) -> set[str]:
    actions: set[str] = set()
    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            for action in normalize_actions(statement.get("Action", [])):
                actions.add(action)
    return actions


def statements_for_action(template: Template, action_name: str) -> list[dict[str, Any]]:
    matching: list[dict[str, Any]] = []
    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            normalized = {
                action.strip().lower()
                for action in normalize_actions(statement.get("Action", []))
            }
            if action_name in normalized:
                matching.append(statement)
    return matching


def test_every_campps_profile_includes_codeartifact_consume_grant() -> None:
    profiles = (
        ServiceRepository(
            name="identity-access", repository="infiquetra/campps-identity-access"
        ),
        ServiceRepository(
            name="platform",
            repository="infiquetra/campps-platform",
            deploy_profile="platform-foundation",
        ),
        ServiceRepository(
            name="contracts",
            repository="infiquetra/campps-contracts",
            deploy_profile="codeartifact-publish",
        ),
    )

    for repository in profiles:
        template = synth_template_for_repositories(repository)
        actions = {action.lower() for action in collect_actions(template)}
        assert "codeartifact:getauthorizationtoken" in actions, repository
        assert "codeartifact:getrepositoryendpoint" in actions, repository
        assert "codeartifact:readfromrepository" in actions, repository
        assert "sts:getservicebearertoken" in actions, repository


def test_every_campps_profile_can_assume_cdk_bootstrap_roles() -> None:
    """Every deploy profile must be able to use the CDK modern-bootstrap
    deploy/file-publishing/image-publishing/lookup roles and pass the
    bootstrap cfn-exec role, scoped to the hnb659fds qualifier in this
    account/region only."""
    expected_assume_resource = (
        "arn:aws:iam::477152411873:role/cdk-hnb659fds-*-477152411873-us-east-1"
    )
    expected_cfn_exec_resource = (
        "arn:aws:iam::477152411873:role/"
        "cdk-hnb659fds-cfn-exec-role-477152411873-us-east-1"
    )

    for repository in PROFILE_REPRESENTATIVE_REPOSITORIES:
        for environment in DEPLOY_ENVIRONMENTS:
            template = synth_template_for_repositories(
                repository, target_environment=environment
            )

            assume_statements = [
                statement
                for policy_document in policy_documents(template)
                for statement in policy_document["Statement"]
                if statement.get("Sid") == "CdkBootstrapAssumeRoles"
            ]
            assert assume_statements, (repository, environment)
            for statement in assume_statements:
                assert set(normalize_actions(statement["Action"])) == {
                    "sts:AssumeRole"
                }, statement
                resources = tuple(normalize_resources(statement["Resource"]))
                assert expected_assume_resource in resources, statement
                assert "*" not in resources, statement

            pass_statements = [
                statement
                for policy_document in policy_documents(template)
                for statement in policy_document["Statement"]
                if statement.get("Sid") == "CdkBootstrapPassExecRole"
            ]
            assert pass_statements, (repository, environment)
            for statement in pass_statements:
                assert set(normalize_actions(statement["Action"])) == {
                    "iam:PassRole"
                }, statement
                resources = tuple(normalize_resources(statement["Resource"]))
                assert expected_cfn_exec_resource in resources, statement
                assert "*" not in resources, statement


def test_platform_foundation_role_can_create_scoped_platform_resources() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="platform",
            repository="infiquetra/campps-platform",
            deploy_profile="platform-foundation",
        )
    )

    create_role = statements_for_action(template, "iam:createrole")
    assert create_role
    assert any(
        "campps-platform-nonprod-*" in str(statement.get("Resource"))
        for statement in create_role
    )
    assert all(
        "iam:PermissionsBoundary"
        in statement.get("Condition", {}).get("StringEquals", {})
        for statement in create_role
    )

    create_key = statements_for_action(template, "kms:createkey")
    assert create_key

    create_domain = statements_for_action(template, "codeartifact:createdomain")
    assert create_domain
    assert any(
        ":domain/infiquetra" in str(statement.get("Resource"))
        for statement in create_domain
    )

    create_repo = statements_for_action(template, "codeartifact:createrepository")
    assert create_repo
    assert any(
        ":repository/infiquetra/campps" in str(statement.get("Resource"))
        for statement in create_repo
    )


def test_platform_foundation_policy_is_split_under_iam_size_limit() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="platform",
            repository="infiquetra/campps-platform",
            deploy_profile="platform-foundation",
        )
    )

    sizes = managed_policy_document_sizes(template)
    deploy_policy_sizes = {
        name: size
        for name, size in sizes.items()
        if name.startswith("campps-platform-nonprod-gha-")
        and "permissions-boundary" not in name
    }

    assert set(deploy_policy_sizes) == {
        "campps-platform-nonprod-gha-deploy-policy",
        "campps-platform-nonprod-gha-runtime-policy",
        "campps-platform-nonprod-gha-data-policy",
    }, deploy_policy_sizes
    for name, size in deploy_policy_sizes.items():
        assert size < IAM_MANAGED_POLICY_SIZE_LIMIT, (name, size)


def test_platform_foundation_split_preserves_key_abilities() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="platform",
            repository="infiquetra/campps-platform",
            deploy_profile="platform-foundation",
        )
    )
    actions = {action.lower() for action in collect_actions(template)}

    assert "events:createeventbus" in actions
    assert "kms:createkey" in actions
    assert "iam:createrole" in actions
    assert "codeartifact:createdomain" in actions
    assert "codeartifact:createrepository" in actions
    assert "cloudwatch:putdashboard" in actions
    assert "logs:createloggroup" in actions
    assert "ssm:getparametersbypath" in actions

    ssm_put = statements_for_action(template, "ssm:putparameter")
    assert ssm_put
    assert any(
        "campps/platform/nonprod/*" in str(statement.get("Resource"))
        for statement in ssm_put
    )

    create_role = statements_for_action(template, "iam:createrole")
    assert create_role
    assert all(
        "iam:PermissionsBoundary"
        in statement.get("Condition", {}).get("StringEquals", {})
        for statement in create_role
    )


def test_platform_foundation_can_read_platform_ssm_namespace_by_path() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="platform",
            repository="infiquetra/campps-platform",
            deploy_profile="platform-foundation",
        )
    )

    get_by_path = statements_for_action(template, "ssm:getparametersbypath")
    assert get_by_path
    resources = [str(statement.get("Resource")) for statement in get_by_path]
    assert any("campps/platform/nonprod" in resource for resource in resources)
    assert any("campps/platform/nonprod/*" in resource for resource in resources)
    for statement in get_by_path:
        resource = str(statement.get("Resource"))
        assert "campps/identity-access/nonprod" not in resource, statement
        assert "campps/contracts/nonprod" not in resource, statement
        assert statement.get("Resource") != "*", statement


def test_serverless_api_can_read_shared_platform_ssm_namespace() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="tenant-setup",
            repository="infiquetra/campps-tenant-setup",
        )
    )

    get_parameter = statements_for_action(template, "ssm:getparameter")
    assert any(
        "campps/platform/nonprod/*" in str(statement.get("Resource"))
        for statement in get_parameter
    )

    get_by_path = statements_for_action(template, "ssm:getparametersbypath")
    assert get_by_path
    resources = [str(statement.get("Resource")) for statement in get_by_path]
    assert any("campps/platform/nonprod" in resource for resource in resources)
    assert any("campps/platform/nonprod/*" in resource for resource in resources)
    for statement in get_by_path:
        resource = str(statement.get("Resource"))
        assert "campps/tenant-setup/nonprod" not in resource, statement
        assert statement.get("Resource") != "*", statement


def test_codeartifact_publish_policy_fits_iam_size_limit() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="contracts",
            repository="infiquetra/campps-contracts",
            deploy_profile="codeartifact-publish",
        )
    )

    sizes = managed_policy_document_sizes(template)
    deploy_policy_sizes = {
        name: size for name, size in sizes.items() if "permissions-boundary" not in name
    }

    assert deploy_policy_sizes
    for name, size in deploy_policy_sizes.items():
        assert size < IAM_MANAGED_POLICY_SIZE_LIMIT, (name, size)


def test_codeartifact_publish_role_can_publish_package_versions() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="contracts",
            repository="infiquetra/campps-contracts",
            deploy_profile="codeartifact-publish",
        )
    )

    publish = statements_for_action(template, "codeartifact:publishpackageversion")
    assert publish
    assert any(
        ":package/infiquetra/campps/*" in str(statement.get("Resource"))
        for statement in publish
    )

    actions = {action.lower() for action in collect_actions(template)}
    assert "sts:getservicebearertoken" in actions
    assert "codeartifact:getauthorizationtoken" in actions


# --- U1: every registered service mints a scoped, env-bound deploy role -------

NEW_BACKEND_SERVICES: tuple[ServiceRepository, ...] = tuple(
    service
    for service in CANONICAL_SERVICE_REPOSITORIES
    if service.name in EXPECTED_SERVERLESS_API_BACKENDS
)


def find_managed_policy(template: Template, policy_name: str) -> dict[str, Any]:
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    matching = [
        policy
        for policy in policies.values()
        if policy.get("Properties", {}).get("ManagedPolicyName") == policy_name
    ]
    assert len(matching) == 1, (policy_name, list(policies))
    return dict(matching[0])


def test_every_serverless_backend_mints_role_and_boundary_per_environment() -> None:
    for service in NEW_BACKEND_SERVICES:
        for environment in DEPLOY_ENVIRONMENTS:
            template = synth_template_for_repositories(
                service, target_environment=environment
            )

            template.has_resource_properties(
                "AWS::IAM::Role",
                {"RoleName": service.role_name(environment)},
            )
            template.has_resource_properties(
                "AWS::IAM::ManagedPolicy",
                {"ManagedPolicyName": service.permissions_boundary_name(environment)},
            )
            # Trust is pinned to the exact repo + environment OIDC subject.
            role = find_deploy_role(template, service.role_name(environment))
            statement = get_assume_role_statement(role)
            assert statement["Condition"]["StringEquals"][
                "token.actions.githubusercontent.com:sub"
            ] == (f"repo:{service.repository}:environment:{environment}"), (
                service.name,
                environment,
            )


def test_full_registry_synthesizes_a_role_for_each_in_scope_service() -> None:
    for environment in DEPLOY_ENVIRONMENTS:
        template = synth_template_for_repositories(
            *CANONICAL_SERVICE_REPOSITORIES, target_environment=environment
        )
        for service in CANONICAL_SERVICE_REPOSITORIES:
            if environment not in service.environments:
                continue
            template.has_resource_properties(
                "AWS::IAM::Role",
                {"RoleName": service.role_name(environment)},
            )


# --- U2: web-app gets a least-privilege static-site profile --------------------

WEB_APP_SERVICE = ServiceRepository(
    name="web-app",
    repository="infiquetra/campps-web-app",
    deploy_profile="web-app",
)

WEB_APP_FORBIDDEN_BACKEND_SERVICES = (
    "lambda",
    "dynamodb",
    "apigateway",
    "events",
    "sqs",
    "secretsmanager",
)


def web_app_deploy_policy_document(template: Template) -> dict[str, Any]:
    policy = find_managed_policy(template, WEB_APP_SERVICE.policy_name("nonprod"))
    return dict(policy["Properties"]["PolicyDocument"])


def test_web_app_role_exists_with_env_scoped_trust() -> None:
    for environment in DEPLOY_ENVIRONMENTS:
        template = synth_template_for_repositories(
            WEB_APP_SERVICE, target_environment=environment
        )

        role_name = f"campps-web-app-{environment}-gha-deploy-role"
        template.has_resource_properties("AWS::IAM::Role", {"RoleName": role_name})
        role = find_deploy_role(template, role_name)
        statement = get_assume_role_statement(role)
        assert statement["Condition"]["StringEquals"][
            "token.actions.githubusercontent.com:sub"
        ] == (f"repo:infiquetra/campps-web-app:environment:{environment}"), environment


def test_web_app_policy_grants_pinned_static_site_actions() -> None:
    template = synth_template_for_repositories(WEB_APP_SERVICE)
    document = web_app_deploy_policy_document(template)

    actions = {
        action.lower()
        for statement in document["Statement"]
        for action in normalize_actions(statement.get("Action", []))
    }
    # The static-site write paths the plan pins.
    assert "s3:putobject" in actions
    assert "s3:createbucket" in actions
    assert "s3:putbucketwebsite" in actions
    assert "cloudfront:createinvalidation" in actions
    assert "cloudfront:createdistribution" in actions
    assert "cloudfront:createoriginaccesscontrol" in actions


def test_web_app_s3_actions_are_scoped_to_service_buckets() -> None:
    template = synth_template_for_repositories(WEB_APP_SERVICE)
    document = web_app_deploy_policy_document(template)

    s3_statements = [
        statement
        for statement in document["Statement"]
        if any(
            action.lower().startswith("s3:")
            for action in normalize_actions(statement.get("Action", []))
        )
        # Skip the shared CDK-assets baseline statement (cdk-hnb659fds bucket).
        and statement.get("Sid") == "StaticSiteBucket"
    ]
    assert s3_statements
    for statement in s3_statements:
        resources = tuple(normalize_resources(statement.get("Resource", [])))
        assert resources, statement
        for resource in resources:
            assert resource.startswith("arn:aws:s3:::campps-web-app-nonprod-*"), (
                resource
            )
            assert resource != "*"


def test_web_app_policy_grants_no_backend_service_actions() -> None:
    template = synth_template_for_repositories(WEB_APP_SERVICE)
    document = web_app_deploy_policy_document(template)

    granted_services = {
        action.split(":", maxsplit=1)[0].lower()
        for statement in document["Statement"]
        for action in normalize_actions(statement.get("Action", []))
    }
    for forbidden in WEB_APP_FORBIDDEN_BACKEND_SERVICES:
        assert forbidden not in granted_services, (forbidden, sorted(granted_services))


def test_web_app_policy_fits_iam_size_limit() -> None:
    for environment in DEPLOY_ENVIRONMENTS:
        template = synth_template_for_repositories(
            WEB_APP_SERVICE, target_environment=environment
        )
        sizes = managed_policy_document_sizes(template)
        deploy_policy_sizes = {
            name: size
            for name, size in sizes.items()
            if name.startswith("campps-web-app-") and "permissions-boundary" not in name
        }
        assert deploy_policy_sizes
        for name, size in deploy_policy_sizes.items():
            assert size < IAM_MANAGED_POLICY_SIZE_LIMIT, (name, size, environment)


# --- U3: an unrecognized deploy profile is a hard error, not a silent default --


def test_unknown_deploy_profile_raises() -> None:
    with pytest.raises(ValueError, match="unknown deploy_profile"):
        synth_template_for_repositories(
            ServiceRepository(
                name="bogus",
                repository="infiquetra/campps-bogus",
                deploy_profile="not-a-real-profile",
            )
        )


def test_known_deploy_profiles_do_not_raise() -> None:
    for service in (
        ServiceRepository(name="a", repository="infiquetra/campps-a"),
        ServiceRepository(
            name="b",
            repository="infiquetra/campps-b",
            deploy_profile="platform-foundation",
        ),
        ServiceRepository(
            name="c",
            repository="infiquetra/campps-c",
            deploy_profile="codeartifact-publish",
        ),
        ServiceRepository(
            name="d",
            repository="infiquetra/campps-d",
            deploy_profile="web-app",
        ),
    ):
        # Should synthesize without raising.
        synth_template_for_repositories(service)
