# Work Session: E2E live-proof role

## Scope

Implemented the `campps-e2e-canary#4` U7 source slice from the canonical
`2026-07-11-e2e-live-proof-infra-plan.md` on
`feat/e2e-live-proof-role`.

## Completed

- Added `campps-e2e-canary-nonprod-gha-live-proof-role` with a one-hour session
  and exact GitHub OIDC audience and nonprod Environment subject.
- Added one managed policy containing only the canonical WorkOS API-key
  `secretsmanager:GetSecretValue` and Identity Access scope-table
  `dynamodb:GetItem` reads.
- Kept the existing e2e canary deploy role and identity-scope readback policy
  unchanged.
- Added exhaustive positive, negative, attachment-isolation,
  higher-environment, unrelated-service, exact suffix-width, and stable-synth
  assertions.
- Recorded the least-privilege decision in the engineering journal.
- Confirmed the canonical secret inventory uses the default Secrets Manager
  key and the GitHub repository/Environment/operator prerequisites remain in
  force.

## Verification

- Focused deploy-role module: 60 passed.
- Full suite: 76 passed.
- Ruff check/format, strict mypy, Bandit, and `git diff --check`: passed.
- Explicit `app_campps_bootstrap.py` synth: passed for all three environments.
- Synth inspection: exactly one nonprod role/policy/output; none in staging or
  production.
- Credentialed nonprod target-stack diff: two additive IAM resources and one
  output; no modify/delete.
- Verified Workflows: passed at subject digest
  `176bb5a5d8b41e5fbe12cf74817f298ecdaa332f486d8148ee61a0719d125757`
  with no blockers or warnings.
- Programmatic code review: no findings at source commit `e739fd4`.
- PR #143 required CI passed code quality, Bandit, Semgrep, Checkov,
  CloudFormation lint, workload synthesis, cost estimation, and validation
  summary; squash merge `cb9cdcd` is live on `main`.
- The merged-main credentialed diff remained additive only. Direct deployment
  of `CamppsNonProdDeployRolesStack` completed with `UPDATE_COMPLETE`.
- CloudFormation output matches
  `campps-e2e-canary-nonprod-gha-live-proof-role`; its one-hour trust requires
  the exact audience and `repo:infiquetra/campps-e2e-canary:environment:nonprod`
  subject.
- The role has one attached managed policy and no inline policies. IAM
  simulation allowed canonical WorkOS secret read and exact-table `GetItem`,
  while sibling secret, staging secret/table, `PutItem`, `Query`,
  `UpdateStack`, `PassRole`, and `kms:Decrypt` were `implicitDeny`.
- The existing e2e canary deploy role retained its four prior policies and did
  not receive the live-proof policy.
- The canary `nonprod` Environment now contains the read-back role ARN as
  `CAMPPS_E2E_LIVE_PROOF_ROLE_ARN`.

## Next Step

U7 is complete. Resume `campps-e2e-canary#4` U8 only after retained fixture IDs
and the synthetic WorkOS test-user email/password are available in the
protected `nonprod` Environment. Then execute the two post-expiry live runs and
record sanitized outcome-close evidence.
