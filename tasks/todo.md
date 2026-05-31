# Project: CAMPPS Staging Deployment & Cost Estimation (Automated)
Date: 2026-05-30
Checkpoint: 2026-05-30-21-50

## Overview
Perform actual cost analysis across all accounts using live Cost Explorer data, establish a baseline for the `campps-staging` account, and execute a fully automated roadmap to configure user SSO access and bootstrap the staging deploy roles.

## Phase: Research & Planning
- [x] Query actual monthly costs by account for April 2026
- [x] Query service breakdown for Management account to identify recurring spending
- [x] Analyze CDK bootstrap stacks for CAMPPS staging deploy roles
- [x] [CHECKPOINT] Write comprehensive Staging & Cost plan and seek user feedback

## Phase: Programmatic SSO Assignment [SEQ]
- [x] [SEQ] Run `aws sso-admin create-account-assignment` using `infiquetra-root` profile to assign your user to `campps-staging` (`050922968859`)
- [x] [SEQ] Prompt SSO browser authentication (`aws sso login`) to fetch a fresh OIDC token containing staging metadata
- [x] [SEQ] Execute `~/bin/get_campps_aws_creds.sh` to sync the new `campps-staging` profile credentials
- [x] [SEQ] Verify active CLI access via `aws sts get-caller-identity --profile campps-staging`

## Phase: Bootstrap & Deployment [SEQ]
- [x] [SEQ] Run CDK bootstrap `cdk bootstrap aws://050922968859/us-east-1` using `campps-staging` profile
- [x] [SEQ] Deploy `CamppsStagingDeployRolesStack` into the Staging account using `campps-staging` profile
- [x] [SEQ] Confirm IAM OIDC role and trust policies are successfully provisioned

## Phase: Review & Finalization
- [x] Document final walkthrough
