# LEARNINGS

> **Empirical findings + mechanisms + fixes + validations.** When something turns out to be true that wasn't obvious — about an AWS API behavior, a CDK quirk, a GitHub Actions gotcha, an SCP rejection, a deploy failure mechanism — it goes here. Include the **evidence** (workflow run ID / commit SHA / AWS error code / log excerpt) and the **mechanism** (why it's true), not just the observation.
>
> **Append new entries to the top.** Most-recent first. Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short descriptive title
>
> **Context.** One paragraph framing the situation (optional).
> **Evidence.** Specific workflow run ID / commit SHA / AWS error code / log excerpt / file:line.
> **Mechanism.** Why it happened — root cause, not just symptoms.
> **Impact.** What it cost — failed deploy, hours debugging, blast radius (optional).
> **Fix.** Concrete action + commit hash or PR #N, OR a QUEUED.md ref if deferred.
> **Validation.** What later run / test proved the fix (if applicable).
> **What surprised.** The thing that wasn't in the original mental model (optional).
> **Generalizable rule.** The lesson stripped of this specific incident — what would I tell a future-me hitting a similar shape?
> **Refs.** Cross-links to DECISIONS / QUEUED / narratives / other LEARNINGS entries (optional).
> ```
>
> Not every entry needs every subheader — small entries can be a paragraph. But the **Generalizable rule** is the highest-value field: without it, future-Claude has to re-derive the lesson from the evidence each time.
>
> If a prior learning is invalidated by new evidence, **update the entry inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**. Never silently overwrite history.
>
> For long-form companion docs (design walkthroughs, post-incident write-ups, inventory snapshots), see [`narratives/`](narratives/) and link to them from the relevant entry.

---

## 2026-04-27

### Amazon WorkSpaces leaves an orphaned Simple AD directory behind when WorkSpaces are deleted, and that directory bills $36/mo indefinitely

**Evidence:** Cost Explorer 90-day breakdown showed `AWS Directory Service` consuming $31–37/mo, dominating recurring spend (~80% of the steady-state $42/mo). `aws ds describe-directories --region us-east-1 --profile infiquetra-root` returned a single Simple AD instance: `d-90677865c8`, name `corp.amazonworkspaces.com`, type `SimpleAD`, size `Small`, `LaunchTime: 2020-05-25`, `SsoEnabled: false`. Cross-checked usage: `aws workspaces describe-workspaces` returned empty, `aws workspaces describe-workspace-directories` returned empty, `aws ec2 describe-instances --filters Name=vpc-id,Values=vpc-088fae61835b3a517` returned empty. The directory had been running unused for ~6 years, accumulating roughly $2,500 of waste.

**Mechanism:** Amazon WorkSpaces requires a directory for user authentication and provisions a Simple AD instance ($0.05/hr = $36/mo Small) when set up via the console wizard if no existing directory is selected. Deleting the WorkSpaces themselves does NOT cascade to the directory — they are independent AWS resources owned by separate services. The directory continues to bill at the hourly Simple AD rate regardless of whether anything is using it. The directory's name (`corp.amazonworkspaces.com`) is a permanent fingerprint of the WorkSpaces-driven creation path. The directory also creates and owns a VPC, 2 subnets in different AZs, an Internet Gateway, route tables, and security groups (`d-XXXXX_controllers`, `d-XXXXX_workspacesMembers`) — all of which become orphaned alongside it.

**Impact:** ~$432/year of pure waste. More importantly, hidden under a service name (Directory Service) that's easy to confuse with Route 53 DNS — neither is what most operators expect when they see "Directory Service" in their cost breakdown.

**Fix:** Deleted the directory via `aws ds delete-directory --directory-id d-90677865c8`. Wait for delete (~5–10 min). The 2 ENIs the directory owned auto-cleaned. The `_controllers` SG auto-deleted; the `_workspacesMembers` SG and the rest of the VPC infrastructure (1 SG, 2 subnets, 1 IGW, 1 non-main route table, the VPC itself) had to be manually torn down in dependency order. Total cleanup time: ~15 minutes once the directory finished deleting.

**Validation:** `aws ds describe-directories` now returns `DirectoryDescriptions: []`. `aws ec2 describe-vpcs --vpc-ids vpc-088fae61835b3a517` returns `InvalidVpcID.NotFound`. Next month's Cost Explorer should show the Directory Service line item drop to $0. April 2026 partial-month already includes ~$31 of spend that won't recur.

**Generalizable rule:** Three lessons:
1. **AWS service names are not always self-explanatory.** "Directory Service" sounds infrastructural; it's actually managed AD. "Route 53" is DNS. They're different bills with different owners.
2. **AWS service deletion rarely cascades.** WorkSpaces → Directory, RDS → snapshots, EC2 → EBS volumes, EC2 → EIPs — in each case the "child" resource keeps billing after the "parent" is gone. When deprovisioning anything, walk the resource graph manually with the relevant `describe-*` calls and clean up downstream artifacts.
3. **Ancient launch times are a tell.** Anything created during the early-experimentation phase of an AWS account (typically the first year) and still running with `SsoEnabled: false` / no recent updates is a high-value audit target. A 2-line cost-anomaly grep ("services with consistent monthly charge despite zero apparent usage") would catch this class of waste systematically.

---

## 2026-04-25

### `SERVICE_CONTROL_POLICY` must be enabled per organization root before SCPs can be created

**Evidence:** Workflow run [24933501603](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24933501603) failed with `AWS::Organizations::Policy | BaseSecuritySCP CREATE_FAILED — "This operation can be performed only for enabled policy types. (Service: Organizations, Status Code: 400, Request ID: 28b75945-824a-4412-af15-5c6e852e1deb)"`. `aws organizations list-roots` showed `PolicyTypes: []` for root `r-f3un`.

**Mechanism:** AWS Organizations supports several policy types (SCP, Tag Policy, Backup Policy, AI Services Opt-Out). Each type must be explicitly enabled per root via `organizations:EnablePolicyType` before any policy of that type can be created or attached. This is an imperative one-time AWS-side step that CDK / CloudFormation cannot manage — there is no `AWS::Organizations::PolicyType` resource.

**Impact:** Even after fixing the SCP document syntax (see prior Principal-field entry), the deploy still failed for a completely unrelated reason. Stack stuck in `ROLLBACK_COMPLETE` requiring manual delete before retry.

**Fix:** Out-of-band CLI: `aws organizations enable-policy-type --root-id r-f3un --policy-type SERVICE_CONTROL_POLICY`. Status transitions `PENDING_ENABLE` → `ENABLED` within seconds.

**Validation:** Workflow run [24933555533](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24933555533) deployed both stacks successfully (`InfiquetraOrganizationStack` + `InfiquetraSSOStack` both `CREATE_COMPLETE`).

**Generalizable rule:** AWS Organizations has imperative org-level configuration steps (policy-type enablement, AWS service trusted-access enablement, all-features mode) that are not represented in CFN/CDK. When introducing a new policy type or trusted service via IaC, check whether a one-time enablement step is required — if so, document it in the deployment runbook because future re-deploys into a fresh org will hit the same wall.

### AWS Service Control Policies forbid the `Principal` element

**Evidence:** Workflow run [24927809223](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24927809223) failed with `AWS::Organizations::Policy | BaseSecuritySCP CREATE_FAILED — "The provided policy document does not meet the requirements of the specified policy type. (Service: Organizations, Status Code: 400)"`. All four statements in `infiquetra_aws_infra/organization_stack.py` had `"Principal": {"AWS": "*"}` — three in `BaseSecurityPolicy`, one in `NonProductionCostControl`.

**Mechanism:** SCPs implicitly apply to every principal in the target accounts; you cannot scope them to a specific principal. AWS Organizations rejects any SCP document containing a `Principal` (or `NotPrincipal`) element. The validation error message does not name the offending element — it just says "doesn't meet requirements", which makes diagnosis non-obvious.

**Impact:** First production deploy after the modular CI/CD refactor failed at the AWS layer. Stack stuck in `ROLLBACK_COMPLETE`. Surfaced only because the prior workflow-startup and venv bugs were resolved enough for the deploy to actually call AWS.

**Fix (PR #7):** Stripped `Principal` from all four SCP statements. Added comments above each policy block explaining the rule.

**Validation:** Local `uv run cdk synth InfiquetraOrganizationStack` rendered both SCPs with zero `Principal` keys (verified by JSON parse of `cdk.out/InfiquetraOrganizationStack.template.json`). `cfn-lint` passed clean. Workflow run [24933555533](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24933555533) deployed without the rejection.

**Generalizable rule:** SCP and IAM identity-policy syntax look nearly identical (both use `Version`, `Statement`, `Effect`, `Action`, `Resource`, `Condition`) but have divergent allowed elements. SCPs forbid `Principal`/`NotPrincipal`; identity policies require `Principal` only when used as resource policies. Copy-pasting from IAM examples is the most likely failure mode. When writing any AWS policy document, look up the per-policy-type element reference, not just the IAM general reference.

### `cdk.json` `app: python3 app.py` runs system Python, not the uv venv

**Evidence:** Workflow run [24927158328](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24927158328) failed in the deploy step with `ModuleNotFoundError: No module named 'aws_cdk'` followed by `python3 app.py: Subprocess exited with error 1`. The reusable deployment workflow was calling bare `cdk deploy InfiquetraOrganizationStack`.

**Mechanism:** When you run `cdk deploy`, the CDK CLI reads `cdk.json` and shells out to whatever the `app` field literally says. Our `cdk.json` has `"app": "python3 app.py"` — that invokes the system `python3`, which has no `aws_cdk` package installed. The CI runner sets up uv and creates a `.venv/`, but `cdk deploy` doesn't activate it; it just calls `python3` from the system PATH.

**Impact:** Every deploy attempt failed at the very first `cdk deploy` invocation. Hidden by the prior workflow-startup bug — only surfaced once that was fixed.

**Fix (PR #5):** Wrapped the `cdk deploy` calls in `reusable-aws-deployment.yml` with `uv run`: `uv run cdk deploy InfiquetraOrganizationStack ...`. This is the same pattern already used by `reusable-cdk-synthesis.yml` (`uv run cdk synth`), so the fix matched existing convention.

**Validation:** Workflow run [24927642584](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24927642584) (the post-merge deploy) reached the CDK steps and `aws_cdk` imported successfully — failure shifted to the subsequent SCP `Principal` issue, confirming this layer was fixed.

**Generalizable rule:** The CDK CLI's `cdk.json:app` field is a literal subprocess command string, not a venv-aware invocation. In CI environments using uv (or any non-default Python interpreter), either (a) wrap `cdk` calls with `uv run` at the workflow boundary, or (b) change `cdk.json:app` to explicitly use the venv — but the workflow-boundary approach keeps `cdk.json` portable for local devs who already have the venv activated.

### Reusable workflow callers must declare ≥ permissions of their callees

**Evidence:** Workflow run [24920573693](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24920573693) ended with `startup_failure` after 1 second on the first push to main following PR #3. No jobs spawned. The reusable `reusable-aws-deployment.yml` declares `id-token: write` and `contents: write` on its `deploy` job, but the caller `deploy-infrastructure.yml` had no `permissions:` block at all.

**Mechanism:** GitHub Actions caps the permissions a reusable workflow can use at whatever the caller's `GITHUB_TOKEN` is granted. Permissions declared inside the reusable workflow are aspirational — they become real only if the caller has elevated its own token to ≥ that scope. Validation happens at workflow compilation time, before any container spins up, which is why the failure was instantaneous and produced no per-job logs.

**Impact:** Every push-to-main deploy died immediately. Hidden during the PR phase because the validation pipeline had its own (correct) permissions block — only the deploy workflow was bare.

**Fix (PR #4):** Added `permissions: contents: read` at the top level of `deploy-infrastructure.yml` (least-privilege baseline for `post-deployment`) and `permissions: { id-token: write, contents: write }` at the `deploy:` job level (Option B, matching the pattern already used in `pull-request-validation.yml`).

**Validation:** Subsequent run [24927158328](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24927158328) progressed past startup, completed AWS OIDC auth, and ran into a different (CDK-side) bug — confirming this layer was fixed.

**Generalizable rule:** When introducing a reusable workflow, audit every caller for matching permissions. The rule of thumb: declare a least-privilege baseline at the caller's top level (typically `contents: read`), then elevate per-job for the specific jobs that call permission-needing reusable workflows. The reusable workflow itself should still declare its needs internally for documentation, but those declarations are not enforcement — the caller's token is.

---
