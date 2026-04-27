# 04 — Troubleshooting

Common problems and their fixes. If something here matches your symptom, the fix is usually fast. If nothing matches, check [`../learnings/LEARNINGS.md`](../learnings/LEARNINGS.md) — past gnarly issues are recorded there with full mechanism + fix.

## AWS CLI / SSO

### `Token has expired and refresh failed`

**Cause**: Your IAM Identity Center interactive session (8h) expired.

**Fix**:
```bash
aws sso login --profile infiquetra-root
```

### Browser opens then closes immediately when running `aws sso login`

**Cause**: Stale SSO cache files.

**Fix**:
```bash
rm -rf ~/.aws/sso/cache
aws sso login --profile infiquetra-root
```

### `An error occurred (AccessDenied) when calling the Foo operation`

**Cause**: You're authenticated to the wrong account, or your permission set doesn't allow that action.

**Fix**:
```bash
# 1. Confirm which account/role you're using
aws sts get-caller-identity --profile infiquetra-root

# 2. If wrong account, switch profiles
aws sts get-caller-identity --profile campps-prod

# 3. If your permission set is too restrictive, ask the admin to assign you
#    to a more permissive set (e.g., from ReadOnlyAccess to PowerUser)
```

Some operations only work on the **management account** (`645166163764`):

- `aws organizations *`
- `aws sso-admin *` (Identity Center)
- `aws identitystore *`
- Cost Explorer, AWS Config aggregator, etc.

Trying to run these against `campps-prod` or `campps-dev` will fail.

## CDK / Synth

### `ModuleNotFoundError: No module named 'aws_cdk'`

**Cause**: CDK is being invoked outside the uv venv. The `cdk.json` `app` field (`python3 app.py`) uses system Python, not the venv.

**Fix**: Always wrap CDK with `uv run`:
```bash
uv run cdk synth --all
uv run cdk deploy InfiquetraOrganizationStack
```

If you see this in CI, the workflow file is missing the `uv run` prefix — see [LEARNINGS](../learnings/LEARNINGS.md) for the full story.

### `cdk synth` fails with `No credentials in environment`

**Cause**: `cdk synth` needs AWS credentials to look up account context (even though it's read-only).

**Fix**:
```bash
aws sso login --profile infiquetra-root
uv run cdk synth --all --profile infiquetra-root
```

### `cdk diff` shows changes you didn't make

**Cause**: Drift — someone (or something) modified resources directly in AWS (console, CLI) without going through CDK. Common sources:

- Manual permission set edits in the console
- Manual SCP attachment via console
- The legacy CAMPPS OU and its children (intentional drift, see [01-aws-organization.md](../ops/01-aws-organization.md))

**Fix**: Decide whether to:

1. **Reconcile via CDK** — update the CDK code to match the live state (or vice versa). Then deploy.
2. **Accept the drift** — the legacy CAMPPS tree is intentional. Make sure new CDK changes don't try to clobber it.
3. **Investigate the change** — `aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=...`

## CloudFormation

### Stack stuck in `ROLLBACK_COMPLETE`

**Cause**: A stack creation failed. CFN cannot transition `ROLLBACK_COMPLETE` → anything via update — only via delete.

**Fix**:
```bash
# 1. Check what failed
aws cloudformation describe-stack-events \
  --stack-name InfiquetraOrganizationStack \
  --profile infiquetra-root --region us-east-1 \
  --query 'StackEvents[?ResourceStatus!=`CREATE_COMPLETE`].{T:Timestamp,R:LogicalResourceId,S:ResourceStatus,Reason:ResourceStatusReason}' \
  --output table

# 2. Fix the underlying issue (in CDK code)

# 3. Delete the stuck stack
aws cloudformation delete-stack \
  --stack-name InfiquetraOrganizationStack \
  --profile infiquetra-root --region us-east-1
aws cloudformation wait stack-delete-complete \
  --stack-name InfiquetraOrganizationStack \
  --profile infiquetra-root --region us-east-1

# 4. Retry deploy via workflow_dispatch
gh workflow run "Deploy Infrastructure" \
  --repo infiquetra/infiquetra-aws-infra \
  -f environment=production -f stack=all
```

### Stack update fails with `UPDATE_ROLLBACK_FAILED`

Less common. Means CFN failed to roll back during an update. Recovery:

```bash
aws cloudformation continue-update-rollback \
  --stack-name <StackName> \
  --profile infiquetra-root --region us-east-1
```

If that doesn't work, you may need to use `--resources-to-skip` to bypass specific resources. Coordinate with the admin before doing this — it can leave inconsistent state.

## GitHub Actions

### Workflow fails immediately with `startup_failure`

**Cause**: Most likely a permissions mismatch between caller and reusable workflow. See [LEARNINGS](../learnings/LEARNINGS.md) for the full story.

**Fix**: Check that the caller workflow declares ≥ permissions the callee needs. For deploy workflows: top-level `permissions: contents: read` + per-job `permissions: { id-token: write, contents: write }`.

### `Configure AWS Credentials` step fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity`

**Cause**: The OIDC trust policy on `infiquetra-aws-infra-gha-role` doesn't match this workflow's claims.

**Fix**:
```bash
# Inspect the role's trust policy
aws iam get-role --role-name infiquetra-aws-infra-gha-role \
  --profile infiquetra-root \
  --query 'Role.AssumeRolePolicyDocument'
```

Currently the trust policy allows `sub LIKE "repo:infiquetra/*"`. If you forked the repo, the `sub` will be `repo:<your-fork>:...` and won't match. Solutions:

1. **Run from a branch in the canonical repo** (preferred)
2. **Add a per-fork condition** (avoid — sprawls trust policy)
3. **Provision a separate IAM role for forks** (correct way if you really need fork-driven deploys)

### Deploy succeeds but your change isn't visible in AWS

**Cause**: CDK skipped the resource because there was no diff (e.g., your change was a no-op or you accidentally edited the wrong stack).

**Fix**:
```bash
# Locally, see what CDK thinks the diff is
uv run cdk diff --all --profile infiquetra-root

# If the diff is empty, your change isn't reaching CDK output.
# Check that you edited the right file and that the value actually changes.
```

## Pre-commit

### Pre-commit hooks fail on commit

**Cause**: Code doesn't pass ruff / mypy / bandit.

**Fix**:
```bash
# See the specific failures
uv run pre-commit run --all-files

# Auto-fix what's auto-fixable
uv run ruff check --fix .
uv run ruff format .

# Stage and re-commit
git add .
git commit
```

If a check is consistently failing on something legitimate (false positive in bandit, etc.), suppress it inline:

- ruff: `# noqa: <rule>`
- mypy: `# type: ignore[<error-code>]`
- bandit: `# nosec` (rare — usually means you should refactor)

## When you're really stuck

1. **Search [`../learnings/LEARNINGS.md`](../learnings/LEARNINGS.md)** — past issues are recorded with full mechanism + fix.
2. **Check the workflow run logs**: `gh run view <RUN_ID> --log-failed`
3. **Check CFN events directly**: `aws cloudformation describe-stack-events --stack-name <Name>`
4. **Re-pull live AWS state** and reconcile manually (see "Recovery / drift detection" sections in `../ops/`).
5. **Add a new entry to `LEARNINGS.md` once you figure it out** — saves the next person from the same dig.

## Asking for help

When asking the admin (or your future self via a `LEARNINGS.md` entry):

- Include the **exact command** you ran
- Include the **first error message** verbatim
- Include the **workflow run ID** if it's a CI failure
- Include the output of `aws sts get-caller-identity --profile <profile>` so you/they know which account+role you're in
- Reference any related items in `docs/learnings/QUEUED.md` or `DECISIONS.md`
