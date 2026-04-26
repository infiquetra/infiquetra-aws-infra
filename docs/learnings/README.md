# Knowledge base — `docs/learnings/`

Living documentation for the infiquetra-aws-infra repo. These four files are
maintained by Claude Code automatically as part of every session — see the
maintenance rules in [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md).

## Files

| File | Purpose |
|------|---------|
| [LEARNINGS.md](LEARNINGS.md) | Empirical findings: what we discovered, the mechanism, the fix, validation, and the generalizable principle. |
| [DECISIONS.md](DECISIONS.md) | Architecture decisions, ADR-style: what we picked, tradeoffs considered, implementation, and "revisit if" conditions. |
| [QUEUED.md](QUEUED.md) | Future-work backlog by priority (P1/P2/P3/Maybe) with concrete "worth it when" triggers. |
| [ARCHIVE.md](ARCHIVE.md) | Shipped + rejected + superseded items, with commit hashes and validation. |
| [audits/](audits/) | Frozen, dated deep-dive snapshots (org audits, post-incident reviews, etc.). |

## Entry formats

### LEARNINGS.md

```markdown
## YYYY-MM-DD

### One-liner title

**Evidence:** specific data — workflow run ID, commit SHA, AWS error code, log excerpt
**Mechanism:** how/why it happened — root cause, code path, AWS API behavior
**Impact:** what it cost — failed deploy, hours debugging, blast radius
**Fix shipped (PR #N / commit SHA):** what was deployed
**Validation:** proof it's fixed — successful run ID, test output
**Generalizable principle:** broad lesson reusable in other contexts
```

Most-recent-first ordering inside each date.

### DECISIONS.md

```markdown
## YYYY-MM-DD

### Descriptive title — what we picked

**Picked:** the option chosen + why it wins
**Tradeoffs considered:**
- Alternative A: pros/cons
- Alternative B: pros/cons
- Why rejected or deferred
**Implementation:** commits, phases, code locations
**Revisit if:** specific conditions under which this decision flips
**Commit:** PR #N / SHA
```

### QUEUED.md

Organized under priority headings (`## P1`, `## P2`, `## P3`, `## Maybe`):

```markdown
### Title

**Status:** ready / in-progress / blocked / not-started
**Why:** compelling reason + use case
**Effort:** S / M / L / XL
**Worth it when:** specific trigger — metric hits X, after Y ships, etc.
**Related items:** dependencies, adjacent work
**Notes:** phase breakdown, gotchas, blockers
```

### ARCHIVE.md

Three entry variants, distinguished by status suffix:

```markdown
### Item name — SHIPPED YYYY-MM-DD
narrative of what was built
**Commits:** SHA / PR #N
**Validation:** proof it works in production

### Item name — REJECTED YYYY-MM-DD
**Reason:** why we decided it's not worth doing
**Revisit if:** conditions that would flip the decision

### Item name — SUPERSEDED YYYY-MM-DD (by entry X)
**Old claim:** what the original entry said
**New evidence:** what contradicts it
**Current state:** link to updated entry in LEARNINGS.md
```

## Maintenance rules (summary)

Full rules live in [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md). Quick reference:

1. Surprising deploy / AWS API failure / non-obvious mechanism → **LEARNINGS.md**
2. Architectural or pipeline-design decision committed → **DECISIONS.md**
3. Promising idea not built right now → **QUEUED.md**
4. QUEUED item ships → move to **ARCHIVE.md** as SHIPPED
5. QUEUED item rejected → move to **ARCHIVE.md** as REJECTED
6. Prior LEARNING/DECISION invalidated → move pre-correction version to **ARCHIVE.md** as SUPERSEDED, update original

The system maintains itself only if Claude follows the contract — there are no hooks or scripts enforcing it.
