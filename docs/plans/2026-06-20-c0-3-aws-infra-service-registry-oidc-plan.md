---
title: C0.3 aws-infra — register CAMPPS services + per-service OIDC deploy roles
type: feat
status: active
date: 2026-06-20
origin: issue-derived (no in-repo upstream doc) — infiquetra-aws-infra#134 + #135, sub-issues of infiquetra/campps-platform#10; canonical service set from campps-context-library phase-1a-build-program.md
---

# C0.3 aws-infra — register CAMPPS services + per-service OIDC deploy roles

## Summary

Register the 6 missing CAMPPS backend services in `campps_service_registry` (S3, #134) so the
deploy-roles stack auto-mints their per-service GitHub OIDC deploy roles (S4, #135), and add a
dedicated `web-app` deploy profile so `campps-web-app` gets a least-privilege static-site role instead
of an overprivileged serverless-api one. Deploy the result to the nonprod account.

## Problem Frame

C0.3's campps-platform half (cookiecutter home + ADR-0005 tag-promotion) shipped via PR #22 and nonprod
is live (`v0.1.0`). The remaining capability work is in this repo: only 4 of the 10 CAMPPS backend
services are registered, so the other 6 have no OIDC deploy role and cannot deploy without static keys.
`campps-web-app` is also unregistered and has no correct deploy profile. Until these land, the C0.3
E2E (campps-platform#17) is blocked.

The deploy-roles machinery already exists and is registry-driven (`campps_deploy_roles_stack.py:49-68`
iterates `CAMPPS_SERVICE_REPOSITORIES`, minting a role + 3 managed policies + permissions boundary per
service per environment). So S4 for the 6 backends is **zero new code** — it rides on the S3 registry
edits. The only genuinely new work is the `web-app` profile.

## Requirements

R1. All 10 CAMPPS deployable backend services are in `CAMPPS_SERVICE_REPOSITORIES` (the 4 existing +
`coppa-consent`, `registration`, `payments`, `health-forms`, `activities-achievements`,
`staff-management`), each producing a correctly-scoped per-environment OIDC deploy role.

R2. `campps-web-app` is registered with a dedicated `web-app` deploy profile scoped to static-site
hosting (S3 + CloudFront + invalidation + the shared CDK-bootstrap baseline) — **not** serverless-api,
so its role carries no Lambda / DynamoDB / API Gateway / EventBridge grants.

R3. `_create_deploy_policies()` handles `web-app` explicitly and **raises** on any unrecognized
`deploy_profile` (no silent serverless-api fallback).

R4. Unit tests assert: registry membership equals the full canonical set; every registered service
mints a deploy role + permissions boundary per declared environment; trust subjects are
environment-scoped; the `web-app` policy grants only static-site actions and none of the
serverless-api actions.

R5. The roles stack is deployed to the nonprod account (`477152411873`) and, for each newly registered
service, the `campps-<name>-nonprod-gha-deploy-role` **exists with the correct env-scoped trust subject**
(`repo:infiquetra/campps-<name>:environment:nonprod`) — verified via `aws iam get-role` / CloudFormation
outputs. (The actual end-to-end OIDC *assume* is **not** provable in this slice: the 6 new service repos
are bare scaffolds with no deploy workflow to mint an OIDC token. That proof is deferred to a service's
first real deploy / the C0.3 E2E — see Deferred to Follow-Up.)

## Key Technical Decisions

**KTD1 — Source the service set from the build program, not the card text.** The cards conflict
("7 service repos" in titles, "10 services + web-app" in AC). Grounded truth
(`campps-context-library` phase-1a-build-program.md): 10 deployable backends (4 registered + 6 new, all
`serverless-api`, all 3 environments) + `campps-web-app` (frontend). Rejected: trusting the literal
"7 service repos".

**KTD2 — S4 for the 6 backends is no new code; it rides on S3.** The stack auto-mints scoped roles from
the registry (`campps_deploy_roles_stack.py:49-68`), so registering the 6 entries satisfies #135 for
them. Rejected: authoring roles per service by hand.

**KTD3 — web-app gets a new, dedicated `web-app` profile (provisional S3+CloudFront scope).** A Flutter
Web static client must not hold backend (Lambda/DynamoDB/API-GW/EventBridge) grants. **Provisional**:
`campps-web-app` is currently an empty scaffold with no CDK stack and no settled deploy target, so the
profile is scoped to the standard static-site pattern and **must be revisited** when the web-app's real
stack lands (it may be Amplify or differ). Rejected: register web-app as serverless-api (overprivileged);
fully defer web-app (operator chose to include provisionally).

**KTD4 — Add an unrecognized-profile guard.** `_create_deploy_policies()` raises `ValueError` for any
`deploy_profile` outside the known set, preventing a future typo from silently minting an overprivileged
serverless-api role. Rejected: leave the silent default fallback (the latent bug agent analysis found).

**KTD5 — Destination is nonprod only for now.** Deploy the roles stack to nonprod (`477152411873`) after
merge; staging (`050922968859`) / production (`431643435299`) role deploys are deferred to a separate,
reviewer-gated `/deploy`. Rationale: nonprod is the active environment toward the Nov-2026 bar.

**KTD6 — The roles stack is deployed with privileged creds via the bootstrap app, not OIDC.** It is
applied through the standalone `app_campps_bootstrap.py` CDK app (`CamppsNonProdDeployRolesStack`) using
an AdministratorAccess profile in the target account — the stack *mints* the per-service OIDC roles, so it
cannot bootstrap itself with them (chicken-and-egg). Rationale: matches how nonprod was deployed
2026-05-29. Rejected: gating this stack behind the OIDC roles it creates (impossible).

## Implementation Units

### U1. Register the 6 missing backend services (S3 #134)

Add 6 `ServiceRepository` entries to `CAMPPS_SERVICE_REPOSITORIES` in
`infiquetra_aws_infra/campps_service_registry.py:35-54` — `coppa-consent`, `registration`, `payments`,
`health-forms`, `activities-achievements`, `staff-management`, each `infiquetra/campps-<name>`, default
`serverless-api` profile, default all-3 environments. No stack changes needed; roles auto-mint.

**Test scenario:** registry membership now equals the canonical 10-backend set; a parametrized test
asserts every `serverless-api` service mints a `campps-<name>-<env>-gha-deploy-role` + permissions
boundary for each declared environment, with an env-scoped trust subject.
**Test file:** `tests/unit/test_campps_deploy_roles_stack.py`

### U2. Add the `web-app` deploy profile + register campps-web-app (S4 #135)

Author `_create_web_app_deploy_policy()` in `infiquetra_aws_infra/campps_deploy_roles_stack.py`. Branch on
`deploy_profile == "web-app"` in `_create_deploy_policies()` (near the existing `:257-275` profile switch).
Register `campps-web-app` (`infiquetra/campps-web-app`, `deploy_profile="web-app"`, all 3 environments).
Add a code comment marking the profile **provisional** per KTD3.

**Pinned provisional action set** (least-privilege static-site deploy; revise when the real web-app CDK
stack lands — KTD3). Mirror the existing profiles' shared baseline, then grant only static-site actions,
all resource-scoped to the service's `campps-web-app-<env>-*` naming:

- **CloudFormation + CDK bootstrap baseline** — same as the other profiles (assume the CDK
  `cdk-hnb659fds-*` bootstrap roles; CloudFormation create/update/describe on the service's own stacks).
- **S3** — `s3:CreateBucket`, `PutBucketPolicy`, `PutBucketWebsite`, `PutEncryptionConfiguration`,
  `PutObject`, `DeleteObject`, `GetObject`, `ListBucket`, `GetBucket*` on `arn:aws:s3:::campps-web-app-<env>-*`.
- **CloudFront** — `CreateDistribution*`, `UpdateDistribution`, `GetDistribution*`,
  `CreateInvalidation`, `Tag/UntagResource`, plus `CreateOriginAccessControl` / `GetOriginAccessControl`
  (OAC for private-bucket origin).
- **No** Lambda / DynamoDB / API Gateway / EventBridge / SQS / Secrets Manager grants.
- **Deferred (custom domain), out of this slice:** ACM (`RequestCertificate` / `DescribeCertificate`) and
  Route53 record management — add only if/when the web-app adopts a custom domain. KMS only if the bucket
  later uses a CMK (default SSE-S3 needs none).

**Test scenario:** the web-app role exists per environment; its policy grants the pinned S3 (`s3:PutObject`
on `campps-web-app-<env>-*`) + CloudFront (`cloudfront:CreateInvalidation`) actions and asserts the
**absence** of `lambda:*`, `dynamodb:*`, `apigateway:*`, `events:*`, `sqs:*`, `secretsmanager:*`; the role
trust subject is env-scoped; managed-policy size fits the IAM 6144-byte limit.
**Test file:** `tests/unit/test_campps_deploy_roles_stack.py`

### U3. Guard unrecognized deploy profiles (KTD4)

In `_create_deploy_policies()`, replace the silent serverless-api default fallback with an explicit
branch set + `raise ValueError(f"unknown deploy_profile: {profile}")` for anything outside
`{serverless-api, platform-foundation, codeartifact-publish, web-app}`.

**Test scenario:** constructing the stack with a `ServiceRepository(deploy_profile="bogus")` raises
`ValueError`.
**Test file:** `tests/unit/test_campps_deploy_roles_stack.py`

### U4. Deploy to nonprod + verify (destination: nonprod-deploy)

After merge, deploy the nonprod roles stack from the **separate bootstrap CDK app** with **privileged
credentials**: `cdk deploy CamppsNonProdDeployRolesStack --app "python3 app_campps_bootstrap.py"` against
the nonprod account (`477152411873`) using an AdministratorAccess profile in `campps-nonprod` (the
bootstrap stack *creates* the per-service OIDC roles, so it cannot assume them — KTD6; this mirrors the
2026-05-29 precedent where `CamppsNonProdDeployRolesStack` reached `UPDATE_COMPLETE`). Verify each new
service's `campps-<name>-nonprod-gha-deploy-role` exists with the env-scoped trust subject (per R5) via
`aws iam get-role` or the stack's CloudFormation outputs. Executed via `/deploy`/`/qa`, not `/work`. The
actual OIDC assume is deferred (R5 / Deferred to Follow-Up).

**Test expectation:** none -- ops/deploy verification (synth assertions live in U1-U3; this unit is the
real nonprod apply + a role-existence/trust check, not an assume probe).

## Scope Boundaries

**Out of scope (true non-goals):**
- Staging / production role deploys — separate reviewer-gated `/deploy` (KTD5).
- The web-app's actual Flutter scaffold / CDK stack — owned by the `campps-web-app` build lane.
- `campps-mvp` (testing), `campps-context-library` (docs) — not deployable services.

**Deferred to Follow-Up Work:**
- **Revisit the `web-app` profile** when `campps-web-app`'s real CDK stack lands — confirm S3+CloudFront
  vs Amplify and tighten least-privilege (tracked against R2/KTD3).
- **Prove the end-to-end OIDC assume** (#135 AC: "a deploy assumes the role with no static creds") — only
  demonstrable once a registered service repo has a real deploy workflow to mint an OIDC token; happens at
  that service's first deploy or via the C0.3 E2E. This slice proves role *existence* + correct trust, not
  the live assume — so #135 closes here for role provisioning, with the assume-proof tracked downstream.
- **Create `infiquetra/campps-e2e-canary`** (with an assumable OIDC role) — a prerequisite for the C0.3
  E2E (campps-platform#17), not part of this slice.

## Risk Analysis & Mitigation

**Risk — provisional web-app profile churn.** If campps-web-app ends up on Amplify or a non-S3 target,
the profile + role need rework. *Mitigation:* scope to least-privilege static-site, mark provisional in
code + journal, and gate a revisit on the web-app build lane.

**Risk — mis-scoped IAM on nonprod.** A new policy could over/under-grant. *Mitigation:* unit tests
assert per-profile scoping and the absence of backend actions on web-app; nonprod-only first, staging/prod
deferred.
