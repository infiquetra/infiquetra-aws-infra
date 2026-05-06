# CAMPPS AWS/CI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AWS/CI foundation for CAMPPS service repositories: SSO-based human access, tightened management OIDC, registry-generated workload deploy roles, and a nonprod/production release flow.

**Architecture:** Keep organization and SSO management in this foundation repository. Use one separate CAMPPS bootstrap CDK entry point for workload-account deploy roles so the existing management-account deployment workflow is not expanded accidentally. Service repositories are registered in source control and get environment-scoped GitHub OIDC roles in `campps-dev` and `campps-prod`.

**Tech Stack:** Python 3.13, AWS CDK v2, AWS Organizations, IAM Identity Center, IAM GitHub OIDC, GitHub Actions, pytest, ruff, mypy.

---

## File Structure

### Existing files to modify

- `github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py`
  - Tighten the management deploy role trust from `repo:infiquetra/*` to this repository on `main`.
  - Stop attaching broad workload-service policies to the management deploy role.

- `github-oidc-bootstrap/tests/unit/test_github_oidc_stack.py`
  - Replace stale assertions with focused tests for the management OIDC provider, exact repository trust, and lack of broad workload policy attachments.

- `infiquetra_aws_infra/sso_stack.py`
  - Add optional, parameter-driven group assignments for management, nonprod developer, prod read-only, and prod break-glass access.
  - Correct the `CamppssDeveloper` permission set name to `CAMPPSDeveloper` before it gets assigned.

- `docs/ops/02-identity-and-access.md`
  - Document the new target access model and the remaining migration steps.

- `docs/ops/03-login-flows.md`
  - Add SSO profile guidance for management, `campps-dev`, and `campps-prod`.

- `docs/ops/04-ci-cd-pipeline.md`
  - Document the split between foundation repo deployment and CAMPPS service repo deployments.

- `docs/engineering-journal/DECISIONS.md`
  - Record the access and deploy-role design decision.

- `docs/engineering-journal/QUEUED.md`
  - Update existing access backlog to reflect what this implementation ships and what remains manual.

### New files to create

- `tests/unit/test_sso_stack.py`
  - Tests permission-set naming and optional SSO group assignments.

- `infiquetra_aws_infra/campps_service_registry.py`
  - Defines the source controlled registry format for CAMPPS service repositories.

- `infiquetra_aws_infra/campps_deploy_roles_stack.py`
  - Generates per-service, per-environment GitHub OIDC deploy roles in workload accounts.

- `tests/unit/test_campps_deploy_roles_stack.py`
  - Tests role names, trust policies, and permission boundaries for generated CAMPPS deploy roles.

- `app_campps_bootstrap.py`
  - Separate CDK entry point for deploying workload-account OIDC providers and deploy roles.

---

## Task 1: Tighten management GitHub OIDC tests

**Files:**
- Modify: `github-oidc-bootstrap/tests/unit/test_github_oidc_stack.py`

- [ ] **Step 1: Replace the stale OIDC bootstrap tests**

Replace the file with this focused test suite:

```python
"""Unit tests for the GitHub OIDC bootstrap stack."""

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

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
            return role
    raise AssertionError("infiquetra-aws-infra-gha-role not found")


def managed_policy_names(template: Template) -> set[str]:
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    return {
        policy["Properties"]["ManagedPolicyName"]
        for policy in policies.values()
        if "ManagedPolicyName" in policy["Properties"]
    }


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
    statement = deploy_role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]

    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert statement["Condition"] == {
        "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": "repo:infiquetra/infiquetra-aws-infra:ref:refs/heads/main",
        }
    }


def test_management_role_has_only_foundation_deploy_policy() -> None:
    template = synth_template()

    assert managed_policy_names(template) == {"infiquetra-aws-infra-gha-cdk-policy"}
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "RoleName": "infiquetra-aws-infra-gha-role",
            "ManagedPolicyArns": Match.array_with(
                [
                    {
                        "Ref": Match.string_like_regexp(
                            ".*CDKDeploymentPolicy.*"
                        )
                    }
                ]
            ),
        },
    )


def test_management_role_policy_does_not_include_workload_admin_actions() -> None:
    template = synth_template()
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    policy_documents = [
        policy["Properties"]["PolicyDocument"] for policy in policies.values()
    ]
    actions = {
        action
        for document in policy_documents
        for statement in document["Statement"]
        for action in statement.get("Action", [])
    }

    assert "lambda:*" not in actions
    assert "apigateway:*" not in actions
    assert "dynamodb:*" not in actions
    assert "events:*" not in actions
    assert "route53:*" not in actions
```

- [ ] **Step 2: Run the focused bootstrap tests and verify they fail**

Run:

```bash
cd github-oidc-bootstrap && uv run pytest tests/unit/test_github_oidc_stack.py -q
```

Expected: FAIL because the current stack still trusts `repo:infiquetra/*` and attaches the broad workload managed policies.

- [ ] **Step 3: Commit the failing tests**

Run this only if commits are authorized for the session:

```bash
git add github-oidc-bootstrap/tests/unit/test_github_oidc_stack.py
git commit -m "test(oidc): capture narrowed foundation deploy role trust"
```

---

## Task 2: Harden the management GitHub OIDC role

**Files:**
- Modify: `github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py:55-76`
- Modify: `github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py:113-139`
- Modify: `github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py:433-634`

- [ ] **Step 1: Attach only the foundation CDK deployment policy**

In `GitHubOIDCStack.__init__`, replace the managed-policy creation and attachment block with:

```python
        # Create the managed policy required for this foundation repository.
        cdk_deployment_policy = self._create_cdk_deployment_policy()

        # Attach only the foundation deployment policy to the management role.
        github_actions_role.add_managed_policy(cdk_deployment_policy)
```

- [ ] **Step 2: Narrow the role trust policy**

Replace `_create_github_actions_role` with:

```python
    def _create_github_actions_role(
        self, oidc_provider: iam.OpenIdConnectProvider, repo_full_name: str
    ) -> iam.Role:
        """Create IAM role for GitHub Actions with repository-scoped trust."""
        return iam.Role(
            self,
            "GitHubActionsDeployRole",
            role_name="infiquetra-aws-infra-gha-role",
            description="Role for GitHub Actions to deploy CDK stacks from infiquetra-aws-infra",
            assumed_by=iam.FederatedPrincipal(
                oidc_provider.open_id_connect_provider_arn,
                {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": (
                            f"repo:{repo_full_name}:ref:refs/heads/main"
                        ),
                    },
                },
                "sts:AssumeRoleWithWebIdentity",
            ),
            max_session_duration=cdk.Duration.hours(12),
        )
```

- [ ] **Step 3: Delete unused broad workload policy helpers**

Delete these methods from `github_oidc_stack.py`:

```text
_create_serverless_policy
_create_event_driven_policy
_create_edge_services_policy
_create_data_analytics_policy
_create_security_policy
_create_infrastructure_policy
```

These methods created broad workload-account permissions that should not live on the management-account deploy role.

- [ ] **Step 4: Run the bootstrap tests**

Run:

```bash
cd github-oidc-bootstrap && uv run pytest tests/unit/test_github_oidc_stack.py -q
```

Expected: PASS.

- [ ] **Step 5: Run bootstrap linting**

Run:

```bash
cd github-oidc-bootstrap && uv run ruff check github_oidc_bootstrap tests
```

Expected: PASS.

- [ ] **Step 6: Commit the OIDC hardening**

Run this only if commits are authorized for the session:

```bash
git add github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py github-oidc-bootstrap/tests/unit/test_github_oidc_stack.py
git commit -m "fix(oidc): scope foundation deploy role to infra repo"
```

---

## Task 3: Add SSO assignment tests

**Files:**
- Create: `tests/unit/test_sso_stack.py`

- [ ] **Step 1: Create failing tests for permission-set naming and group assignments**

Create `tests/unit/test_sso_stack.py` with:

```python
"""Unit tests for the Infiquetra Identity Center stack."""

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.organization_stack import OrganizationStack
from infiquetra_aws_infra.sso_stack import SSOStack


def synth_template() -> Template:
    app = App()
    organization_stack = OrganizationStack(
        app,
        "TestOrganizationStack",
        env=Environment(account="645166163764", region="us-east-1"),
    )
    sso_stack = SSOStack(
        app,
        "TestSSOStack",
        organization_stack=organization_stack,
        env=Environment(account="645166163764", region="us-east-1"),
    )
    return Template.from_stack(sso_stack)


def test_campps_developer_permission_set_uses_correct_name() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SSO::PermissionSet",
        {
            "Name": "CAMPPSDeveloper",
            "ManagedPolicies": ["arn:aws:iam::aws:policy/PowerUserAccess"],
        },
    )


def test_prod_breakglass_permission_set_exists() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SSO::PermissionSet",
        {
            "Name": "CAMPPSProductionBreakGlassAdministrator",
            "SessionDuration": "PT4H",
            "ManagedPolicies": ["arn:aws:iam::aws:policy/AdministratorAccess"],
        },
    )


def test_optional_group_parameters_exist() -> None:
    template = synth_template()

    template.has_parameter("InfiquetraAdminsGroupId", {"Type": "String"})
    template.has_parameter("CamppsDevelopersGroupId", {"Type": "String"})
    template.has_parameter("CamppsProdReadOnlyGroupId", {"Type": "String"})
    template.has_parameter("CamppsProdBreakGlassAdminsGroupId", {"Type": "String"})


def test_group_assignments_target_expected_accounts() -> None:
    template = synth_template()

    template.resource_count_is("AWS::SSO::Assignment", 4)
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "InfiquetraAdminsGroupId"},
            "TargetId": "645166163764",
            "TargetType": "AWS_ACCOUNT",
        },
    )
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "CamppsDevelopersGroupId"},
            "TargetId": "477152411873",
            "TargetType": "AWS_ACCOUNT",
        },
    )
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "CamppsProdReadOnlyGroupId"},
            "TargetId": "431643435299",
            "TargetType": "AWS_ACCOUNT",
        },
    )
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "CamppsProdBreakGlassAdminsGroupId"},
            "TargetId": "431643435299",
            "TargetType": "AWS_ACCOUNT",
        },
    )


def test_group_assignments_are_conditionally_created() -> None:
    template_json = synth_template().to_json()
    assignment_resources = [
        resource
        for resource in template_json["Resources"].values()
        if resource["Type"] == "AWS::SSO::Assignment"
    ]

    assert assignment_resources
    for resource in assignment_resources:
        assert "Condition" in resource
        assert resource["Condition"].endswith("Provided")


def test_core_admin_assignment_uses_core_admin_permission_set() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalId": {"Ref": "InfiquetraAdminsGroupId"},
            "PermissionSetArn": {
                "Fn::GetAtt": [
                    Match.string_like_regexp("CoreAdminPermissionSet.*"),
                    "PermissionSetArn",
                ]
            },
        },
    )
```

- [ ] **Step 2: Run the SSO tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_sso_stack.py -q
```

Expected: FAIL because `CAMPPSDeveloper`, production break-glass, parameters, and assignments do not exist yet.

- [ ] **Step 3: Commit the failing SSO tests**

Run this only if commits are authorized for the session:

```bash
git add tests/unit/test_sso_stack.py
git commit -m "test(sso): capture CAMPPS group assignment model"
```

---

## Task 4: Add optional SSO group assignments

**Files:**
- Modify: `infiquetra_aws_infra/sso_stack.py`
- Test: `tests/unit/test_sso_stack.py`

- [ ] **Step 1: Add account ID constants near the top of `sso_stack.py`**

After imports, add:

```python
MANAGEMENT_ACCOUNT_ID = "645166163764"
CAMPPS_DEV_ACCOUNT_ID = "477152411873"
CAMPPS_PROD_ACCOUNT_ID = "431643435299"
```

- [ ] **Step 2: Call the new assignment methods from the constructor**

In `SSOStack.__init__`, after `self.create_permission_sets()`, add:

```python
        self.create_assignment_parameters()
        self.create_account_assignments()
```

- [ ] **Step 3: Fix the CAMPPS developer permission set name**

In `create_permission_sets`, change:

```python
            name="CamppssDeveloper",
```

to:

```python
            name="CAMPPSDeveloper",
```

- [ ] **Step 4: Add the production break-glass permission set**

After `self.campps_developer_permission_set`, add:

```python
        self.campps_prod_breakglass_permission_set = sso.CfnPermissionSet(
            self,
            "CamppsProductionBreakGlassPermissionSet",
            name="CAMPPSProductionBreakGlassAdministrator",
            description="Emergency administrative access for CAMPPS production workloads",
            instance_arn=self.sso_instance_arn,
            session_duration="PT4H",
            managed_policies=["arn:aws:iam::aws:policy/AdministratorAccess"],
            tags=[
                cdk.CfnTag(key="Role", value="BreakGlassAdministrator"),
                cdk.CfnTag(key="BusinessUnit", value="Apps"),
                cdk.CfnTag(key="Project", value="CAMPPS"),
                cdk.CfnTag(key="Environment", value="Production"),
                cdk.CfnTag(key="AccessLevel", value="Full"),
            ],
        )
```

- [ ] **Step 5: Add assignment parameter and condition helpers**

Add these methods before `create_outputs`:

```python
    def create_assignment_parameters(self) -> None:
        """Create optional group ID parameters for Identity Center assignments."""
        self.infiquetra_admins_group_id = cdk.CfnParameter(
            self,
            "InfiquetraAdminsGroupId",
            type="String",
            default="",
            description="Identity Center group ID for management account administrators",
        )
        self.campps_developers_group_id = cdk.CfnParameter(
            self,
            "CamppsDevelopersGroupId",
            type="String",
            default="",
            description="Identity Center group ID for CAMPPS nonprod developers",
        )
        self.campps_prod_readonly_group_id = cdk.CfnParameter(
            self,
            "CamppsProdReadOnlyGroupId",
            type="String",
            default="",
            description="Identity Center group ID for CAMPPS production read-only access",
        )
        self.campps_prod_breakglass_group_id = cdk.CfnParameter(
            self,
            "CamppsProdBreakGlassAdminsGroupId",
            type="String",
            default="",
            description="Identity Center group ID for CAMPPS production break-glass administrators",
        )

    def assignment_parameter_condition(
        self, condition_id: str, parameter: cdk.CfnParameter
    ) -> cdk.CfnCondition:
        """Create a condition that is true when an assignment parameter is set."""
        return cdk.CfnCondition(
            self,
            condition_id,
            expression=cdk.Fn.condition_not(
                cdk.Fn.condition_equals(parameter.value_as_string, "")
            ),
        )
```

- [ ] **Step 6: Add assignment creation helpers**

Add these methods after `assignment_parameter_condition`:

```python
    def create_group_assignment(
        self,
        assignment_id: str,
        principal_id: cdk.CfnParameter,
        permission_set_arn: str,
        account_id: str,
        condition: cdk.CfnCondition,
    ) -> None:
        """Create a conditional Identity Center group assignment."""
        assignment = sso.CfnAssignment(
            self,
            assignment_id,
            instance_arn=self.sso_instance_arn,
            permission_set_arn=permission_set_arn,
            principal_id=principal_id.value_as_string,
            principal_type="GROUP",
            target_id=account_id,
            target_type="AWS_ACCOUNT",
        )
        assignment.cfn_options.condition = condition

    def create_account_assignments(self) -> None:
        """Create optional group-based account assignments."""
        infiquetra_admins_provided = self.assignment_parameter_condition(
            "InfiquetraAdminsGroupIdProvided", self.infiquetra_admins_group_id
        )
        campps_developers_provided = self.assignment_parameter_condition(
            "CamppsDevelopersGroupIdProvided", self.campps_developers_group_id
        )
        campps_prod_readonly_provided = self.assignment_parameter_condition(
            "CamppsProdReadOnlyGroupIdProvided", self.campps_prod_readonly_group_id
        )
        campps_prod_breakglass_provided = self.assignment_parameter_condition(
            "CamppsProdBreakGlassAdminsGroupIdProvided",
            self.campps_prod_breakglass_group_id,
        )

        self.create_group_assignment(
            "InfiquetraAdminsManagementAssignment",
            self.infiquetra_admins_group_id,
            self.core_admin_permission_set.attr_permission_set_arn,
            MANAGEMENT_ACCOUNT_ID,
            infiquetra_admins_provided,
        )
        self.create_group_assignment(
            "CamppsDevelopersNonProdAssignment",
            self.campps_developers_group_id,
            self.campps_developer_permission_set.attr_permission_set_arn,
            CAMPPS_DEV_ACCOUNT_ID,
            campps_developers_provided,
        )
        self.create_group_assignment(
            "CamppsProdReadOnlyAssignment",
            self.campps_prod_readonly_group_id,
            self.readonly_permission_set.attr_permission_set_arn,
            CAMPPS_PROD_ACCOUNT_ID,
            campps_prod_readonly_provided,
        )
        self.create_group_assignment(
            "CamppsProdBreakGlassAssignment",
            self.campps_prod_breakglass_group_id,
            self.campps_prod_breakglass_permission_set.attr_permission_set_arn,
            CAMPPS_PROD_ACCOUNT_ID,
            campps_prod_breakglass_provided,
        )
```

- [ ] **Step 7: Add output and property entries for the break-glass permission set**

In `create_outputs`, add:

```python
        CfnOutput(
            self,
            "CamppsProductionBreakGlassPermissionSetArn",
            value=self.campps_prod_breakglass_permission_set.attr_permission_set_arn,
            description="CAMPPS Production Break-Glass Permission Set ARN",
        )
```

In `permission_sets`, add:

```python
            "campps_prod_breakglass": (
                self.campps_prod_breakglass_permission_set.attr_permission_set_arn
            ),
```

- [ ] **Step 8: Run the SSO tests**

Run:

```bash
uv run pytest tests/unit/test_sso_stack.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit the SSO assignment implementation**

Run this only if commits are authorized for the session:

```bash
git add infiquetra_aws_infra/sso_stack.py tests/unit/test_sso_stack.py
git commit -m "feat(sso): add CAMPPS group assignment scaffolding"
```

---

## Task 5: Add CAMPPS deploy-role registry tests

**Files:**
- Create: `tests/unit/test_campps_deploy_roles_stack.py`

- [ ] **Step 1: Create failing tests for generated service deploy roles**

Create `tests/unit/test_campps_deploy_roles_stack.py` with:

```python
"""Unit tests for CAMPPS service deploy role generation."""

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.campps_deploy_roles_stack import CamppsDeployRolesStack
from infiquetra_aws_infra.campps_service_registry import ServiceRepository


def synth_template(target_environment: str = "nonprod") -> Template:
    app = App()
    stack = CamppsDeployRolesStack(
        app,
        "TestCamppsDeployRolesStack",
        target_environment=target_environment,
        service_repositories=(
            ServiceRepository(
                name="tenant-setup",
                repository="infiquetra/campps-tenant-setup-service",
            ),
        ),
        env=Environment(account="477152411873", region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_deploy_role_uses_service_and_environment_name() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-tenant-setup-nonprod-gha-deploy-role"},
    )


def test_deploy_role_trust_is_exact_repo_and_environment() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": "sts:AssumeRoleWithWebIdentity",
                                "Condition": {
                                    "StringEquals": {
                                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                                        "token.actions.githubusercontent.com:sub": "repo:infiquetra/campps-tenant-setup-service:environment:nonprod",
                                    }
                                },
                            }
                        )
                    ]
                )
            }
        },
    )


def test_production_role_uses_production_environment_subject() -> None:
    template = synth_template(target_environment="production")

    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "campps-tenant-setup-production-gha-deploy-role"},
    )
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Condition": {
                                    "StringEquals": {
                                        "token.actions.githubusercontent.com:sub": "repo:infiquetra/campps-tenant-setup-service:environment:production"
                                    }
                                }
                            }
                        )
                    ]
                )
            }
        },
    )


def test_deploy_policy_excludes_organization_and_sso_actions() -> None:
    template = synth_template()
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    actions = {
        action
        for policy in policies.values()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
        for action in statement.get("Action", [])
    }

    forbidden_prefixes = ("organizations:", "sso:", "identitystore:")
    assert not any(
        action.startswith(forbidden_prefixes) for action in actions
    ), actions


def test_stack_creates_oidc_provider_for_workload_account() -> None:
    template = synth_template()

    template.has_resource_properties(
        "Custom::AWSCDKOpenIdConnectProvider",
        {
            "Url": "https://token.actions.githubusercontent.com",
            "ClientIDList": ["sts.amazonaws.com"],
        },
    )
```

- [ ] **Step 2: Run the deploy-role tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_campps_deploy_roles_stack.py -q
```

Expected: FAIL because the registry and deploy-role stack do not exist yet.

- [ ] **Step 3: Commit the failing deploy-role tests**

Run this only if commits are authorized for the session:

```bash
git add tests/unit/test_campps_deploy_roles_stack.py
git commit -m "test(campps): capture service deploy role generation"
```

---

## Task 6: Add the CAMPPS service registry and deploy-role stack

**Files:**
- Create: `infiquetra_aws_infra/campps_service_registry.py`
- Create: `infiquetra_aws_infra/campps_deploy_roles_stack.py`
- Create: `app_campps_bootstrap.py`
- Test: `tests/unit/test_campps_deploy_roles_stack.py`

- [ ] **Step 1: Create the service registry module**

Create `infiquetra_aws_infra/campps_service_registry.py` with:

```python
"""Registry of CAMPPS service repositories allowed to deploy workloads."""

from dataclasses import dataclass
from typing import Literal

DeployEnvironment = Literal["nonprod", "production"]


@dataclass(frozen=True)
class ServiceRepository:
    """A CAMPPS repository that can receive generated deploy roles."""

    name: str
    repository: str
    environments: tuple[DeployEnvironment, ...] = ("nonprod", "production")
    deploy_profile: str = "serverless-api"

    def github_subject(self, environment: DeployEnvironment) -> str:
        return f"repo:{self.repository}:environment:{environment}"

    def role_name(self, environment: DeployEnvironment) -> str:
        return f"campps-{self.name}-{environment}-gha-deploy-role"

    def policy_name(self, environment: DeployEnvironment) -> str:
        return f"campps-{self.name}-{environment}-gha-deploy-policy"


CAMPPS_SERVICE_REPOSITORIES: tuple[ServiceRepository, ...] = ()
```

- [ ] **Step 2: Create the deploy-role stack**

Create `infiquetra_aws_infra/campps_deploy_roles_stack.py` with:

```python
"""GitHub OIDC deploy roles for CAMPPS workload service repositories."""

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

from .campps_service_registry import (
    CAMPPS_SERVICE_REPOSITORIES,
    DeployEnvironment,
    ServiceRepository,
)

CAMPPS_DEV_ACCOUNT_ID = "477152411873"
CAMPPS_PROD_ACCOUNT_ID = "431643435299"


class CamppsDeployRolesStack(Stack):
    """Create environment-scoped deploy roles for CAMPPS service repos."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        target_environment: DeployEnvironment,
        service_repositories: tuple[
            ServiceRepository, ...
        ] = CAMPPS_SERVICE_REPOSITORIES,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.target_environment = target_environment
        self.service_repositories = service_repositories

        github_oidc_provider = self.create_oidc_provider()
        for service in self.service_repositories:
            if self.target_environment in service.environments:
                self.create_service_deploy_role(service, github_oidc_provider)

    def create_oidc_provider(self) -> iam.OpenIdConnectProvider:
        return iam.OpenIdConnectProvider(
            self,
            "GitHubOIDCProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
            thumbprints=["1111111111111111111111111111111111111111"],
        )

    def create_service_deploy_role(
        self,
        service: ServiceRepository,
        oidc_provider: iam.OpenIdConnectProvider,
    ) -> None:
        role = iam.Role(
            self,
            f"{self.pascal_case(service.name)}DeployRole",
            role_name=service.role_name(self.target_environment),
            description=(
                f"Deploy {service.repository} to CAMPPS {self.target_environment}"
            ),
            assumed_by=iam.FederatedPrincipal(
                oidc_provider.open_id_connect_provider_arn,
                {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": service.github_subject(
                            self.target_environment
                        ),
                    }
                },
                "sts:AssumeRoleWithWebIdentity",
            ),
            max_session_duration=cdk.Duration.hours(2),
        )
        role.add_managed_policy(self.create_service_deploy_policy(service))
        CfnOutput(
            self,
            f"{self.pascal_case(service.name)}DeployRoleArn",
            value=role.role_arn,
            description=f"Deploy role ARN for {service.repository}",
        )

    def create_service_deploy_policy(
        self, service: ServiceRepository
    ) -> iam.ManagedPolicy:
        return iam.ManagedPolicy(
            self,
            f"{self.pascal_case(service.name)}DeployPolicy",
            managed_policy_name=service.policy_name(self.target_environment),
            description=(
                f"Serverless deploy permissions for {service.repository} "
                f"in {self.target_environment}"
            ),
            document=iam.PolicyDocument(
                statements=self.serverless_api_policy_statements(service)
            ),
        )

    def serverless_api_policy_statements(
        self, service: ServiceRepository
    ) -> list[iam.PolicyStatement]:
        stack_prefix = f"campps-{service.name}-{self.target_environment}"
        return [
            iam.PolicyStatement(
                actions=[
                    "cloudformation:CreateStack",
                    "cloudformation:UpdateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:GetTemplate",
                    "cloudformation:CreateChangeSet",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:ValidateTemplate",
                ],
                resources=[
                    f"arn:aws:cloudformation:{self.region}:{self.account}:stack/{stack_prefix}-*/*"
                ],
            ),
            iam.PolicyStatement(
                actions=[
                    "cloudformation:DescribeStacks",
                    "cloudformation:ListStacks",
                    "sts:GetCallerIdentity",
                ],
                resources=["*"],
            ),
            iam.PolicyStatement(
                actions=[
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:PassRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:UpdateRole",
                    "iam:UpdateAssumeRolePolicy",
                ],
                resources=[
                    f"arn:aws:iam::{self.account}:role/{stack_prefix}-*",
                    f"arn:aws:iam::{self.account}:role/cdk-*",
                ],
            ),
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                resources=[
                    f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}",
                    f"arn:aws:s3:::cdk-*-assets-{self.account}-{self.region}/*",
                ],
            ),
            iam.PolicyStatement(
                actions=[
                    "lambda:*",
                    "apigateway:*",
                    "apigatewayv2:*",
                    "dynamodb:*",
                    "events:*",
                    "sqs:*",
                    "logs:*",
                    "cloudwatch:*",
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:PutParameter",
                    "secretsmanager:GetSecretValue",
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:GenerateDataKey",
                ],
                resources=["*"],
                conditions={"StringEquals": {"aws:RequestedRegion": self.region}},
            ),
        ]

    def pascal_case(self, value: str) -> str:
        return "".join(part.capitalize() for part in value.split("-"))
```

- [ ] **Step 3: Create the separate CAMPPS bootstrap CDK app**

Create `app_campps_bootstrap.py` with:

```python
#!/usr/bin/env python3
import aws_cdk as cdk
from dotenv import load_dotenv

from infiquetra_aws_infra.campps_deploy_roles_stack import (
    CAMPPS_DEV_ACCOUNT_ID,
    CAMPPS_PROD_ACCOUNT_ID,
    CamppsDeployRolesStack,
)

load_dotenv()

app = cdk.App()

CamppsDeployRolesStack(
    app,
    "CamppsNonProdDeployRolesStack",
    target_environment="nonprod",
    env=cdk.Environment(account=CAMPPS_DEV_ACCOUNT_ID, region="us-east-1"),
    description="GitHub OIDC deploy roles for CAMPPS nonprod service repositories",
)

CamppsDeployRolesStack(
    app,
    "CamppsProductionDeployRolesStack",
    target_environment="production",
    env=cdk.Environment(account=CAMPPS_PROD_ACCOUNT_ID, region="us-east-1"),
    description="GitHub OIDC deploy roles for CAMPPS production service repositories",
)

app.synth()
```

- [ ] **Step 4: Run the deploy-role tests**

Run:

```bash
uv run pytest tests/unit/test_campps_deploy_roles_stack.py -q
```

Expected: PASS.

- [ ] **Step 5: Run a bootstrap app synth**

Run:

```bash
uv run cdk -a "python app_campps_bootstrap.py" synth --quiet
```

Expected: PASS. Because the registry is empty, the synthesized workload stacks should contain the OIDC provider and no service deploy roles until a real service repo is added.

- [ ] **Step 6: Commit the deploy-role registry implementation**

Run this only if commits are authorized for the session:

```bash
git add app_campps_bootstrap.py infiquetra_aws_infra/campps_service_registry.py infiquetra_aws_infra/campps_deploy_roles_stack.py tests/unit/test_campps_deploy_roles_stack.py
git commit -m "feat(campps): add registry generated deploy roles"
```

---

## Task 7: Document the new foundation model

**Files:**
- Modify: `docs/ops/02-identity-and-access.md`
- Modify: `docs/ops/03-login-flows.md`
- Modify: `docs/ops/04-ci-cd-pipeline.md`
- Modify: `docs/engineering-journal/DECISIONS.md`
- Modify: `docs/engineering-journal/QUEUED.md`

- [ ] **Step 1: Update identity and access docs**

In `docs/ops/02-identity-and-access.md`, add a section after the current assignment table:

```markdown
## Target CAMPPS access model

CAMPPS workload development should use group-based Identity Center assignments instead of direct user assignments.

| Group | Account | Permission set | Purpose |
|---|---|---|---|
| `InfiquetraAdmins` | `645166163764` | `CoreAdministrator` | Organization, SSO, and foundation administration |
| `CAMPPSDevelopers` | `477152411873` | `CAMPPSDeveloper` | Nonprod service deployment and debugging |
| `CAMPPSProdReadOnly` | `431643435299` | `ReadOnlyAccess` | Production inspection |
| `CAMPPSProdBreakGlassAdmins` | `431643435299` | `CAMPPSProductionBreakGlassAdministrator` | Emergency production changes |

The CDK template makes these assignments conditional on group ID parameters. This lets us deploy the permission sets safely before the groups exist, then pass group IDs once they are verified.

Do not remove the legacy direct assignments until the replacement SSO profiles are tested.
```

- [ ] **Step 2: Update login flow docs**

In `docs/ops/03-login-flows.md`, add this profile guidance near the local CLI section:

```markdown
## CAMPPS local development profiles

Use SSO profiles for local AWS work. Do not create long-lived IAM users or access keys.

Recommended local profiles:

| Profile | Account | Role | Use |
|---|---|---|---|
| `infiquetra-root` | `645166163764` | `CoreAdministrator` | Organization and SSO foundation work |
| `campps-dev` | `477152411873` | `CAMPPSDeveloper` | Local nonprod deploys and debugging |
| `campps-prod-readonly` | `431643435299` | `ReadOnlyAccess` | Production inspection |
| `campps-prod-breakglass` | `431643435299` | `CAMPPSProductionBreakGlassAdministrator` | Emergency production changes only |

Local deploys are allowed for `campps-dev` when they target the same stack names and CDK environment as GitHub nonprod deploys. Production deploys should normally use the protected GitHub Actions path.
```

- [ ] **Step 3: Update CI/CD docs**

In `docs/ops/04-ci-cd-pipeline.md`, add this section near the deployment workflow discussion:

```markdown
## CAMPPS service repository deployment model

The foundation repository deploys organization and SSO resources. CAMPPS service repositories deploy workload resources.

Each service repo should have:

1. read-only PR validation with no AWS write access
2. a nonprod GitHub environment that assumes a deploy role in `campps-dev`
3. a protected production GitHub environment that assumes a deploy role in `campps-prod`
4. a local SSO path for nonprod iteration against the same stack names used by CI

Service deploy roles are generated from the CAMPPS service registry, not from broad `repo:infiquetra/*` trust. A new service repo is onboarded by adding it to the registry and deploying `app_campps_bootstrap.py`.
```

- [ ] **Step 4: Add the engineering journal decision**

Add this entry near the top of `docs/engineering-journal/DECISIONS.md`:

```markdown
## 2026-05-06

### Use registry-generated per-repo OIDC roles for CAMPPS workload deployments

**Decision.** CAMPPS service repositories get exact repository and GitHub environment scoped deploy roles in workload accounts. Nonprod deploys use `campps-dev`; production deploys use `campps-prod`; local SSO deploys remain allowed for nonprod iteration only when they converge on the same stack names as CI.
**Rejected alternatives.**
- Reuse `infiquetra-aws-infra-gha-role`: rejected because it is a management-account role with Organizations and SSO permissions.
- Use `repo:infiquetra/*` for all deploy roles: rejected for write access because it lets every current and future org repo attempt workload deployment.
- Local-only deploys until the app matures: rejected because it delays release-flow validation and creates migration debt.
**Implementation.** Tighten the management OIDC role, add conditional SSO group assignments, and add a CAMPPS service registry that generates per-repo workload deploy roles.
**Revisit when.** Service repo onboarding becomes frequent enough that the registry belongs in a dedicated CAMPPS bootstrap repository, or when GitHub environments no longer fit the release model.
**Commit.** Pending implementation PR.
```

- [ ] **Step 5: Update the queued access item**

In `docs/engineering-journal/QUEUED.md`, update the P2 legacy admin migration item notes to include:

```markdown
**Notes:** Replacement group assignment scaffolding exists in CDK. Do not remove legacy direct assignments until the new group IDs have been passed to the stack, SSO profiles are verified, and break-glass access is confirmed.
```

- [ ] **Step 6: Commit documentation updates**

Run this only if commits are authorized for the session:

```bash
git add docs/ops/02-identity-and-access.md docs/ops/03-login-flows.md docs/ops/04-ci-cd-pipeline.md docs/engineering-journal/DECISIONS.md docs/engineering-journal/QUEUED.md
git commit -m "docs(campps): document AWS CI foundation model"
```

---

## Task 8: Run full local verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run root unit tests**

Run:

```bash
uv run pytest tests/unit/test_sso_stack.py tests/unit/test_campps_deploy_roles_stack.py -q
```

Expected: PASS.

- [ ] **Step 2: Run bootstrap unit tests**

Run:

```bash
cd github-oidc-bootstrap && uv run pytest tests/unit/test_github_oidc_stack.py -q
```

Expected: PASS.

- [ ] **Step 3: Run linting**

Run:

```bash
uv run ruff check .
cd github-oidc-bootstrap && uv run ruff check github_oidc_bootstrap tests
```

Expected: PASS.

- [ ] **Step 4: Run type checks**

Run:

```bash
uv run mypy .
cd github-oidc-bootstrap && uv run mypy github_oidc_bootstrap tests
```

Expected: PASS.

- [ ] **Step 5: Synthesize the foundation app**

Run:

```bash
GITHUB_REPO=infiquetra-aws-infra CDK_DEFAULT_ACCOUNT=645166163764 CDK_DEFAULT_REGION=us-east-1 uv run cdk synth --all --quiet
```

Expected: PASS.

- [ ] **Step 6: Synthesize the CAMPPS bootstrap app**

Run:

```bash
uv run cdk -a "python app_campps_bootstrap.py" synth --quiet
```

Expected: PASS.

- [ ] **Step 7: Inspect generated templates for high-risk trust**

Run:

```bash
grep -R "repo:infiquetra/\*" cdk.out github-oidc-bootstrap/cdk.out || true
```

Expected: no matches in deploy-role trust policies.

- [ ] **Step 8: Commit verification-only fixes if needed**

If verification required fixes, commit them separately only if commits are authorized:

```bash
git add <changed-files>
git commit -m "fix(campps): address foundation verification issues"
```

---

## Task 9: Deployment preflight checklist

**Files:**
- No code changes expected.

- [ ] **Step 1: Inspect current Identity Center groups**

Run only with explicit approval because this calls AWS APIs:

```bash
INSTANCE=arn:aws:sso:::instance/ssoins-7223f05fc9da6e24
STORE=d-90676975b4
aws identitystore list-groups \
  --identity-store-id "$STORE" \
  --profile infiquetra-root \
  --query 'Groups[].{DisplayName:DisplayName,GroupId:GroupId}' \
  --output table
```

Expected: see existing groups and confirm which group IDs should be passed to the SSO stack.

- [ ] **Step 2: Deploy SSO assignment parameters only after group IDs are known**

Run only with explicit approval:

```bash
GITHUB_REPO=infiquetra-aws-infra \
CDK_DEFAULT_ACCOUNT=645166163764 \
CDK_DEFAULT_REGION=us-east-1 \
uv run cdk deploy InfiquetraSSOStack \
  --profile infiquetra-root \
  --parameters InfiquetraAdminsGroupId=<group-id> \
  --parameters CamppsDevelopersGroupId=<group-id> \
  --parameters CamppsProdReadOnlyGroupId=<group-id> \
  --parameters CamppsProdBreakGlassAdminsGroupId=<group-id>
```

Expected: CloudFormation updates SSO assignments without removing legacy direct assignments.

- [ ] **Step 3: Test SSO access before removing legacy assignments**

Run only with explicit approval:

```bash
aws sts get-caller-identity --profile infiquetra-root
aws sts get-caller-identity --profile campps-dev
aws sts get-caller-identity --profile campps-prod-readonly
aws sts get-caller-identity --profile campps-prod-breakglass
```

Expected: each profile returns the expected account ID.

- [ ] **Step 4: Deploy the GitHub OIDC bootstrap hardening**

Run only with explicit approval:

```bash
cd github-oidc-bootstrap && uv run cdk deploy --profile infiquetra-root
```

Expected: the trust policy for `infiquetra-aws-infra-gha-role` no longer contains `repo:infiquetra/*`.

- [ ] **Step 5: Deploy CAMPPS bootstrap stacks after first service repo is registered**

Do not run this until `CAMPPS_SERVICE_REPOSITORIES` contains a real repo:

```bash
uv run cdk -a "python app_campps_bootstrap.py" deploy CamppsNonProdDeployRolesStack --profile campps-dev
uv run cdk -a "python app_campps_bootstrap.py" deploy CamppsProductionDeployRolesStack --profile campps-prod-breakglass
```

Expected: workload-account OIDC providers and per-service deploy roles are created.

---

## Spec Coverage Review

- Human SSO access: Tasks 3, 4, 7, and 9.
- Management OIDC hardening: Tasks 1, 2, 7, and 9.
- Registry-generated deploy roles: Tasks 5, 6, 7, and 9.
- Nonprod GitHub deployment plus local SSO deploys: Tasks 6, 7, and 9.
- Production protected deploy path: Tasks 6, 7, and 9.
- Non-access foundations and release flow documentation: Task 7.
- Verification: Task 8 and Task 9.

No real service repo is registered in this plan because the first deployable service will be chosen by the CAMPPS blueprint context packs. The registry and deploy-role stack are implemented and tested with a fixture service, and production deploy roles are created when the first real service repo is added.
