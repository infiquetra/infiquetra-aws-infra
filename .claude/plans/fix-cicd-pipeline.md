# Fix CI/CD Pipeline Plan

**Date**: 2025-10-05
**Status**: In Progress

## 📊 Current State Analysis

### Working Components
- ✅ **OIDC Setup**: The GitHub OIDC provider exists at `arn:aws:iam::645166163764:oidc-provider/token.actions.githubusercontent.com`
- ✅ **IAM Role**: The role `infiquetra-aws-infra-gha-role` is deployed and configured
- ✅ **Repository Configuration**: `AWS_DEPLOY_ROLE_ARN` exists as both a repository variable and secret
- ✅ **AWS Access**: Local AWS SSO authentication working with `infiquetra-root` profile

### Identified Issues
1. ❌ **Issue #1**: CD workflow references `${{ vars.AWS_DEPLOY_ROLE_ARN }}` but should use `${{ secrets.AWS_DEPLOY_ROLE_ARN }}`
2. ❌ **Issue #2**: Git tag push fails with permission denied for `github-actions[bot]`
3. ❌ **Issue #3**: Duplicate configuration - role ARN exists as both secret and variable

## 🎯 Tasks to Complete

### Task 1: Fix GitHub Actions Authentication Configuration
- [ ] **File**: `.github/workflows/cd.yml`
- [ ] **Changes**:
  - Line 77: Change `${{ vars.AWS_DEPLOY_ROLE_ARN }}` to `${{ secrets.AWS_DEPLOY_ROLE_ARN }}`
  - Line 85: Change `${{ vars.AWS_DEPLOY_ROLE_ARN }}` to `${{ secrets.AWS_DEPLOY_ROLE_ARN }}`
- [ ] **Reason**: The role ARN is stored as a secret, not a variable

### Task 2: Fix Git Tag Push Permissions
- [ ] **File**: `.github/workflows/cd.yml`
- [ ] **Line**: 111
- [ ] **Current**: `git push origin "$TAG_NAME"`
- [ ] **New**: `git push https://x-access-token:${{ github.token }}@github.com/${{ github.repository }} "$TAG_NAME"`
- [ ] **Alternative Option**: Use the checkout action with persist-credentials
- [ ] **Reason**: Explicit token authentication needed for tag creation

### Task 3: Clean Up Duplicate Configuration
- [ ] Remove the repository variable `AWS_DEPLOY_ROLE_ARN` (keep only the secret)
- [ ] Via GitHub UI: Settings → Secrets and variables → Actions → Variables → Delete

### Task 4: Test the Pipeline
- [ ] Create a test commit to trigger the CD pipeline
- [ ] Verify OIDC authentication succeeds
- [ ] Verify CDK stacks deploy (or at least synthesize)
- [ ] Verify git tag is created and pushed
- [ ] Check the GitHub Actions summary for any warnings

### Task 5: Optional Improvements
- [ ] Add CDK bootstrap check before deployment
- [ ] Add deployment drift detection
- [ ] Configure Slack/email notifications for deployment status

## 📝 Implementation Details

### Modified cd.yml Sections

#### Authentication Fix (around line 77-85):
```yaml
    - name: 🔍 Debug Role ARN
      run: |
        echo "Role ARN to assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}"  # Changed from vars
        echo "Repository: ${{ github.repository }}"
        echo "Ref: ${{ github.ref }}"
        echo "Actor: ${{ github.actor }}"

    - name: 🔐 Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v5
      with:
        role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}  # Changed from vars
        role-session-name: GitHubActions-${{ github.run_id }}-${{ github.run_attempt }}
        aws-region: us-east-1
```

#### Git Tag Fix (around line 103-112):
```yaml
    - name: 🏷️ Create deployment tag
      if: success()
      run: |
        TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
        TAG_NAME="deploy-${TIMESTAMP}-${{ github.sha }}"
        git config user.name "github-actions[bot]"
        git config user.email "github-actions[bot]@users.noreply.github.com"
        git tag -a "$TAG_NAME" -m "Deployment on ${TIMESTAMP} - ${{ github.event.inputs.stack || 'all' }} stack(s)"
        git push https://x-access-token:${{ github.token }}@github.com/${{ github.repository }} "$TAG_NAME"
        echo "🏷️ **Created deployment tag**: \`$TAG_NAME\`" >> $GITHUB_STEP_SUMMARY
```

## 🔍 Verification Commands

```bash
# Check OIDC provider
aws iam list-open-id-connect-providers --profile infiquetra-root

# Check IAM role
aws iam get-role --role-name infiquetra-aws-infra-gha-role --profile infiquetra-root

# Check GitHub secrets
gh secret list --repo infiquetra/infiquetra-aws-infra

# Check GitHub variables
gh variable list --repo infiquetra/infiquetra-aws-infra

# Check recent workflow runs
gh run list --repo infiquetra/infiquetra-aws-infra --limit 5

# View failed run logs
gh run view <RUN_ID> --repo infiquetra/infiquetra-aws-infra --log-failed
```

## 📊 Success Criteria

1. CD pipeline runs successfully on push to main
2. OIDC authentication works (no credential errors)
3. CDK stacks deploy or synthesize without errors
4. Git tags are created and visible in the repository
5. No duplicate configuration warnings
6. GitHub Actions summary shows all green checks

## 🚨 Rollback Plan

If changes cause issues:
1. Revert the cd.yml changes via git
2. Keep using manual deployments with `cdk deploy --profile infiquetra-root`
3. Investigate CloudTrail logs for authentication issues

## 📝 Notes

- The most recent successful run was commit `24ee0ab` which removed CDK bootstrap
- The failure started with commit `a858a54` when trying to refactor OIDC bootstrap
- The OIDC provider and role are confirmed to exist and be properly configured
- The issue is primarily configuration references in the workflow files

## Next Steps After Fix

Once the CI/CD pipeline is working:
1. Review and potentially migrate the suspended CAMPPS accounts
2. Implement the AWS Organizations structure as designed
3. Configure SSO permission sets for the team
4. Set up cost allocation tags and budgets