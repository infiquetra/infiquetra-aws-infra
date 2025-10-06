# CI/CD Pipeline Migration Guide

## Overview

This document describes the migration from the monolithic CI/CD pipelines to a modular, reusable architecture. The new structure improves maintainability, testability, and supports multi-environment deployments.

## What Changed

### Before: Monolithic Workflows

**Old Structure:**
```
.github/workflows/
├── ci.yml          (165 lines, all-in-one validation)
├── cd.yml          (137 lines, deployment pipeline)
└── deploy.yml      (90 lines, manual deployment)
```

**Problems:**
- Heavy code duplication across workflows
- Setup steps repeated in every workflow
- Mix of pip and uv installations
- Hard to test locally
- Single environment only (production)
- Difficult to maintain and extend

### After: Modular Architecture

**New Structure:**
```
.github/
├── actions/                          # Composite actions (reusable setup)
│   ├── setup-python-uv/action.yml   # Python + uv installation
│   ├── setup-node-cdk/action.yml    # Node.js + CDK CLI
│   └── setup-aws-credentials/action.yml  # AWS OIDC authentication
│
├── workflows/
│   ├── reusable-code-quality.yml    # Ruff + mypy checks
│   ├── reusable-security-scan.yml   # Bandit + semgrep + checkov
│   ├── reusable-cdk-synthesis.yml   # CDK synthesis + validation
│   ├── reusable-aws-deployment.yml  # Multi-environment deployment
│   ├── pull-request-validation.yml  # PR validation (replaces ci.yml)
│   └── deploy-infrastructure.yml    # Deployment (replaces cd.yml + deploy.yml)
│
└── CICD-MIGRATION.md                # This guide

.actrc                                # Local testing configuration
```

**Benefits:**
- DRY: No duplicated setup code
- Modular: Each component has a single responsibility
- Reusable: Composite actions and workflows can be called anywhere
- Testable: Optimized for local testing with act
- Multi-environment: Support for production, nonprod, staging
- Consistent: Uses uv everywhere

## Migration Details

### Composite Actions

#### `setup-python-uv`
Replaces scattered Python setup code across all workflows.

**Old way (repeated everywhere):**
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.13'

- name: Cache Python dependencies
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}

- name: Install uv
  run: |
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "$HOME/.local/bin" >> $GITHUB_PATH

- name: Install dependencies
  run: uv sync --dev
```

**New way:**
```yaml
- name: Setup Python with uv
  uses: ./.github/actions/setup-python-uv
  with:
    python-version: '3.13'
```

**Outputs:**
- `python-version`: Installed Python version
- `uv-version`: Installed uv version
- `cache-hit`: Whether cache was used

#### `setup-node-cdk`
Consolidates Node.js and CDK CLI installation.

**Old way:**
```yaml
- name: Install Node.js for CDK CLI
  uses: actions/setup-node@v4
  with:
    node-version: '18'

- name: Install CDK CLI
  run: npm install -g aws-cdk
```

**New way:**
```yaml
- name: Setup Node.js and CDK CLI
  uses: ./.github/actions/setup-node-cdk
  with:
    node-version: '18'
```

#### `setup-aws-credentials`
Wraps AWS OIDC authentication with helpful outputs.

**Old way:**
```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v5
  with:
    role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
    role-session-name: GitHubActions-${{ github.run_id }}
    aws-region: us-east-1
```

**New way:**
```yaml
- name: Configure AWS credentials
  uses: ./.github/actions/setup-aws-credentials
  with:
    aws-role-arn: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
    aws-region: us-east-1
```

### Reusable Workflows

#### Code Quality (`reusable-code-quality.yml`)

**What it does:**
- Runs ruff linting (includes import sorting)
- Runs ruff formatting check
- Runs mypy type checking
- Generates GitHub step summaries

**Inputs:**
- `python-version` (default: '3.13')
- `working-directory` (default: '.')

**Outputs:**
- `quality-status`: 'pass' or 'fail'

**Usage:**
```yaml
jobs:
  quality:
    uses: ./.github/workflows/reusable-code-quality.yml
    with:
      python-version: '3.13'
```

#### Security Scanning (`reusable-security-scan.yml`)

**What it does:**
- Runs bandit (Python security)
- Runs semgrep (pattern-based security)
- Runs checkov (CloudFormation security, if cdk.out exists)
- Counts total findings
- Uploads security reports as artifacts

**Inputs:**
- `python-version` (default: '3.13')
- `working-directory` (default: '.')
- `upload-sarif` (default: false)

**Outputs:**
- `security-findings-count`: Total number of findings

**Usage:**
```yaml
jobs:
  security:
    uses: ./.github/workflows/reusable-security-scan.yml
    with:
      upload-sarif: false
```

#### CDK Synthesis (`reusable-cdk-synthesis.yml`)

**What it does:**
- Synthesizes all CDK stacks
- Runs cfn-lint on generated templates
- Runs checkov on CloudFormation templates
- Generates cost estimation
- Uploads cdk.out as artifact

**Inputs:**
- `python-version` (default: '3.13')
- `node-version` (default: '18')
- `working-directory` (default: '.')
- `cdk-account` (required)
- `cdk-region` (required)

**Outputs:**
- `synthesis-status`: 'pass' or 'fail'
- `template-count`: Number of templates generated

**Usage:**
```yaml
jobs:
  synthesis:
    uses: ./.github/workflows/reusable-cdk-synthesis.yml
    with:
      cdk-account: '645166163764'
      cdk-region: 'us-east-1'
```

#### AWS Deployment (`reusable-aws-deployment.yml`)

**What it does:**
- Authenticates to AWS via OIDC
- Deploys specified stack(s)
- Creates git tags for production deployments
- Generates detailed deployment summary

**Inputs:**
- `environment` (required: production, nonprod, staging)
- `stack` (required: all, organization, sso)
- `aws-account` (required)
- `aws-region` (default: 'us-east-1')
- `require-approval` (default: true)
- `python-version` (default: '3.13')
- `node-version` (default: '18')

**Secrets:**
- `aws-role-arn` (required)

**Outputs:**
- `deployment-status`: 'success', 'failure', or 'skipped'
- `deployment-tag`: Git tag created (production only)

**Usage:**
```yaml
jobs:
  deploy:
    uses: ./.github/workflows/reusable-aws-deployment.yml
    with:
      environment: production
      stack: all
      aws-account: '645166163764'
      aws-region: 'us-east-1'
      require-approval: false
    secrets:
      aws-role-arn: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
```

### Main Workflows

#### Pull Request Validation (`pull-request-validation.yml`)

**Replaces:** `ci.yml`

**Trigger:**
- Pull requests to `main`
- Manual workflow dispatch

**Jobs:**
1. `code-quality`: Runs in parallel
2. `security-scan`: Runs in parallel with code-quality
3. `cdk-synthesis`: Runs after code-quality
4. `validation-summary`: Final summary combining all results

**No breaking changes** - Same behavior as before, but modular

**Example workflow run:**
```
PR #123: Add new SSO permission set

✅ Code Quality: All checks passed
⚠️  Security Scan: 2 findings (review artifacts)
✅ CDK Synthesis: Successful (2 templates generated)

🚀 Ready for merge and deployment!
```

#### Deploy Infrastructure (`deploy-infrastructure.yml`)

**Replaces:** `cd.yml` and `deploy.yml` (consolidated)

**Triggers:**
- Push to `main` (auto-deploy to production)
- Manual workflow dispatch with environment/stack selection

**Jobs:**
1. `deploy`: Uses reusable-aws-deployment.yml
2. `post-deployment`: Summary and status

**Workflow Dispatch Inputs:**
- `environment`: production (default), nonprod, staging
- `stack`: all (default), organization, sso

**Example manual deployment:**
```yaml
# Deploy SSO stack to production
environment: production
stack: sso

# Deploy all stacks to nonprod
environment: nonprod
stack: all
```

## Multi-Environment Support

### Environment Configuration

The new pipeline supports multiple environments:

| Environment | AWS Account | Auto-Deploy | Approval Required |
|-------------|-------------|-------------|-------------------|
| Production  | 645166163764 | Yes (on push to main) | No |
| NonProd     | TBD | No (manual only) | No |
| Staging     | TBD | No (manual only) | No |

### Setting Up New Environments

1. **Create AWS Account** for the new environment
2. **Bootstrap CDK** in the new account
3. **Set up OIDC provider** using `github-oidc-bootstrap/`
4. **Update workflow** to map environment to account:

```yaml
# In deploy-infrastructure.yml
aws-account: ${{ (inputs.environment == 'production') && '645166163764' || 'NEW-ACCOUNT-ID' }}
```

5. **Add GitHub secret** (if using different role):
```bash
gh secret set AWS_NONPROD_ROLE_ARN --body "arn:aws:iam::NEW-ACCOUNT:role/..."
```

### Deploying to Different Environments

**Production (automatic on merge):**
```bash
git push origin main
# Triggers automatic deployment to production
```

**Production (manual):**
```bash
gh workflow run deploy-infrastructure.yml -f environment=production -f stack=all
```

**NonProd:**
```bash
gh workflow run deploy-infrastructure.yml -f environment=nonprod -f stack=all
```

**Staging:**
```bash
gh workflow run deploy-infrastructure.yml -f environment=staging -f stack=sso
```

## Local Testing with act

### Installation

**macOS:**
```bash
brew install act
```

**Linux:**
```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

### Configuration

The repository includes `.actrc` for local testing configuration:

```bash
# Container settings
-P ubuntu-latest=catthehacker/ubuntu:act-latest
--container-architecture linux/amd64

# Secrets (set via environment)
-s GITHUB_TOKEN
-s AWS_DEPLOY_ROLE_ARN

# Environment variables
--env CDK_DEFAULT_ACCOUNT=645166163764
--env CDK_DEFAULT_REGION=us-east-1
--env GITHUB_REPO=infiquetra-aws-infra
```

### Testing Workflows Locally

**Test pull request validation:**
```bash
act pull_request -W .github/workflows/pull-request-validation.yml
```

**Test specific job:**
```bash
act -j code-quality -W .github/workflows/pull-request-validation.yml
```

**Test deployment (dry run):**
```bash
act workflow_dispatch -W .github/workflows/deploy-infrastructure.yml --dry-run
```

**List available workflows:**
```bash
act -l
```

**Debug with verbose output:**
```bash
act pull_request -W .github/workflows/pull-request-validation.yml -v
```

### Limitations with act

- **OIDC authentication**: Won't work locally (AWS OIDC requires GitHub infrastructure)
- **Secrets**: Must be provided via environment variables or `.secrets` file
- **Artifacts**: Saved locally in `/tmp/act-*`
- **GitHub API**: Limited functionality without valid GITHUB_TOKEN

## Breaking Changes

### None for End Users

The new pipeline maintains backward compatibility:
- Same triggers (PR to main, push to main)
- Same required secrets
- Same deployment behavior
- Same artifact names

### For Pipeline Maintainers

If you were directly referencing workflow files:

**Old:**
```yaml
uses: ./.github/workflows/ci.yml  # ❌ No longer exists
```

**New:**
```yaml
uses: ./.github/workflows/pull-request-validation.yml  # ✅ Use this
```

## Migration Checklist

- [x] Create composite actions for setup steps
- [x] Create reusable workflows for each pipeline stage
- [x] Create new main workflows (pull-request-validation, deploy-infrastructure)
- [x] Delete old workflows (ci.yml, cd.yml, deploy.yml)
- [x] Create `.actrc` for local testing
- [x] Update `.claude/CLAUDE.md` documentation
- [x] Create migration guide (this document)
- [ ] Test pull-request-validation workflow with actual PR
- [ ] Test deploy-infrastructure workflow on main branch
- [ ] Test local execution with act
- [ ] Document any issues or adjustments needed

## Troubleshooting

### Composite Action Not Found

**Error:**
```
Error: Unable to resolve action `./.github/actions/setup-python-uv`
```

**Solution:**
Ensure you've checked out the repository with actions:
```yaml
- name: Checkout code
  uses: actions/checkout@v4  # Must be BEFORE using composite actions
```

### Reusable Workflow Outputs Not Available

**Error:**
```
Error: Context access might be invalid: needs.code-quality.outputs.quality-status
```

**Solution:**
Ensure the reusable workflow defines outputs at both job and workflow levels:
```yaml
# In reusable workflow
on:
  workflow_call:
    outputs:
      quality-status:
        value: ${{ jobs.code-quality.outputs.status }}

jobs:
  code-quality:
    outputs:
      status: ${{ steps.final-status.outputs.status }}
```

### act Fails with Container Architecture Error

**Error:**
```
Error: container architecture mismatch
```

**Solution:**
Use the `.actrc` file or add flag:
```bash
act --container-architecture linux/amd64
```

### CDK Synthesis Fails Locally with act

**Error:**
```
Error: CDK_DEFAULT_ACCOUNT environment variable not set
```

**Solution:**
Ensure environment variables are set in `.actrc`:
```bash
--env CDK_DEFAULT_ACCOUNT=645166163764
--env CDK_DEFAULT_REGION=us-east-1
```

## Next Steps

1. **Test the new pipelines** with a test PR
2. **Monitor the first production deployment** closely
3. **Set up nonprod/staging environments** when ready
4. **Consider adding**:
   - Slack/Teams notifications for deployments
   - Cost alerts on unexpected increases
   - Automated rollback on deployment failures
   - Progressive deployments (canary/blue-green)

## Questions or Issues?

If you encounter issues with the new pipeline:

1. Check this migration guide first
2. Review `.claude/CLAUDE.md` for detailed documentation
3. Test locally with `act` to debug issues
4. Check GitHub Actions logs for detailed error messages
5. Open an issue in the repository with logs and context

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Reusable Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
- [Composite Actions](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action)
- [act - Run GitHub Actions Locally](https://github.com/nektos/act)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
