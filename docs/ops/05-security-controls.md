# 05 — Security Controls

What's actually blocking what — SCPs, MFA, root protection, OIDC trust scoping. With honest gaps.

## Service Control Policies — the live state

Two customer-managed SCPs exist, both deployed by `OrganizationStack`.

| SCP | Policy ID | Attached to OUs | Inherited by accounts |
|---|---|---|---|
| `BaseSecurityPolicy` | `p-oop3272h` | `Core`, `Media`, `Apps`, `Consulting` | `campps-prod`, `campps-staging` after account creation, `campps-dev` (via `Apps`) |
| `NonProductionCostControl` | `p-caqfo4ef` | `Apps>CAMPPS>Staging` and `Apps>CAMPPS>NonProd` | `campps-staging` after account creation (via `Staging`), `campps-dev` (via `NonProd`) |

As of the 2026-05-02 CAMPPS account migration (see [ARCHIVE](../engineering-journal/ARCHIVE.md)), the legacy workload accounts are in the CDK-managed OU tree and inherit the appropriate SCPs. The new `campps-staging` account will inherit `BaseSecurityPolicy` through `Apps` and `NonProductionCostControl` through `Apps / CAMPPS / Staging` once account creation completes.

> **Verifying inheritance**: `aws organizations list-policies-for-target --target-id <account-id>` only shows direct attachments (normally `FullAWSAccess` for workload accounts). To see inherited SCPs, walk the parent chain. See [LEARNINGS](../engineering-journal/LEARNINGS.md) 2026-05-02.

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

> **Important about SCPs**: They never apply to the management account (`645166163764`). The 2026-05-02 CAMPPS migration moved the workload accounts under SCP coverage, but the mgmt account stays SCP-free regardless. AWS treats the mgmt account as the safety hatch.

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

Restricts non-prod and staging accounts to small burstable EC2 instance types. Useful guardrail against accidental `r5.24xlarge` launches outside production. Active for `campps-dev` since the 2026-05-02 migration and targeted for `campps-staging` after account creation.

## What's NOT covered by SCPs (today)

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
| **SCP-level MFA enforcement** | The `RequireMFAForSensitiveActions` statement in `BaseSecurityPolicy` blocks IAM/Organizations writes without MFA. Active on `campps-prod` and `campps-dev` since the 2026-05-02 migration; pending verification for `campps-staging` after account creation. Uses `BoolIfExists`, so service principals are unaffected. |
| **mgmt account root user** | Not in scope of SCPs. Verify root MFA is enabled in the AWS Console: IAM → Account → MFA. |

## Root user protection

| Account | Root MFA | Root used recently? |
|---|---|---|
| `infiquetra` (645166163764) | _verify in console_ | _verify_ |
| `campps-prod` (431643435299) | _verify_ | _verify_ |
| `campps-staging` (pending deployment) | _pending account creation_ | _pending verification_ |
| `campps-dev` (477152411873) | _verify_ | _verify_ |

> Action item: confirm root user MFA is enabled and root is not used for daily ops on all four accounts after `campps-staging` is created. There's no API to query root-MFA status programmatically — this requires console verification.

## OIDC trust scoping

The management GitHub Actions role's CDK target restricts assumption to:

```text
sub == "repo:infiquetra/infiquetra-aws-infra:ref:refs/heads/main"
aud == "sts.amazonaws.com"
```

That role is for this foundation repository only. It can deploy management-account infrastructure such as Organizations, Identity Center, IAM, and the foundation bootstrap stack, so CAMPPS service repositories must not reuse it.

CAMPPS service repositories use separate workload-account roles with GitHub environment scoped subjects:

```text
repo:infiquetra/<service-repo>:environment:<nonprod|staging|production>
```

To change the management trust policy: edit `github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py`, then `cd github-oidc-bootstrap && uv run cdk deploy --profile infiquetra-root`. To add a CAMPPS service repository, add it to `infiquetra_aws_infra/campps_service_registry.py` and deploy the workload bootstrap stacks after preflight approval.

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
| SCPs deployed and inherited by workload accounts | ✅ Legacy dev/prod covered; staging pending account creation verification |
| Root user lockdown | ⚠️ Verify in console |
| CloudTrail | ⚠️ Presumed default org trail; verify via API |
| OIDC trust scope | ⚠️ Org-wide, could be tighter |
| Backup / DR | ❌ Not configured |
| Centralized secrets | ❌ Not configured |

**Top items to address next** (in priority order):

1. **Tighten OIDC trust to the specific repo + branch** (one-line change in bootstrap stack)
2. **Verify CloudTrail org trail and root MFA on all four accounts after staging exists** (manual, console-only verification)
3. **Enable AWS Backup org policies** at the root for centralized backup posture
