# 07 — What's Next

You said you feel "lost" and are "spending too much time getting setup." This page is the antidote.

## The honest assessment

You are **not lost**. You're at the end of the organization foundation phase and the beginning of the CAMPPS service-deployment phase. Specifically:

| | State |
|---|---|
| AWS Organizations + OUs deployed | ✅ |
| SCPs written + inherited by workload accounts | ✅ |
| Identity Center live baseline | ✅ 13 live permission sets + legacy direct admin assignments |
| Identity Center CAMPPS target | 🟡 14 permission sets + optional group assignments defined in CDK; needs preflight and deploy |
| Foundation GitHub OIDC federation | ✅ CDK target scoped to this repo's `main` branch |
| CAMPPS service GitHub OIDC roles | 🟡 Per-repo workload-account roles defined in CDK; needs preflight and deploy |
| End-to-end foundation CI/CD pipeline | ✅ |
| Successful foundation auto-deploy on push to main | ✅ |
| Engineering journal mechanism (`docs/engineering-journal/`) | ✅ |
| Comprehensive documentation (this) | ✅ (you're reading it) |

**The organization plumbing is done.** The remaining setup is specifically about safely turning on service-repo deployment paths, not endlessly polishing the foundation repo.

## What's actually left in "setup"

These are real, but they are bounded. Only the first two block the first GitHub Actions deployment from a CAMPPS service repo:

| Item | Effort | Why it matters |
|---|---|---|
| Preflight and deploy the CAMPPS workload deploy-role stacks | M | Service repositories cannot deploy through GitHub Actions until `CamppsNonProdDeployRolesStack` and `CamppsProductionDeployRolesStack` exist in the workload accounts |
| Preflight and deploy the SSO group assignments | M | Lets local development use `CAMPPSDeveloper`, production inspection use read-only, and production write access stay break-glass instead of legacy daily admin |
| Verify root MFA + CloudTrail org trail across all 3 accounts | S | Console/API checks that increase confidence before real workloads carry pilot data |
| Upgrade GitHub Actions to Node 24 before 2026-06-02 | S | Current annotations are non-blocking, but the forced cutover has a real deadline |
| Decide backup, secret, and retention conventions for the first service | M | Best done with the first real workload shape in hand, not as abstract foundation work |

**Total time to address the access/deploy setup**: probably a focused day, because the code target exists but still needs careful preflight and staged deployment. Not weeks.

(The CAMPPS account migration and the WorkSpaces Directory Service decommission both shipped — see [`../engineering-journal/ARCHIVE.md`](../engineering-journal/ARCHIVE.md).)

## What you should actually do next

### Option 1 — Build a thing

Start with the first CAMPPS service slice and deploy the simplest useful version to `campps-dev`:

- A Lambda function behind API Gateway
- A small service-owned database or parameter set
- A GitHub Actions nonprod deploy that assumes `campps-tenant-setup-nonprod-gha-deploy-role`

This forces you to:
- Use the `CAMPPSDeveloper` target profile for local nonprod debugging
- Exercise a service-owned CDK app outside this foundation repo
- Prove the per-repo OIDC role and permissions boundary model
- Generate real cost data
- Discover what else you need for one actual service instead of guessing across all future repos

The discoveries from doing this **will tell you what setup is actually needed** — vs. what setup feels productive but isn't.

### Option 2 — Pick one P2 item from QUEUED and ship it

[`../engineering-journal/QUEUED.md`](../engineering-journal/QUEUED.md) has the prioritized backlog. The previous P1 (CAMPPS account migration) shipped on 2026-05-02; the next-most-consequential P2 items are workload deploy-role bootstrap and migration off legacy direct `AdministratorAccess` assignments. Ship one in a single PR, archive the entry. Rinse, repeat.

## What you should NOT do next

- **Don't refactor the CI/CD pipeline again.** It's working. Resist.
- **Don't add a fifth OU type.** Four (Core, Media, Apps, Consulting) is enough until you have multiple accounts in any of them.
- **Don't enable AWS Config / Security Hub yet.** Both have meaningful costs ($30-50/mo each per account) and minimal benefit until you have workloads to monitor.
- **Don't write more SCPs.** The two you have are sufficient for the current workload-account tree.
- **Don't broaden OIDC trust to avoid registry updates.** Adding a repo to the registry is deliberate friction for write access.
- **Don't switch from CDK to Terraform / Pulumi / SAM.** You're past the cost of the choice.

## Mapping to backlog items

Backlog of all known work items, with priorities and "worth it when" triggers:

→ [`../engineering-journal/QUEUED.md`](../engineering-journal/QUEUED.md)

History of what's been shipped:

→ [`../engineering-journal/ARCHIVE.md`](../engineering-journal/ARCHIVE.md)

Why we made specific architectural choices:

→ [`../engineering-journal/DECISIONS.md`](../engineering-journal/DECISIONS.md)

Empirical findings from past debugging:

→ [`../engineering-journal/LEARNINGS.md`](../engineering-journal/LEARNINGS.md)

## A suggested cadence going forward

| Frequency | Activity |
|---|---|
| Per PR | Update `LEARNINGS.md` if anything non-obvious surfaced; update `DECISIONS.md` if a meaningful trade-off was made |
| Per shipped backlog item | Move from `QUEUED.md` → `ARCHIVE.md` |
| Monthly | Skim `06-cost.md`'s "where to look for surprises" commands for unexpected spend |
| Quarterly | Re-pull live AWS state (the commands at the bottom of each ops doc) and reconcile with what's documented; refresh diagrams via `uv run python docs/ops/diagrams/generate.py` |
| When adding a CAMPPS service repo | Add it to `infiquetra_aws_infra/campps_service_registry.py`, synthesize the workload bootstrap stacks, and confirm matching GitHub environments exist |

## The one-line summary

> Organization foundation is done. Preflight the CAMPPS access/deploy target, then build the smallest real service slice in `campps-dev` and let the next gaps surface naturally.
