# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AWS CDK infrastructure as code for Infiquetra LLC's multi-business organizational structure. This repository manages AWS Organizations, SSO permission sets, and enterprise-grade CI/CD pipelines using GitHub Actions with OIDC authentication.

**AWS Account**: 645166163764 (infiquetra management account)
**AWS Region**: us-east-1
**AWS Profile**: infiquetra-root

## 📓 Engineering journal — AUTO-MAINTAIN

Living documentation at [`docs/engineering-journal/`](../docs/engineering-journal/) — pattern adopted from `infiquetra/home-lab/docs/engineering-journal/`. The directory IS the engineering journal; the files inside are its sections.

| File | Purpose |
|------|---------|
| [LEARNINGS.md](../docs/engineering-journal/LEARNINGS.md) | Empirical findings + mechanisms + fixes + validations |
| [DECISIONS.md](../docs/engineering-journal/DECISIONS.md) | Architecture decisions (ADR-style) with rationale + revisit conditions |
| [QUEUED.md](../docs/engineering-journal/QUEUED.md) | Future-work items by priority with "worth it when" triggers |
| [ARCHIVE.md](../docs/engineering-journal/ARCHIVE.md) | Shipped + rejected + superseded items |
| [audits/](../docs/engineering-journal/audits/) | Dated deep-dive audits — frozen snapshots of cross-source analysis |
| [narratives/](../docs/engineering-journal/narratives/) | Self-contained, longer-form companion docs (design walkthroughs, post-incident write-ups, inventory snapshots) — readable cold by an outside reader |

**Maintenance rules (Claude: follow these without being asked):**

1. **After a deploy, CDK refactor, or AWS API failure** that produces a surprising
   result, a confirmed bug, or a non-obvious mechanism worth remembering
   → add a dated entry to `LEARNINGS.md`. Include the evidence (workflow run ID,
   commit, AWS error code) and the **mechanism** (why it happened, not just what),
   and a **Generalizable rule** line stripping the lesson from the specific incident.

2. **After committing an architectural or pipeline-design decision** (pick A over B,
   flip a flag, change a permission scope, add/remove a workflow stage)
   → add an entry to `DECISIONS.md` with rationale + rejected alternatives +
   "revisit when" condition. Include the commit hash or PR number.

3. **Whenever a promising idea surfaces but we don't build it right now**
   → add to `QUEUED.md` with priority (P0/P1/P2/P3/Maybe), concrete "worth it when"
   trigger, and rough effort estimate. Don't skip — these items are easy to lose.

4. **When a QUEUED item ships** → move its entry to `ARCHIVE.md` as SHIPPED with
   the commit hash + date. Remove from QUEUED.md.

5. **When a QUEUED item is rejected** → move to `ARCHIVE.md` as REJECTED with the
   reason + under what conditions we'd revisit. Remove from QUEUED.md.

6. **When a prior LEARNING or DECISION is invalidated** → update the original
   entry with the correction AND move the pre-correction version to `ARCHIVE.md`
   as SUPERSEDED. Never silently overwrite history.

7. **When something needs a longer write-up than fits in an entry**
   (full design narrative, multi-page post-mortem, inventory snapshot for forensics)
   → create `docs/engineering-journal/narratives/YYYY-MM-DD-short-slug.md` and link
   to it from the relevant LEARNINGS / DECISIONS entry. The four core files stay
   scannable; long-form companion lives next door.

**Entry format.** Each of the four core files has a block-quote intro at the top
spelling out its format. New entries use these subheaders where applicable:
**Context / Evidence / Mechanism / Fix (or queued) / Validation / What surprised /
Generalizable rule / Refs**. Not every entry needs every subheader, but the
**Generalizable rule** line is the highest-value field — without it, future-Claude
has to re-derive the lesson from the evidence each time.

**Don't wait to be asked.** When any of these triggers fire in a session, update
the files as part of the same commit that ships the change. The whole point of
these files is that they maintain themselves.

## Core Architecture

### Stack Structure

The infrastructure is organized into two primary CDK stacks:

1. **OrganizationStack** (`infiquetra_aws_infra/organization_stack.py`)
   - Creates AWS Organizations structure for business units
   - Defines Service Control Policies (SCPs)
   - Manages organizational units (OUs): Core, Media, Apps, Consulting
   - Includes CAMPPS sub-structure under Apps OU (Production, NonProd)
   - Root ID: `r-f3un`

2. **SSOStack** (`infiquetra_aws_infra/sso_stack.py`)
   - Creates AWS SSO (Identity Center) permission sets
   - Depends on OrganizationStack
   - SSO Instance ARN: `arn:aws:sso:::instance/ssoins-7223f05fc9da6e24`
   - Permission sets: CoreAdministrator, SecurityAuditor, BillingManager, MediaDeveloper/Administrator, AppsDeveloper/Administrator, CamppssDeveloper, ConsultingDeveloper/Administrator, ReadOnlyAccess

### CDK Application Entry Point

**File**: `app.py`
- Uses `python-dotenv` to load environment variables
- Creates both stacks with dependency chain (SSO depends on Organization)
- Environment configuration via `CDK_DEFAULT_ACCOUNT` and `CDK_DEFAULT_REGION`

### GitHub OIDC Bootstrap

**Directory**: `github-oidc-bootstrap/`
- Separate CDK app for one-time GitHub Actions OIDC setup
- Creates OIDC provider and IAM role: `infiquetra-aws-infra-gha-role`
- Enables passwordless GitHub Actions authentication to AWS
- Has its own `app.py`, stack implementation, and test suite

## Essential Commands

### Environment Setup

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Install CDK CLI globally
npm install -g aws-cdk
```

### AWS Authentication

```bash
# Login to AWS SSO
aws sso login --profile infiquetra-root

# Verify credentials
aws sts get-caller-identity --profile infiquetra-root
```

### CDK Operations

```bash
# Synthesize all stacks
cdk synth --all

# Synthesize with quiet output (for CI)
GITHUB_REPO=infiquetra-aws-infra uv run cdk synth --quiet

# Deploy organization stack
cdk deploy InfiquetraOrganizationStack --profile infiquetra-root

# Deploy SSO stack
cdk deploy InfiquetraSSOStack --profile infiquetra-root

# Show differences before deployment
cdk diff --profile infiquetra-root

# Destroy a stack (use with caution)
cdk destroy <StackName> --profile infiquetra-root
```

### Code Quality and Testing

```bash
# Lint code (includes import sorting)
ruff check .

# Fix linting issues automatically
ruff check --fix .

# Format code
ruff format .

# Type checking
mypy .

# Security scanning
bandit -r .

# Run all pre-commit hooks (recommended before committing)
pre-commit run --all-files
```

### GitHub OIDC Bootstrap (One-Time Setup)

```bash
cd github-oidc-bootstrap

# Setup environment
cp .env.example .env
# Edit .env with account details

# Install dependencies
uv sync --dev

# Deploy OIDC provider
uv run cdk deploy --profile infiquetra-root

# Get role ARN for GitHub secret
aws cloudformation describe-stacks \
  --stack-name infiquetra-aws-infra-gha-bootstrap \
  --profile infiquetra-root \
  --query 'Stacks[0].Outputs[?OutputKey==`GitHubActionsRoleArn`].OutputValue' \
  --output text
```

## CI/CD Architecture

### Overview

The CI/CD pipeline is modular and reusable, built with:
- **Composite Actions** (`.github/actions/`): Reusable setup steps
- **Reusable Workflows** (`.github/workflows/reusable-*.yml`): Modular pipeline components
- **Main Workflows**: Pull request validation and deployment orchestration

### GitHub Actions Authentication

**CRITICAL**: This repository uses GitHub OIDC for AWS authentication. Never use AWS access keys.

- **OIDC Provider**: `token.actions.githubusercontent.com`
- **IAM Role**: `infiquetra-aws-infra-gha-role`
- **GitHub Secret**: `AWS_DEPLOY_ROLE_ARN`
- **Trust Policy Restrictions**:
  - Repository: `infiquetra/infiquetra-aws-infra`
  - Branches: `main`, `develop`
  - Pull requests targeting `main`
  - Organization members only

### Composite Actions

**`setup-python-uv`** - Install Python 3.13 and uv package manager
- Caches pip dependencies
- Installs uv from astral.sh
- Runs `uv sync --dev` to install all dependencies
- Outputs: python-version, uv-version, cache-hit

**`setup-node-cdk`** - Install Node.js and AWS CDK CLI
- Installs Node.js (default: 18)
- Installs AWS CDK CLI globally
- Outputs: node-version, cdk-version

**`setup-aws-credentials`** - Configure AWS credentials via OIDC
- Uses aws-actions/configure-aws-credentials@v5
- Requires `id-token: write` permission
- Outputs: aws-account-id, aws-region

### Reusable Workflows

**`reusable-code-quality.yml`** - Code quality checks
- Runs ruff linting (includes import sorting)
- Runs ruff formatting check
- Runs mypy type checking
- Outputs: quality-status (pass/fail)

**`reusable-security-scan.yml`** - Security scanning
- Runs bandit (Python security scan)
- Runs semgrep (pattern-based security scan)
- Runs checkov on CloudFormation templates (if cdk.out exists)
- Uploads security reports as artifacts
- Outputs: security-findings-count

**`reusable-cdk-synthesis.yml`** - CDK synthesis and validation
- Synthesizes all CDK stacks
- Runs cfn-lint on generated templates
- Runs checkov on CloudFormation templates
- Generates cost estimation
- Uploads cdk.out as artifact
- Outputs: synthesis-status, template-count

**`reusable-aws-deployment.yml`** - AWS deployment
- Supports multi-environment deployment (production, nonprod, staging)
- Configurable stack deployment (all, organization, sso)
- Creates git tags for production deployments
- Generates detailed deployment summary
- Outputs: deployment-status, deployment-tag

### Main Workflows

**`pull-request-validation.yml`** (replaces ci.yml)
- **Trigger**: Pull requests to `main`, workflow_dispatch
- **Jobs**:
  - code-quality: Parallel
  - security-scan: Parallel with code-quality
  - cdk-synthesis: After code-quality
  - validation-summary: Final summary with all results
- **No AWS authentication required** - synthesis only

**`deploy-infrastructure.yml`** (replaces cd.yml and deploy.yml)
- **Trigger**: Push to `main`, workflow_dispatch
- **Jobs**:
  - deploy: Uses reusable-aws-deployment.yml
  - post-deployment: Summary and status
- **Inputs** (workflow_dispatch):
  - environment: production (default), nonprod, staging
  - stack: all (default), organization, sso
- **Required Permissions**:
  - `id-token: write` (for OIDC)
  - `contents: write` (for tagging)

### Testing CI/CD Locally with act

Install act:
```bash
# macOS
brew install act

# Linux
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

Test workflows locally:
```bash
# Test pull request validation
act pull_request -W .github/workflows/pull-request-validation.yml

# Test specific job
act -j code-quality -W .github/workflows/pull-request-validation.yml

# Test deployment workflow (dry run)
act workflow_dispatch -W .github/workflows/deploy-infrastructure.yml --dry-run

# View available workflows
act -l
```

Configuration file `.actrc` provides:
- Container architecture settings
- Environment variables (CDK_DEFAULT_ACCOUNT, etc.)
- Secret placeholders for testing

## Development Workflow

### ⚠️ CRITICAL: Always Start from Updated Main Branch

**MANDATORY WORKFLOW FOR ALL NEW WORK:**

```bash
# 1. ALWAYS start by updating main branch
git checkout main
git pull origin main

# 2. Create feature branch from fresh main
git checkout -b feature/your-feature-name

# 3. Make your changes
# ... edit files ...

# 4. Local validation
ruff check . && ruff format . && mypy . && cdk synth --all

# 5. Commit and push
git add .
git commit -m "feat: description"
git push origin feature/your-feature-name

# 6. Create pull request
gh pr create --title "Title" --body "Description"
```

**Why this matters:**
- Prevents merge conflicts from divergent branches
- Ensures you're building on the latest infrastructure state
- Reduces CI/CD failures from outdated dependencies
- Maintains clean git history

### Making Infrastructure Changes

1. **Update main branch** (REQUIRED)
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Create feature branch from updated main**
   ```bash
   git checkout -b feature/description
   ```

3. **Make changes** to CDK stacks in `infiquetra_aws_infra/`

4. **Local validation**
   ```bash
   ruff check . && ruff format . && mypy . && cdk synth --all
   ```

5. **Commit and push**
   ```bash
   git add .
   git commit -m "feat: description"
   git push origin feature/description
   ```

6. **Create pull request** - CI pipeline validates automatically

7. **Review and merge** - CD pipeline deploys to AWS

### Working with GitHub CLI

```bash
# View recent workflow runs
gh run list --repo infiquetra/infiquetra-aws-infra --limit 5

# View specific run logs (failed steps only)
gh run view <run-id> --repo infiquetra/infiquetra-aws-infra --log-failed

# Create pull request with summary
gh pr create --title "Title" --body "$(cat <<'EOF'
## Summary
- Change 1
- Change 2

## Test plan
- [ ] Validated CDK synthesis
- [ ] Reviewed security scans
EOF
)"
```

**Note**: The `gh` command defaults to github.com. Only use `GH_HOST=github.com` when explicitly needed.

## Important Constraints

### Service Control Policies (SCPs)

**BaseSecurityPolicy** - Applied to all OUs:
- Denies root user actions
- Denies deletion of logging resources (CloudTrail, CloudWatch Logs)
- Requires MFA for sensitive IAM and Organizations operations

**NonProductionCostControl** - Applied to CAMPPS NonProd OU:
- Restricts EC2 instance types to t3/t4g (nano, micro, small, medium)
- Prevents expensive instance launches in non-prod

### Stack Dependencies

**CRITICAL**: The `SSOStack` depends on `OrganizationStack`. Always deploy in order:
1. InfiquetraOrganizationStack
2. InfiquetraSSOStack

Attempting to deploy SSO first will fail.

### CAMPPS OU placement

Both CAMPPS workload accounts live in the CDK-managed `Apps>CAMPPS` tree as of 2026-05-02:
- `campps-prod` (431643435299) — `Apps/CAMPPS/Production` (`ou-f3un-cec60ji6`)
- `campps-dev` (477152411873) — `Apps/CAMPPS/NonProd` (`ou-f3un-yb8hu7vq`)

The legacy top-level `CAMPPS` OU and its `workloads/{PRODUCTION,SDLC}` + `CICD/PRODUCTION` subtree have been deleted. The previously-suspended `campps-cicd` account (424272146308) was already removed from the org before this work — the empty `CICD/PRODUCTION` OU was its only remaining trace, and is now gone too.

Both accounts inherit `BaseSecurityPolicy` from the `Apps` OU; `campps-dev` additionally inherits `NonProductionCostControl` from `NonProd` (restricts EC2 launches to t3/t4g nano-medium).

See [`docs/engineering-journal/ARCHIVE.md`](../docs/engineering-journal/ARCHIVE.md) 2026-05-02 entry for the migration write-up.

## Python Configuration

### Package Management

- **Primary**: `uv` (modern, fast package manager)
- **Fallback**: `pip` (requirements.txt maintained for compatibility)
- **Python Version**: 3.13+

### Code Quality Standards

- **Linter & Formatter**: ruff (line length: 88, includes import sorting)
- **Type Checking**: mypy (strict mode, excludes github-oidc-bootstrap/app.py)
- **Security**: bandit (excludes tests/)

### Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:
- ruff (linter and formatter)
- mypy (type checking, excludes github-oidc-bootstrap/)
- bandit (security scanning)

## Environment Variables

Required for local development and CI/CD:

```bash
CDK_DEFAULT_ACCOUNT=645166163764
CDK_DEFAULT_REGION=us-east-1
GITHUB_REPO=infiquetra-aws-infra
```

For GitHub OIDC bootstrap, use `.env` file in `github-oidc-bootstrap/` directory.

## Common Issues and Solutions

### CDK Synthesis Fails

```bash
# Verify AWS credentials
aws sts get-caller-identity --profile infiquetra-root

# Check environment variables
echo $CDK_DEFAULT_ACCOUNT
echo $CDK_DEFAULT_REGION

# Ensure dependencies are installed
uv sync
```

### GitHub Actions Authentication Failures

```bash
# Verify OIDC provider exists
aws iam list-open-id-connect-providers --profile infiquetra-root

# Verify role exists and check trust policy
aws iam get-role --role-name infiquetra-aws-infra-gha-role --profile infiquetra-root

# Check GitHub secret is set correctly
# Navigate to: Settings → Secrets and variables → Actions
# Verify: AWS_DEPLOY_ROLE_ARN = arn:aws:iam::645166163764:role/infiquetra-aws-infra-gha-role
```

### CloudFormation Stack Updates Fail

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name <StackName> \
  --profile infiquetra-root

# Continue update rollback if stuck
aws cloudformation continue-update-rollback \
  --stack-name <StackName> \
  --profile infiquetra-root
```

### Pre-commit Hook Failures

```bash
# Run hooks manually to see issues
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

## File Structure Notes

```
├── infiquetra_aws_infra/          # Main CDK stacks
│   ├── organization_stack.py      # AWS Organizations structure
│   ├── sso_stack.py              # AWS SSO permission sets
│   └── __init__.py
├── github-oidc-bootstrap/         # One-time OIDC setup (separate CDK app)
│   ├── app.py                    # Bootstrap CDK app entry point
│   ├── github_oidc_bootstrap/    # Bootstrap stack implementation
│   └── tests/                    # Bootstrap tests (88% coverage)
├── .github/workflows/            # CI/CD pipelines
│   ├── ci.yml                   # Pull request validation
│   └── cd.yml                   # Deployment pipeline
├── .claude/                     # Claude Code configuration
├── app.py                       # Main CDK app entry point
├── cdk.json                     # CDK configuration
├── pyproject.toml               # Python project config (uv-based)
├── requirements.txt             # Python dependencies (pip)
└── .pre-commit-config.yaml      # Pre-commit hooks
```

## Security Best Practices

1. **Never commit AWS credentials** - Use OIDC for GitHub Actions
2. **Always review SCPs** before applying to production OUs
3. **Use least-privilege permissions** when creating new permission sets
4. **Test in non-prod** environments before deploying to production OUs
5. **Tag all resources** for cost allocation and security tracking
6. **Enable MFA** for administrator-level permission sets
7. **Monitor CloudTrail** for role assumption and sensitive operations
8. **Review security scan results** in CI pipeline before merging

## Cost Management

- **Organizations**: Free
- **SSO**: Free (up to 5GB logs)
- **CloudTrail**: Standard logging costs apply
- **CloudWatch Logs**: Based on ingestion and retention
- **SCP enforcement**: Free, but controls spending via policy

Monitor costs by:
- OU tags (BusinessUnit: Core, Media, Apps, Consulting)
- Project tags (Project: CAMPPS)
- Environment tags (Environment: Production, AccountType: NonProduction)
