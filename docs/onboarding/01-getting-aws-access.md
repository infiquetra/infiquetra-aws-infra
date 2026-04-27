# 01 — Getting AWS Access

Step-by-step for first-time access to the Infiquetra AWS environment.

## Prerequisites

You need an admin (currently `jefcox`) to:

1. **Create your user** in AWS Identity Center
2. **Assign you to a permission set** on the appropriate accounts
3. **Send you the SSO portal URL**: `https://d-90676975b4.awsapps.com/start`

If you don't have these yet, ask the admin. The rest of this guide assumes you do.

## What permission set should you ask for?

Pick based on what you actually need to do, not "the most powerful one." See [`../ops/02-identity-and-access.md`](../ops/02-identity-and-access.md) for the full table.

| Your role | Ask for |
|---|---|
| Working on Apps business unit | `AppsDeveloper` (PowerUser) on the relevant account, or `AppsAdministrator` (Admin) if you'll be deploying infrastructure |
| Working on Media | `MediaDeveloper` or `MediaAdministrator` |
| Working on Consulting | `ConsultingDeveloper` or `ConsultingAdministrator` |
| Working on CAMPPS | `CamppssDeveloper` |
| Auditing / read-only investigation | `SecurityAuditor` or `ReadOnlyAccess` |
| Reviewing bills / costs | `BillingManager` |
| Org-wide infra ops (this repo) | `CoreAdministrator` on the mgmt account `645166163764` |

## First-time browser login

1. Open `https://d-90676975b4.awsapps.com/start` in your browser.
2. Sign in with the email/password the admin gave you (you'll be prompted to set a permanent password and register MFA on first login).
3. You'll see tiles for each AWS account you have access to. Click an account → click a permission set → opens the AWS Console signed in to that account+role.

## Setting up the AWS CLI locally

If you don't have the AWS CLI yet:

```bash
# macOS
brew install awscli

# Linux
sudo apt install awscli           # Debian/Ubuntu
sudo dnf install awscli           # Fedora/RHEL

# Verify version (need >= 2.15.0 for OIDC token refresh)
aws --version
```

### Configure the SSO session

Add this to `~/.aws/config`:

```ini
[sso-session infiquetra]
sso_start_url = https://d-90676975b4.awsapps.com/start
sso_region = us-east-1
sso_registration_scopes = sso:account:access

[profile infiquetra-root]
sso_session = infiquetra
sso_account_id = 645166163764
sso_role_name = AdministratorAccess
region = us-east-1

[profile campps-prod]
sso_session = infiquetra
sso_account_id = 431643435299
sso_role_name = AdministratorAccess
region = us-east-1

[profile campps-dev]
sso_session = infiquetra
sso_account_id = 477152411873
sso_role_name = AdministratorAccess
region = us-east-1
```

Adjust `sso_role_name` per profile to whatever permission set you were assigned.

### Log in

```bash
aws sso login --profile infiquetra-root
```

This opens your browser, you authenticate (MFA if registered), and the CLI caches an SSO token good for 8 hours.

### Verify access

```bash
aws sts get-caller-identity --profile infiquetra-root
```

Expected output:

```json
{
    "UserId": "AROAxxx:your-username",
    "Account": "645166163764",
    "Arn": "arn:aws:sts::645166163764:assumed-role/AWSReservedSSO_AdministratorAccess_xxx/your-username"
}
```

If you see this, you're in. If you see "Token has expired" or "AccessDenied", re-check your config and confirm the admin assigned you to the permission set you're trying to use.

## Session lifetime — what to expect

| Action | Lifetime |
|---|---|
| `aws sso login` keeps you authenticated for | 8 hours (interactive session) |
| Role credentials auto-refresh in the background | every ~1 hour |
| Force re-login after | 8 hours of inactivity, OR if you `rm ~/.aws/sso/cache/*.json` |

You don't need to manually re-login through a typical workday. If you walk away for a long lunch and come back to "Token has expired", just re-run `aws sso login`.

## Switching accounts mid-session

```bash
# Use any profile by name
aws sts get-caller-identity --profile campps-prod
aws sts get-caller-identity --profile campps-dev

# Or set a default for the shell
export AWS_PROFILE=campps-dev
aws sts get-caller-identity     # uses campps-dev
```

A single `aws sso login --sso-session infiquetra` covers all profiles that share the `sso-session` block.

## What you'll need beyond access

For working on this specific repo, also see [`02-local-dev-setup.md`](02-local-dev-setup.md). For other repos in the `infiquetra` org, the same SSO access works — but each repo has its own setup steps.

## Asking for more access

If your assigned permission set is too restrictive (e.g., you have `SecurityAuditor` but need to deploy something), file a request with the admin via whatever channel you have established. Don't try to escalate via console — SCPs and IAM policies will block it. The right path is: admin assigns you to a different permission set (e.g., adds you to `CoreAdministrator`).

## Removing access

When someone leaves the team:

1. Admin removes their user account from Identity Center (`aws identitystore delete-user`).
2. All permission set assignments tied to that user become orphaned and inactive immediately.
3. Their SSO portal access stops working within minutes.
4. Any cached STS credentials they have on local laptops continue to work for up to the permission set's `SessionDuration` (1-12h depending on the set), then fail to refresh.

There is no separate "deprovisioning checklist" — Identity Center user deletion is the one-stop revocation.
