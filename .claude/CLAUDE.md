# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AWS CDK infrastructure as code for Infiquetra LLC's multi-business organizational structure. This repository manages AWS Organizations, SSO permission sets, and enterprise-grade CI/CD pipelines using GitHub Actions with OIDC authentication.

**AWS Account**: 645166163764 (infiquetra management account)
**AWS Region**: us-east-1
**AWS Profile**: infiquetra-root

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
# Format code
black .
ruff format .

# Lint code
flake8 .
ruff check .

# Sort imports
isort .

# Type checking
mypy .

# Security scanning
bandit -r .

# Run all pre-commit hooks
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

### CI Pipeline (`.github/workflows/ci.yml`)

**Trigger**: Pull requests to `main`

**Stages**:
1. Code quality: black, flake8, isort
2. Security scanning: bandit, semgrep
3. CDK synthesis validation
4. CloudFormation linting (cfn-lint)
5. Infrastructure security scanning (checkov)
6. Cost estimation

**No AWS authentication required** - synthesis only

### CD Pipeline (`.github/workflows/cd.yml`)

**Trigger**: Push to `main` or manual workflow dispatch

**Stages**:
1. OIDC authentication to AWS
2. Deploy organization stack (optional)
3. Deploy SSO stack (optional)
4. Create deployment tag
5. Generate deployment summary

**Required Permissions**:
- `id-token: write` (for OIDC)
- `contents: write` (for tagging)

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
black . && flake8 . && isort . && cdk synth --all

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
   black . && flake8 . && isort . && cdk synth --all
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

### CAMPPS Migration Context

**Current State**:
- `campps-cicd` (424272146308) - SUSPENDED, needs resolution
- `campps-prod` (431643435299) - In CAMPPS/workloads/PRODUCTION
- `campps-dev` (477152411873) - In CAMPPS/workloads/SDLC

**New Structure**:
- Apps OU → CAMPPS OU → Production OU
- Apps OU → CAMPPS OU → NonProd OU

Migration requires resolving the suspended account first.

## Python Configuration

### Package Management

- **Primary**: `uv` (modern, fast package manager)
- **Fallback**: `pip` (requirements.txt maintained for compatibility)
- **Python Version**: 3.13+

### Code Quality Standards

- **Formatter**: black (line length: 88)
- **Linter**: flake8 + ruff
- **Import Sorting**: isort (black profile)
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
