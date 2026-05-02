# Engineering Journal — Narratives

Self-contained, longer-form companion documents to the four core journal files (LEARNINGS / DECISIONS / QUEUED / ARCHIVE).

**When to write a narrative here:** when you need a doc that's *standalone* — readable cold by an outside reader (security review, post-mortem audience, future-you 6 months from now, a new contributor onboarding to an area). Decision narratives, inventory snapshots, design walkthroughs, post-incident write-ups, ADR-companion explanations.

A LEARNINGS or DECISIONS entry can be terse because its readers already share the surrounding context. A narrative makes that context explicit so it stands on its own.

**Naming:** `YYYY-MM-DD-short-topic-slug.md`. Date-prefixed for chronological browsing. The four core files cite narratives via relative link (`narratives/<file>.md`) when an entry needs the longer form.

**Each narrative is editable but should preserve a "Last updated YYYY-MM-DD" trail in-file rather than silently overwriting.** Inventory snapshots and post-mortems in particular have a "this was true on date X" property that matters for forensics — re-running the inventory should produce a new dated narrative, not overwrite the old one.

## Difference from `audits/`

- `audits/` are *analytical* — they take a dataset and a lens and produce findings + recommendations. Often multi-lens, often short-lived in their actionability (findings get routed back into LEARNINGS / QUEUED).
- `narratives/` are *expository* — they explain something (a design, an event, a snapshot of state) so it can be understood without surrounding context. Often referenced by LEARNINGS / DECISIONS entries that point at them for the full story.

## Files

*(Add new entries below as narratives are created.)*

| File | Topic | Pairs with |
|------|-------|-----------|
| *(empty — add as narratives are written)* | | |
