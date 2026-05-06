# Operations Documentation

You are the owner/operator. This is the comprehensive snapshot of **what currently exists in AWS**, **what CDK manages**, **who logs in**, **how**, **what it costs**, and **what to focus on next**.

> Audience: The operator (you) — assumes AWS / CDK familiarity. For newcomer-friendly walkthroughs, see [`../onboarding/`](../onboarding/).
>
> Snapshot date: **2026-05-06** for the CAMPPS access target model and **2026-05-02** for the org tree refresh after CAMPPS migration. Cost data still reflects 2026-04-27. Re-pull any time the AWS state diverges materially from what's documented.

## You are here

```mermaid
flowchart LR
    you([You]) --> q{What do<br/>you need?}
    q -->|Mental model| ctx[01 — Organization]
    q -->|Who logs in?| iam[02 — Identity & Access]
    q -->|How do I log in?| login[03 — Login Flows]
    q -->|How does CI deploy?| ci[04 — CI/CD Pipeline]
    q -->|What's blocked?| sec[05 — Security Controls]
    q -->|What's it costing?| cost[06 — Cost]
    q -->|What's next?| next[07 — What's Next]
```

## Sections

| # | Section | What's in it |
|---|---|---|
| 01 | [AWS Organization](01-aws-organization.md) | The full account + OU tree, SCP coverage by account, what CDK manages vs. what's intentionally outside its scope |
| 02 | [Identity & Access](02-identity-and-access.md) | Live and target SSO permission sets, legacy and group-based assignments, GitHub OIDC roles, IAM trust chains |
| 03 | [Login Flows](03-login-flows.md) | Step-by-step flows for developer SSO login, CI/CD OIDC federation, MFA, session lifecycle |
| 04 | [CI/CD Pipeline](04-ci-cd-pipeline.md) | Composite actions + reusable workflows, the deploy chain, branch protection, what runs where |
| 05 | [Security Controls](05-security-controls.md) | Service Control Policies (active on both workload accounts since 2026-05-02), MFA enforcement, what's actually blocked |
| 06 | [Cost](06-cost.md) | Last 30/90 days actual spend, per-service pricing model, projections as workloads grow |
| 07 | [What's Next](07-whats-next.md) | The minimum forward path: stop "getting set up", start building. Cross-references [`../engineering-journal/QUEUED.md`](../engineering-journal/QUEUED.md). |

## At a glance

| | |
|---|---|
| **AWS Organization** | `r-f3un` in account `645166163764` (infiquetra) |
| **Active accounts** | `infiquetra` (mgmt), `campps-prod`, `campps-dev` |
| **OUs** | 7 total (all CDK-managed; both workload accounts placed in `Apps/CAMPPS/{Production,NonProd}`) |
| **SCPs** | 2 customer-managed (BaseSecurityPolicy, NonProductionCostControl) |
| **Identity Center users** | 1 (`jefcox`) + 1 group (`Administrators`, currently empty) |
| **SSO permission sets** | Live audit: 13; CDK target: 14 |
| **GitHub OIDC roles** | Foundation role target is repo/main scoped; CAMPPS service roles are per-repo and workload-account scoped |
| **CFN stacks deployed** | 3 (Organization, SSO, gha-bootstrap) |
| **Last 30 days spend** | $84 (mostly Amazon Registrar + AWS Directory Service) |
| **Last 90 days spend** | $173 |
| **Auto-deploy on push to main** | enabled, OIDC-authenticated |

## Key things to know

`★ Diagram in the docs are PNGs in [diagrams/](diagrams/), regenerable via:`

```bash
uv run python docs/ops/diagrams/generate.py
```

- **Both workload accounts are in the CDK-managed OU tree** (as of 2026-05-02). `campps-prod` lives in `Apps/CAMPPS/Production`; `campps-dev` lives in `Apps/CAMPPS/NonProd`. The legacy `CAMPPS` subtree has been deleted. See [01-aws-organization.md](01-aws-organization.md) and the [ARCHIVE](../engineering-journal/ARCHIVE.md) entry for the migration narrative.
- **SCPs are active on both workload accounts.** `BaseSecurityPolicy` inherited via `Apps`; `NonProductionCostControl` additionally inherited by `campps-dev` via `NonProd`. See [05-security-controls.md](05-security-controls.md).
- **You currently log in via legacy direct `AdministratorAccess` assignments**, but the CDK target now defines group-based management, CAMPPS dev, production read-only, and production break-glass access. Migration is a P2 backlog item. See [02-identity-and-access.md](02-identity-and-access.md).
- **The CI/CD pipeline is fully working** as of 2026-04-25 — see the [`../engineering-journal/ARCHIVE.md`](../engineering-journal/ARCHIVE.md) for the multi-PR stabilization story.
- **Most of your monthly spend is Amazon Registrar (domain registration) + AWS Directory Service.** Neither is created by this repo's CDK — both predate this repo. See [06-cost.md](06-cost.md).
