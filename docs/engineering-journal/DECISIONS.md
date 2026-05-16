# DECISIONS

> **ADR-style records of architectural / pipeline-design / process choices.** When you commit a chosen path over alternatives — pick A over B, flip a flag, change a permission scope, add or remove a workflow stage — capture rationale + tradeoff + revisit-when condition + commit hash.
>
> The point is to make **revisit conditions explicit** so a future Claude (or human) reading "why did we pick X?" gets the answer cold, including when it would be right to reconsider.
>
> **Append new entries to the top.** Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short title
>
> **Decision.** What we picked + why it wins.
> **Rejected alternatives.**
> - Alternative A: pros/cons
> - Alternative B: pros/cons
> - Why rejected or deferred
> **Implementation.** Commits, phases, code locations (optional).
> **Revisit when.** Specific conditions under which this decision flips.
> **Commit.** PR #N / SHA.
> ```
>
> When new evidence invalidates a decision, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**.

---

## 2026-05-16

### Rename the CAMPPS nonprod account nickname from `campps-dev` to `campps-nonprod`

**Decision.** Rename the workload account nickname from `campps-dev` to `campps-nonprod` everywhere it appears as a human-facing name or local identifier: the AWS Organizations account Name, the IAM account alias (`camppsdev` → `camppsnonprod`, sign-in URL follows), the CDK constant `CAMPPS_DEV_ACCOUNT_ID` → `CAMPPS_NONPROD_ACCOUNT_ID`, CLI profile examples, and the ops/onboarding docs and diagrams. Account ID `477152411873` is unchanged. The account already lives in `Apps / CAMPPS / NonProd`, so this aligns the nickname with the environment it actually represents.

**Rationale.** The account was originally nicknamed `campps-dev` but functions as the shared nonprod environment (it is the OIDC target for the `nonprod` GitHub environment and the `Apps/CAMPPS/NonProd` OU). The `dev` nickname created a split between the account's name and its `nonprod` environment label, which was a recurring source of confusion in deploy docs and the GitHub-environment-to-account mapping. Renaming removes that split.

**Rejected alternatives.**
- Leave the nickname as `campps-dev`: zero churn, but perpetuates the name/environment mismatch and keeps every doc and diagram having to explain that `campps-dev` is really nonprod.
- Rename the CDK construct/logical ID `CamppsDevelopersDevAssignment` and the `CamppsDevelopers` SSO group too: superficially consistent, but renaming the logical ID would force a replacement of the live SSO assignment, and `CamppsDevelopers` names the human group (developers, the people), not the environment. Both were deliberately left as-is.

**Impact.** Naming only, zero functional impact. No change to the account ID, any ARN, OIDC trust policy, deploy-role name, permission set, SSO assignment, or CloudFormation logical ID. `cdk synth CamppsNonProdDeployRolesStack` produces no template change. The CDK constant rename is a pure source-symbol rename (same string value `"477152411873"`).

**Revisit when.** Reconsider the nickname if a dedicated developer-iteration account is ever split out from shared nonprod, at which point `campps-dev` could be reintroduced for that distinct account.

**Commit.** This PR (`chore/rename-campps-dev-to-campps-nonprod`).

## 2026-05-15

### Create CAMPPS staging as a separate CDK-managed AWS account

**Decision.** Create `campps-staging` as its own AWS account under `Apps / CAMPPS / Staging`, managed by CDK from creation forward. This keeps staging blast radius, billing, SCP inheritance, and GitHub environment trust separate from both `campps-dev` and `campps-prod`.

**Rejected alternatives.**
- Reuse `campps-dev` for staging: fastest path, but it blends developer iteration with release rehearsals and makes promotion failures harder to isolate.
- Create a staging OU now but delay account creation: preserves the tree shape, but leaves service workflows and SSO assignments with another placeholder to revisit.
- Put staging inside `NonProd`: simpler SCP attachment, but it hides staging's promotion role and makes GitHub environment mapping less explicit.

**Implementation.** `OrganizationStack` creates the staging OU and `campps-staging` account target. `SSOStack` grants CAMPPS developers access to the staging account. Deploy-role generation adds staging as a first-class environment after the account ID is available.

**Revisit when.** Reconsider a separate staging account if CAMPPS stays single-service and low-risk long enough that account overhead materially exceeds the isolation value, or if AWS Organizations account quota/cost governance makes another account operationally expensive.

**Commit.** Implementation commits `cde7a7f`, `d8ce8c7`, `bda2f8d`, `2787a8b`, and `97cb51a`.

## 2026-05-06

### Use SSO for human CAMPPS access and per-repository OIDC roles for service deployments

**Decision.** Use AWS Identity Center group assignments for human access and registry-generated GitHub OIDC deploy roles for CAMPPS service repositories. Local development can deploy to `campps-dev` through the `CAMPPSDeveloper` permission set, while normal CI/CD deployments use per-service roles in `campps-dev` and `campps-prod` with trust scoped to the exact GitHub repository and environment.

**Rejected alternatives.** 
- Reuse `infiquetra-aws-infra-gha-role` for service repositories: fastest path, but it gives application repos a management-account role that can affect Organizations, SSO, IAM, and foundation stacks.
- Use one org-wide CAMPPS write deploy role: avoids IAM changes when adding repos, but creates lateral movement risk because any trusted repo could deploy with the same write permissions.
- Keep production deployments local-only until the app matures: simple for one developer, but delays auditability, environment protection, and release-flow testing until the riskiest stage.

**Implementation.** `infiquetra_aws_infra/sso_stack.py` defines optional Identity Center group assignments. `github-oidc-bootstrap/github_oidc_bootstrap/github_oidc_stack.py` tightens the management OIDC role to this repo's `main` branch. `infiquetra_aws_infra/campps_service_registry.py`, `infiquetra_aws_infra/campps_deploy_roles_stack.py`, and `app_campps_bootstrap.py` define the workload-account deploy-role target.

**Revisit when.** Reconsider the per-repo registry if CAMPPS has enough repositories that adding a service to this foundation repo becomes a material delivery bottleneck. At that point, prefer automating registry updates or moving the registry to a dedicated CAMPPS bootstrap repo before broadening write-role trust.

**Commit.** Pending — foundation target implemented locally, not yet deployed.

## 2026-04-25

### Create new `Apps>CAMPPS>{Production,NonProd}` OUs alongside existing top-level CAMPPS — additive, not migrative

**Decision:** Let CDK create the new nested CAMPPS scaffolding under `Apps OU` while leaving the pre-existing top-level CAMPPS OU (`ou-f3un-s13dqexp`, with its `workloads/PRODUCTION`, `workloads/SDLC`, and empty `CICD` sub-OUs) untouched. Two CAMPPS OUs coexist temporarily.

**Rejected alternatives:**
- *Import the existing CAMPPS OU into CDK*: would have required a CDK custom resource or CFN import workflow; existing OU has hand-built sub-tree that doesn't match the CDK-target shape; high risk of CFN trying to delete/recreate the live structure containing real accounts.
- *Pre-migrate accounts before deploying CDK*: would have required moving `campps-prod` and `campps-dev` to root, deleting the old CAMPPS, then deploying. Deploy failure would have left accounts orphaned at root.
- *Picked: deploy new structure alongside, migrate accounts as a separate deliberate step*: CDK deploy is reversible (just `cdk destroy` the new OUs if they're empty); account migration is an explicit `move-account` API call per account when ready; least risky.

**Implementation:** No code change required — `infiquetra_aws_infra/organization_stack.py` already creates the new OUs at distinct CDK addresses. The decision is procedural, not in code.

**Revisit when:** SSO permission-set rollout is ready to attach to the new OUs and we want one source of truth in CDK. At that point, run the account-migration step (queued in QUEUED.md as P1) and `delete-organizational-unit` the old top-level CAMPPS once empty.

**Executed 2026-05-02:** Trigger fired — both workload accounts migrated into the CDK-managed tree, all 6 legacy OUs deleted. The dual-CAMPPS situation is over. See [`ARCHIVE.md`](ARCHIVE.md) 2026-05-02 entry.

**Commit:** Procedural — see workflow_dispatch run [24933555533](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24933555533) for the deploy that established this state.

### Disable `push: branches: [main]` trigger temporarily during multi-step deploy debug (re-enabled after stabilization)

**Decision:** When a deploy is broken at the AWS layer in a way that requires multiple iterative fixes, defensively cut the auto-trigger so each commit-to-fix doesn't queue another doomed run. Restore once the pipeline is proven end-to-end.

**Rejected alternatives:**
- *Leave auto-deploy on*: every fix-commit triggers a real deploy attempt. Noisy, generates failed-run alerts, leaves CFN stacks repeatedly stuck in `ROLLBACK_COMPLETE` requiring manual cleanup.
- *Use `[skip ci]` in commit messages*: per-commit discipline; easy to forget; doesn't apply to merge commits from squash-merge.
- *Add a `paths-ignore: ['**']` guard*: hacky, hides the disable in non-obvious config.
- *Picked: comment out the `push:` trigger with an inline note explaining why and how to restore*: explicit, version-controlled, easy to revert in a single PR.

**Implementation:** PR #6 commented out `push:` and added a comment block with the exact YAML to restore. PR #8 reverted by uncommenting.

**Revisit when:** A future multi-step debug session lasts long enough that the disable-then-restore overhead exceeds the noise cost. At that point, consider a more permanent guard like a manual gate on production deploys.

**Commit:** PR [#6](https://github.com/infiquetra/infiquetra-aws-infra/pull/6) (disable), PR [#8](https://github.com/infiquetra/infiquetra-aws-infra/pull/8) (re-enable).

### Wrap `cdk deploy` with `uv run` at workflow call sites rather than editing `cdk.json`

**Decision:** Change the workflow scripts in `reusable-aws-deployment.yml` to invoke `uv run cdk deploy ...` instead of bare `cdk deploy ...`. Leave `cdk.json:app = "python3 app.py"` alone.

**Rejected alternatives:**
- *Edit `cdk.json` to `app: "uv run python3 app.py"`*: one-line root-cause fix; applies to all CDK invocations everywhere; helps local devs who forget to `source .venv/bin/activate`. Downside: forces uv as a runtime dependency for any CDK invocation against this repo, including for potential future contributors using plain `pip`/`venv`. Also creates a recursive `uv run` if the caller already wrapped (idempotent in practice, but odd).
- *Activate the venv in the workflow before calling cdk*: extra step, more imperative, deviates from the existing `uv run cdk synth` pattern.
- *Picked: workflow-boundary `uv run` wrapping*: matches `reusable-cdk-synthesis.yml`'s existing pattern, keeps `cdk.json` simple and tool-agnostic, makes the venv contract explicit at the CI boundary where the runner is set up.

**Implementation:** PR #5 changed two call sites in `reusable-aws-deployment.yml` (Organization Stack deploy + SSO Stack deploy). No `cdk.json` change.

**Revisit when:** A third call site is added without remembering the wrapping, or local devs hit the same bug enough to justify the cdk.json change.

**Commit:** PR [#5](https://github.com/infiquetra/infiquetra-aws-infra/pull/5).

### Per-job permissions over top-level (Option B) for `deploy-infrastructure.yml`

**Decision:** Set top-level `permissions: contents: read` (least-privilege baseline) and elevate only the `deploy:` job to `{ id-token: write, contents: write }` for OIDC + git tag push. Leave `post-deployment:` at the top-level baseline.

**Rejected alternatives:**
- *Option A — top-level only with broad perms*: 2 lines instead of 6, all jobs get the elevated token. Simpler. Downside: `post-deployment` doesn't need write access; broader blast radius if any step is compromised.
- *Option B — per-job least-privilege*: 6 lines, defense-in-depth. Matches the precedent set by `pull-request-validation.yml` (which already uses per-job permissions for `code-quality`, `security-scan`, `cdk-synthesis`, `validation-summary`).
- *Picked: Option B*: consistency with existing pattern outweighs the small verbosity cost.

**Implementation:** PR #4 added the two `permissions:` blocks to `deploy-infrastructure.yml`.

**Revisit when:** A new job is added to `deploy-infrastructure.yml` and the per-job pattern becomes painful, OR `pull-request-validation.yml` flips to top-level-only (in which case match for consistency).

**Commit:** PR [#4](https://github.com/infiquetra/infiquetra-aws-infra/pull/4).

---
