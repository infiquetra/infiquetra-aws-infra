# 01 — AWS Organization

The complete picture of what's in AWS Organizations: accounts, OUs, SCP coverage, and what CDK is responsible for vs. what is intentionally outside CDK's scope.

## Top-level facts

| Field | Value |
|---|---|
| Organization root ID | `r-f3un` |
| Organization owner / mgmt account | `645166163764` (infiquetra) |
| Owner email | `jeff@infiquetra.com` |
| Active accounts | 3 |
| OUs | 7 (all CDK-managed) |
| Customer-managed SCPs | 2 (BaseSecurityPolicy, NonProductionCostControl) |
| Region for global services | `us-east-1` |
| Enabled policy types at root | `SERVICE_CONTROL_POLICY` (enabled 2026-04-25, see [LEARNINGS](../engineering-journal/LEARNINGS.md)) |

## Visual: full OU tree

![Organization Structure](diagrams/02-org-structure.png)

## Tree (text version)

```
Root [r-f3un]
├── infiquetra            [645166163764]   mgmt account, jeff@infiquetra.com
│
├── Core                  [ou-f3un-772uqvdc]   empty
├── Media                 [ou-f3un-8hynekjx]   empty
├── Consulting            [ou-f3un-esi8ublq]   empty
└── Apps                  [ou-f3un-srsbk9oh]
    └── CAMPPS            [ou-f3un-pb5ixa96]
        ├── Production    [ou-f3un-cec60ji6]
        │   └── campps-prod  [431643435299]
        └── NonProd       [ou-f3un-yb8hu7vq]
            └── campps-dev   [477152411873]
```

All OUs are CDK-managed. The legacy top-level `CAMPPS` subtree and its
`workloads/*` + `CICD/*` children were deleted on 2026-05-02 — see the
[engineering journal entry](../engineering-journal/ARCHIVE.md) for the migration
narrative.

## Accounts

| Account ID | Name | Email | Status | Lives in |
|---|---|---|---|---|
| `645166163764` | infiquetra | jeff@infiquetra.com | ACTIVE | Root (mgmt accounts don't go in OUs) |
| `431643435299` | campps-prod | _unset shown_ | ACTIVE | `Apps / CAMPPS / Production` |
| `477152411873` | campps-dev | _unset shown_ | ACTIVE | `Apps / CAMPPS / NonProd` |

**Note**: `campps-cicd` (`424272146308`) was the originally-suspended account flagged in `.claude/audit-current-state.md` (2025-07-13). It was closed or removed before the 2026-05-02 migration; the empty `CICD/PRODUCTION` OU that was its last trace was deleted as part of that migration.

## What CDK manages — `OrganizationStack`

CDK code at `infiquetra_aws_infra/organization_stack.py` produces these resources via the `InfiquetraOrganizationStack` CFN stack:

| Resource | CDK ID | Live AWS ID |
|---|---|---|
| OU | `CoreOU` | `ou-f3un-772uqvdc` |
| OU | `MediaOU` | `ou-f3un-8hynekjx` |
| OU | `ConsultingOU` | `ou-f3un-esi8ublq` |
| OU | `AppsOU` | `ou-f3un-srsbk9oh` |
| OU | `AppsCamppsOU` | `ou-f3un-pb5ixa96` |
| OU | `CamppsProductionOU` | `ou-f3un-cec60ji6` |
| OU | `CamppsNonProdOU` | `ou-f3un-yb8hu7vq` |
| SCP | `BaseSecuritySCP` | `p-oop3272h` (BaseSecurityPolicy) |
| SCP | `NonProdCostControlSCP` | `p-caqfo4ef` (NonProductionCostControl) |

**10 resources total** in `InfiquetraOrganizationStack` (including a CDK metadata resource).

**Stack state** (as of snapshot): `CREATE_COMPLETE`, last updated `2026-04-25T14:54:48Z`.

## What CDK does NOT manage

These exist in AWS but live outside the CDK stack — changes to them won't show up in `cdk diff`:

| Resource | Why CDK doesn't manage it |
|---|---|
| `campps-prod` and `campps-dev` accounts | Account creation requires `organizations:CreateAccount` and is typically not in IaC — even if it were, importing existing accounts into CDK is risky. Account-to-OU placement is a separate imperative `move-account` operation. |
| `infiquetra` mgmt account | Mgmt accounts in AWS Organizations cannot be moved into OUs and are not modeled in CDK |
| Organization itself (`r-f3un`) | Created when AWS Organizations was first turned on for this account |
| `SERVICE_CONTROL_POLICY` enablement at the root | Imperative one-time AWS-side step; no CFN equivalent. See [LEARNINGS](../engineering-journal/LEARNINGS.md). |

## SCP coverage by account

Effective SCPs for each workload account, after the 2026-05-02 migration:

| Account | Direct SCPs | Inherited via | Effective deny set |
|---|---|---|---|
| `campps-prod` (431643435299) | `FullAWSAccess` | `Apps` → `BaseSecurityPolicy` | root user, delete logging, IAM/Org without MFA |
| `campps-dev` (477152411873) | `FullAWSAccess` | `Apps` → `BaseSecurityPolicy`, `NonProd` → `NonProductionCostControl` | above + EC2 launches outside `t3/t4g` `{nano,micro,small,medium}` |

**Note**: `aws organizations list-policies-for-target --target-id <account-id>` only shows direct attachments (which is just `FullAWSAccess` for both accounts). To see inherited policies, walk the parent chain with `list-parents` + `list-policies-for-target` at each level. See [LEARNINGS](../engineering-journal/LEARNINGS.md) 2026-05-02 for the gotcha.

## Historical: the dual-CAMPPS situation (now resolved)

From 2026-04-25 to 2026-05-02 the org had two OUs named "CAMPPS" — a CDK-managed empty one under `Apps`, and a legacy pre-CDK one at the root holding the live accounts. The legacy tree was deleted on 2026-05-02 once the accounts were moved into the CDK-managed tree. See [ARCHIVE](../engineering-journal/ARCHIVE.md) 2026-05-02 for the full migration narrative and [DECISIONS](../engineering-journal/DECISIONS.md) for the original additive-deploy rationale.

## Deploying changes

The OU tree is created/updated by:

```bash
# Manual deploy (debugging)
uv run cdk deploy InfiquetraOrganizationStack --profile infiquetra-root

# Via CI on push to main
git push origin main
# → triggers .github/workflows/deploy-infrastructure.yml
# → which calls reusable-aws-deployment.yml
# → which runs `uv run cdk deploy` for both stacks in order
```

`SSOStack` depends on `OrganizationStack`. Always deploy organization first.

## Recovery / drift detection

If state drifts (e.g., a manually created OU appears, an SCP attachment is removed in console):

```bash
# Check live state vs. CDK
uv run cdk diff InfiquetraOrganizationStack --profile infiquetra-root

# Re-pull live OU tree
aws organizations list-organizational-units-for-parent \
  --parent-id r-f3un --profile infiquetra-root

# List SCP attachments per policy
aws organizations list-targets-for-policy \
  --policy-id p-oop3272h --profile infiquetra-root
```
