# GitHub OIDC Bootstrap for Infiquetra Organizations

This enterprise-grade CDK application creates the necessary GitHub OIDC provider and IAM role for the `infiquetra/infiquetra-organizations` repository to securely deploy CDK stacks using GitHub Actions with least-privilege access.

## What This Creates

1. **GitHub OIDC Identity Provider**: Allows GitHub Actions to authenticate with AWS using OpenID Connect
2. **IAM Role**: `GitHubActionsDeployRole` with scoped permissions for CDK deployments
3. **Trust Policy**: Restricts access to specific repository, branches, and organization members
4. **Comprehensive Security**: Least-privilege permissions with resource-specific scoping

## Security Features

- **Repository Restriction**: Only the `infiquetra/infiquetra-organizations` repository can assume this role
- **Branch & PR Restriction**: Limited to `main`, `develop` branches and main-branch pull requests
- **Organization Restriction**: Only infiquetra organization members can trigger workflows
- **Session Duration**: Maximum 12-hour session duration
- **Least Privilege**: All permissions scoped to specific resources where possible
- **Resource Tagging**: Comprehensive tagging for security and cost management

## Prerequisites

Before deploying this bootstrap stack, ensure you have:

- [uv](https://docs.astral.sh/uv/) installed (modern Python package manager)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) **v2.1029.1 or later** (`npm install -g aws-cdk@latest`)
- AWS credentials configured with administrative access
- Python 3.11+ installed

> **⚠️ CDK Version Requirement**: This project requires CDK CLI v2.1029.1+ to support cloud assembly schema v48.0.0. If you encounter version mismatch errors, update your CDK CLI:
> ```bash
> npm install -g aws-cdk@latest
> cdk --version  # Should show 2.1029.1 or higher
> ```

## Quick Start

### 1. Navigate to Bootstrap Directory

```bash
cd github-oidc-bootstrap
```

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your AWS account details:
# CDK_DEFAULT_ACCOUNT=645166163764
# CDK_DEFAULT_REGION=us-east-1
```

### 3. Install Dependencies

```bash
# Install with uv (recommended)
uv sync --dev

# Or use make shortcut
make install
```

### 4. Deploy the Stack

```bash
# Deploy directly with CDK
uv run cdk deploy --profile infiquetra-root

# Optional: Synthesize first to review templates
uv run cdk synth
```

### 5. Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name GitHubOIDCBootstrap \
  --profile infiquetra-root \
  --query 'Stacks[0].StackStatus'
```

## Common Commands

### Deployment Commands

```bash
# Deploy the stack
uv run cdk deploy --profile infiquetra-root

# Deploy with no approval prompts
uv run cdk deploy --require-approval never --profile infiquetra-root

# Synthesize CloudFormation templates
uv run cdk synth

# Show diff before deployment
uv run cdk diff --profile infiquetra-root

# Destroy the stack (when needed)
uv run cdk destroy --profile infiquetra-root
```

### Development Commands

```bash
# Run tests
make test
# Or: uv run pytest tests/ -v

# Lint code
make lint
# Or: uv run ruff check . && uv run mypy .

# Format code
make format
# Or: uv run ruff format . && uv run ruff check --fix .

# Clean up generated files
make clean
```

## Modern Development Tooling

This project uses modern Python tooling:

- **uv**: Fast Python package manager and dependency resolver
- **ruff**: Lightning-fast linter and formatter
- **mypy**: Static type checking
- **pytest**: Comprehensive testing framework
- **bandit**: Security vulnerability scanner
- **cfn-lint**: CloudFormation template validation

## Retrieve the Role ARN

After successful deployment, retrieve the IAM role ARN for GitHub Actions:

```bash
# Get the role ARN from stack outputs
aws cloudformation describe-stacks \
  --stack-name GitHubOIDCBootstrap \
  --profile infiquetra-root \
  --query 'Stacks[0].Outputs[?OutputKey==`GitHubActionsRoleArn`].OutputValue' \
  --output text
```

**Expected output:**
```
arn:aws:iam::645166163764:role/GitHubActionsDeployRole
```

## Setting up GitHub Repository

### 1. Add the Role ARN as a Repository Secret

Navigate to your GitHub repository settings and add a new repository secret:

- **Name**: `AWS_DEPLOY_ROLE_ARN`
- **Value**: The role ARN from the stack output (format: `arn:aws:iam::645166163764:role/GitHubActionsDeployRole`)

### 2. Update Your Workflow

The main deployment workflow (`.github/workflows/deploy.yml`) should be updated to use OIDC authentication. The workflow is already configured to use the `AWS_DEPLOY_ROLE_ARN` secret.

## Security Features

- **Repository Restriction**: Only the `infiquetra/infiquetra-organizations` repository can assume this role
- **Branch Restriction**: Only `main`, `develop` branches and pull requests can use the role
- **Session Duration**: Maximum 12-hour session duration
- **Least Privilege**: Permissions scoped to CDK deployment requirements

## IAM Permissions Included

The role includes permissions for:

- CloudFormation stack operations
- IAM role and policy management
- S3 bucket operations (for CDK assets)
- AWS Organizations management
- AWS SSO administration
- CloudTrail operations
- Systems Manager parameters
- Basic EC2 and STS operations

## Troubleshooting

### Common Issues

1. **CDK Version Mismatch**:
   ```
   Error: Maximum schema version supported is 45.x.x, but found 48.0.0
   ```
   **Solution**: Update CDK CLI:
   ```bash
   npm install -g aws-cdk@latest
   cdk --version  # Should show 2.1029.1 or higher
   ```

2. **Profile not found**:
   ```bash
   aws configure list-profiles  # Check available profiles
   aws sso login --profile infiquetra-root  # Login if using SSO
   ```

3. **Stack already exists**:
   ```bash
   # View existing stack
   aws cloudformation describe-stacks --stack-name GitHubOIDCBootstrap --profile infiquetra-root
   ```

4. **Insufficient permissions**: The deployment profile needs administrative access to create IAM roles and OIDC providers

### Verification Commands

**Verify OIDC provider:**
```bash
aws iam list-open-id-connect-providers --profile infiquetra-root
# Should show: token.actions.githubusercontent.com
```

**Verify IAM role:**
```bash
aws iam get-role --role-name GitHubActionsDeployRole --profile infiquetra-root
# Should show role with GitHub trust policy
```

**Test GitHub Actions locally (optional):**
```bash
# Use act to test workflows locally (requires Docker)
act -j test-oidc --secret-file .env
```

## Cleanup

To remove the bootstrap resources when no longer needed:

```bash
# Destroy the stack
uv run cdk destroy --profile infiquetra-root

# Confirm when prompted
# Are you sure you want to delete: GitHubOIDCBootstrap (y/n)? y
```

**⚠️ Warning**: Only destroy this stack if you no longer need GitHub Actions to deploy to your AWS account.

## Next Steps

After successfully deploying this bootstrap stack:

1. **Copy the Role ARN**: Save the `GitHubActionsDeployRole` ARN from the stack outputs
2. **Set GitHub Secret**: Add `AWS_DEPLOY_ROLE_ARN` secret to your repository
3. **Test the Pipeline**: Create a test PR to verify GitHub Actions can assume the role
4. **Clean Up**: Remove any old AWS access keys from GitHub secrets

## Troubleshooting

### Deployment Issues

**CDK Version Errors:**
```bash
# Update CDK CLI if you see schema version errors
npm install -g aws-cdk@latest
cdk --version  # Should be 2.1029.1 or higher
```

**Profile Issues:**
```bash
# Verify AWS profile is configured
aws sts get-caller-identity --profile infiquetra-root

# Configure SSO if needed
aws sso login --profile infiquetra-root
```

**Permission Issues:**
- Ensure the `infiquetra-root` profile has administrative access
- Check that you're deploying to the correct account (645166163764)

### Quick Health Check

```bash
# Test your setup before deployment
uv --version      # Should show uv version
cdk --version     # Should show 2.1029.1+
aws sts get-caller-identity --profile infiquetra-root  # Should show correct account
```

## Support

If you encounter issues with this bootstrap process, check:

1. AWS CloudTrail logs for authentication issues
2. GitHub Actions logs for role assumption problems
3. CloudFormation events for deployment failures