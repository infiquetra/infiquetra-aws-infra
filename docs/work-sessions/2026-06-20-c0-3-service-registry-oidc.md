---
title: Work session — C0.3 aws-infra service registry + per-service OIDC deploy roles
date: 2026-06-20
issue: infiquetra-aws-infra#134, infiquetra-aws-infra#135 (sub-issues of campps-platform#10)
plan: docs/plans/2026-06-20-c0-3-aws-infra-service-registry-oidc-plan.md
doc_review: docs/reviews/2026-06-20-c0-3-aws-infra-service-registry-oidc-review.md
branch: worktree-c0-3-service-registry-oidc
destination: nonprod-deploy
status: PR-ready (pending review gate)
---

# Work session — C0.3 service registry + OIDC deploy roles

## What was built (by U-ID)

- **U1 — register the 6 missing backend services (S3, #134).** Added `coppa-consent`,
  `registration`, `payments`, `health-forms`, `activities-achievements`, `staff-management` to
  `CAMPPS_SERVICE_REPOSITORIES` (`infiquetra_aws_infra/campps_service_registry.py`), each
  `infiquetra/campps-<name>`, default `serverless-api`, all 3 environments. The registry-driven
  stack (`campps_deploy_roles_stack.py:49-68`) auto-mints a per-service, per-env OIDC deploy role +
  3 managed policies + permissions boundary — **no new role code** (S4 #135 rides on S3 for the
  backends, per KTD2).

- **U2 — add the `web-app` deploy profile + register `campps-web-app` (S4, #135).** Authored
  `_create_web_app_deploy_policy()` and a `deploy_profile == "web-app"` branch in
  `_create_deploy_policies()`. Registered `campps-web-app` (`deploy_profile="web-app"`). The policy
  is **provisional** (KTD3): shared CloudFormation + CDK-bootstrap baseline, S3 object/bucket ops
  scoped to `campps-web-app-<env>-*`, CloudFront distribution + invalidation + OAC management — and
  **no** Lambda / DynamoDB / API Gateway / EventBridge / SQS / Secrets Manager grants. CloudFront
  create-class actions are on `*` (AWS has no resource-level IAM support for them); everything
  scopable is pinned to this account's distributions.

- **U3 — guard unrecognized profiles (KTD4).** Replaced the silent `serverless-api` default fallback
  in `_create_deploy_policies()` with an explicit branch per known profile + a
  `raise ValueError(f"unknown deploy_profile: {profile!r}")`. A profile typo can no longer silently
  mint an over-privileged serverless-api role.

## Key decisions honored

- KTD1 canonical set sourced from `campps-context-library` phase-1a-build-program (10 backends +
  web-app), not the conflicting "7 vs 10" card text.
- KTD3 web-app profile shipped **provisional**, marked in code + DECISIONS; revisit when the real
  web-app CDK stack lands (S3+CloudFront vs Amplify).
- web-app reuses the generic permissions boundary; it is **inert** for web-app because the web-app
  deploy policy grants no `iam:CreateRole` (no app role is ever created under that boundary). R4's
  "permissions boundary per env exists" is still satisfied.

## Files modified

- `infiquetra_aws_infra/campps_service_registry.py` (+34): 6 backends + web-app, provisional comment.
- `infiquetra_aws_infra/campps_deploy_roles_stack.py` (+122): web-app policy builder + explicit
  profile branches + guard.
- `tests/unit/test_campps_deploy_roles_stack.py` (+335, 17 new tests): canonical-set membership;
  parametrized role+boundary+env-scoped-trust per serverless backend × env; web-app static-site
  scope + no-backend-actions + size<6144 + env-scoped trust; unknown-profile raises.
- `docs/engineering-journal/DECISIONS.md`, `.gitignore` (ignore `.claude/saga/`),
  `docs/plans/...`, `docs/reviews/...` carried from `/plan` + `/doc-review`.

## Checks run (evidence)

- `ruff check .` → All checks passed. `ruff format` → clean.
- `mypy .` → Success, no issues (17 source files).
- `pytest` (full suite) → all pass; deploy-roles file 72 tests green.
- `cdk synth --app "python3 app_campps_bootstrap.py"` → synthesizes all 3 envs × 11 services
  (SYNTH_OK).

## Code-review gate (Phase 5) — PASS

- **Deep review** at `REVIEWED_SHA=cfb2a04`: a 5-lens adversarial workflow (IAM least-privilege /
  built-vs-planned / guard+registry correctness / test false-confidence / OIDC trust), 5 agents,
  ~352k tokens. Verdict **PASS — no P0/P1 (no P2)**; 6 P3 notes. Agents empirically validated
  non-vacuity (injected `lambda:CreateFunction` → the no-backend-actions test failed as expected;
  confirmed the `ValueError` guard fires at synth time).
- **Acted on 2 P3 notes** (test hardening, commit `d66a087`, production code unchanged): added `web-app`
  to `PROFILE_REPRESENTATIVE_REPOSITORIES` (now asserts web-app's `iam:PassRole`/`AssumeRole` scope +
  size across all envs) and strengthened `test_known_deploy_profiles_do_not_raise` to assert each
  profile mints a role + policy.
- **Focused delta re-review** at `REVIEWED_SHA=d66a087`: PASS, no P0/P1/P2; production byte-identical to
  `cfb2a04`; 43 tests green. Remaining P3 notes are documented-provisional (web-app static-site scope,
  CloudFront `*` create-class, inert generic boundary) — tracked as KTD3 revisit follow-ups, not defects.

## Next step

PR-ready. Offer to open the PR (`infiquetra-aws-infra#134` + `#135`) under operator confirmation. U4
(nonprod apply + role-existence/trust verification) is **out of `/work` scope** — it routes to
`/deploy` + `/qa` after merge (destination `nonprod-deploy`).
