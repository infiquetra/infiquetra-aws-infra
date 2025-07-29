# Infiquetra Organizations Infrastructure

AWS Organizations and SSO infrastructure as code for Infiquetra LLC business structure using AWS CDK.

[![Validate CDK](https://github.com/namredips/infiquetra-organizations/actions/workflows/validate.yml/badge.svg)](https://github.com/namredips/infiquetra-organizations/actions/workflows/validate.yml)
[![Security Scan](https://github.com/namredips/infiquetra-organizations/actions/workflows/security-scan.yml/badge.svg)](https://github.com/namredips/infiquetra-organizations/actions/workflows/security-scan.yml)

## Overview

This repository contains the AWS CDK infrastructure code to manage the AWS Organizations structure for Infiquetra LLC and its subsidiary business units:

```
Infiquetra, LLC (Holding Company)
├── Infiquetra Media, LLC       (Online content, branding, media)
├── Infiquetra Apps, LLC        (Software product development)
└── Infiquetra Consulting, LLC  (Contracting & consulting services)
```

## Architecture

### AWS Organizations Structure

```
Root (645166163764 - infiquetra)
├── Core OU (Security, Logging, Shared Services)
├── Media OU (Infiquetra Media, LLC)
├── Apps OU (Infiquetra Apps, LLC)
│   └── CAMPPS (Migrated CAMPPS accounts)
│       ├── Production
│       └── NonProd
└── Consulting OU (Infiquetra Consulting, LLC)
```

### AWS SSO Permission Sets

| Permission Set | Purpose | Session Duration | Business Unit |
|----------------|---------|------------------|---------------|
| CoreAdministrator | Full access for core infrastructure | 4 hours | Core |
| SecurityAuditor | Security auditing and compliance | 8 hours | Core |
| BillingManager | Billing and cost management | 12 hours | Core |
| MediaDeveloper | Development access for media workloads | 8 hours | Media |
| MediaAdministrator | Full access for media resources | 4 hours | Media |
| AppsDeveloper | Development access for software products | 8 hours | Apps |
| AppsAdministrator | Full access for apps resources | 4 hours | Apps |
| CamppssDeveloper | Specific access for CAMPPS workloads | 8 hours | Apps |
| ConsultingDeveloper | Development access for consulting projects | 8 hours | Consulting |
| ConsultingAdministrator | Full access for consulting resources | 4 hours | Consulting |
| ReadOnlyAccess | Read-only access for contractors | 4 hours | Any |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+ (for CDK CLI)
- AWS CLI configured with `infiquetra-root` profile
- AWS SSO access to the management account

### Installation

1. Clone the repository:
```bash
git clone https://github.com/namredips/infiquetra-organizations.git
cd infiquetra-organizations
```

2. Set up the Python environment:
```bash
uv sync
source .venv/bin/activate
```

3. Install CDK CLI:
```bash
npm install -g aws-cdk
```

### Deployment

1. Configure your AWS profile:
```bash
aws sso login --profile infiquetra-root
```

2. Bootstrap CDK (if not already done):
```bash
cdk bootstrap --profile infiquetra-root
```

3. Deploy the organization structure:
```bash
cdk deploy InfiquetraOrganizationStack --profile infiquetra-root
```

4. Deploy the SSO configuration:
```bash
cdk deploy InfiquetraSSOStack --profile infiquetra-root
```

## Project Structure

```
├── .claude/                           # Claude Code configuration and plans
│   ├── plans/                         # Implementation plans and documentation
│   └── audit-current-state.md         # Current AWS organization audit
├── .github/workflows/                 # GitHub Actions CI/CD pipelines
│   ├── validate.yml                   # Code validation and linting
│   ├── deploy.yml                     # Automated deployment
│   ├── security-scan.yml              # Security scanning
│   └── cost-estimate.yml              # Cost impact analysis
├── infiquetra_organizations/          # CDK stack implementations
│   ├── organization_stack.py          # AWS Organizations structure
│   └── sso_stack.py                   # AWS SSO permission sets
├── app.py                             # CDK application entry point
├── requirements.txt                   # Python dependencies
├── requirements-dev.txt               # Development dependencies
```

## Migration from Current State

### Current CAMPPS Structure
The existing CAMPPS accounts are currently organized as:
- `campps-cicd` (424272146308) - **SUSPENDED** - needs resolution
- `campps-prod` (431643435299) - In CAMPPS/workloads/PRODUCTION
- `campps-dev` (477152411873) - In CAMPPS/workloads/SDLC

### Migration Plan
1. **Resolve Suspended Account**: Address the suspended `campps-cicd` account
2. **Deploy New Structure**: Create the new business unit OUs
3. **Move Accounts**: Migrate CAMPPS accounts to the new Apps/CAMPPS OU structure
4. **Clean Up**: Remove old OU structure after successful migration

## Security Features

### Service Control Policies (SCPs)
- **Base Security Policy**: Applied to all business units
  - Denies root user actions
  - Prevents deletion of logging resources
  - Requires MFA for sensitive actions
- **NonProduction Cost Control**: Restricts expensive instance types in non-prod environments

### Branch Protection
- Requires pull request reviews
- Requires status checks to pass
- Enforces administrator restrictions
- Dismisses stale reviews automatically

## CI/CD Workflows

### Validation Pipeline (`validate.yml`)
- Python linting with flake8
- Code formatting with black
- Import sorting with isort
- Security scanning with bandit
- CDK synthesis validation
- CloudFormation template linting

### Deployment Pipeline (`deploy.yml`)
- Automated deployment on main branch
- Manual deployment with stack selection
- AWS credentials via OIDC
- Deployment summaries and notifications

### Security Scanning (`security-scan.yml`)
- Daily automated security scans
- Multiple security tools (Bandit, Semgrep, Checkov)
- CloudFormation security best practices
- Artifact upload for detailed reports

### Cost Estimation (`cost-estimate.yml`)
- Cost impact analysis on PRs
- Infrastructure change summaries
- Cost monitoring recommendations
- Automated PR comments with estimates

## Development Workflow

1. Create a feature branch from `main`
2. Make your changes to the CDK stacks
3. Run local validation:
   ```bash
   source .venv/bin/activate
   black .
   flake8 .
   cdk synth
   ```
4. Create a pull request
5. Review cost estimates and security scans
6. Merge after approval and passing checks
7. Automatic deployment to AWS

## Monitoring and Compliance

### Cost Management
- Business unit cost allocation via OU tags
- Cost budgets per organizational unit
- Cost anomaly detection recommendations
- Regular cost reviews and optimization

### Security Monitoring
- Centralized CloudTrail logging
- AWS Config compliance rules
- GuardDuty threat detection
- Regular security audits

## Troubleshooting

### Common Issues

**CDK Synthesis Fails**
```bash
# Check your AWS credentials
aws sts get-caller-identity --profile infiquetra-root

# Ensure dependencies are installed
pip install -r requirements.txt
```

**Permission Denied Errors**
- Ensure you're using the correct AWS profile
- Verify SSO session is active
- Check IAM permissions for organizations and SSO operations

**CAMPPS Account Migration**
- Resolve the suspended `campps-cicd` account first
- Plan migration during maintenance windows
- Test access patterns after migration

## Contributing

1. Follow the development workflow above
2. Ensure all tests and security scans pass
3. Update documentation for any architectural changes
4. Follow the principle of least privilege for new permission sets

## Support

For questions or issues:
- Check the [audit documentation](.claude/audit-current-state.md)
- Review [implementation plans](.claude/plans/)
- Create an issue in this repository

## License

This infrastructure code is proprietary to Infiquetra LLC.