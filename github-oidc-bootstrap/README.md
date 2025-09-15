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
- [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) installed (`npm install -g aws-cdk`)
- AWS credentials configured with administrative access
- Python 3.11+ installed

## Quick Start

### 1. Clone and Navigate

```bash
cd github-oidc-bootstrap
```

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your account details
export CDK_DEFAULT_ACCOUNT=your-account-id
export CDK_DEFAULT_REGION=us-east-1
```

### 3. Install Dependencies

```bash
# Using modern uv package manager
make install

# Or manually with uv
uv sync --dev
```

### 4. Quality Checks

```bash
# Run all quality checks (tests, linting, security)
make check
```

### 5. Deploy Stack

```bash
# Synthesize and validate templates
make synth validate

# Deploy with confirmation
make deploy
```

## Modern Development Workflow

This project uses modern Python tooling:

- **uv**: Fast Python package manager and dependency resolver
- **ruff**: Lightning-fast linter and formatter
- **mypy**: Static type checking
- **pytest**: Comprehensive testing framework
- **bandit**: Security vulnerability scanner
- **cfn-lint**: CloudFormation template validation

### 6. Retrieve the Role ARN

After successful deployment, the stack will output the IAM role ARN. You can also retrieve it with:

```bash
aws cloudformation describe-stacks \
  --stack-name GitHubOIDCBootstrap \
  --profile infiquetra-root \
  --query 'Stacks[0].Outputs[?OutputKey==`GitHubActionsRoleArn`].OutputValue' \
  --output text
```

## Setting up GitHub Repository

### 1. Add the Role ARN as a Repository Secret

Navigate to your GitHub repository settings and add a new repository secret:

- **Name**: `AWS_DEPLOY_ROLE_ARN`
- **Value**: The role ARN from the stack output (format: `arn:aws:iam::645166163764:role/GitHubActionsDeployRole`)

### 2. Update Your Workflow

The main deployment workflow (`.github/workflows/deploy.yml`) should be updated to use OIDC authentication instead of hardcoded credentials.

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

1. **Profile not found**: Ensure the `infiquetra-root` AWS profile is configured
2. **Insufficient permissions**: The deployment profile needs administrative access
3. **Region mismatch**: This stack deploys to `us-east-1` by default

### Verification

To verify the OIDC provider was created correctly:

```bash
aws iam list-open-id-connect-providers --profile infiquetra-root
```

To verify the role exists:

```bash
aws iam get-role --role-name GitHubActionsDeployRole --profile infiquetra-root
```

## Cleanup

To remove the bootstrap resources:

```bash
cdk destroy --profile infiquetra-root
```

**⚠️ Warning**: Only destroy this stack if you no longer need GitHub Actions to deploy to your AWS account.

## Next Steps

After deploying this bootstrap stack:

1. Update the main repository's deployment workflow to use OIDC
2. Remove any hardcoded AWS credentials from GitHub secrets
3. Test the deployment pipeline with a test branch or pull request

## Support

If you encounter issues with this bootstrap process, check:

1. AWS CloudTrail logs for authentication issues
2. GitHub Actions logs for role assumption problems
3. CloudFormation events for deployment failures