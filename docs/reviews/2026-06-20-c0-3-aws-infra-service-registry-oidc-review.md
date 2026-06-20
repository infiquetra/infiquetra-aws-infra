---
title: Doc-review — C0.3 aws-infra service-registry + OIDC roles plan
type: doc-review
date: 2026-06-20
status: not-blocked
target: docs/plans/2026-06-20-c0-3-aws-infra-service-registry-oidc-plan.md
reviewed_revision: working tree (uncommitted)
linked_issues: infiquetra-aws-infra#134, infiquetra-aws-infra#135, infiquetra/campps-platform#10
---

# Doc-review — C0.3 aws-infra service-registry + OIDC roles plan

## Verdict

**Ready to drive implementation. Not blocked** — no P0/P1 remain after safe fixes. An inline `/work`
agent can execute U1–U3 confidently; U4 (nonprod deploy) is now grounded in the real bootstrap-app +
privileged-cred path.

## Applied fixes (safe, evidence-backed, in place)

| # | Fix | Evidence |
|---|---|---|
| F1 | **R5 + U4 rewritten** to specify the real deploy path: privileged `cdk deploy CamppsNonProdDeployRolesStack` via `app_campps_bootstrap.py` with AdministratorAccess (the bootstrap stack mints the OIDC roles, so it can't use them). | `app_campps_bootstrap.py:18-40`; QUEUED.md:35 (2026-05-29 nonprod precedent) |
| F2 | **R5 verification corrected** from "a role-assume is verified" to "role exists with correct env-scoped trust"; the live OIDC assume moved to Deferred (the 6 service repos are bare scaffolds with no deploy workflow to mint a token). | repos are scaffolds (gh: only README/LICENSE/.gitignore) |
| F3 | **Added KTD6** (privileged bootstrap-app deploy / chicken-and-egg) and a Deferred-to-Follow-Up entry clarifying #135 closes for role *provisioning*, with the assume-proof tracked downstream. | same as F1/F2 |

## Findings — all resolved (operator-requested fix pass, 2026-06-20)

| Priority | Status | Finding / resolution |
|---|---|---|
| P2 | **resolved** | **web-app profile action set was not pinned.** Fixed: U2 now pins a concrete provisional least-privilege set — S3 (`campps-web-app-<env>-*`-scoped object/bucket ops), CloudFront (distribution + `CreateInvalidation` + OAC), CDK-bootstrap baseline; **no** Lambda/DynamoDB/API-GW/EventBridge/SQS/Secrets; ACM/Route53 (custom domain) + KMS explicitly deferred. Still marked provisional (revise when the real web-app CDK stack lands). |
| P3 | **resolved** | **`origin:` not repo-relative.** Fixed: re-labeled `issue-derived (no in-repo upstream doc)` — accurate, since the plan derives from the GitHub issues, not an in-repo brainstorm. |
| P3 | **resolved (no-op)** | **`tenant-setup` history note.** Confirmed correctly registered; no plan change needed — recorded so `/work` doesn't re-litigate. |

## Residual risk from limited evidence

The `web-app` deploy profile is designed against an *assumed* S3+CloudFront target because
`campps-web-app` is an empty scaffold. If that assumption is wrong (e.g. Amplify), U2's policy and the
web-app role need revision — already captured as a Deferred follow-up and a provisional code comment.
No way to reduce this further without first settling the web-app deploy architecture.
