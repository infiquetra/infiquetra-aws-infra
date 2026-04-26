# DECISIONS

Architecture decisions, ADR-style. Most recent first.

See [README.md](README.md) for entry format.

---

## 2026-04-25

### Create new `Apps>CAMPPS>{Production,NonProd}` OUs alongside existing top-level CAMPPS — additive, not migrative

**Picked:** Let CDK create the new nested CAMPPS scaffolding under `Apps OU` while leaving the pre-existing top-level CAMPPS OU (`ou-f3un-s13dqexp`, with its `workloads/PRODUCTION`, `workloads/SDLC`, and empty `CICD` sub-OUs) untouched. Two CAMPPS OUs coexist temporarily.

**Tradeoffs considered:**
- *Import the existing CAMPPS OU into CDK*: would have required a CDK custom resource or CFN import workflow; existing OU has hand-built sub-tree that doesn't match the CDK-target shape; high risk of CFN trying to delete/recreate the live structure containing real accounts.
- *Pre-migrate accounts before deploying CDK*: would have required moving `campps-prod` and `campps-dev` to root, deleting the old CAMPPS, then deploying. Deploy failure would have left accounts orphaned at root.
- *Picked: deploy new structure alongside, migrate accounts as a separate deliberate step*: CDK deploy is reversible (just `cdk destroy` the new OUs if they're empty); account migration is an explicit `move-account` API call per account when ready; least risky.

**Implementation:** No code change required — `infiquetra_aws_infra/organization_stack.py` already creates the new OUs at distinct CDK addresses. The decision is procedural, not in code.

**Revisit if:** SSO permission-set rollout is ready to attach to the new OUs and we want one source of truth in CDK. At that point, run the account-migration step (queued in QUEUED.md as P1) and `delete-organizational-unit` the old top-level CAMPPS once empty.

**Commit:** Procedural — see workflow_dispatch run [24933555533](https://github.com/infiquetra/infiquetra-aws-infra/actions/runs/24933555533) for the deploy that established this state.

### Disable `push: branches: [main]` trigger temporarily during multi-step deploy debug (re-enabled after stabilization)

**Picked:** When a deploy is broken at the AWS layer in a way that requires multiple iterative fixes, defensively cut the auto-trigger so each commit-to-fix doesn't queue another doomed run. Restore once the pipeline is proven end-to-end.

**Tradeoffs considered:**
- *Leave auto-deploy on*: every fix-commit triggers a real deploy attempt. Noisy, generates failed-run alerts, leaves CFN stacks repeatedly stuck in `ROLLBACK_COMPLETE` requiring manual cleanup.
- *Use `[skip ci]` in commit messages*: per-commit discipline; easy to forget; doesn't apply to merge commits from squash-merge.
- *Add a `paths-ignore: ['**']` guard*: hacky, hides the disable in non-obvious config.
- *Picked: comment out the `push:` trigger with an inline note explaining why and how to restore*: explicit, version-controlled, easy to revert in a single PR.

**Implementation:** PR #6 commented out `push:` and added a comment block with the exact YAML to restore. PR #8 reverted by uncommenting.

**Revisit if:** A future multi-step debug session lasts long enough that the disable-then-restore overhead exceeds the noise cost. At that point, consider a more permanent guard like a manual gate on production deploys.

**Commit:** PR [#6](https://github.com/infiquetra/infiquetra-aws-infra/pull/6) (disable), PR [#8](https://github.com/infiquetra/infiquetra-aws-infra/pull/8) (re-enable).

### Wrap `cdk deploy` with `uv run` at workflow call sites rather than editing `cdk.json`

**Picked:** Change the workflow scripts in `reusable-aws-deployment.yml` to invoke `uv run cdk deploy ...` instead of bare `cdk deploy ...`. Leave `cdk.json:app = "python3 app.py"` alone.

**Tradeoffs considered:**
- *Edit `cdk.json` to `app: "uv run python3 app.py"`*: one-line root-cause fix; applies to all CDK invocations everywhere; helps local devs who forget to `source .venv/bin/activate`. Downside: forces uv as a runtime dependency for any CDK invocation against this repo, including for potential future contributors using plain `pip`/`venv`. Also creates a recursive `uv run` if the caller already wrapped (idempotent in practice, but odd).
- *Activate the venv in the workflow before calling cdk*: extra step, more imperative, deviates from the existing `uv run cdk synth` pattern.
- *Picked: workflow-boundary `uv run` wrapping*: matches `reusable-cdk-synthesis.yml`'s existing pattern, keeps `cdk.json` simple and tool-agnostic, makes the venv contract explicit at the CI boundary where the runner is set up.

**Implementation:** PR #5 changed two call sites in `reusable-aws-deployment.yml` (Organization Stack deploy + SSO Stack deploy). No `cdk.json` change.

**Revisit if:** A third call site is added without remembering the wrapping, or local devs hit the same bug enough to justify the cdk.json change.

**Commit:** PR [#5](https://github.com/infiquetra/infiquetra-aws-infra/pull/5).

### Per-job permissions over top-level (Option B) for `deploy-infrastructure.yml`

**Picked:** Set top-level `permissions: contents: read` (least-privilege baseline) and elevate only the `deploy:` job to `{ id-token: write, contents: write }` for OIDC + git tag push. Leave `post-deployment:` at the top-level baseline.

**Tradeoffs considered:**
- *Option A — top-level only with broad perms*: 2 lines instead of 6, all jobs get the elevated token. Simpler. Downside: `post-deployment` doesn't need write access; broader blast radius if any step is compromised.
- *Option B — per-job least-privilege*: 6 lines, defense-in-depth. Matches the precedent set by `pull-request-validation.yml` (which already uses per-job permissions for `code-quality`, `security-scan`, `cdk-synthesis`, `validation-summary`).
- *Picked: Option B*: consistency with existing pattern outweighs the small verbosity cost.

**Implementation:** PR #4 added the two `permissions:` blocks to `deploy-infrastructure.yml`.

**Revisit if:** A new job is added to `deploy-infrastructure.yml` and the per-job pattern becomes painful, OR `pull-request-validation.yml` flips to top-level-only (in which case match for consistency).

**Commit:** PR [#4](https://github.com/infiquetra/infiquetra-aws-infra/pull/4).

---
