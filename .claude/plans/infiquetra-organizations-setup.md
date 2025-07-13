# Comprehensive Infiquetra AWS Organizations & GitHub Setup Plan

**Date:** July 13, 2025  
**Status:** In Progress  
**Project:** infiquetra-organizations

## Current State Analysis
✅ GitHub account validated (`namredips` with access to `emccode` org)  
✅ AWS CLI with `infiquetra-root` profile available  
✅ Python3 and required tools installed  
✅ CAMPPS AWS profiles exist for migration planning  
❌ Virtual environment not yet set up  
❌ Current AWS org structure needs auditing  
❌ GitHub repository and CI/CD not created  

## Target Business Structure
```
Infiquetra, LLC (Holding Company)
├── Infiquetra Media, LLC       (Online content, branding, media)
├── Infiquetra Apps, LLC        (Software product development)
└── Infiquetra Consulting, LLC  (Contracting & consulting services)
```

## Target AWS Organization Structure
```
Infiquetra, LLC (Root/Management Account)
├── Core OU (Security, Logging, Shared Services)
├── Media OU → Infiquetra Media, LLC accounts
├── Apps OU → Infiquetra Apps, LLC + existing CAMPPS accounts
└── Consulting OU → Infiquetra Consulting, LLC accounts
```

## Phase 1: Environment & Repository Setup
1. **Python Virtual Environment**
   - Run `./setup-env.sh` to create `.env` virtual environment
   - Install CDK dependencies and development tools
   - Activate environment for development

2. **GitHub Repository Creation**
   - Create `infiquetra-organizations` repository under `namredips`
   - Initialize git, set up remote, push initial structure
   - Configure branch protection rules

3. **GitHub Actions CI/CD Setup**
   - Create `.github/workflows/` directory structure
   - **CDK Validation Workflow**: Lint, typecheck, and validate CDK code
   - **CDK Deploy Workflow**: Deploy to AWS on main branch
   - **Security Scanning**: Run security scans on CDK templates
   - **Cost Estimation**: Generate cost estimates for infrastructure changes

## Phase 2: AWS Current State Audit
1. **Organization Structure Discovery**
   - Audit current accounts with `aws organizations list-accounts`
   - Map existing OUs with `aws organizations list-organizational-units`
   - Document CAMPPS account placement and dependencies

2. **SSO Configuration Analysis**
   - Audit SSO instances and permission sets
   - Document current user/group assignments
   - Identify access patterns for new business units

## Phase 3: CDK Implementation
1. **Core Infrastructure Stacks**
   - `OrganizationStack`: OU structure, SCPs, account factory
   - `SSOStack`: Identity management and permission sets
   - Account baseline configurations

2. **Migration Strategy**
   - Plan for existing CAMPPS accounts under Apps OU
   - Ensure minimal disruption during reorganization
   - Maintain existing access patterns during transition

## Phase 4: CI/CD Workflows
1. **Validation Pipeline**
   - Python linting (flake8, black)
   - CDK synthesis and validation
   - CloudFormation template security scanning
   - Cost impact analysis

2. **Deployment Pipeline**
   - Automated deployment on main branch
   - Environment-specific configurations
   - Rollback capabilities
   - Notification integrations

## Phase 5: Security & Governance
1. **Service Control Policies per OU**
   - Prevent privilege escalation
   - Cost control and resource restrictions
   - Compliance enforcement

2. **Cross-Account Access & Monitoring**
   - Define IAM roles for each business unit
   - Set up centralized logging and monitoring
   - Implement break-glass access procedures

## Key Considerations
- Work around existing CAMPPS accounts without disruption
- Ensure minimal downtime during reorganization
- Maintain security best practices throughout
- Plan for future business unit expansion
- Implement comprehensive monitoring and compliance

## Success Criteria
- All business units have dedicated OUs with appropriate governance
- SSO configured with proper permission sets per business unit
- CI/CD pipeline enables safe infrastructure changes
- Existing CAMPPS accounts successfully migrated to Apps OU
- Centralized security and compliance monitoring in place

## Risk Mitigation
- Test all changes in non-production environments first
- Maintain rollback procedures for all deployments
- Document all changes and maintain change logs
- Regular security reviews and compliance audits