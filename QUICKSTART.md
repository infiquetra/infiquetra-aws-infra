# Quick Start Guide - CAMPPS Development

## Environment Setup ✅

Your sandbox environment is now fully configured with:

- ✅ **AWS CLI v1.42.56** - Installed via pip
- ✅ **Python 3.13.8** - Virtual environment activated
- ✅ **uv 0.8.17** - Fast Python package manager
- ✅ **CDK CLI 2.1030.0** - AWS Cloud Development Kit
- ✅ **All Dependencies** - 130 packages installed
- ✅ **Environment Variables** - `.env` configured

## Activate Development Environment

```bash
# Always run this first in new terminal sessions
source .venv/bin/activate

# Verify environment
python --version  # Should show 3.13.8
cdk --version    # Should show 2.1030.0
aws --version    # Should show 1.42.56
```

## Essential Development Commands

### CDK Operations

```bash
# Synthesize all stacks (validate infrastructure code)
export GITHUB_REPO=infiquetra-aws-infra
uv run cdk synth --quiet

# Synthesize specific stack
uv run cdk synth InfiquetraOrganizationStack
uv run cdk synth InfiquetraSSOStack

# View differences (when connected to AWS)
cdk diff InfiquetraOrganizationStack --profile infiquetra-root

# Deploy (when connected to AWS)
cdk deploy InfiquetraOrganizationStack --profile infiquetra-root
cdk deploy InfiquetraSSOStack --profile infiquetra-root
```

### Code Quality (Pre-commit Checks)

```bash
# Lint and auto-fix code
ruff check . --fix

# Format code
ruff format .

# Type checking
mypy .

# Run all checks at once
ruff check . && ruff format . && mypy .
```

### Testing

```bash
# Run tests (when tests are created)
pytest

# Run with coverage
pytest --cov=infiquetra_aws_infra
```

## CAMPPS-Specific Resources

### Permission Set
The `CamppssDeveloper` permission set (infiquetra_aws_infra/sso_stack.py:163-178) provides:
- **Base**: PowerUserAccess
- **Session**: 8 hours
- **Regions**: us-east-1, us-west-2
- **Services**: S3, DynamoDB, Lambda, API Gateway, CloudFormation, CloudWatch, Logs

### Organizational Structure
```
Apps OU (infiquetra_aws_infra/organization_stack.py:66-76)
└── CAMPPS OU (line 92-102)
    ├── Production OU (line 105-114)
    │   └── campps-prod (431643435299)
    └── NonProd OU (line 116-125)
        └── campps-dev (477152411873)
```

### CAMPPS Accounts
- **campps-prod** (431643435299) - Production environment
- **campps-dev** (477152411873) - Development environment
- **campps-cicd** (424272146308) - **SUSPENDED** (needs resolution)

## Next Steps for CAMPPS Development

### Option 1: Work in Sandbox (No AWS Connection)
You can develop infrastructure code and test synthesis without AWS credentials:

```bash
# Make changes to CDK stacks
vim infiquetra_aws_infra/organization_stack.py

# Validate changes
export GITHUB_REPO=infiquetra-aws-infra
uv run cdk synth --quiet

# Check code quality
ruff check . && ruff format . && mypy .

# Commit and push
git add .
git commit -m "feat: add CAMPPS infrastructure"
git push -u origin claude/setup-project-login-011CUM5VBMcuf2sNh9x9xMBd
```

### Option 2: Connect to AWS (For Deployment)
To actually deploy to AWS, you need AWS SSO configured:

1. **Configure AWS SSO** (requires AWS SSO portal URL from admin)
   ```bash
   aws configure sso --profile infiquetra-root
   # Provide: SSO start URL, region (us-east-1)
   ```

2. **Login to AWS**
   ```bash
   aws sso login --profile infiquetra-root
   aws sts get-caller-identity --profile infiquetra-root
   ```

3. **Deploy Infrastructure**
   ```bash
   cdk deploy InfiquetraOrganizationStack --profile infiquetra-root
   cdk deploy InfiquetraSSOStack --profile infiquetra-root
   ```

## Creating CAMPPS Infrastructure

### Example: Add a CAMPPS-specific Stack

1. **Create new stack file**:
   ```bash
   vim infiquetra_aws_infra/campps_stack.py
   ```

2. **Define CAMPPS resources** (example):
   ```python
   #!/usr/bin/env python3
   from typing import Any
   import aws_cdk as cdk
   from aws_cdk import Stack
   from constructs import Construct

   class CamppsStack(Stack):
       """CAMPPS application infrastructure stack."""

       def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
           super().__init__(scope, construct_id, **kwargs)

           # Add CAMPPS resources here
           # Example: S3 buckets, DynamoDB tables, Lambda functions
   ```

3. **Register in app.py**:
   ```python
   from infiquetra_aws_infra.campps_stack import CamppsStack

   campps_stack = CamppsStack(
       app,
       "InfiquetraCamppsStack",
       env=env,
       description="CAMPPS application infrastructure",
   )
   ```

4. **Validate**:
   ```bash
   export GITHUB_REPO=infiquetra-aws-infra
   uv run cdk synth InfiquetraCamppsStack
   ```

## File Locations

- **Infrastructure Code**: `infiquetra_aws_infra/`
  - `organization_stack.py` - AWS Organizations structure
  - `sso_stack.py` - IAM Identity Center permission sets
  - `__init__.py` - Package initialization

- **CDK App**: `app.py` - Application entry point

- **Configuration**:
  - `.env` - Environment variables (CDK account, region)
  - `cdk.json` - CDK configuration
  - `pyproject.toml` - Python project config

- **GitHub Actions**: `.github/workflows/`
  - `ci.yml` - Pull request validation
  - `cd.yml` - Deployment pipeline

## Troubleshooting

### CDK Synthesis Fails
```bash
# Check environment variables
cat .env

# Ensure GITHUB_REPO is set
export GITHUB_REPO=infiquetra-aws-infra

# Try with verbose output
uv run cdk synth --verbose
```

### AWS CLI Not Working
```bash
# Add to PATH
export PATH=$PATH:~/.local/bin

# Verify installation
which aws
aws --version
```

### Type Errors
```bash
# Run mypy to see specific errors
mypy infiquetra_aws_infra/

# Check pyproject.toml for mypy configuration
cat pyproject.toml | grep -A 20 "\[tool.mypy\]"
```

## Git Workflow

```bash
# Check current branch
git branch

# Make changes and validate
ruff check . && ruff format . && mypy .
export GITHUB_REPO=infiquetra-aws-infra
uv run cdk synth --quiet

# Commit changes
git add .
git commit -m "feat: description of changes"

# Push to feature branch
git push -u origin claude/setup-project-login-011CUM5VBMcuf2sNh9x9xMBd

# Create pull request (via GitHub UI or gh CLI)
```

## Resources

- **AWS CDK Docs**: https://docs.aws.amazon.com/cdk/
- **CDK Python API**: https://docs.aws.amazon.com/cdk/api/v2/python/
- **Project README**: `/home/user/infiquetra-aws-infra/README.md`
- **Claude Instructions**: `/home/user/infiquetra-aws-infra/.claude/CLAUDE.md`
- **Audit Report**: `/home/user/infiquetra-aws-infra/.claude/audit-current-state.md`

---

**You're all set!** Start coding for CAMPPS by modifying the CDK stacks or creating new ones. 🚀
