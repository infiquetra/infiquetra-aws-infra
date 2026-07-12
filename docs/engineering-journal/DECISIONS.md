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

## 2026-07-11

### Give the protected nonprod E2E proof its own two-read role

**Decision.** Create a dedicated one-hour GitHub OIDC role for
`campps-e2e-canary`'s protected `nonprod` Environment. Its single managed policy
permits only `secretsmanager:GetSecretValue` on the canonical WorkOS API-key
secret's exact six-character generated-suffix pattern and `dynamodb:GetItem` on
the exact Identity Access nonprod scope table.

**Rejected alternatives.**
- Add the provider secret to the existing deploy role: rejected because the
  live proof needs no CloudFormation, IAM, CDK, or application deployment
  authority.
- Reuse the existing identity-scope readback policy: rejected because it is
  attached to the broad deploy role and cannot establish a two-read runtime
  boundary.
- Add `kms:Decrypt`: rejected because live inventory confirms the secret uses
  the default Secrets Manager key. A customer-managed key would require
  re-planning instead of widening this role.
- Create staging or production equivalents: rejected because no corresponding
  protected live-proof lane exists.

**Implementation.**
`infiquetra_aws_infra/campps_deploy_roles_stack.py` creates the guarded role,
policy, and `CamppsE2eCanaryLiveProofRoleArn` output. Focused assertions in
`tests/unit/test_campps_deploy_roles_stack.py` pin trust, session length,
actions, resources, attachment isolation, environment/repository guards, and
stable synthesis.

**Revisit when.** The live proof moves to another environment, the canonical
secret uses a customer-managed key, the proof requires an additional AWS API,
or GitHub supports an independently reviewed private-repository Environment.

**Commit.** PR #143; source commit `e739fd4`, squash merge `cb9cdcd`.
`CamppsNonProdDeployRolesStack` reached `UPDATE_COMPLETE` in account
`477152411873`. Live readback confirmed the exact role trust and one attached
two-read policy; IAM simulation allowed only the canonical secret read and
scope-table `GetItem` while denying sibling/higher-environment, write, query,
CloudFormation, role-pass, and KMS cases. The existing deploy role did not
receive the live-proof policy.

## 2026-07-05

### Parent-zone ACME access is scoped to one webhook TXT record

**Decision.** Attach a CloudFormation-managed inline policy to the existing
`letsencrypt-route53` IAM user that permits `route53:ChangeResourceRecordSets`
only for the `TXT` record `_acme-challenge.webhooks.infiquetra.com` in the
`infiquetra.com` hosted zone.

**Rejected alternatives.**
- Reuse the Olympus-zone-only policy: rejected because DNS-01 for
  `webhooks.infiquetra.com` must write in the parent hosted zone.
- Grant broad parent-zone certbot access: rejected because certbot needs only
  the ACME challenge name for the webhook ingress certificate.
- Move the certbot user fully into this stack: deferred because the existing
  user and key already back the live webhook TLS role.

**Implementation.** `HomeLabDnsStack` attaches
`home-lab-webhook-certbot-route53` to `letsencrypt-route53`, and
`tests/unit/test_home_lab_dns_stack.py` pins the TXT-record scope.

**Revisit when.** More parent-zone hostnames use the same edge certificate, or
ACME moves to another credential mechanism.

### Home-lab DDNS IAM owns permission, not live A record values

**Decision.** Add a dedicated `HomeLabDnsStack` that creates the
`home-lab-route53-ddns` IAM user and a least-privilege Route 53 policy for the
home-lab webhook records. The stack does not create access keys and does not
own the mutable A record values.

**Rejected alternatives.**
- CloudFormation-owned A records: rejected because a later deploy could revert
  a residential WAN IP back to a stale literal.
- CloudFormation-created access keys: rejected because the secret access key
  would become stack output/state material.
- Broad Route 53 access: rejected because the updater needs only A-record
  UPSERTs for the webhook ingress names plus `GetChange` and record readback.

**Implementation.** `infiquetra_aws_infra/home_lab_dns_stack.py` adds the
policy, `app.py` synthesizes `InfiquetraHomeLabDnsStack`, and
`tests/unit/test_home_lab_dns_stack.py` pins the no-access-key and
record-scope invariants.

**Revisit when.** The webhook edge moves fully to AWS ingress, the home-lab no
longer needs residential DDNS, or the updater can use a short-lived role
instead of a vaulted IAM user key.

## 2026-07-02

### E2E canary identity-scope readback grant (nonprod only)

**Decision.** Plan a single narrowly-scoped managed policy for `campps-e2e-canary-nonprod-gha-deploy-role`, granting only `dynamodb:GetItem` on `campps-identity-access-nonprod`. The grant should be implemented as a standalone optional helper in `CamppsDeployRolesStack`, gated to `e2e-canary` + `nonprod`, mirroring the tenant-setup seam-proof helper instead of broadening the shared `serverless-api` deploy policy.

**Rejected alternatives.**
- Add the grant to the shared serverless deploy profile: would give unrelated services identity-access table readback.
- Add `Query`, `Scan`, batch reads, or table wildcards: unnecessary for the live proof, which requires one `GetItem` against the identity-access nonprod table.
- Add staging or production grants: speculative privilege with no matching e2e-canary lane or live proof requirement.

**Implementation.** `infiquetra_aws_infra/campps_deploy_roles_stack.py` — method `_create_e2e_canary_identity_scope_readback_policy`; `tests/unit/test_campps_deploy_roles_stack.py` — positive role/policy attachment test plus higher-environment, helper-guard, unrelated-service, and tenant-setup regression coverage. Plan: `docs/plans/2026-07-02-e2e-canary-identity-scope-readback-iam-plan.md`.

**Revisit when.** The e2e canary proof runs in staging/production, the readback shape needs a different DynamoDB operation, or a second fixture needs a similar grant and the helper pattern should become a small reusable optional-policy registry.

**Commit.** PR #142, branch `fix/e2e-canary-identity-scope-readback`, implementation commit `ac0b543`; nonprod deploy completed for `CamppsNonProdDeployRolesStack` and IAM simulation returned `allowed`.

---

## 2026-06-23

### Cross-service deploy-role grant for the scope-origination seam proof (tenant-setup nonprod only)

**Decision.** Add a single narrowly-scoped managed policy (`campps-tenant-setup-nonprod-gha-seam-proof-policy`) to the tenant-setup nonprod deploy role, granting `events:PutEvents` on the shared platform bus (`campps-platform-nonprod`) and `dynamodb:GetItem` on identity-access's table (`campps-identity-access-nonprod`). This unblocks the deploy-gated integration test `tests/integration/test_scope_origination_seam_deployed.py` (campps-tenant-setup PR #67), which proves the producer → bus → consumer seam end-to-end against real deployed infrastructure. The grant is implemented as a standalone method `_create_scope_seam_proof_policy` that returns `None` for every service/environment combination except `tenant-setup` + `nonprod`, so the guard is co-located with the grant and easy to audit.

**Rejected alternatives.**
- Dedicated seam-proof IAM role: adds OIDC trust configuration, a second role ARN to thread through CI, and operational complexity — disproportionate for a two-action grant that runs in a single lane.
- Broadening the permissions boundary: the boundary governs app-role creation, not the deploy role itself; touching it for a deploy-time test concern mixes two distinct scopes.
- Granting staging/production as well: the proof only runs in the nonprod lane; granting production/staging deploy roles read into identity-access's table would be speculative privilege with no corresponding test gate.

**Implementation.** `infiquetra_aws_infra/campps_deploy_roles_stack.py` — method `_create_scope_seam_proof_policy`; `tests/unit/test_campps_deploy_roles_stack.py` — one positive test + three negative tests.

**Revisit when.** The seam proof is extended to staging or production lanes (at that point, extend the guard condition and add corresponding tests); or the proof is retired (remove the method and its call site).

**Commit.** PR feat/l1-a-seam-proof-deploy-grant / campps-tenant-setup PR #67.

---

## 2026-06-20

### C0.3 — register all CAMPPS services + add a `web-app` deploy profile

**Decision.** Register the 6 missing CAMPPS backend services in `CAMPPS_SERVICE_REPOSITORIES`
(`coppa-consent`, `registration`, `payments`, `health-forms`, `activities-achievements`,
`staff-management` — all `serverless-api`, all 3 envs) so the registry-driven deploy-roles stack
auto-mints their per-service OIDC roles (S4 rides on S3 — no new role code for backends). Add a new,
dedicated `web-app` deploy profile (static-site: S3 + CloudFront + invalidation + CDK-bootstrap baseline)
for `campps-web-app` instead of the default serverless-api, and make `_create_deploy_policies()` raise on
any unrecognized profile. Canonical service set sourced from `campps-context-library`
phase-1a-build-program.md, not the conflicting "7 vs 10" card text. Deploy to nonprod (`477152411873`)
only; staging/production deferred to a reviewer-gated `/deploy`.

**Rejected alternatives.**
- Register `campps-web-app` as `serverless-api` — gives a Flutter Web static client Lambda/DynamoDB/API-GW
  grants it never uses (overprivileged). Rejected.
- Fully defer `campps-web-app` — cleaner, but operator chose to include it provisionally now.
- Keep the silent serverless-api fallback for unknown profiles — a latent footgun; replaced with a guard.
- Trust the cards' literal "7 service repos" — contradicted by the build program (10 backends + web-app).

**Implementation.** Plan: `docs/plans/2026-06-20-c0-3-aws-infra-service-registry-oidc-plan.md`. Touches
`infiquetra_aws_infra/campps_service_registry.py`, `infiquetra_aws_infra/campps_deploy_roles_stack.py`,
`tests/unit/test_campps_deploy_roles_stack.py`.

**Revisit when.** `campps-web-app`'s real CDK stack lands — confirm S3+CloudFront vs Amplify and tighten
the `web-app` profile's least-privilege scope (the profile is shipped **provisional** because the web-app
is an empty scaffold today with no settled deploy target).

**Commit.** PR [#137](https://github.com/infiquetra/infiquetra-aws-infra/pull/137) squash-merged as
`0a69c19` (2026-06-20). Deployed to nonprod `477152411873` via `app_campps_bootstrap.py`
(`CamppsNonProdDeployRolesStack`, additive-only: 40 adds / 0 modify-delete); R5 verified live — all 7 new
roles exist with env-scoped trust `repo:infiquetra/campps-<svc>:environment:nonprod`.
infiquetra-aws-infra#134 + #135 (both CLOSED 2026-06-20); parent campps-platform#10.

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
