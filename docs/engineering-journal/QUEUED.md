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

## P1

### Migrate `campps-prod` and `campps-dev` accounts into new `Apps>CAMPPS>{Production,NonProd}` OUs

**Status:** not-started
**Why:** As of 2026-04-25 the CDK creates a new `Apps>CAMPPS>Production` and `Apps>CAMPPS>NonProd` OU pair, but the actual accounts (`431643435299 campps-prod`, `477152411873 campps-dev`) still live under the pre-existing top-level `CAMPPS` OU (`ou-f3un-s13dqexp`) in `workloads/PRODUCTION` and `workloads/SDLC` respectively. Two CAMPPS OUs coexist; one is empty CDK scaffolding, the other has the live accounts.
**Effort:** S (per-account `aws organizations move-account` calls + verification)
**Worth it when:** SSO permission-set rollout from `SSOStack` is ready to attach to the new OUs. Without that, moving accounts gives no immediate benefit. Also worth it when the live OU tree's complexity (`workloads/PRODUCTION`/`workloads/SDLC` + empty `CICD`) becomes confusing in the console.
**Related items:** Cleanup of empty `CICD` OU (`ou-f3un-ewwb2txi`) and the old top-level `CAMPPS` OU itself once empty.
**Notes:** Phase 1: move `campps-prod` from `workloads/PRODUCTION` to `Apps>CAMPPS>Production`. Phase 2: move `campps-dev` from `workloads/SDLC` to `Apps>CAMPPS>NonProd`. Phase 3: `delete-organizational-unit` for the empty `workloads/PRODUCTION`, `workloads/SDLC`, `workloads`, `CICD`, and `CAMPPS` OUs (in dependency order). All operations support dry-run via `--dry-run`-equivalent describe calls.

## P2

### Migrate user off legacy `AdministratorAccess` permission set onto CDK-managed `CoreAdministrator`

**Status:** not-started
**Why:** Currently using `AWSReservedSSO_AdministratorAccess_12c07039380b9161` — the AWS-default permission set created when SSO was first set up in 2021. This is invisible to the CDK (`sso_stack.py` defines a separate `CoreAdministrator` set with `AdministratorAccess` policy attached). Long-term goal is single source of truth in CDK.
**Effort:** S (assign self to new permission set, verify access, optionally unassign from legacy)
**Worth it when:** `CoreAdministrator`'s `PT4H` session duration is acceptable, or the related Maybe item below (bump to PT12H) ships first. Also worth it when other team members need admin access — onboarding via the CDK-managed set is cleaner than the legacy one.
**Related items:** Maybe item to bump `core_admin_permission_set` from PT4H → PT12H in `sso_stack.py`.
**Notes:** Don't unassign self from the legacy set until `CoreAdministrator` access is verified working — risk of locking out.

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
**Effort:** M (this repo doesn't currently have a `tests/` directory; would need to set up pytest + a single test file + wire into CI's code-quality reusable workflow)
**Worth it when:** The four files are non-trivially populated (currently each has 4–5 entries; cost of loss is moderate but not severe). Defer until the files contain at least 20+ entries each, or until a near-miss happens.
**Related items:** None.
**Notes:** Test logic is trivial: assert each of the four core paths exists. Most of the effort is the pytest scaffolding.

### Bump `core_admin_permission_set` `session_duration` from PT4H to PT12H in `sso_stack.py`

**Status:** not-started
**Why:** `AdministratorAccess` was bumped to PT12H out-of-band on 2026-04-25. The CDK-managed admin-equivalent set (`CoreAdministrator`, line 48–55 of `infiquetra_aws_infra/sso_stack.py`) is at PT4H. Inconsistency between the legacy and CDK-managed admin sets means migrating off the legacy set (P2 item above) is currently a downgrade.
**Effort:** S (one-line CDK edit + deploy)
**Worth it when:** Doing the P2 migration off legacy `AdministratorAccess`. Bundling these two changes into one PR makes the migration a true lateral move rather than a session-duration regression.
**Related items:** P2 — Migrate off legacy AdministratorAccess.
**Notes:** Same reasoning could apply to `media_admin_permission_set`, `apps_admin_permission_set`, `consulting_admin_permission_set` (all at PT4H). Decide whether to bump only `CoreAdministrator` or all admin-tier sets.

---
