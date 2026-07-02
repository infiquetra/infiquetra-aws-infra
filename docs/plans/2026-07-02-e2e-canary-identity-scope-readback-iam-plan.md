---
title: Add e2e-canary nonprod identity-scope readback IAM grant
type: fix
status: active
date: 2026-07-02
origin: ""
deepened: 2026-07-02
---

# Add e2e-canary nonprod identity-scope readback IAM grant

## Summary

Add one optional managed policy to the CAMPPS deploy-role stack for only `campps-e2e-canary` in `nonprod`, attached only to `campps-e2e-canary-nonprod-gha-deploy-role`, granting exactly `dynamodb:GetItem` on `campps-identity-access-nonprod`.

The work is a minimum IAM unblocking change for the `tenant-config-publish-and-scope` live proof. It should not broaden the base deploy profile, staging, production, or unrelated service roles.

---

## Problem Frame

The e2e canary live proof publishes a synthetic tenant/session through `campps-tenant-setup`, then reads back the identity-access projection row at `PK=TENANT#{tenant_id}` and `SK=SCOPE#session#{session_id}`. Current IAM simulation for `arn:aws:iam::477152411873:role/campps-e2e-canary-nonprod-gha-deploy-role` returns `implicitDeny` for `dynamodb:GetItem` on `arn:aws:dynamodb:us-east-1:477152411873:table/campps-identity-access-nonprod`.

The repo already has a comparable pattern for a deploy-gated cross-service proof: `_create_scope_seam_proof_policy` returns `None` unless the service is `tenant-setup` and the target environment is `nonprod`, then attaches a narrow managed policy to that deploy role.

---

## Requirements

R1. `campps-e2e-canary-nonprod-gha-deploy-role` receives a dedicated managed policy for identity scope readback.

R2. The policy grants only `dynamodb:GetItem` on `arn:aws:dynamodb:us-east-1:477152411873:table/campps-identity-access-nonprod`.

R3. The synthesized policy does not include `dynamodb:Query`, `dynamodb:Scan`, wildcard DynamoDB table access, staging resources, or production resources.

R4. No e2e-canary staging or production role/policy is synthesized.

R5. Unrelated service deploy roles do not receive the e2e-canary identity-scope readback policy.

R6. The existing tenant-setup seam-proof grant remains functionally unchanged.

R7. Validation covers unit synthesis, lint/type checks, CDK synth, nonprod workload-stack deploy, and IAM simulation readback.

---

## Key Technical Decisions

KTD1. Use a standalone optional managed-policy helper: mirror `_create_scope_seam_proof_policy` instead of modifying the shared `serverless-api` deploy policy because this grant is for one live proof lane, not a general deploy capability.

KTD2. Gate on both service and environment: require `service_repository.name == "e2e-canary"` and `target_environment == "nonprod"` even though the registry already marks e2e-canary nonprod-only, because the helper should be auditable and testable if registry shape changes.

KTD3. Grant only table-level `dynamodb:GetItem`: use the exact identity-access nonprod table ARN and do not add `Query`, `Scan`, table wildcards, or row-key IAM conditions; the runtime tenant/session keys are synthetic and the acceptance contract is the one required `GetItem` simulation.

KTD4. Pin the managed policy name: use `campps-e2e-canary-nonprod-gha-identity-scope-readback-policy` so the policy is auditable in IAM and unit tests can assert the exact synthesized attachment.

KTD5. Deploy through the CAMPPS workload bootstrap path: changes to `CamppsNonProdDeployRolesStack` require the workload deploy-role stack, not only the management-account foundation pipeline.

---

## High-Level Technical Design

The deploy-role stack already creates a role per in-scope service/environment, attaches the deploy-profile managed policies, then conditionally attaches the tenant-setup seam-proof policy.

```
CAMPPS_SERVICE_REPOSITORIES
  -> CamppsDeployRolesStack(target_environment)
    -> skip services not in environment
    -> create deploy role
    -> attach base deploy-profile policies
    -> attach tenant-setup seam-proof policy when tenant-setup + nonprod
    -> attach e2e-canary identity readback policy when e2e-canary + nonprod
```

The new policy should be parallel to the tenant-setup helper, not folded into the base deploy policies. The managed policy name should be `campps-e2e-canary-nonprod-gha-identity-scope-readback-policy`.

---

## Implementation Units

### U1. Add the e2e-canary nonprod readback policy helper

Add the narrow IAM policy without changing shared deploy-profile grants.

**Goal:** Create an optional managed-policy helper in `CamppsDeployRolesStack` and attach it only when the current service is `e2e-canary` and the target environment is `nonprod`.

**Requirements:** R1, R2, R3, R4, R5.

**Dependencies:** None.

**Files:** `infiquetra_aws_infra/campps_deploy_roles_stack.py`; `tests/unit/test_campps_deploy_roles_stack.py`.

**Approach:** Add a method next to `_create_scope_seam_proof_policy` that returns `iam.ManagedPolicy | None`. The method should return `None` for every service/environment combination except `e2e-canary` + `nonprod`, and its non-`None` branch should contain exactly one `iam.PolicyStatement` with `actions=["dynamodb:GetItem"]` and the formatted identity-access nonprod table ARN.

**Patterns to follow:** The existing constructor attaches optional policies after base deploy policies at `infiquetra_aws_infra/campps_deploy_roles_stack.py:62-75`. The tenant-setup seam-proof helper demonstrates the guard-return pattern at `infiquetra_aws_infra/campps_deploy_roles_stack.py:1602-1663`.

**Test scenarios:** Happy path: synthesize only `ServiceRepository(name="e2e-canary", repository="infiquetra/campps-e2e-canary", environments=("nonprod",))` for `nonprod`; assert the managed policy exists, has exactly one statement, grants only `dynamodb:GetItem`, targets only `table/campps-identity-access-nonprod`, and the e2e-canary deploy role includes a `ManagedPolicyArns` reference to that policy.

**Test scenarios:** Real registry higher environments: synthesize `CANONICAL_SERVICE_REPOSITORIES` for `staging` and `production`; assert no e2e-canary role is synthesized and no identity-scope readback policy or higher-environment identity-access table resource appears.

**Test scenarios:** Helper guard: synthesize a test-only `ServiceRepository(name="e2e-canary", repository="infiquetra/campps-e2e-canary", environments=("nonprod", "staging", "production"))` for `staging` and `production`; if those test-only roles are present, assert the identity-scope readback policy is still absent.

**Verification:** The generated CloudFormation contains one new managed policy and one new role attachment in the nonprod e2e-canary template, with no changes to base policy names or permissions boundaries.

### U2. Add regression tests for isolation and existing seam-proof behavior

Prove the new policy is not accidentally generalized.

**Goal:** Extend `tests/unit/test_campps_deploy_roles_stack.py` with positive and negative synthesis coverage for the new grant while preserving the tenant-setup seam-proof tests.

**Requirements:** R3, R4, R5, R6.

**Dependencies:** U1.

**Files:** `tests/unit/test_campps_deploy_roles_stack.py`.

**Approach:** Add an `E2E_CANARY_REPO` fixture constant near the existing `TENANT_SETUP_REPO` seam-proof section. Add policy-name helpers or assertions that search `AWS::IAM::ManagedPolicy` names by exact managed policy name or suffix, matching the existing `find_managed_policy` helper.

**Patterns to follow:** `find_managed_policy` already locates synthesized managed policies by exact name at `tests/unit/test_campps_deploy_roles_stack.py:1106-1114`. Existing e2e-canary tests assert the fixture is nonprod-only and role-gated at `tests/unit/test_campps_deploy_roles_stack.py:258-265` and `tests/unit/test_campps_deploy_roles_stack.py:1160-1200`. The tenant-setup seam-proof tests at `tests/unit/test_campps_deploy_roles_stack.py:1376-1451` provide the positive/negative policy structure.

**Test scenarios:** Happy path: e2e-canary nonprod gets exactly one identity-scope readback policy and the role attachment points at it.

**Test scenarios:** Isolation: synthesize tenant-setup, identity-access, and at least one unrelated serverless service for nonprod; assert none receive or synthesize the e2e-canary readback policy.

**Test scenarios:** Higher environments: synthesize the real canonical registry for staging and production; assert no e2e-canary role or identity-scope readback policy is produced.

**Test scenarios:** Regression: keep the existing tenant-setup seam-proof policy name and its two expected statements unchanged, and assert it does not acquire the e2e-canary readback policy.

**Verification:** `uv run pytest tests/unit/test_campps_deploy_roles_stack.py -q` proves the positive grant, negative environments, unrelated-service isolation, and tenant-setup regression in one focused suite.

### U3. Validate, deploy nonprod, and record operational evidence

Ship only after the synthesized policy passes local gates and live IAM simulation.

**Goal:** Validate the narrow synthesis result, deploy the nonprod workload deploy-role stack, and prove the live role can perform the required `GetItem`.

**Requirements:** R7.

**Dependencies:** U1, U2.

**Files:** `docs/engineering-journal/DECISIONS.md`; `docs/engineering-journal/LEARNINGS.md` only if deployment reveals a durable surprise.

**Approach:** Keep the decision entry tied to the helper, policy name, rejected broad grants, and revisit conditions. Deployment should target `CamppsNonProdDeployRolesStack` from `app_campps_bootstrap.py`; do not rely on the management-account foundation workflow alone.

**Patterns to follow:** `app_campps_bootstrap.py:18-24` defines the nonprod deploy-role stack. The engineering journal notes that workload deploy-role policy changes require the CAMPPS workload deploy-role stack and a live IAM simulation at `docs/engineering-journal/LEARNINGS.md:71-83`.

**Test scenarios:** Integration: after deploy, run IAM simulation for principal `arn:aws:iam::477152411873:role/campps-e2e-canary-nonprod-gha-deploy-role`, action `dynamodb:GetItem`, resource `arn:aws:dynamodb:us-east-1:477152411873:table/campps-identity-access-nonprod`; expected result is `allowed`.

**Test scenarios:** Checklist-only: confirm the required e2e-canary actor-token GitHub/operator environment secret exists before the live workflow is run; do not add the token value or secret wiring to this repo.

**Verification:** Local gates pass, CDK synth succeeds, `CamppsNonProdDeployRolesStack` deploys, and IAM simulation returns `allowed` for the exact required action/resource.

---

## Risks & Dependencies

| risk | impact | mitigation |
|------|--------|------------|
| Wrong deployment path | Source merges but the live nonprod role remains denied. | Deploy `CamppsNonProdDeployRolesStack` via the CAMPPS workload bootstrap app and verify with IAM simulation. |
| Grant accidentally lands in a shared profile | Unrelated services inherit identity-access table readback. | Keep the grant in a guarded optional helper and test unrelated services. |
| Higher environments receive speculative access | Staging/production deploy roles get unnecessary cross-service read access. | Gate on `target_environment == "nonprod"` and add staging/production negative synthesis tests. |

---

## Verification Gates

Run the narrow checks first, then broaden only after unit synthesis passes.

```bash
uv run pytest tests/unit/test_campps_deploy_roles_stack.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy infiquetra_aws_infra tests
uv run cdk synth --all --quiet
uv run cdk -a "python app_campps_bootstrap.py" synth --quiet
```

Deploy the nonprod workload deploy-role stack after the local gates pass.

```bash
uv run cdk -a "python app_campps_bootstrap.py" deploy \
  CamppsNonProdDeployRolesStack \
  --profile campps-nonprod --region us-east-1
```

After nonprod deployment, run IAM simulation for the live role/action/resource.

```bash
aws iam simulate-principal-policy \
  --profile campps-nonprod \
  --policy-source-arn arn:aws:iam::477152411873:role/campps-e2e-canary-nonprod-gha-deploy-role \
  --action-names dynamodb:GetItem \
  --resource-arns arn:aws:dynamodb:us-east-1:477152411873:table/campps-identity-access-nonprod
```

---

## Scope Boundaries

This plan does not add `Query`, `Scan`, batch reads, write actions, table wildcards, staging grants, production grants, or unrelated service-role grants.

This plan does not run the full `campps-e2e-canary` live workflow; that is a follow-up verification once IAM simulation is allowed and required operator/GitHub environment prerequisites are confirmed.

---

## Sources / Research

| source | evidence |
|--------|----------|
| `infiquetra_aws_infra/campps_deploy_roles_stack.py:49-75` | Stack iterates in-scope service repositories and attaches optional managed policies to each deploy role. |
| `infiquetra_aws_infra/campps_deploy_roles_stack.py:1602-1663` | Tenant-setup seam-proof policy is a guarded helper with nonprod-only cross-service grants. |
| `infiquetra_aws_infra/campps_service_registry.py:88-98` | `e2e-canary` is explicitly registered as a nonprod-only deploy fixture. |
| `tests/unit/test_campps_deploy_roles_stack.py:1106-1114` | Unit tests already provide exact managed-policy lookup helpers. |
| `tests/unit/test_campps_deploy_roles_stack.py:1160-1200` | Existing tests prove e2e-canary role creation is nonprod-only. |
| `tests/unit/test_campps_deploy_roles_stack.py:1376-1451` | Existing seam-proof tests provide the positive/negative policy-test model. |
| `cdk.json:1-3` | The default CDK app is `python3 app.py`, so workload deploy-role synth needs an explicit app override. |
| `docs/ops/04-ci-cd-pipeline.md:194-208` | Workload deploy-role synth/deploy uses `uv run cdk -a "python app_campps_bootstrap.py"` and deploys nonprod first. |
| `docs/engineering-journal/DECISIONS.md:47-62` | Prior tenant-setup seam-proof decision records the narrow grant pattern and rejected broad grants. |
| `docs/engineering-journal/LEARNINGS.md:71-83` | Workload deploy-role policy changes require the CAMPPS workload deploy-role stack plus live IAM simulation. |
