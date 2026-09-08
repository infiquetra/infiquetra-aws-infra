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

## 2026-09-08

### Restore Identity-table Decrypt on the Tenant Setup nonprod seam-proof policy

**Decision.** Add one `kms:Decrypt` statement,
`ScopeSeamConsumerTableKeyDecrypt`, to the existing
`campps-tenant-setup-nonprod-gha-seam-proof-policy` on
`campps-tenant-setup-nonprod-gha-deploy-role`. Resource is `*` only because KMS
aliases cannot be named there. Conditions are conjunctive:
`kms:ViaService=dynamodb.us-east-1.amazonaws.com`, encryption-context table name
`campps-identity-access-nonprod`, encryption-context subscriber account
`self.account`, and `ForAnyValue:StringEquals` on
`alias/campps-platform-nonprod-pii`. Existing `events:PutEvents` and
`dynamodb:GetItem` statements stay. No Query/Scan/PutItem, no other KMS action,
no staging/production/other-service grant, no change to the Canary live-proof
role or Identity D8 ops role.

Identity #134 switched that table to the platform PII customer-managed key, so
the already-reviewed GetItem became unusable. This restores that read; it does
not add a new table or action scope. Architect
`4205f3a8f3e88ff76469118919f905b5b6d0c2a8` and Planner
`4712d53a3dcef61a834b57d83514d75be24d4317` bind the statement. This is not
infra #162 bootstrap work.

**Rejected alternatives.**
- *Widen the live-proof or D8 ops-role Decrypt:* different principals and
  owners; the denied caller is the Tenant Setup GitHub deploy role.
- *Copy RegistrationTableKeyDecrypt unchanged:* that statement lacks the
  Identity table/subscriber encryption context required here.
- *Put the key ARN in Resource without conditions:* broader than the reviewed
  alias-plus-ViaService-plus-context pattern; fallback only if this exact
  statement still denies after deploy.
- *Edit the key policy, SCP, or a new role:* not authorized for this unit.

**Implementation.** `_create_scope_seam_proof_policy` in
`infiquetra_aws_infra/campps_deploy_roles_stack.py`; seam-proof assertions in
`tests/unit/test_campps_deploy_roles_stack.py`.

**Revisit when.** A post-deploy REAL-BUS rerun still denies Decrypt with this
statement live (then Resource may become the exact key ARN from the platform
SSM parameter, never condition removal); or the seam proof is retired.

**Commit.** See PR for SHA. Source-only: this decision does not deploy
`CamppsNonProdDeployRolesStack`.

## 2026-09-07

### Preserve exact bootstrap selectors and recover only owned resources

**Decision.** Standard Repair 3 follows Planner `9c73c522` and Architect
[`6f5b609`](https://github.com/infiquetra/campps-tenant-setup/blob/6f5b6099692bb26b7bdd7053b840f0503d0716b4/docs/runs/164/continuation-review-disposition.md):
retain the accepted IAM implementation and strengthen the existing tests against
rendered secret resources. Both approved logical names keep the generated
six-character suffix selector in the exact account/region. Same-name recreation
remains selectable and requires owning setup/configuration revalidation; selector
tests are not live permission proof.

Canary owns signed workflow-name uniqueness and rename regressions; infra owns
coordinated trust changes. B1 may precede exact child roles, whose deployed
outputs and effective trust remain Release/Tester readback responsibilities.
The named pending nonprod protection/main/OIDC/configuration evidence remains
open. All six claims and the existing final-main-message/exact-SHA validation
protocol below stay binding.

For retirement, stop new runs while preserving authorized cleanup. Inspect
original operations, restore only owned suspension lineage/prior state, finish
or retain truthful event obligations, revoke only the dedicated operator grant,
and record incomplete cleanup honestly. Then disable owned bootstrap delegation
and remove its protected binding through the authorized owner procedure.
Outstanding bootstrap and child sessions must expire or receive existing
targeted authorized revocation; stopping new OIDC sessions does not erase them.
Only afterward review removal of B1's role, managed policy and output as a
reverse delta on **current** shared-stack source. Preserve concurrent changes,
the shared OIDC provider, proof/deploy/service roles, accounts, secrets and
durable recovery/audit records. Use only the exact nonprod app/stack and safe
main protocol. Normal cleanup retains reusable roles/account/profile.

**Rejected alternatives.**
- Broad secret wildcards, speculative KMS access, new role-order guards or
  workflow monitors would exceed the demonstrated evidence gaps.
- Shared-stack destruction or a historical template could remove unrelated
  current resources and cannot safely restore owned fixture state.
- Disabling all access before cleanup could strand owned suspension/event
  obligations; stopping OIDC alone would leave child sessions active.

**Implementation.** Existing selector tests and
[`03-login-flows.md`](../ops/03-login-flows.md#owned-cleanup-and-bootstrap-removal).
New selector cases are expected to pass the unchanged reviewed implementation;
there is no fabricated failing-test history. No cloud action is performed.
**Revisit when.** A maintained selector case demonstrates an actual defect, an
approved logical name/role/workflow contract changes, or live readback proves a
binding mismatch; return to the existing owner for a bounded disposition.
**Commit.** PR #163, Standard Repair 3 evidence/docs delta from `31bea23a`.
Completed repair counts remain two standard / zero expert pending whole-batch review.

### Bind this delivery's main merge to a final `[skip actions]` message plus exact-SHA validation

**Decision.** Keep RP-B1's four-file custody and do not edit workflows. For this
bounded delivery only, Delivery Manager / Release must land the reviewed main
commit with literal `[skip actions]` in the **actual resulting main commit
message**, then dispatch existing `pull-request-validation.yml` at a ref fixed
to that final SHA, then deploy only with the local renewed `campps-nonprod`
executor and `python3 app_campps_bootstrap.py` / `CamppsNonProdDeployRolesStack`.
Feature heads and the main-target PR keep ordinary required checks; they must
not carry skip markers. Cancelling a started `Deploy Infrastructure` run is not
prevention. This unit does not merge, dispatch, or deploy.

This does not reopen the 2026-04-25 rejection of casual per-feature `[skip ci]`
markers. That rejection still holds for ordinary commits because squash merges
drop them. Architect coverage `791cf63b1969b9ee09ea357bd1d6281d3903c838` binds
the skip token to the **final merge message** and pairs it with explicit
exact-SHA dispatch, which is the failure the earlier decision named.

**Rejected alternatives.**
- *Normal main merge:* `deploy-infrastructure.yml` at `1435ae1b` triggers on
  every main push with no paths filter and defaults to production/`all` on the
  foundation Organization and SSO stacks. That is an unauthorized deploy.
- *Cancel the foundation run after it starts:* not prevention; the run has
  already launched.
- *Put `[skip actions]` on the feature head or PR body:* GitHub skip tokens
  apply to the triggering commit. A marker on an earlier commit, title, or body
  does not protect the merge commit and would suppress required candidate PR
  checks.
- *Edit `deploy-infrastructure.yml` or add a paths filter:* workflow files are
  outside RP-B1 custody; Architect forbids inferring a workflow change.
- *Treat PR-validation green as bootstrap deploy proof:* that workflow synths
  the default organization app, does not run pytest, and has no AWS deploy
  step.
- *Dispatch `Deploy Infrastructure` for the bootstrap stack:* that workflow
  cannot select `app_campps_bootstrap.py` / `CamppsNonProdDeployRolesStack`.

**Implementation.** Documented in `docs/ops/03-login-flows.md` under the
prerequisite-operator bootstrap. No workflow, pin, or app change.

**Revisit when.** Live merge policy cannot preserve the final `[skip actions]`
message, or branch protection / merge-queue mechanics prevent exact-SHA
dispatch. Then DM returns the concrete constraint to Architect/Planner for an
assigned minimal deployment guard. Do not apply this skip/dispatch protocol to
unrelated repository work.

**Commit.** See PR for SHA. This decision does not merge to main or deploy.

### Add a dedicated nonprod OIDC prerequisite-operator role instead of widening live-proof

**Decision.** Mint one e2e-canary nonprod role,
`campps-e2e-canary-nonprod-gha-prerequisite-operator-role`, in the existing
`CamppsDeployRolesStack`. Reuse the stack OIDC provider. Trust six exact GitHub
claims (audience, subject, repository, environment, `refs/heads/main`, workflow
name `Tenant Setup Prerequisites Nonprod`) with a one-hour session. Permissions
are the locked-index CodeArtifact projection, GetSecretValue on the dedicated
operator bundle and reviewed WorkOS API-key secret, and AssumeRole on the exact
T1 fixture-ops and planned I2 platform-operator names in `self.account`. Publish
only `CamppsE2eCanaryPrerequisiteOperatorRoleArn`. Leave ordinary live-proof and
deploy policies byte-for-byte equivalent.

`_codeartifact_consume_statements` gains an optional `projection="locked_index"`
mode. Default `ci_sync` keeps metadata reads and the unconditioned bearer token
for existing consumers. The bootstrap does not copy `GetRepositoryEndpoint` or
package-metadata actions because the locked-index install does not resolve an
endpoint.

`kms:Decrypt` is omitted. The same WorkOS API-key and operator-bundle secret
reads already in this stack have no Secrets Manager CMK grant, and live secret
inventory was unrun (SSO renewal pending). Adding unused `kms:Decrypt` would
widen authority without evidence.

Infra does not emit `TenantSetupFixtureOpsRoleArn` or
`IdentityPlatformOperatorOpsRoleArn`. Those stay with Tenant Setup RP-T2 and
Identity RP-I2. Runtime configuration must use reviewed deployed outputs, not
synth-predicted ARNs.

**Rejected alternatives.**
- *Widen `campps-e2e-canary-nonprod-gha-live-proof-role`:* that role is the
  retained-read path (aud+sub only, DynamoDB/GetItem, payments PutEvents). Mixing
  bootstrap package/secret/AssumeRole into it would let retained-read inherit
  operator authority.
- *Copy the existing CodeArtifact consume helper unchanged:* it grants
  repository-endpoint and package-metadata reads and an unconditioned bearer
  token. Architect `cc63e089` forbids copying those unless maintained code
  actually uses them.
- *Grant `kms:Decrypt` speculatively with ViaService:* the plan allows KMS only
  if those secret reads use a customer-managed key. No current inventory shows
  that.
- *Emit all three protected-variable outputs from infra:* Architect coverage
  `3f68dc35` binds one infra output; the other two are service-owned.
- *Trust only aud+sub like live-proof:* the bootstrap must fail closed on
  missing repository, environment, ref, or workflow-name claims.

**Implementation.** `infiquetra_aws_infra/campps_deploy_roles_stack.py` —
`_create_e2e_canary_prerequisite_operator_role` and the `locked_index`
projection. Tests in `tests/unit/test_campps_deploy_roles_stack.py`. Operator
flow: `docs/ops/03-login-flows.md`. Synth/diff only
`python3 app_campps_bootstrap.py` / `CamppsNonProdDeployRolesStack`.

**Revisit when.** Live GetSecretValue returns AccessDenied that names a
customer-managed key (then add exact-key Secrets Manager `kms:ViaService` plus
encryption context); the dedicated bundle or WorkOS API-key logical name
changes; or a maintained install path starts resolving
`GetRepositoryEndpoint`.

**Commit.** See PR for SHA. Source-only: this decision does not deploy
`CamppsNonProdDeployRolesStack`.

## 2026-08-20

### Grant campps-platform's nonprod deploy role a dedicated e2e-canary health policy

**Decision.** Attach one optional managed policy,
`campps-platform-nonprod-gha-e2e-canary-health-policy`, to
`campps-platform-nonprod-gha-deploy-role` only. The policy has two statements:
`cloudformation:DescribeStacks` on
`arn:aws:cloudformation:us-east-1:477152411873:stack/campps-e2e-canary-nonprod/*`
and `lambda:InvokeFunctionUrl` on
`arn:aws:lambda:us-east-1:477152411873:function:campps-e2e-canary-nonprod-health`.
The helper `_create_platform_e2e_canary_health_policy` returns `None` unless
`service_repository.name == "platform"` and `target_environment == "nonprod"`.
Resource names are nonprod literals, not interpolated from the environment.

This unblocks campps-platform's enforced e2e canary
(`tests/e2e/test_cookiecutter_deploy.py`), which today skips on
`DescribeStacks` `AccessDenied` and reports green while proving nothing
(infiquetra-aws-infra #156 / campps-platform #43).

**Rejected alternatives.**
- *Widen `_create_platform_foundation_deploy_policies`:* would give every
  future platform-foundation consumer the canary probe grant. The grant is one
  live-proof lane, not a general deploy capability.
- *One statement with both actions:* CloudFormation and Lambda ARNs cannot
  share a resource list without over-granting one of them.
- *Gate on `"campps-platform"`:* the registry name is `platform`; that gate
  would always return `None`.
- *Interpolate `{target_environment}` into the stack/function names:* a
  forgotten environment check would then name staging/production canaries.
- *Add `lambda:InvokeFunction`:* issue #156 names exactly two actions.
  Unconditioned `InvokeFunction` would also allow `aws lambda invoke`. The
  canary function's resource policy already emits both actions for a *different*
  principal. Follow-up only if the live SigV4 GET 403s after this identity
  grant is deployed.
- *Staging or production grants:* the enforced canary runs in nonprod only.

**Implementation.** `infiquetra_aws_infra/campps_deploy_roles_stack.py` —
`_create_platform_e2e_canary_health_policy`. Tests in
`tests/unit/test_campps_deploy_roles_stack.py` call the factory for every
non-matching service/environment pair, assert the exact ARNs, assert attachment
to exactly one role, and hash-freeze the three existing platform nonprod
policies plus staging/production full-registry synth. Plan:
`docs/plans/2026-08-20-platform-e2e-canary-health-iam-plan.md`.

**Revisit when.** The live SigV4 GET returns 403 after this policy is
deployed (then consider `lambda:InvokeFunction` with
`lambda:InvokedViaFunctionUrl=true`); the canary moves to another environment;
or the health function is renamed away from the pinned literal.

**Commit.** See PR for SHA. Source-only: this decision does not deploy
`CamppsNonProdDeployRolesStack`.

## 2026-08-01

### Grant the tenant.read denial gate by literal tenant id, wildcarding only the API id

**Decision.** `campps-tenant-setup-nonprod-gha-tenant-read-deny-gate-policy` grants
`execute-api:Invoke` on
`arn:aws:execute-api:us-east-1:<acct>:*/nonprod/GET/tenants/tenant-out-of-scope-golive`
— exact stage, exact method, and a path terminating in the literal out-of-scope
tenant the gate reads. Only the API id is wildcarded. This stack deliberately
holds no service's API id, and the privilege being wildcarded is "GET one tenant
that does not exist", which is worth nothing on any API in the account.

The gate it enables signs as the deploy role, which is in identity-access's
`SERVICE_PRINCIPAL_ALLOWLIST` with `authorization:evaluate` and no
`subject_actions` — so its denial proves those two lists stay separate rather than
merely proving strangers are refused.

**Rejected alternatives.**
- *Wildcard the path (`GET/tenants/*`)*: an `execute-api` ARN wildcard matches
  across `/`, so this also grants `/tenants/{id}/seed-runs`, `/camps`, `/sessions`
  and every sibling. It reads like a one-route change and is not one. A unit test
  (`test_tenant_read_deny_gate_grant_cannot_reach_sub_resources`) fails if a
  trailing `*` is ever added; verified by mutation.
- *Resolve the API id from SSM*: `/campps/services/tenant-setup/nonprod/api-url`
  exists, but it is a URL and a deferred CFN dynamic reference, so extracting the
  id needs `Fn::Select`/`Fn::Split` gymnastics at synth. Not worth it to remove a
  wildcard that costs nothing.
- *Put the grant in campps-tenant-setup's own stack*: would give exact API ids via
  `arn_for_execute_api` and keep it to one repo, but requires the deploy role to
  attach a policy to itself — a privilege-escalation shape deploy policies should
  refuse, not enable.
- *Use the e2e-canary live-proof role instead*: verified it holds zero
  `execute-api:Invoke` (policy v4: secretsmanager, two dynamodb GetItem, events,
  kms), so it cannot invoke any API, and it is not in the allowlist either. It
  fails both halves of what the gate needs.

**Implementation.** `_create_tenant_read_deny_gate_policy`, gated to
tenant-setup + nonprod (staging and production never hold an invoke grant they do
not exercise). Constant `TENANT_READ_DENY_GATE_TENANT_ID` documents the
cross-repo coupling to `CAMPPS_GOLIVE_OUT_OF_SCOPE_TENANT_ID` in
campps-tenant-setup's deploy-nonprod workflow.

**Revisit when.** The gate moves off a fixed tenant id; the route gains a real
in-scope read the gate should also exercise; or a second service needs the same
shape, at which point the tenant id should become a parameter rather than a
module constant.

**Commit.** See PR for SHA.

## 2026-08-01

### Let Tenant Setup mint its nonprod test-user token without GitHub secrets

**Decision.** Attach one nonprod-only managed policy to the existing Tenant
Setup GitHub deploy role. The policy grants only
`secretsmanager:GetSecretValue` on Tenant Setup's service-owned WorkOS
test-user bundle and
the Identity Access WorkOS API-key secret, each constrained to Secrets
Manager's exact six-character generated suffix. Tenant Setup can then mint a
short-lived user token inside the test process rather than storing an expiring
token in a GitHub Environment secret.

**Rejected alternatives.** Broad access to the Identity Access or E2E secret
namespaces would exceed the proof's needs. Sharing E2E Canary's retained-user
bundle would bind Tenant Setup to a different authorization identity. Reusing
the E2E Canary live-proof role would cross repository trust boundaries.
Keeping static access tokens in GitHub would preserve the expiry failure that
caused this repair.

**Implementation.** `campps_deploy_roles_stack.py` creates and attaches the
guarded policy only for `tenant-setup` in `nonprod`; focused synthesis tests pin
the action, two resource patterns, attachment, environment guard, and
repository isolation.

**Revisit when.** The proof moves to another environment, the bundle contract
changes, or either secret moves to a customer-managed KMS key that requires an
explicit decrypt grant.

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

**Superseded in part, 2026-09-08.** The two-action description is incomplete after Identity #134 encrypted that table with the platform PII key. The same policy now also carries one DynamoDB-via-service `kms:Decrypt` for that table; see the 2026-09-08 entry. Staging/production exclusion and tenant-setup-only attachment are unchanged.

**Rejected alternatives.**
- Dedicated seam-proof IAM role: adds OIDC trust configuration, a second role ARN to thread through CI, and operational complexity — disproportionate for a bounded grant that runs in a single lane.
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
