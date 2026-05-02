# Engineering Journal — `infiquetra-aws-infra`

Living documentation for the AWS Organizations + SSO + CI/CD infrastructure managed by this repo. Prevents knowledge loss across sessions.

The journal is the *directory*; the four core files plus `audits/` and `narratives/` are its sections. Pattern adopted from `infiquetra/home-lab/docs/engineering-journal/`.

## Files in this folder

| File | What it holds | When to update |
|------|---------------|----------------|
| [LEARNINGS.md](LEARNINGS.md) | Empirical findings + mechanisms + fixes + validations | Every time a deploy, CDK refactor, or AWS API call produces a surprising result, a confirmed bug, or a non-obvious mechanism worth remembering |
| [DECISIONS.md](DECISIONS.md) | ADR-style records of architectural / pipeline-design / process choices | Every time we pick between options + commit to a path (additive vs migrative deploy, workflow-boundary `uv run` vs cdk.json edit, disable auto-deploy during debug) |
| [QUEUED.md](QUEUED.md) | Future-work items — prioritized, with "worth it when" triggers | Whenever an idea surfaces that we don't build now but don't want to forget |
| [ARCHIVE.md](ARCHIVE.md) | Shipped + rejected + superseded items | When a QUEUED item either lands OR is explicitly rejected; when a LEARNING/DECISION is invalidated |
| [audits/](audits/) | Dated deep-dive audits — frozen snapshots of cross-source analysis (cost reviews, org structure audits, post-incident reviews) | After a multi-source investigation produces substantial data worth mining |
| [narratives/](narratives/) | Self-contained, longer-form companion docs (design walkthroughs, post-incident write-ups, inventory snapshots) | When you need a doc that's standalone-readable cold by an outside reader (security review, future-you 6 months out) |

## How to maintain

**This folder is self-maintaining via [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md)** — which instructs Claude to update these files as work proceeds, without the user having to ask. Specifically:

- **After a deploy, CDK refactor, or AWS API failure that produced surprise:** add a dated entry to `LEARNINGS.md` if the mechanism wasn't already documented. Include the **Generalizable rule** line — that's the highest-value field.
- **After a decision (do option X instead of Y):** add an entry to `DECISIONS.md` with rationale + revisit-when condition + commit hash.
- **When an idea comes up but isn't being built now:** add to `QUEUED.md` with priority + "worth it when…" trigger.
- **When a QUEUED item ships:** move the entry to `ARCHIVE.md` with the commit hash + SHIPPED date.
- **When a QUEUED item is rejected:** move to `ARCHIVE.md` as REJECTED with reason + revisit conditions.
- **When a decision gets reversed or an assumption is invalidated:** update the original entry inline with the correction AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED. Never silently overwrite history.
- **When something needs a longer write-up than fits an entry:** create `narratives/YYYY-MM-DD-short-slug.md` and link from the relevant LEARNINGS / DECISIONS entry.

Each of the four core files has a block-quote intro at the top with its own format spec — read those when adding entries.

## Quick navigation by topic

- WorkSpaces orphaned Simple AD directory ($432/yr waste) → [LEARNINGS](LEARNINGS.md) 2026-04-27
- SCP `Principal` field rejection → [LEARNINGS](LEARNINGS.md) 2026-04-25
- `SERVICE_CONTROL_POLICY` per-root enablement → [LEARNINGS](LEARNINGS.md) 2026-04-25
- Reusable workflow caller-permissions rule → [LEARNINGS](LEARNINGS.md) 2026-04-25
- `cdk deploy` venv wrapping (`uv run`) → [LEARNINGS](LEARNINGS.md) 2026-04-25 + [DECISIONS](DECISIONS.md) 2026-04-25
- Additive (not migrative) Apps>CAMPPS deploy → [DECISIONS](DECISIONS.md) 2026-04-25
- CAMPPS account migration into new OU tree → [QUEUED](QUEUED.md) P1
- 2025-07-13 AWS Org audit (frozen snapshot) → [audits/2025-07-13-aws-org-audit.md](audits/2025-07-13-aws-org-audit.md)
