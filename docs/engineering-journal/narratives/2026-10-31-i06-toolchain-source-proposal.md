# I06 guarded toolchain source proposal — 2026-10-31

Status: SOURCE CANDIDATE; native, project and hosted qualification pending.
Base commit: `fdf52462f02f0d19eb7467301b45c40ba3b13974`.
Base tree: `078b34f93e6d3a4710cfb626b0100b3ecad8c87b`.
Branch: `ci/20261031-i06-guarded-toolchains`.
This proposal was derived from clean tracked source. The earlier I06 worktree remains quarantined; it supplies no source clearance. Accepted small guarded requests do not establish the cause of its earlier hook denial.

## Tool and action provenance

The approved qualification evidence specifies uv 0.13.6 and Node 22.23.4. Retained `execution/a07-root-sdk-first-native-result.json` records successful version checks for both (the overall operation failed later; it is not whole-toolchain clearance). Python 3.13.16 is the approved AWS full 764-test baseline. Retained `execution/i04-aws-offline-synth-results.json`, source `748bfa9fdce017a28324d6bdbb004b2d760a08d3`, identifies authentic npm-integrity-verified CDK CLI 2.1144.0 and exit-zero foundation, monitoring and nonprod-role synthesis. The clean role workflows already use CLI 2.1144.0. CDK library 2.207.0 is not the CLI version.

Independently fetched upstream `action.yml` at each exact immutable revision during this task:

| Action | Exact revision |
| --- | --- |
| [setup-python](https://github.com/actions/setup-python/blob/a26af69be951a213d495a4c3e4e4022e16d87065/action.yml) | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| [setup-uv](https://github.com/astral-sh/setup-uv/blob/d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86/action.yml) | `d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86` |
| [cache](https://github.com/actions/cache/blob/0057852bfaa89a56745cba8c7296529d2fc39830/action.yml) | `0057852bfaa89a56745cba8c7296529d2fc39830` |
| [setup-node](https://github.com/actions/setup-node/blob/49933ea5288caeca8642d1e84afbd3f7d6820020/action.yml) | `49933ea5288caeca8642d1e84afbd3f7d6820020` |

The setup-uv source declares version, enable-cache and uv-version output. Its own cache is disabled; the retained cache-deps output reports actions/cache's actual uv cache restore. setup-python supplies the resolved installed version and interpreter path. These are source contracts, not new execution receipts.

## Complete current composite consumer inventory

Paths below are under `.github/workflows/`. All nine Python calls currently install the repository root `pyproject.toml` plus `uv.lock`; no caller passes a composite working directory. Reusable workflow working-directory inputs still apply to later validation steps and default to `.`. The separate `github-oidc-bootstrap/uv.lock` is not installed by any current composite call and is therefore not a root-cache input.

| Workflow / job | Python input | Node composite input |
| --- | --- | --- |
| reusable-code-quality.yml / code-quality | inputs.python-version | none |
| reusable-security-scan.yml / security-scan | inputs.python-version | none |
| reusable-cdk-synthesis.yml / cdk-synthesis | inputs.python-version | inputs.node-version |
| reusable-aws-deployment.yml / deploy | inputs.python-version | inputs.node-version |
| pull-request-validation.yml / monitoring-iam | 3.13.16 | 22.23.4 |
| pull-request-validation.yml / nonprod-role-ci-guards | 3.13.16 | none; direct setup-node 22.23.4 |
| pull-request-validation.yml / unit-tests | 3.13.16 | none; direct setup-node 22.23.4 |
| deploy-campps-nonprod-roles.yml / deploy | 3.13.16 | none; direct setup-node 22.23.4 |
| bootstrap-campps-nonprod-roles.yml / bootstrap | 3.13.16 | none |

Reusable Python defaults become 3.13.16; reusable Node defaults become 22.23.4. PR quality/security/synthesis callers and deploy-infrastructure explicitly select those versions. All three Node composite calls retain the default CDK input, now 2.1144.0. No current caller specifies latest. Exact CDK overrides remain available through the existing environment-bound input; floating values fail. Existing Python/Node input expressions and all output names/step IDs remain available. Triggers, permissions, admission checks, statuses, scanner scope, artifact handling and deployment ordering stay unchanged.

## Cache and lock contract

Require both root files before restore; never accept an empty missing-lock hash. Discover the uv cache with `uv cache dir`; cache no virtual environment. The exact key includes runner OS, architecture, installed uv version, resolved Python version, root pyproject and lock content hashes. There are no broad restore keys. Sync uses `--frozen --dev`, the installed interpreter path via environment, and disables automatic Python downloads. Frozen mode preserves the lock; later qualification must separately verify manifest/lock consistency. Cache data confers no source, artifact or deployment authorization.

## Required offline qualification — not executed here

1. Parse workflows/actions with the supported parser and run existing shell/parser/admission contracts. Confirm all nine Python/three Node calls above, direct Node helpers, input overrides, step IDs, output wiring and permission/status/trigger graphs. Negative controls: absent root lock/manifest fails before restore; changed lock/manifest, OS, arch, uv or Python misses the old key; floating CDK input fails; missing tools and unsuccessful install propagate failure. Validate actual uv version/cache path and resolved interpreter identity.
2. In approved disposable offline namespaces with authentic pre-staged tools/downloads, exercise every inventory row, including full quality/security checks, the complete AWS unit suite, monitoring guards, role guards, bootstrap guards and OIDC bootstrap tests. Retain genuine scanner execution errors. Exercise both default and exact-version override paths and reusable working-directory behavior. Preserve all existing case inventories and expected refusals. No cloud credentials or mutation calls.
3. Compare base and candidate normalized CloudFormation JSON for foundation, monitoring, nonprod-role and the separate GitHub OIDC bootstrap apps. Retain raw templates and hashes. Remove only documented volatile metadata; explain every semantic or IAM difference and hold unexplained differences. Test the bootstrap app's own frozen lock in its own namespace rather than claiming the root cache installs it.
4. Bound timing to one cold and one warm setup pair per distinct root dependency/tool identity on equivalent runner resources, with a five-minute per-setup limit; serialize resource-heavy work. Use an empty uv download cache for cold and only its saved bytes for warm, always fresh virtual environments. Record setup/restore/save/sync timings, bytes, hit output and installed-package inventories. Require equivalent results, unchanged lock/manifest hashes and no unexplained regression. Separate offline pre-staged replay timing from later hosted download/cache-service timing. Make no private-allowance savings claim for this public repository.

## Release and rollback

This task authorizes source only. No SDK/project/test/CDK/install/deploy runs or release decisions occurred. Review and all qualification above must finish before any merge decision. A merge changes shared composites and automatically triggers the foundation deployment workflow, so it requires a new concrete owner decision. If compatibility fails, restore both composites and all caller version changes as one unit; revert this proposal's journal records with them. Never roll back deployed infrastructure blindly or bypass role/bootstrap admission controls.
