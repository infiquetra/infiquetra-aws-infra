---
title: Grant campps-platform nonprod deploy role least-privilege access to the e2e canary
type: fix
status: active
date: 2026-08-20
origin: https://github.com/infiquetra/infiquetra-aws-infra/issues/156
destination: merge
orchestration: inline
---

# Grant campps-platform nonprod deploy role least-privilege access to the e2e canary

## Summary

Add one optional managed policy to `CamppsDeployRolesStack`, attached only to `campps-platform-nonprod-gha-deploy-role`, granting exactly `cloudformation:DescribeStacks` on `campps-e2e-canary-nonprod` and `lambda:InvokeFunctionUrl` on `campps-e2e-canary-nonprod-health`.

This is a source-only IAM unblocking change for the campps-platform enforced e2e canary. It must not widen the platform-foundation deploy profile, staging, production, or any other service role.

---

## Problem Frame

`campps-platform`'s enforced e2e canary (`tests/e2e/test_cookiecutter_deploy.py` on origin/main `430f36b`) describes stack `campps-e2e-canary-nonprod`, reads the `HealthUrl` output, and issues a SigV4-signed GET against the IAM-authenticated Lambda Function URL.

Independently re-measured 2026-08-20 in account `477152411873` / `us-east-1` against `arn:aws:iam::477152411873:role/campps-platform-nonprod-gha-deploy-role`:

| action | resource | `simulate-principal-policy` |
|---|---|---|
| `cloudformation:DescribeStacks` | `arn:aws:cloudformation:us-east-1:477152411873:stack/campps-e2e-canary-nonprod/*` | `implicitDeny` (no matched statements) |
| `lambda:InvokeFunctionUrl` | `arn:aws:lambda:us-east-1:477152411873:function:campps-e2e-canary-nonprod-health` | `implicitDeny` (no matched statements) |

The stack exists (`UPDATE_COMPLETE`) and exposes `HealthUrl`. The health function exists with `AuthType=AWS_IAM` and explicit name `campps-e2e-canary-nonprod-health`. The function resource policy names only `campps-e2e-canary-nonprod-gha-deploy-role`, so it cannot save the platform deploy role.

The test catches `ClientError` / `BotoCoreError` from `DescribeStacks` and calls `pytest.skip`, so the gate reports green while proving nothing.

The live role has three attached managed policies and **zero** inline policies (`list-role-policies` → `PolicyNames: []`). Issue #156's "inline policy" wording is a misnomer for the managed policy named `campps-platform-nonprod-gha-deploy-policy`.

---

## Requirements

R1. `campps-platform-nonprod-gha-deploy-role` receives a dedicated managed policy for the e2e canary health probe.

R2. The policy grants only `cloudformation:DescribeStacks` on `arn:aws:cloudformation:us-east-1:477152411873:stack/campps-e2e-canary-nonprod/*` and only `lambda:InvokeFunctionUrl` on `arn:aws:lambda:us-east-1:477152411873:function:campps-e2e-canary-nonprod-health`.

R3. No action wildcards, no account-wide resource ARNs, no `lambda:InvokeFunction` in this change.

R4. The factory returns `None` for every service other than `platform` and every environment other than `nonprod`. Unit tests call the factory and assert that, not only the synthesized happy path.

R5. Template assertions prove the policy is attached to `campps-platform-nonprod-gha-deploy-role` and to no other role.

R6. `campps-platform-nonprod-gha-data-policy`, `campps-platform-nonprod-gha-runtime-policy`, and `campps-platform-nonprod-gha-deploy-policy` PolicyDocuments are byte-unchanged. Staging and production full-registry synth templates are byte-unchanged.

R7. Validation is local only: unit tests, lint, type check, security scan, CDK synth. No AWS writes, no deployment tag, no closure of campps-platform #43.

---

## Key Technical Decisions

KTD1. Use a standalone optional managed-policy helper: mirror `_create_scope_seam_proof_policy` instead of modifying `_create_platform_foundation_deploy_policies`, because this grant is one live-proof lane, not a general platform deploy capability.

KTD2. Gate on both `service_repository.name == "platform"` and `target_environment == "nonprod"`. The registry name is `platform`, not `campps-platform`; the role name prefix is added by `ServiceRepository.role_name`. A gate on `"campps-platform"` would silently return `None` forever. Tests must include that trap.

KTD3. Two statements, not one: CloudFormation and Lambda resource ARNs cannot share a statement. Pin nonprod resource name literals (`campps-e2e-canary-nonprod`, `campps-e2e-canary-nonprod-health`) rather than interpolating `target_environment`, so a forgotten environment gate still cannot name a staging or production canary.

KTD4. Pin the managed policy name to `campps-platform-nonprod-gha-e2e-canary-health-policy` so attachment tests can assert the exact synthesized name.

KTD5. Do not add `lambda:InvokeFunction` in this change. Issue #156 and the campps-platform umbrella plan name exactly two actions. The canary function's resource policy already emits both `InvokeFunctionUrl` and `InvokeFunction` (with `InvokedViaFunctionUrl`) for a *different* principal. If a later authorized deploy still 403s the SigV4 GET, that is a follow-up identity grant with the `InvokedViaFunctionUrl` condition — queued, not invented here.

KTD6. Source-only destination is `merge`. Deployment of `CamppsNonProdDeployRolesStack` is a separately authorized operator step. A green `Deploy Infrastructure` workflow is not evidence the grant is live (LEARNINGS 2026-06-17, issue #155).

---

## High-Level Technical Design

The constructor already attaches optional managed policies after the profile policies. Add one more helper in that list.

```
CAMPPS_SERVICE_REPOSITORIES
  -> CamppsDeployRolesStack(target_environment)
    -> skip services not in environment
    -> create deploy role
    -> attach base deploy-profile policies
    -> attach existing optional helpers (seam-proof, tenant-read deny, ...)
    -> attach platform e2e-canary health policy when platform + nonprod
```

`campps_service_registry.py` does not change. `platform` is already registered with the `platform-foundation` profile in all three environments.

---

## Implementation Units

### U1. Add the platform nonprod e2e-canary health policy helper

Add the narrow IAM policy without changing shared platform-foundation grants.

**Goal:** Create an optional managed-policy helper in `CamppsDeployRolesStack` and attach it only when the current service is `platform` and the target environment is `nonprod`.

**Requirements:** R1, R2, R3, R4.

**Dependencies:** None.

**Files:** `infiquetra_aws_infra/campps_deploy_roles_stack.py`.

**Approach:** Add `_create_platform_e2e_canary_health_policy` next to `_create_scope_seam_proof_policy` / `_create_e2e_canary_identity_scope_readback_policy`. Return `None` unless `service_repository.name == "platform"` and `target_environment == "nonprod"`. The non-`None` branch creates one managed policy with two `iam.PolicyStatement`s: `E2eCanaryStackDescribe` (`cloudformation:DescribeStacks` on `stack/campps-e2e-canary-nonprod/*`) and `E2eCanaryHealthInvoke` (`lambda:InvokeFunctionUrl` on `function:campps-e2e-canary-nonprod-health`). Lambda uses `ArnFormat.COLON_RESOURCE_NAME`; CloudFormation uses `ArnFormat.SLASH_RESOURCE_NAME`. Call the helper from `__init__` after the existing optional attachments.

**Patterns to follow:** Guard-return helpers at `infiquetra_aws_infra/campps_deploy_roles_stack.py:1693` and `:1830`. Constructor optional-attach loop at `:78-106`.

**Test scenarios:** Covered by U2. This unit is not independently landable without the tests that prove the gate.

**Verification:** Synthesized nonprod platform template contains one new managed policy and one new role attachment; staging/production templates and the three existing platform policy documents hash-match the pre-change freeze.

### U2. Prove the gate, the ARNs, the single attachment, and no collateral

Negative tests are the product. A happy-path-only suite is not evidence.

**Goal:** Extend `tests/unit/test_campps_deploy_roles_stack.py` so that deleting the environment check, starring a resource, attaching the policy to a second role, or editing a base platform policy each turns the suite red.

**Requirements:** R4, R5, R6.

**Dependencies:** U1.

**Files:** `tests/unit/test_campps_deploy_roles_stack.py`.

**Approach:** Directly construct a `CamppsDeployRolesStack` with no services and call the factory for every `CAMPPS_SERVICE_REPOSITORIES` × `{nonprod, staging, production}` pair except `platform`+`nonprod`, plus a `name="campps-platform"` trap. Synth the matching pair and assert exact actions and exact ARN fragments. Synth the full canonical registry for nonprod and assert the new policy's logical ID appears in `ManagedPolicyArns` of exactly one role, named `campps-platform-nonprod-gha-deploy-role`. Hash the three existing platform nonprod PolicyDocuments and the full staging/production registry templates against values frozen from `origin/main` at `b6809bc`.

**Patterns to follow:** `find_managed_policy_with_logical_id` at `tests/unit/test_campps_deploy_roles_stack.py:1111`. Tenant-read-deny negative + literal-ARN tests at `:1517-1568`. E2e-canary helper-guard at `:1726`.

**Test scenarios:** Factory returns `None` for every non-matching service and every non-matching environment, including the `campps-platform` name trap and a higher-environment `platform` role that still exists.

**Test scenarios:** Happy path: exactly two statements, exact actions, exact resource ARNs, no action wildcards, Lambda ARN contains no `*`, CloudFormation ARN's only `*` is the stack unique id.

**Test scenarios:** Full-registry nonprod synth attaches the new policy to `campps-platform-nonprod-gha-deploy-role` and to no other role, including the e2e-canary deploy role and live-proof role.

**Test scenarios:** SHA-256 of the three named platform nonprod PolicyDocuments matches the pre-change freeze. SHA-256 of staging and production full-registry `Template.to_json()` matches the pre-change freeze.

**Verification:** `uv run pytest tests/unit/test_campps_deploy_roles_stack.py -q` plus a mutation pass that deletes the environment check and confirms the factory-None test fails.

### U3. Record the decision, the live-measurement correction, and the residual risk

Ship the journal in the same commit as the code.

**Goal:** Record the binding choices and the non-obvious live facts so a later session does not re-derive them.

**Requirements:** R7.

**Dependencies:** U1, U2.

**Files:** `docs/engineering-journal/DECISIONS.md`; `docs/engineering-journal/LEARNINGS.md`; `docs/engineering-journal/QUEUED.md`.

**Approach:** DECISIONS captures KTD1–KTD5. LEARNINGS records that the live role has three managed policies and zero inline policies, and that the canary Function URL resource policy names the canary deploy role, not the platform role. QUEUED records the dual-permission residual (`lambda:InvokeFunction` with `InvokedViaFunctionUrl`) as worth-it-when the post-deploy SigV4 GET returns 403.

**Test expectation:** none -- documentation only.

**Verification:** Journal entries are in the same commit as the helper.

---

## Risks & Dependencies

| risk | impact | mitigation |
|------|--------|------------|
| Forgotten environment gate grants the policy in staging/production | Higher-env deploy roles get a canary probe grant they never exercise | Factory-None tests over every env; frozen staging/production template hashes |
| Gate on `"campps-platform"` instead of `"platform"` | Helper always returns `None`; the defect stays | Name-trap test plus positive attachment on `name="platform"` |
| Resource `"*"` still passes an actions-only assertion | Account-wide invoke/describe | Assert the exact ARN fragments; Lambda ARN must contain no `*` |
| Adding `lambda:InvokeFunction` "to be safe" | Widens the grant past issue #156 into `aws lambda invoke` unless conditioned | KTD5; queued follow-up only if the live probe 403s |
| Merge reported as live | False confidence; policy stays at current version | KTD6; LEARNINGS 2026-06-17 already names this trap |

---

## Verification Gates

Local only. No `cdk deploy`, no IAM mutation, no tag push.

```bash
uv run pytest tests/unit/test_campps_deploy_roles_stack.py -q
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy infiquetra_aws_infra tests
uv run bandit -r infiquetra_aws_infra
uv run cdk synth --all --quiet
uv run cdk -a "python app_campps_bootstrap.py" synth --quiet
```

After a separately authorized deploy of `CamppsNonProdDeployRolesStack` (not this change):

```bash
aws iam list-policy-versions \
  --policy-arn arn:aws:iam::477152411873:policy/campps-platform-nonprod-gha-e2e-canary-health-policy

aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::477152411873:role/campps-platform-nonprod-gha-deploy-role \
  --action-names cloudformation:DescribeStacks \
  --resource-arns arn:aws:cloudformation:us-east-1:477152411873:stack/campps-e2e-canary-nonprod/*

aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::477152411873:role/campps-platform-nonprod-gha-deploy-role \
  --action-names lambda:InvokeFunctionUrl \
  --resource-arns arn:aws:lambda:us-east-1:477152411873:function:campps-e2e-canary-nonprod-health
```

Then run the campps-platform e2e canary and confirm it executes rather than skips.

---

## Scope Boundaries

This plan does not add `lambda:InvokeFunction`, `cloudformation:Describe*`, Function URL auth-type conditions, staging grants, production grants, unrelated service-role grants, or any change to the platform-foundation core/runtime/data policies.

This plan does not deploy `CamppsNonProdDeployRolesStack`, does not mutate IAM, does not push a deployment tag, and does not close campps-platform #43.

`infiquetra_aws_infra/campps_service_registry.py` is unchanged. `platform` is already registered.

---

## Sources / Research

| source | evidence |
|--------|----------|
| Live `simulate-principal-policy` 2026-08-20 | Both required actions `implicitDeny` with empty `MatchedStatements` |
| Live `list-attached-role-policies` / `list-role-policies` | Three managed policies, zero inline |
| Live `describe-stacks` / `get-function-url-config` | Stack `UPDATE_COMPLETE` with `HealthUrl`; function `campps-e2e-canary-nonprod-health`, `AuthType=AWS_IAM` |
| Live `lambda get-policy` | Resource policy principal is the canary deploy role, not the platform role |
| `campps-e2e-canary` origin/main `infra/stacks/e2e_canary_stack.py` | Explicit `function_name=campps-e2e-canary-{env}-health` |
| `campps-platform` origin/main `tests/e2e/test_cookiecutter_deploy.py` | DescribeStacks → HealthUrl → SigV4 GET; AccessDenied skips |
| `infiquetra_aws_infra/campps_deploy_roles_stack.py:78-106` | Optional managed-policy attach loop |
| `infiquetra_aws_infra/campps_deploy_roles_stack.py:1693-1753` | Guard-return helper pattern |
| `infiquetra_aws_infra/campps_service_registry.py:36-40` | Registry name is `platform` |
| `docs/plans/2026-07-02-e2e-canary-identity-scope-readback-iam-plan.md` | Prior art for this problem shape |
