# ARCHIVE

Shipped + rejected + superseded items. Most recent first.

See [README.md](README.md) for entry format.

---

## 2026-04-25

### Modular CI/CD pipeline refactor — SHIPPED 2026-04-25

Rebuilt the CI/CD pipeline as composable parts: composite actions for setup steps, reusable workflows for each concern (code quality, security scan, CDK synthesis, AWS deployment), and slim main workflows that orchestrate them. Replaced the monolithic `ci.yml` (165 lines) and `cd.yml`+`deploy.yml` (227 lines combined) with `pull-request-validation.yml` (97 lines) and `deploy-infrastructure.yml` (96 lines).

Composite actions: `setup-python-uv`, `setup-node-cdk`, `setup-aws-credentials`.

Reusable workflows: `reusable-code-quality.yml`, `reusable-security-scan.yml`, `reusable-cdk-synthesis.yml`, `reusable-aws-deployment.yml`.

Initial PR landed broken in a way that wasn't catchable in PR validation (the deploy workflow only triggers on push-to-main). Stabilization required four follow-up PRs: #4 (caller permissions), #5 (uv-run cdk wrapping), #7 (SCP Principal field), #8 (re-enable auto-deploy + remove orphaned pre-#3 files).

**Commits:** PRs [#3](https://github.com/infiquetra/infiquetra-aws-infra/pull/3), [#4](https://github.com/infiquetra/infiquetra-aws-infra/pull/4), [#5](https://github.com/infiquetra/infiquetra-aws-infra/pull/5), [#7](https://github.com/infiquetra/infiquetra-aws-infra/pull/7), [#8](https://github.com/infiquetra/infiquetra-aws-infra/pull/8).
**Validation:** Workflow_dispatch run [24933555533](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24933555533) and push run [24934083656](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24934083656) both completed successfully end-to-end with both stacks `CREATE_COMPLETE`.

### AWS Organizations + SSO stacks first successful production deploy — SHIPPED 2026-04-25

Both `InfiquetraOrganizationStack` and `InfiquetraSSOStack` reached `CREATE_COMPLETE` for the first time. Created OUs at root (Core, Media, Apps, Consulting) plus nested `Apps>CAMPPS>{Production,NonProd}` scaffolding. SCPs `BaseSecurityPolicy` and `NonProductionCostControl` created and attached to target OUs. SSO permission sets created per `sso_stack.py` definitions.

Pre-existing top-level `CAMPPS` OU and the `infiquetra` management account were untouched (additive deploy by design — see DECISIONS.md).

**Commits:** Deployed from main `f93e38e` (post-PR #7 merge) via workflow_dispatch.
**Validation:** Deployment tag `deploy-20260425-145556-f93e38e` pushed by the workflow. `aws cloudformation list-stacks` confirms both stacks `CREATE_COMPLETE`. `aws organizations list-organizational-units-for-parent --parent-id r-f3un` shows the new tree alongside the legacy CAMPPS.

### Removed orphaned pre-#3 reusable workflow files — SHIPPED 2026-04-25

Deleted `.github/workflows/reusable-deploy.yml`, `reusable-security.yml`, and `reusable-test.yml` — three files that predated the PR #3 modular refactor and had zero callers in the new pipeline. Verified via grep across `.github/workflows/` before deletion. The CICD-MIGRATION.md "Next Steps" list had flagged them for removal once the new pipeline was validated; that condition was met after the successful workflow_dispatch run on 2026-04-25.

**Commits:** PR [#8](https://github.com/infiquetra/infiquetra-aws-infra/pull/8) (bundled with the auto-deploy re-enable).
**Validation:** Post-merge push run [24934083656](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24934083656) succeeded — no broken references from the deletions.

### Bumped legacy `AdministratorAccess` permission set from PT1H to PT12H — SHIPPED 2026-04-25

Out-of-band CLI change: `aws sso-admin update-permission-set --permission-set-arn arn:aws:sso:::permissionSet/ssoins-7223f05fc9da6e24/ps-4908f02414180aa1 --session-duration PT12H`. The legacy `AdministratorAccess` permission set is the AWS-default one created at SSO setup in 2021 and is NOT managed by `sso_stack.py` — so the change is permanent (no CDK drift risk).

Trigger was a 1-hour role-cred TTL during a debug session that required multiple `aws sso login` cycles. Bumping to PT12H matches the precedent set by the existing `BillingManager` permission set (also PT12H).

**Commits:** None — out-of-band CLI change. Documented here.
**Validation:** `aws sso-admin describe-permission-set --permission-set-arn ...` returns `SessionDuration: PT12H`. Effective in next `aws sso login` cycle.

---
