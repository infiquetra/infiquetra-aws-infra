# 05 — Security Controls

What's actually blocking what — SCPs, MFA, root protection, OIDC trust scoping. With honest gaps.

## Service Control Policies — the live state

Two customer-managed SCPs exist, both deployed by `OrganizationStack`.

| SCP | Policy ID | Attached to OUs | Effective scope |
|---|---|---|---|
| `BaseSecurityPolicy` | `p-oop3272h` | `Core`, `Media`, `Apps`, `Consulting` | The 4 CDK-managed top-level OUs (all currently empty) |
| `NonProductionCostControl` | `p-caqfo4ef` | `Apps>CAMPPS>NonProd` (`ou-f3un-yb8hu7vq`) | The CDK-managed NonProd OU (currently empty) |

`⚠ The gap:` The legacy `CAMPPS` OU and its sub-tree (`workloads/PRODUCTION`, `workloads/SDLC`, `CICD`) — which is where `campps-prod` and `campps-dev` actually live — has **no SCP attached**. The security policy effectively does nothing for the active workloads today.

This is a known consequence of the additive-deploy decision documented in [`../engineering-journal/DECISIONS.md`](../engineering-journal/DECISIONS.md). The fix is the P1 [QUEUED](../engineering-journal/QUEUED.md) item — migrate accounts into the new structure. Until then, **the SCPs documented below do not apply to your real workloads**.

## SCP details

### BaseSecurityPolicy (`p-oop3272h`)

Source: `infiquetra_aws_infra/organization_stack.py` lines 134–172.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyRootUserActions",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {"StringEquals": {"aws:PrincipalType": "Root"}}
    },
    {
      "Sid": "DenyDeleteLoggingResources",
      "Effect": "Deny",
      "Action": [
        "logs:DeleteLogGroup",
        "logs:DeleteLogStream",
        "cloudtrail:DeleteTrail",
        "cloudtrail:StopLogging"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RequireMFAForSensitiveActions",
      "Effect": "Deny",
      "Action": [
        "iam:DeleteUser",
        "iam:DeleteRole",
        "iam:DeletePolicy",
        "organizations:*"
      ],
      "Resource": "*",
      "Condition": {"BoolIfExists": {"aws:MultiFactorAuthPresent": "false"}}
    }
  ]
}
```

What each statement does **once attached to an OU containing real accounts**:

| Sid | Effect |
|---|---|
| `DenyRootUserActions` | Blocks any action by the account's root user. Forces use of IAM users / SSO roles. |
| `DenyDeleteLoggingResources` | Prevents deletion of CloudTrail trails and CloudWatch log groups — preserves audit trails even from compromised admin sessions. |
| `RequireMFAForSensitiveActions` | Blocks IAM user/role/policy deletion and **all** Organizations writes from sessions without MFA. The `BoolIfExists` form ensures it applies whether the claim is missing or false. |

> **Important about SCPs**: They never apply to the management account (`645166163764`). So even when the legacy CAMPPS gets migrated into the CDK-managed tree, the mgmt account stays SCP-free. AWS treats the mgmt account as the safety hatch.

### NonProductionCostControl (`p-caqfo4ef`)

Source: `infiquetra_aws_infra/organization_stack.py` lines 195–220.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyExpensiveInstanceTypes",
    "Effect": "Deny",
    "Action": "ec2:RunInstances",
    "Resource": "arn:aws:ec2:*:*:instance/*",
    "Condition": {
      "StringNotEquals": {
        "ec2:InstanceType": [
          "t3.nano", "t3.micro", "t3.small", "t3.medium",
          "t4g.nano", "t4g.micro", "t4g.small", "t4g.medium"
        ]
      }
    }
  }]
}
```

Restricts non-prod accounts to small burstable EC2 instance types. Useful guardrail against accidental `r5.24xlarge` launches in dev. Once a non-prod account is in the new `Apps>CAMPPS>NonProd` OU, this kicks in automatically.

## What's NOT covered by SCPs (today)

- **Anything in `campps-prod`** — no SCP at any ancestor OU
- **Anything in `campps-dev`** — same
- **Anything in `infiquetra` (mgmt)** — SCPs never apply to mgmt accounts, by design

So the practical security posture today rests on:

1. IAM Identity Center role-based access (you're a single user, single group, with `AdministratorAccess`)
2. MFA at the IdP layer (Identity Store-managed)
3. OIDC trust policy on the GHA role (limits which GitHub workflows can deploy)
4. CloudTrail logging (presumably enabled — verify in console; not deployed by this CDK)

## MFA — current state

| Layer | Enforcement |
|---|---|
| **Identity Center sign-in** | MFA registered for `jefcox` (FIDO/TOTP). Required at portal sign-in based on the IAM IC `Authentication` settings. |
| **SCP-level MFA enforcement** | The `RequireMFAForSensitiveActions` statement in `BaseSecurityPolicy` would block IAM/Organizations writes without MFA — but only on accounts in OUs where it's attached, which today is none of the workload accounts. |
| **mgmt account root user** | Not in scope of SCPs. Verify root MFA is enabled in the AWS Console: IAM → Account → MFA. |

## Root user protection

| Account | Root MFA | Root used recently? |
|---|---|---|
| `infiquetra` (645166163764) | _verify in console_ | _verify_ |
| `campps-prod` (431643435299) | _verify_ | _verify_ |
| `campps-dev` (477152411873) | _verify_ | _verify_ |

> Action item: confirm root user MFA is enabled and root is not used for daily ops on all three accounts. There's no API to query root-MFA status programmatically — this requires console verification.

## OIDC trust scoping

The GitHub Actions role's trust policy restricts assumption to:

```
sub LIKE "repo:infiquetra/*"
aud == "sts.amazonaws.com"
```

`⚠ Observation:` The `sub` filter is **organization-wide**, not repo-specific. Any repo in `infiquetra/*` can assume `infiquetra-aws-infra-gha-role`. If another repo is added (e.g., `infiquetra/some-other-app`) and its workflow misuses this role, it gets the same blast radius.

**Tightening**: change to `sub LIKE "repo:infiquetra/infiquetra-aws-infra:*"` to limit to this single repo, or even `sub == "repo:infiquetra/infiquetra-aws-infra:ref:refs/heads/main"` to limit to the main branch (prevents PR branches from deploying).

To change: edit `github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_bootstrap_stack.py`, then `cd github-oidc-bootstrap && uv run cdk deploy --profile infiquetra-root`.

## What CloudTrail and CloudWatch Logs look like

Neither is deployed by this CDK. CloudTrail in the mgmt account is presumably the AWS-default org-level trail (created when AWS Organizations was first set up). To verify:

```bash
aws cloudtrail describe-trails --profile infiquetra-root --region us-east-1 \
  --query 'trailList[].{Name:Name,IsOrgTrail:IsOrganizationTrail,IsMultiRegion:IsMultiRegionTrail,LogFileBucket:S3BucketName}'
```

Expected: at least one trail covering all accounts in the org, writing to an S3 bucket in the mgmt account.

## Backup, encryption, secrets

None of these are addressed by the current CDK. They're on the future roadmap:

- **AWS Backup**: not configured. Backup policies (a different policy type at the org root) would need to be enabled and attached.
- **Default encryption**: relies on per-service defaults. KMS keys are not centralized.
- **Secrets management**: Secrets Manager has $0.86/mo current cost (likely a single test secret) — see [06-cost.md](06-cost.md). No centralized rotation.

## Summary — what gives you confidence today

| Layer | State |
|---|---|
| OIDC for CI/CD (no static AWS keys) | ✅ Working |
| MFA at IdP for human logins | ✅ Verify enabled |
| SCPs deployed | ⚠️ Yes, but attached to empty OUs only |
| Root user lockdown | ⚠️ Verify in console |
| CloudTrail | ⚠️ Presumed default org trail; verify via API |
| OIDC trust scope | ⚠️ Org-wide, could be tighter |
| Backup / DR | ❌ Not configured |
| Centralized secrets | ❌ Not configured |
| Per-account guardrails on real workloads | ❌ Pending account migration into new OU tree |

**Top three to address first** (in priority order):

1. **Migrate workload accounts into the new OU tree** so SCPs actually apply (P1, [QUEUED](../engineering-journal/QUEUED.md))
2. **Tighten OIDC trust to the specific repo + branch** (one-line change in bootstrap stack)
3. **Verify CloudTrail org trail and root MFA on all three accounts** (manual, console-only verification)
