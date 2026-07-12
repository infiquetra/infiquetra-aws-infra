---
title: E2E Live-Proof Role Code Review
date: 2026-07-11
target_repository: infiquetra/infiquetra-aws-infra
target_branch: feat/e2e-live-proof-role
base_revision: 2dfb3f4
reviewed_revision: e739fd4
verified_subject_sha256: 176bb5a5d8b41e5fbe12cf74817f298ecdaa332f486d8148ee61a0719d125757
blocked: false
---

# E2E Live-Proof Role Code Review

## Review Result

The U7 infrastructure source is safe to enter the PR loop. No P0, P1, P2, or
P3 finding survived the full review and validator gate.

| field | value |
| --- | --- |
| plan | `campps-e2e-canary/docs/plans/2026-07-11-e2e-live-proof-infra-plan.md` |
| issue | `infiquetra/campps-e2e-canary#4` |
| work session | `docs/work-sessions/2026-07-11-e2e-live-proof-role.md` |
| reviewed SHA | `e739fd4` |
| verified subject | `176bb5a5d8b41e5fbe12cf74817f298ecdaa332f486d8148ee61a0719d125757` |
| blocked | false |
| findings | none |

## Scope Check

**CLEAN.** `2dfb3f4..e739fd4` changes only the deploy-role stack, its focused
assertions, and the infrastructure decision. It does not change the existing
deploy role, deploy policy, service registry, workload app, deployment
workflow, or higher-environment resources. The unrelated untracked
`docs/FULL_REPO_CODE_REVIEW.md` is outside commit and review attribution.

## Built vs Planned

| requirement | state | evidence |
| --- | --- | --- |
| R1: separate one-hour exact-subject role | DONE | Synth pins the role name, 3600-second session, OIDC audience, and exact nonprod Environment subject. |
| R2: exactly two runtime reads | DONE | One policy contains only canonical WorkOS `GetSecretValue` and exact-table `GetItem`. |
| R3: no deploy-role or higher-environment widening | DONE | Attachment-isolation, unrelated-service, staging, and production assertions pass. |
| R4: positive and negative source proof | DONE | Focused assertions cover actions, resources, suffix width, no KMS/write/query/scan, stable synth, and all environment templates. |
| R5: deployment prerequisites and diff | DONE | GitHub controls and default-key secret inventory were read back; the credentialed target-stack diff is additive only. |
| R6: post-deploy readback | UNVERIFIABLE | Correctly deferred until the merged source is explicitly deployed to nonprod. |

**SOURCE COMPLETION:** 5 DONE, 1 UNVERIFIABLE, 0 PARTIAL, 0 NOT-DONE, 0
CHANGED.

## Checks

- Focused deploy-role module: 60 tests passed.
- Full suite: 76 tests passed.
- Ruff check and format, strict mypy, Bandit, and `git diff --check` passed.
- Explicit workload bootstrap synth passed for nonprod, staging, and production.
- Template readback found one nonprod live-proof role/policy/output and none in
  staging or production.
- Credentialed `CamppsNonProdDeployRolesStack` diff contains two additive IAM
  resources and one output, with no modify or delete operation.
- Verified Workflows passed with thirteen selected roles, four required
  command-backed validators, no blockers, and no warnings.

## Residual Risk

This review proves source and the pre-deploy change set, not deployed AWS
state. Merge does not deploy `app_campps_bootstrap.py`. CloudFormation status,
role trust, attached policy, positive/negative IAM simulation, unchanged deploy
role, and final Environment role-ARN wiring remain explicit post-merge gates.

> Verdict: PROCEED TO PR GATE. No unresolved P0/P1 finding and the review is
> fresh for `e739fd4`.

Review complete
