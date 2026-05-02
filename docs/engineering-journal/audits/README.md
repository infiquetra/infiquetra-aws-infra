# Audits

Post-hoc deep dives into the AWS environment, organization structure, and CI/CD pipeline. Each audit is a dated standalone document (or subdirectory if it's multi-lens) committed as historical record.

These are distinct from the living docs in the parent directory:
- `LEARNINGS.md` / `DECISIONS.md` / `QUEUED.md` / `ARCHIVE.md` are continuously updated.
- Audits in this directory are **frozen snapshots** — a specific dataset analyzed through a specific lens, committed as historical record. Findings that lead to action get routed back out into the living docs.

## When to run an audit

- Before a major architectural change (org restructure, account migration, IAM model overhaul) — capture the baseline so the diff after the change is legible.
- After a cost-anomaly investigation that touched multiple AWS services — preserve the cross-service synthesis instead of letting it die in chat history.
- When a pipeline exhibits a confusing meta-behavior that isn't explained by any single LEARNING (e.g., "deploys appear stuck but are actually idle because of CFN drift").
- When a security review or compliance check produces multi-source findings worth a structured write-up.

## Current audits

| Date | Audit | Scope |
|------|-------|-------|
| 2025-07-13 | [AWS Org audit](./2025-07-13-aws-org-audit.md) | Organization structure baseline before CDK adoption |

## How to structure a new audit

For a single-lens audit: `audits/YYYY-MM-DD-<short-name>.md`.

For a multi-lens audit (multiple analysis angles or supporting reports):

```
audits/YYYY-MM-DD-<short-name>/
├── README.md                      # unified synthesis (dedupe + rank + route)
├── analysis_<lens1>.md            # per-lens detailed findings
├── analysis_<lens2>.md
└── ...
```

Raw data dumps (CloudTrail JSON exports, Cost Explorer CSVs, full `describe-*` outputs) should NOT be committed if large — keep them in `/tmp/` on the operator workstation and reference the dump path in the audit.
