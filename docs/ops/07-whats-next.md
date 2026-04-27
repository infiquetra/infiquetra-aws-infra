# 07 — What's Next

You said you feel "lost" and are "spending too much time getting setup." This page is the antidote.

## The honest assessment

You are **not lost**. You're at the end of a foundation phase. Specifically:

| | State |
|---|---|
| AWS Organizations + OUs deployed | ✅ |
| SCPs written + deployed | ✅ |
| Identity Center + 13 permission sets | ✅ |
| GitHub OIDC federation | ✅ |
| End-to-end CI/CD pipeline (modular, reusable) | ✅ |
| Successful auto-deploy on push to main | ✅ |
| Knowledge-base mechanism (`docs/learnings/`) | ✅ |
| Comprehensive documentation (this) | ✅ (you're reading it) |

**The infra plumbing is done.** Continuing to polish it has diminishing returns.

## What's actually left in "setup"

These are real but small. None should block you from building application code:

| Item | Effort | Why it could wait |
|---|---|---|
| Migrate `campps-prod`/`campps-dev` accounts into new OU tree | S | The legacy structure works. SCP coverage is the only benefit. |
| Tighten OIDC trust from `repo:infiquetra/*` to `repo:infiquetra/infiquetra-aws-infra:*` | XS | Real concern only when you add other repos to the org |
| Verify root MFA + CloudTrail org trail across all 3 accounts | S | Console-only checks; once-per-quarter cadence is fine |
| Investigate $36/mo Directory Service line item | XS | Money, not infrastructure — fix when convenient |
| Migrate self off legacy `AdministratorAccess` permission set | S | Cosmetic / consistency; doesn't unblock anything |
| Bump `CoreAdministrator` from PT4H → PT12H in CDK | XS | Bundle with the migration above |

**Total time to address all six**: probably 2-4 hours of focused work, spread over a couple sessions. Not weeks.

## What you should actually do next

### Option 1 — Build a thing

Pick one of your business ideas (Media, Apps, or Consulting) and deploy the simplest possible thing in `campps-dev`:

- A Lambda function that returns "hello world" via API Gateway
- A static site hosted on S3 + CloudFront
- A scheduled EventBridge rule that does anything

This forces you to:
- Use the SSO permission sets you set up
- Exercise the CDK pattern in a different stack
- Generate real cost data
- Discover what else you need (a new account? a new OU? a new permission set? a service-specific role?)

The discoveries from doing this **will tell you what setup is actually needed** — vs. what setup feels productive but isn't.

### Option 2 — Decommission the cost surprise

Open AWS Console → Directory Service. Find what's running. If unused, delete it. Saves ~$430/yr. Probably 30 minutes of work. Tangible win.

### Option 3 — Pick one P1/P2 item from QUEUED and ship it

[`../learnings/QUEUED.md`](../learnings/QUEUED.md) has prioritized backlog. The P1 (CAMPPS migration) is the most consequential. Ship it in a single PR, archive the entry. Rinse, repeat.

## What you should NOT do next

- **Don't refactor the CI/CD pipeline again.** It's working. Resist.
- **Don't add a fifth OU type.** Four (Core, Media, Apps, Consulting) is enough until you have multiple accounts in any of them.
- **Don't enable AWS Config / Security Hub yet.** Both have meaningful costs ($30-50/mo each per account) and minimal benefit until you have workloads to monitor.
- **Don't write more SCPs.** The two you have are sufficient until they actually attach to a workload-bearing OU.
- **Don't switch from CDK to Terraform / Pulumi / SAM.** You're past the cost of the choice.

## Mapping to backlog items

Backlog of all known work items, with priorities and "worth it when" triggers:

→ [`../learnings/QUEUED.md`](../learnings/QUEUED.md)

History of what's been shipped:

→ [`../learnings/ARCHIVE.md`](../learnings/ARCHIVE.md)

Why we made specific architectural choices:

→ [`../learnings/DECISIONS.md`](../learnings/DECISIONS.md)

Empirical findings from past debugging:

→ [`../learnings/LEARNINGS.md`](../learnings/LEARNINGS.md)

## A suggested cadence going forward

| Frequency | Activity |
|---|---|
| Per PR | Update `LEARNINGS.md` if anything non-obvious surfaced; update `DECISIONS.md` if a meaningful trade-off was made |
| Per shipped backlog item | Move from `QUEUED.md` → `ARCHIVE.md` |
| Monthly | Skim `06-cost.md`'s "where to look for surprises" commands for unexpected spend |
| Quarterly | Re-pull live AWS state (the commands at the bottom of each ops doc) and reconcile with what's documented; refresh diagrams via `uv run python docs/ops/diagrams/generate.py` |
| When adding a new repo to `infiquetra/*` | Decide: (a) tighten the OIDC trust to be repo-specific, or (b) add a per-repo IAM role |

## The one-line summary

> Foundation is done. Pick a real project, build the smallest version of it in `campps-dev`, and let the gaps surface naturally.
