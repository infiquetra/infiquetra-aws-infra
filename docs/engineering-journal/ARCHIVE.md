# ARCHIVE

> **The graveyard of QUEUED, LEARNINGS, and DECISIONS items.** When something from `QUEUED.md` ships, it moves here as **SHIPPED**. When something is consciously rejected, it moves here as **REJECTED** with the reason + revisit conditions. When a `LEARNINGS.md` or `DECISIONS.md` entry is invalidated by new evidence, the pre-correction version moves here as **SUPERSEDED**.
>
> **Never silently delete.** History is the point — future Claude (or human) reading "did we ever consider X?" or "why did we change our mind on Y?" gets the answer.
>
> **Append new entries to the top.** Most-recent first. Three entry variants:
>
> ```markdown
> ### Item name — SHIPPED YYYY-MM-DD
> narrative of what was built
> **Commits:** SHA / PR #N
> **Validation:** proof it works in production
>
> ### Item name — REJECTED YYYY-MM-DD
> **Reason:** why we decided it's not worth doing
> **Revisit when:** conditions that would flip the decision
>
> ### Item name — SUPERSEDED YYYY-MM-DD (by entry X)
> **Old claim:** what the original entry said
> **New evidence:** what contradicts it
> **Current state:** link to updated entry in LEARNINGS.md
> ```
>
> Prune entries older than 12 months only if they're no longer instructive.

---

## 2026-05-02

### CAMPPS account migration into CDK-managed OU tree — SHIPPED 2026-05-02

Moved `campps-dev` (`477152411873`) from legacy `CAMPPS/workloads/SDLC` (`ou-f3un-egwd0huq`) into CDK-managed `Apps/CAMPPS/NonProd` (`ou-f3un-yb8hu7vq`), then `campps-prod` (`431643435299`) from legacy `CAMPPS/workloads/PRODUCTION` (`ou-f3un-ad24hdlv`) into CDK-managed `Apps/CAMPPS/Production` (`ou-f3un-cec60ji6`). Dev moved first as canary. After both moves, deleted 6 empty legacy OUs leaf-first: `workloads/PRODUCTION` (`ou-f3un-ad24hdlv`), `workloads/SDLC` (`ou-f3un-egwd0huq`), `workloads` (`ou-f3un-bhg44nrb`), `CICD/PRODUCTION` (`ou-f3un-cfcpbryc`), `CICD` (`ou-f3un-ewwb2txi`), and the legacy `CAMPPS` root (`ou-f3un-s13dqexp`).

The dual-CAMPPS situation is over. Root now has exactly 4 OUs (Core, Media, Consulting, Apps), all CDK-managed. `cdk diff --all` shows zero drift.

Both accounts now inherit `BaseSecurityPolicy` from the `Apps` OU; `campps-dev` additionally inherits `NonProductionCostControl` from `NonProd`. This is the SCP enforcement that was pending account migration per `docs/ops/05-security-controls.md`.

Surfaced a `list-policies-for-target` quirk during verification — recorded in [LEARNINGS.md](LEARNINGS.md).

**Commits:** No CDK code change — pure AWS API work via `aws organizations move-account` and `delete-organizational-unit`. Doc + journal updates landed in the same PR as the diagram regeneration.
**Validation:** `aws organizations list-organizational-units-for-parent --parent-id r-f3un` returns only Core/Media/Consulting/Apps. `aws organizations list-parents --child-id 431643435299` returns `ou-f3un-cec60ji6`. `aws organizations list-parents --child-id 477152411873` returns `ou-f3un-yb8hu7vq`. `uv run cdk diff --all --profile infiquetra-root` reports `Number of stacks with differences: 0`.

---

## 2026-04-27

### Decommissioned orphaned WorkSpaces Simple AD directory + its VPC — SHIPPED 2026-04-27

Surfaced during the comprehensive cost-doc work: a Simple AD directory (`d-90677865c8`, name `corp.amazonworkspaces.com`) had been running unused since 2020-05-25, billing ~$36/mo (~$432/yr, ~$2,500 lifetime). Confirmed orphan: zero WorkSpaces, zero registered WorkSpaces directories, zero EC2 instances in its VPC. Deleted the directory via `aws ds delete-directory`, waited for the ~5-min teardown, then cleaned up the auto-orphaned VPC infrastructure in dependency order (1 SG, 2 subnets, 1 IGW, 1 non-main route table, the VPC itself).

Full mechanism + lessons captured in [`LEARNINGS.md`](LEARNINGS.md).

**Commits:** No code change — out-of-band CLI cleanup. Documented in LEARNINGS + this entry.
**Validation:** `aws ds describe-directories` returns empty. `aws ec2 describe-vpcs --vpc-ids vpc-088fae61835b3a517` returns `InvalidVpcID.NotFound`. Expected next-month Cost Explorer drop: ~$36 → $0 on the Directory Service line. Steady-state monthly run rate should fall from ~$42 → ~$6.

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
