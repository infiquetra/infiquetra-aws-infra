# QUEUED

> **Future-work items by priority with explicit "worth it when" triggers.** When a promising idea surfaces but we don't build it right now, it goes here. Don't skip the entry just because it feels minor — these are easy to lose.
>
> Organized under priority headings (`## P0` must-ship-before-X, `## P1` urgent, `## P2` important, `## P3` nice-to-have, `## Maybe`). Add a `## P0` section only when an entry needs it.
>
> Format:
>
> ```markdown
> ### Short title
>
> **Status:** ready / in-progress / blocked / not-started
> **Why:** compelling reason + use case
> **Effort:** S / M / L / XL (or hours / half-day / day / week)
> **Worth it when:** specific trigger — metric hits X, after Y ships, etc.
> **Related items:** dependencies, adjacent work (optional)
> **Notes:** phase breakdown, gotchas, blockers (optional)
> ```
>
> When the work is done → move the entry to `ARCHIVE.md` as SHIPPED with date + commit/PR.
> When the work is consciously rejected → move to `ARCHIVE.md` as REJECTED with reason + revisit conditions.
> Always preserve the entry in `ARCHIVE.md`; never silently delete from QUEUED.

---

## P2

### Wire the CAMPPS bootstrap app into a guarded CD path (or a drift-check)

**Status:** not-started
**Why:** The `app_campps_bootstrap.py` stacks (`CamppsNonProdDeployRolesStack` et al.) are **not** deployed by any workflow — `deploy-infrastructure.yml` only deploys the management `app.py` (org/SSO). So a registry/role change merges green to `main` and silently does **nothing** in the workload accounts until a human remembers to run a separate privileged `cdk deploy`. This gap has now bitten **two** threads: C0.1 (2026-06-17, role policy fix) and C0.3 (2026-06-20, 7 new roles). Each time, "merged + CI green" read as done while the roles were absent from AWS. A guarded CD path (or at minimum a CI drift-check that flags undeployed bootstrap-app changes) would close the recurring "merge ≠ deployed" trap.
**Effort:** M (design the OIDC/identity for a privileged-but-scoped bootstrap deploy — the stack mints the very OIDC roles it would need, so it can't self-bootstrap; likely a dedicated approval-gated workflow assuming an AdministratorAccess-class role per workload account, or a lighter drift-only check first).
**Worth it when:** The next time a CAMPPS workload-role change is expected (e.g. staging/production role rollout, or the next service registration) — or sooner if the manual step is forgotten and causes a silent no-op deploy.
**Related items:** `app_campps_bootstrap.py`, `infiquetra_aws_infra/campps_deploy_roles_stack.py`, `.github/workflows/deploy-infrastructure.yml`. LEARNINGS 2026-06-17 + 2026-06-20 (the recurrence); DECISIONS 2026-06-20 (C0.3, KTD6 chicken-and-egg).
**Notes:** Start with the cheaper drift-check (flag when `cdk diff` on the bootstrap app is non-empty against deployed state) before building full auto-deploy — auto-deploying privileged role stacks on every merge has its own blast-radius risk, so a flag-not-apply signal may be the right first increment.

### Bootstrap CAMPPS workload deploy roles before first service repo release

**Status:** in-progress (nonprod deployed; production pending)
**Why:** The registry-generated deploy roles are deployed in `campps-nonprod` for the active service repositories, but production deploy roles are still pending until the production profile/approval path is confirmed and `CamppsProductionDeployRolesStack` is deployed into `campps-prod`.
**Effort:** S remaining (production preflight, diff review, deploy, and output verification)
**Worth it when:** Before the first CAMPPS service repo production deployment through GitHub Actions.
**Related items:** `app_campps_bootstrap.py`, `infiquetra_aws_infra/campps_service_registry.py`, `infiquetra_aws_infra/campps_deploy_roles_stack.py`, PRs [#131](https://github.com/infiquetra/infiquetra-aws-infra/pull/131) and [#132](https://github.com/infiquetra/infiquetra-aws-infra/pull/132).
**Notes:** Nonprod shipped on 2026-05-29 from main `d69badd`: `CamppsNonProdDeployRolesStack` reached `UPDATE_COMPLETE` and outputs exist for `campps-platform`, `campps-contracts`, and `campps-identity-access`. `campps-platform` nonprod workflow run [26657306997](https://github.com/infiquetra/campps-platform/actions/runs/26657306997) verified the platform SSM contract through direct `ssm:GetParametersByPath`. Production remains paused because the runbook names `campps-prod-breakglass`, while the local AWS config currently exposes `campps-prod`; confirm the intended production profile before deploying. `tenant-setup` remains deferred until the repository exists.

### Migrate human access off legacy direct `AdministratorAccess` assignments

**Status:** in-progress
**Why:** Current live access still uses direct legacy `AdministratorAccess` assignments for `jefcox` in the management, `campps-nonprod`, and `campps-prod` accounts. The CDK target now defines optional group assignments for management admin, CAMPPS nonprod, production read-only, and production break-glass access. Long-term goal is group-based Identity Center access managed by CDK.
**Effort:** M (verify/create groups, deploy parameters, test profiles, then remove legacy direct assignments)
**Worth it when:** The SSO target change is ready for an explicit preflight and the new profiles can be tested in order: management admin, nonprod developer, prod read-only, prod break-glass.
**Related items:** Maybe item to bump `core_admin_permission_set` from PT4H → PT12H in `sso_stack.py`.
**Notes:** Do not remove legacy assignments until every replacement profile has been tested. The CDK parameters are intentionally empty by default so a deploy cannot create broken assignments with guessed group IDs.

### Bump IAM Identity Center "Session duration" knob (interactive sessions)

**Status:** not-started
**Why:** Currently 8 hours interactive / 7 days background. 8h is fine for most days but tight for marathon debug sessions. Console-only setting (no CLI parity).
**Effort:** S (single console click)
**Worth it when:** 8h debug session limit becomes recurring friction. The supporting permission-set `SessionDuration` was already bumped to PT12H on 2026-04-25 for `AdministratorAccess`; bumping the IAM IC interactive session would let role creds last the full 12h without re-login.
**Related items:** None.
**Notes:** Path: AWS Console → IAM Identity Center → Settings → Authentication → Session duration → Configure. Trade-off: longer sessions = more exposure if a laptop is stolen. For solo dev on personal machine, 12-24h is reasonable.

## P3

### Upgrade GitHub Actions to Node 24-compatible versions before 2026-06-02

**Status:** not-started
**Why:** Every workflow run currently emits a deprecation annotation: `actions/checkout@v4`, `actions/cache@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, and `aws-actions/configure-aws-credentials@v5` all run on Node 20. GitHub will force Node 24 by 2026-06-02 and remove Node 20 entirely on 2026-09-16.
**Effort:** S (per-action version bump + verify each workflow still passes)
**Worth it when:** Action publishers release Node 24-supporting versions. For now, annotations are non-blocking — they don't fail runs. Track upstream releases on each action's repo.
**Related items:** None.
**Notes:** Could opt into Node 24 early via `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` env var to test compatibility before the forced cutover. Worth doing as a single "Node 24 readiness" PR once all action versions are available.

## Maybe

### Add a `tests/` lint that guards `docs/engineering-journal/*.md` from accidental deletion

**Status:** not-started
**Why:** Mirrors home-lab's `tests/unit/test_no_legacy_artifacts.py` pattern. Prevents an inattentive cleanup commit from removing the engineering-journal files. Cost-of-loss: months of accumulated context.
**Effort:** S (pytest configuration and `tests/unit/` already exist; remaining work is one guard test plus CI wiring if the guard should block PRs)
**Worth it when:** The four files are non-trivially populated (currently each has 4–5 entries; cost of loss is moderate but not severe). Defer until the files contain at least 20+ entries each, or until a near-miss happens.
**Related items:** None.
**Notes:** Test logic is trivial: assert each of the four core paths exists. The old pytest scaffolding concern is gone; CI currently runs ruff, mypy, and CDK synthesis, but not `uv run pytest`.

### Bump `core_admin_permission_set` `session_duration` from PT4H to PT12H in `sso_stack.py`

**Status:** not-started
**Why:** `AdministratorAccess` was bumped to PT12H out-of-band on 2026-04-25. The CDK-managed admin-equivalent set (`CoreAdministrator` in `infiquetra_aws_infra/sso_stack.py`) is at PT4H. Inconsistency between the legacy and CDK-managed admin sets means migrating off the legacy set (P2 item above) is currently a downgrade.
**Effort:** S (one-line CDK edit + deploy)
**Worth it when:** Doing the P2 migration off legacy `AdministratorAccess`. Bundling these two changes into one PR makes the migration a true lateral move rather than a session-duration regression.
**Related items:** P2 — Migrate off legacy AdministratorAccess.
**Notes:** Same reasoning could apply to `media_admin_permission_set`, `apps_admin_permission_set`, `campps_prod_breakglass_permission_set`, and `consulting_admin_permission_set` (all at PT4H). Decide whether to bump only `CoreAdministrator` or all admin-tier sets.

---
