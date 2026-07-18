"""Unit tests for CAMPPS service deploy role generation."""

import json
from collections.abc import Iterable
from fnmatch import fnmatchcase
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
    # Byte-for-byte mirror of the campps-platform#24 E2E deploy fixture in
    # CAMPPS_SERVICE_REPOSITORIES. NOT a product service: nonprod-only (KTD2),
    # default serverless-api profile (KTD4). It is excluded from the product-set
    # assertions below via FIXTURE_SERVICE_NAMES, but kept in this exact-equality
    # mirror so any unexpected registry drift still fails the suite.
    ServiceRepository(
        name="e2e-canary",
        repository="infiquetra/campps-e2e-canary",
        environments=("nonprod",),
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

# Registered repositories that are E2E/deploy fixtures rather than product
# services. They are deliberately excluded from the product-set assertions
# (backend count, three-environment coverage, serverless-profile set) and are
# asserted separately for their fixture-specific scoping. See campps-platform#24
# KTD3: name-based exclusion is cheapest-correct for a single fixture; promote to
# a typed marker on ServiceRepository when a second fixture appears.
FIXTURE_SERVICE_NAMES = frozenset({"e2e-canary"})


def test_registry_membership_equals_canonical_set() -> None:
    assert CAMPPS_SERVICE_REPOSITORIES == CANONICAL_SERVICE_REPOSITORIES


def test_registry_has_ten_backends_plus_web_app() -> None:
    backends = [
        service
        for service in CAMPPS_SERVICE_REPOSITORIES
        if service.deploy_profile != "web-app"
        and service.name not in FIXTURE_SERVICE_NAMES
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
        if service.name in FIXTURE_SERVICE_NAMES:
            continue
        assert service.environments == ("nonprod", "staging", "production"), service


def test_e2e_canary_fixture_is_nonprod_only() -> None:
    canary = next(
        service
        for service in CAMPPS_SERVICE_REPOSITORIES
        if service.name == "e2e-canary"
    )
    assert canary.environments == ("nonprod",), canary
    assert canary.deploy_profile == "serverless-api", canary


def test_serverless_api_backends_use_default_profile() -> None:
    serverless_backends = {
        service.name
        for service in CAMPPS_SERVICE_REPOSITORIES
        if service.deploy_profile == "serverless-api"
        and service.name not in FIXTURE_SERVICE_NAMES
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
    ServiceRepository(
        name="web-app",
        repository="infiquetra/campps-web-app",
        deploy_profile="web-app",
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


def test_web_app_role_can_fetch_pinned_contract_assets() -> None:
    template = synth_template_for_repositories(
        ServiceRepository(
            name="web-app",
            repository="infiquetra/campps-web-app",
            deploy_profile="web-app",
        )
    )

    asset_reads = statements_for_action(
        template,
        "codeartifact:getpackageversionasset",
    )
    assert asset_reads
    assert any(
        ":package/infiquetra/campps/*" in str(statement.get("Resource"))
        for statement in asset_reads
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
    return find_managed_policy_with_logical_id(template, policy_name)[1]


def find_managed_policy_with_logical_id(
    template: Template, policy_name: str
) -> tuple[str, dict[str, Any]]:
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    matching = [
        (logical_id, policy)
        for logical_id, policy in policies.items()
        if policy.get("Properties", {}).get("ManagedPolicyName") == policy_name
    ]
    assert len(matching) == 1, (policy_name, list(policies))
    logical_id, policy = matching[0]
    return logical_id, dict(policy)


def managed_policy_names(template: Template) -> set[str]:
    names: set[str] = set()
    for policy in template.find_resources("AWS::IAM::ManagedPolicy").values():
        name = policy.get("Properties", {}).get("ManagedPolicyName")
        if isinstance(name, str):
            names.add(name)
    return names


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


# --- campps-platform#24: the E2E canary fixture mints a nonprod-only role ------


def test_e2e_canary_mints_nonprod_role_with_scoped_trust() -> None:
    canary = next(
        service
        for service in CANONICAL_SERVICE_REPOSITORIES
        if service.name == "e2e-canary"
    )
    template = synth_template_for_repositories(canary, target_environment="nonprod")

    role_name = canary.role_name("nonprod")
    template.has_resource_properties("AWS::IAM::Role", {"RoleName": role_name})
    role = find_deploy_role(template, role_name)
    statement = get_assume_role_statement(role)
    assert (
        statement["Condition"]["StringEquals"][
            "token.actions.githubusercontent.com:sub"
        ]
        == "repo:infiquetra/campps-e2e-canary:environment:nonprod"
    )


def test_e2e_canary_role_absent_from_staging_and_production() -> None:
    # KTD2 env-gating: even when the whole registry is synthesized for the higher
    # environments, the nonprod-only canary must mint no staging/production role.
    canary = next(
        service
        for service in CANONICAL_SERVICE_REPOSITORIES
        if service.name == "e2e-canary"
    )
    higher_envs: tuple[DeployEnvironment, ...] = ("staging", "production")
    for environment in higher_envs:
        template = synth_template_for_repositories(
            *CANONICAL_SERVICE_REPOSITORIES, target_environment=environment
        )
        role_names = {
            role.get("Properties", {}).get("RoleName")
            for role in template.find_resources("AWS::IAM::Role").values()
        }
        assert canary.role_name(environment) not in role_names, (
            environment,
            sorted(name for name in role_names if name),
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
        # Each known profile must synthesize *and* actually mint a deploy role
        # plus its managed deploy policy — not merely fail to raise.
        template = synth_template_for_repositories(service)
        template.has_resource_properties(
            "AWS::IAM::Role",
            {"RoleName": service.role_name("nonprod")},
        )
        template.has_resource_properties(
            "AWS::IAM::ManagedPolicy",
            {"ManagedPolicyName": service.policy_name("nonprod")},
        )


# --- campps-tenant-setup PR #67: scope-origination seam proof grant --------
#
# The nonprod deploy role for tenant-setup needs two cross-service permissions
# to run tests/integration/test_scope_origination_seam_deployed.py:
#   - events:PutEvents on the shared platform bus (campps-platform-nonprod)
#   - dynamodb:GetItem on identity-access's table (campps-identity-access-nonprod)
#
# The grant is scoped to tenant-setup + nonprod only.

TENANT_SETUP_REPO = ServiceRepository(
    name="tenant-setup",
    repository="infiquetra/campps-tenant-setup",
)

E2E_CANARY_REPO = ServiceRepository(
    name="e2e-canary",
    repository="infiquetra/campps-e2e-canary",
    environments=("nonprod",),
)

E2E_CANARY_ALL_ENVIRONMENTS_REPO = ServiceRepository(
    name="e2e-canary",
    repository="infiquetra/campps-e2e-canary",
)

SEAM_PROOF_POLICY_NAME = "campps-tenant-setup-nonprod-gha-seam-proof-policy"
IDENTITY_SCOPE_READBACK_POLICY_NAME = (
    "campps-e2e-canary-nonprod-gha-identity-scope-readback-policy"
)
IDENTITY_SCOPE_READBACK_POLICY_SUFFIX = "-gha-identity-scope-readback-policy"
LIVE_PROOF_ROLE_NAME = "campps-e2e-canary-nonprod-gha-live-proof-role"
LIVE_PROOF_POLICY_NAME = "campps-e2e-canary-nonprod-gha-live-proof-policy"
LIVE_PROOF_POLICY_SUFFIX = "-gha-live-proof-policy"


def assert_no_identity_scope_readback_policy(template: Template) -> None:
    policy_names = managed_policy_names(template)
    assert not any(
        name.endswith(IDENTITY_SCOPE_READBACK_POLICY_SUFFIX) for name in policy_names
    ), f"Unexpected identity-scope readback policy: {policy_names}"


def assert_no_live_proof_resources(template: Template) -> None:
    role_names = {
        role.get("Properties", {}).get("RoleName")
        for role in template.find_resources("AWS::IAM::Role").values()
    }
    policy_names = managed_policy_names(template)
    outputs = template.to_json().get("Outputs", {})

    assert LIVE_PROOF_ROLE_NAME not in role_names, role_names
    assert not any(name.endswith(LIVE_PROOF_POLICY_SUFFIX) for name in policy_names), (
        policy_names
    )
    assert "CamppsE2eCanaryLiveProofRoleArn" not in outputs, outputs


def test_tenant_setup_nonprod_deploy_role_has_seam_proof_policy() -> None:
    """Positive: tenant-setup nonprod role is attached to the seam proof policy
    and that policy contains exactly the two scoped cross-service grants."""
    template = synth_template_for_repositories(
        TENANT_SETUP_REPO, target_environment="nonprod"
    )

    # The policy must exist with the expected name.
    policy = find_managed_policy(template, SEAM_PROOF_POLICY_NAME)
    document = policy["Properties"]["PolicyDocument"]

    statements_by_sid = {
        stmt["Sid"]: stmt for stmt in document["Statement"] if "Sid" in stmt
    }
    assert set(statements_by_sid) == {
        "ScopeSeamProducerEmit",
        "ScopeSeamConsumerReadback",
    }

    # ScopeSeamProducerEmit: events:PutEvents on the platform bus.
    assert "ScopeSeamProducerEmit" in statements_by_sid, statements_by_sid.keys()
    producer_stmt = statements_by_sid["ScopeSeamProducerEmit"]
    assert set(normalize_actions(producer_stmt["Action"])) == {"events:PutEvents"}
    producer_resources = str(producer_stmt["Resource"])
    assert "event-bus/campps-platform-nonprod" in producer_resources, producer_resources

    # ScopeSeamConsumerReadback: dynamodb:GetItem on identity-access's table.
    assert "ScopeSeamConsumerReadback" in statements_by_sid, statements_by_sid.keys()
    consumer_stmt = statements_by_sid["ScopeSeamConsumerReadback"]
    assert set(normalize_actions(consumer_stmt["Action"])) == {"dynamodb:GetItem"}
    consumer_resources = str(consumer_stmt["Resource"])
    assert "table/campps-identity-access-nonprod" in consumer_resources, (
        consumer_resources
    )


def test_tenant_setup_staging_has_no_seam_proof_policy() -> None:
    """Negative: no seam-proof policy is synthesized for tenant-setup staging."""
    template = synth_template_for_repositories(
        TENANT_SETUP_REPO, target_environment="staging"
    )
    policy_names = {
        policy.get("Properties", {}).get("ManagedPolicyName")
        for policy in template.find_resources("AWS::IAM::ManagedPolicy").values()
    }
    assert not any(
        name is not None and "gha-seam-proof-policy" in name for name in policy_names
    ), f"Unexpected seam-proof policy in staging: {policy_names}"


def test_tenant_setup_production_has_no_seam_proof_policy() -> None:
    """Negative: no seam-proof policy is synthesized for tenant-setup production."""
    template = synth_template_for_repositories(
        TENANT_SETUP_REPO, target_environment="production"
    )
    policy_names = {
        policy.get("Properties", {}).get("ManagedPolicyName")
        for policy in template.find_resources("AWS::IAM::ManagedPolicy").values()
    }
    assert not any(
        name is not None and "gha-seam-proof-policy" in name for name in policy_names
    ), f"Unexpected seam-proof policy in production: {policy_names}"


def test_identity_access_nonprod_has_no_seam_proof_policy() -> None:
    """Negative: no seam-proof policy is synthesized for identity-access nonprod."""
    template = synth_template_for_repositories(
        ServiceRepository(
            name="identity-access",
            repository="infiquetra/campps-identity-access",
        ),
        target_environment="nonprod",
    )
    policy_names = {
        policy.get("Properties", {}).get("ManagedPolicyName")
        for policy in template.find_resources("AWS::IAM::ManagedPolicy").values()
    }
    assert not any(
        name is not None and "gha-seam-proof-policy" in name for name in policy_names
    ), f"Unexpected seam-proof policy for identity-access: {policy_names}"


# --- e2e-canary identity-scope readback grant -------------------------------
#
# The nonprod deploy role for e2e-canary needs a single cross-service permission
# to run tenant-config-publish-and-scope:
#   - dynamodb:GetItem on identity-access's table (campps-identity-access-nonprod)
#
# The grant is scoped to e2e-canary + nonprod only.


def test_e2e_canary_nonprod_deploy_role_has_identity_scope_readback_policy() -> None:
    """Positive: e2e-canary nonprod role can read exactly one identity table."""
    template = synth_template_for_repositories(
        E2E_CANARY_REPO, target_environment="nonprod"
    )

    policy_logical_id, policy = find_managed_policy_with_logical_id(
        template, IDENTITY_SCOPE_READBACK_POLICY_NAME
    )
    document = policy["Properties"]["PolicyDocument"]
    statements = document["Statement"]

    assert len(statements) == 1, statements
    statement = statements[0]
    assert statement["Sid"] == "IdentityScopeReadback"
    assert set(normalize_actions(statement["Action"])) == {"dynamodb:GetItem"}

    resources = str(statement["Resource"])
    assert "table/campps-identity-access-nonprod" in resources, resources
    assert "campps-identity-access-staging" not in resources
    assert "campps-identity-access-production" not in resources
    assert "*" not in resources

    role = find_deploy_role(template, E2E_CANARY_REPO.role_name("nonprod"))
    managed_policy_arns = role["Properties"]["ManagedPolicyArns"]
    assert {"Ref": policy_logical_id} in managed_policy_arns


def test_e2e_canary_real_registry_has_no_higher_environment_readback_policy() -> None:
    """Negative: the real registry mints no e2e-canary higher-env role or policy."""
    higher_envs: tuple[DeployEnvironment, ...] = ("staging", "production")
    for environment in higher_envs:
        template = synth_template_for_repositories(
            *CANONICAL_SERVICE_REPOSITORIES,
            target_environment=environment,
        )
        role_names = {
            role.get("Properties", {}).get("RoleName")
            for role in template.find_resources("AWS::IAM::Role").values()
        }

        assert E2E_CANARY_REPO.role_name(environment) not in role_names, (
            environment,
            sorted(name for name in role_names if name),
        )
        assert_no_identity_scope_readback_policy(template)


def test_e2e_canary_higher_environment_helper_guard_returns_no_policy() -> None:
    """Negative: even an all-env canary test fixture gets no higher-env policy."""
    higher_envs: tuple[DeployEnvironment, ...] = ("staging", "production")
    for environment in higher_envs:
        template = synth_template_for_repositories(
            E2E_CANARY_ALL_ENVIRONMENTS_REPO,
            target_environment=environment,
        )

        template.has_resource_properties(
            "AWS::IAM::Role",
            {"RoleName": E2E_CANARY_ALL_ENVIRONMENTS_REPO.role_name(environment)},
        )
        assert_no_identity_scope_readback_policy(template)


def test_unrelated_nonprod_services_have_no_identity_scope_readback_policy() -> None:
    """Negative: the e2e canary readback grant does not leak to other services."""
    unrelated_services = (
        TENANT_SETUP_REPO,
        ServiceRepository(
            name="identity-access",
            repository="infiquetra/campps-identity-access",
        ),
        ServiceRepository(
            name="registration",
            repository="infiquetra/campps-registration",
        ),
    )

    for service_repository in unrelated_services:
        template = synth_template_for_repositories(
            service_repository,
            target_environment="nonprod",
        )
        assert_no_identity_scope_readback_policy(template)


# --- e2e-canary dedicated live-proof role ----------------------------------


def test_e2e_canary_nonprod_has_dedicated_two_read_live_proof_role() -> None:
    template = synth_template_for_repositories(
        E2E_CANARY_REPO, target_environment="nonprod"
    )

    policy_logical_id, policy = find_managed_policy_with_logical_id(
        template, LIVE_PROOF_POLICY_NAME
    )
    statements = policy["Properties"]["PolicyDocument"]["Statement"]
    statements_by_sid = {statement["Sid"]: statement for statement in statements}

    assert set(statements_by_sid) == {
        "WorkOsProviderSecretRead",
        "IdentityScopeReadback",
        "PaymentsEmitterPutEvents",
    }
    assert set(
        normalize_actions(statements_by_sid["WorkOsProviderSecretRead"]["Action"])
    ) == {"secretsmanager:GetSecretValue"}
    secret_resource = str(statements_by_sid["WorkOsProviderSecretRead"]["Resource"])
    assert (
        "secretsmanager:us-east-1:477152411873:secret:"
        "campps/identity-access/nonprod/workos/api-key-??????"
    ) in secret_resource
    assert set(
        normalize_actions(statements_by_sid["IdentityScopeReadback"]["Action"])
    ) == {"dynamodb:GetItem"}
    scope_resource = str(statements_by_sid["IdentityScopeReadback"]["Resource"])
    assert (
        "dynamodb:us-east-1:477152411873:table/campps-identity-access-nonprod"
    ) in scope_resource

    emitter_statement = statements_by_sid["PaymentsEmitterPutEvents"]
    assert set(normalize_actions(emitter_statement["Action"])) == {"events:PutEvents"}
    emitter_resource = str(emitter_statement["Resource"])
    assert (
        "events:us-east-1:477152411873:event-bus/campps-platform-nonprod"
    ) in emitter_resource
    assert emitter_statement["Condition"] == {
        "StringEquals": {"events:source": "campps.payments"}
    }

    role = find_deploy_role(template, LIVE_PROOF_ROLE_NAME)
    assert role["Properties"]["MaxSessionDuration"] == 3600
    assert role["Properties"]["ManagedPolicyArns"] == [{"Ref": policy_logical_id}]

    trust = get_assume_role_statement(role)
    assert trust["Condition"]["StringEquals"] == {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": (
            "repo:infiquetra/campps-e2e-canary:environment:nonprod"
        ),
    }

    outputs = template.to_json()["Outputs"]
    output_get_att = outputs["CamppsE2eCanaryLiveProofRoleArn"]["Value"]["Fn::GetAtt"]
    assert output_get_att[0].startswith("E2eCanaryLiveProofRole")
    assert output_get_att[1] == "Arn"


def test_live_proof_policy_has_no_widened_actions_or_resources() -> None:
    template = synth_template_for_repositories(
        E2E_CANARY_REPO, target_environment="nonprod"
    )
    _, policy = find_managed_policy_with_logical_id(template, LIVE_PROOF_POLICY_NAME)
    statements = policy["Properties"]["PolicyDocument"]["Statement"]

    actions = {
        action
        for statement in statements
        for action in normalize_actions(statement["Action"])
    }
    resources = {
        resource
        for statement in statements
        for resource in normalize_resources(statement["Resource"])
    }

    assert actions == {
        "secretsmanager:GetSecretValue",
        "dynamodb:GetItem",
        "events:PutEvents",
    }
    assert "*" not in actions
    assert "*" not in resources
    assert not any(action.startswith("kms:") for action in actions)
    assert not any(
        action in {"dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem"}
        for action in actions
    )
    # The one write action (events:PutEvents) must be source-scoped, never a bare
    # bus grant, so the canary cannot spoof another producer's events.
    put_events_statements = [
        statement
        for statement in statements
        if "events:PutEvents" in normalize_actions(statement["Action"])
    ]
    assert len(put_events_statements) == 1
    assert put_events_statements[0]["Condition"] == {
        "StringEquals": {"events:source": "campps.payments"}
    }
    assert not any(
        "staging" in resource or "production" in resource for resource in resources
    )


def test_live_proof_secret_pattern_has_exact_generated_suffix_width() -> None:
    template = synth_template_for_repositories(
        E2E_CANARY_REPO, target_environment="nonprod"
    )
    _, policy = find_managed_policy_with_logical_id(template, LIVE_PROOF_POLICY_NAME)
    statement = next(
        statement
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
        if statement["Sid"] == "WorkOsProviderSecretRead"
    )
    resource = str(statement["Resource"])
    resource_pattern = "campps/identity-access/nonprod/workos/api-key-??????"

    assert resource_pattern in resource
    assert resource.count("?") == 6
    assert "/api-key-*" not in resource
    assert "/api-key-copy-" not in resource
    assert "/api-key-old-" not in resource
    assert fnmatchcase(
        "campps/identity-access/nonprod/workos/api-key-Ab12xy",
        resource_pattern,
    )
    for forbidden_name in (
        "campps/identity-access/nonprod/workos/api-key-copy-Ab12xy",
        "campps/identity-access/nonprod/workos/api-key-old-Ab12xy",
        "campps/identity-access/nonprod/workos/api-key-Ab12x",
        "campps/identity-access/nonprod/workos/api-key-Ab12xyz",
        "campps/identity-access/staging/workos/api-key-Ab12xy",
    ):
        assert not fnmatchcase(forbidden_name, resource_pattern)


def test_live_proof_policy_is_not_attached_to_existing_deploy_role() -> None:
    template = synth_template_for_repositories(
        E2E_CANARY_REPO, target_environment="nonprod"
    )
    live_policy_logical_id, _ = find_managed_policy_with_logical_id(
        template, LIVE_PROOF_POLICY_NAME
    )
    deploy_role = find_deploy_role(template, E2E_CANARY_REPO.role_name("nonprod"))

    assert {"Ref": live_policy_logical_id} not in deploy_role["Properties"][
        "ManagedPolicyArns"
    ]
    assert find_managed_policy(template, IDENTITY_SCOPE_READBACK_POLICY_NAME)


def test_live_proof_resources_are_nonprod_e2e_canary_only() -> None:
    higher_environments: tuple[DeployEnvironment, ...] = ("staging", "production")
    for environment in higher_environments:
        higher_template = synth_template_for_repositories(
            E2E_CANARY_ALL_ENVIRONMENTS_REPO,
            target_environment=environment,
        )
        assert_no_live_proof_resources(higher_template)

    for unrelated_service in (
        TENANT_SETUP_REPO,
        ServiceRepository(
            name="identity-access",
            repository="infiquetra/campps-identity-access",
        ),
    ):
        unrelated_template = synth_template_for_repositories(
            unrelated_service,
            target_environment="nonprod",
        )
        assert_no_live_proof_resources(unrelated_template)


def test_live_proof_synth_is_stable() -> None:
    first = synth_template_for_repositories(
        E2E_CANARY_REPO, target_environment="nonprod"
    ).to_json()
    second = synth_template_for_repositories(
        E2E_CANARY_REPO, target_environment="nonprod"
    ).to_json()

    assert first == second
