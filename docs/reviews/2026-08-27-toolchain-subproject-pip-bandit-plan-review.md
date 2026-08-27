# Doc Review — 2026-08-27 toolchain sub-project / pip / bandit plan

## Readiness Result

- **Target:** `docs/plans/2026-08-27-toolchain-subproject-pip-bandit-plan.md`
- **Reviewed revision:** working tree (plan is uncommitted; base revision `origin/main` = `078c310`, verified by fetch)
- **Blocked status:** BLOCKED — one P0 finding makes the plan's U2→U3 execution order guaranteed to fail as specified
- **Rubric engine:** unavailable in this skill installation (`lifecycle_review.py` not found under the skill or plugin directories); readiness-skeptic pass ran fully. This is a plan-phase artifact in `docs/plans/`; the rubric engine covers idea/spec/issue phases, so coverage loss is limited.

## Findings

| key | priority | status | title |
|-----|----------|--------|-------|
| D1 | P0 | open | U2 leaves repo in state where bandit config-load conflict (P2) fails its own verification gates |
| D2 | P1 | open | Bandit "never loads" claim is wrong: bandit auto-discovers `./.bandit` as an ini config |
| D3 | P1 | open | U4 drops bandit's default excludes and the hook's `tests/` exclusion — `.venv`, `build`, `tests/` become scanned |
| D4 | P1 | open | KTD3 proposes pip as supported install path while the cited standard explicitly forbids bare-pip project dependency management |
| D5 | P2 | open | `.bandit` contains a 42-test `tests =` allowlist; deleting it without reconciling silently re-enables ~40 disabled checks |
| D6 | P2 | open | Plan's U1/U2 "Dependencies: None (parallel)" is a false safety: concurrent `uv sync` runs against the shared environment race |
| D7 | P2 | open | Issue #160's "out-of-scope: do NOT change root hook revisions" directly conflicts with U2's rev changes — no reconciliation recorded |
| D8 | P2 | open | R6 requires `uv run pytest -q` at repo root — pre-existing broken gate (no root pytest configuration; `[tool.pytest.ini_options] testpaths=["tests"]` is present but root pytest is not part of any existing workflow) |
| D9 | P3 | open | Plan cites `reusable-security-scan.yml:58` for current bandit form — line number verified correct as of `078c310` |
| D10 | P3 | open | Plan targets exact pins `ruff==0.15.18`/`mypy==2.1.0`/`bandit==1.9.4`; upstream published pins verified current today (latest PyPI: bandit 1.9.4, mypy 2.3.1, ruff 0.16.5 — published standard pins are behind latest-PyPI for mypy/ruff but match `docs/repositories/python-toolchain.md` at `9759385` dated 2026-08-26) |

### D1 (P0) — U2 fails its own verification gate as specified

U2 runs first (its "Dependencies: None"), U3 depends on U2. U2's verification block (line 116) and the Verification Gates block (lines 185-189) both require `pre-commit run --all-files` and `uv run bandit -c pyproject.toml -r .` to pass **after U2**. But D2's empirical result shows that while `.bandit` still exists (it is not deleted until U3), `bandit -c pyproject.toml` merges the ini's `tests =` allowlist with the TOML's `skips = ["B101","B601"]` and exits 2 with `Non-exclusive include/exclude test sets: {'B101','B601'}`. An agent following the plan literally runs U2, hits this failure, and cannot proceed to U3 (which contains the fix). The plan never instructs deleting `.bandit` inside U2. **Fix:** either move the `.bandit` deletion into U2, or reorder so config wiring (current U3) precedes the pin bump (current U2), or add to U2 an explicit verification-skip noting the conflict is expected until U3.

### D2 (P1) — The central problem-frame claim is false

Line 38 states bandit "does not auto-discover either" config. Empirically false at bandit 1.8.6: bare `uv run bandit -r . -v` logs `[main] INFO Found project level .bandit file: ./.bandit` and applies its `tests`/`skips`. The gap named "curated Bandit config never loads" is wrong in mechanism — the TOML config never loads (true, because `bandit[toml]` plus `-c` are both absent), but `.bandit` **does** load and has been the de-facto config in CI and local runs (CI invokes `uv run bandit -r .`). The plan's Gap 3 framing mis-describes current behavior, which matters because D3/D5's regressions flow from this mis-characterization. **Fix:** correct Gap 3 to record that `.bandit` auto-loads today as ini, and `[tool.bandit]` is the config that never loads.

### D3 (P1) — Execution silently drops the hook's `tests/` exclusion and bandit's default excludes

The current pre-commit hook (`:23`) excludes `^(tests/|github-oidc-bootstrap/tests/);` the planned hook args `--configfile pyproject.toml` omit any `--exclude` and the TOML's `exclude_dirs = ["tests", ".venv", "build"]` does not cover `github-oidc-bootstrap/tests` or `node_modules`, `cdk.out` (which `.bandit`'s `exclude =` line did cover). Separately, passing `-f json` on the command line overrides any config-file `output_format`, but more importantly the workflow currently relies on bandit's default recursive-scan excludes (`.venv`, `build`) that are silently overridden once `--configfile pyproject.toml` is passed with a narrower `exclude_dirs` list. **Fix:** either extend the TOML `exclude_dirs` with `github-oidc-bootstrap/tests`, `node_modules`, `cdk.out`, or retain a CLI `-x` arg; record the intended coverage delta explicitly in KTD4.

### D4 (P1) — KTD3 contradicts the very standard the plan claims to follow

The plan's KTD3 keeps `requirements.txt` as a supported pip path. But `docs/repositories/python-toolchain.md:42` in the cited standard states: *"Do not use `poetry` or bare `pip` for project dependency management."* The plan's own Sources table cites this document as the authority. Issue #160 itself offers the alternative "stop presenting the pip path." The plan never reconciles why it chooses the first branch of the issue over the explicit prohibition in the standard. **Fix:** either adopt the issue's second branch (mark pip path unsupported, point at `uv sync`), or record an explicit decision with rationale for deviating from the standard (e.g. external consumers cannot use `uv`); the current KTD3 asserts the choice without justification.

### D5 (P2) — `.bandit` allowlist deletion re-enables ~40 disabled checks without assessment

`.bandit:2` disables 42 bandit test IDs via a broad `tests = ...` allowlist (including B3xx crypto, B4xx XML, B5xx SSL, B6xx injection families). The `[tool.bandit]` TOML skips only B101, B601. Deleting `.bandit` without reconciling the two sets silently re-enables ~40 potentially-noisy or intentionally-disabled checks across the repo. The plan's risk table mentions `.bandit` deletion breaking a local invocation but not the coverage delta. **Fix:** in U3 or KTD4, record a one-time comparison scan (`uv run bandit -c .bandit -r .` vs `uv run bandit -c pyproject.toml -r .`) as a verification step and either extend TOML `skips` or accept new findings explicitly.

### D6 (P2) — "Parallel" execution units race on the shared uv environment

U1 and U2 both say "Dependencies: None (parallel with U1/U2)". Both run `uv lock` + `uv sync --dev` — U1 against `github-oidc-bootstrap/`, U2 against the root. uv environments are per-project; the two `uv sync` runs do not write the same `.venv`. That claim is safe for the lock sync itself. But U2's verification then runs `pre-commit run --all-files` which invokes the mypy/bandit hooks over `github-oidc-bootstrap/` source — if U1's lockfile regen is still in flight, the hooked runs resolve against an in-transition lockfile. More importantly the plan presents these as freely parallelizable to an executor without an ordering constraint on the gates. **Fix:** either record the real dependency (U2's `pre-commit run` step depends on U1's lockfile being final) or drop the "parallel" framing.

### D7 (P2) — Issue scope exclusion vs plan U2 change conflict unreconciled

Issue #160 explicitly lists "Do NOT change the three root hook revisions" as a non-goal, because they were "now correct" at the floors `v0.12.5`/`v1.17.0`/`1.8.6` (the 2026-08-22 floors). The plan's U2 changes exactly those revs to the new exact pins. The plan does note (line 32) "the target has moved from the issue's floor wording to the exact pin" — this is a deliberate supersession of the issue's acceptance criteria, which is legitimate, but it is presented as drift correction rather than a scope amendment, and requires the issue to be updated or the PR to record the override. **Fix:** record in the plan (or as an issue comment) that acceptance criterion "floors at or above" and the non-goal "do not change revs" are superseded by the published-standard's own 2026-08-26 move; link the superseding standard commit.

### D8 (P2) — Root `uv run pytest` gate is pre-existing broken

R6 and the Verification Gates block include `uv run pytest -q`. Root pytest is configured (`testpaths = ["tests"]`), `tests/unit/` exists, but pytest at the root is not exercised by any existing CI workflow — `pull-request-validation.yml` has no pytest job. Whether this passes today at `078c310` is unverified by the plan (no evidence cited). If it fails on unrelated pre-existing grounds, the PR gains an out-of-scope repair. **Fix:** pre-verify `uv run pytest -q` at `078c310` before the PR, or explicitly scope-test-only the bootstrap package (`uv run pytest github-oidc-bootstrap/tests`).

### D9/D10 (P3) — minor

Line numbers and pin values verified against live sources; residual risk noted in the readiness summary.

## Applied Safe Fixes

None. No edits made to the plan document: every correction either requires an engineering decision (D4 pip-vs-no-pip, D6 execution order) or changes a factual claim whose intended replacement the plan author should own (D2, D3, D5).

## Readiness Summary

The plan is well-researched and most local claims verify against `origin/main` at `078c310` (line numbers for `pyproject.toml`, `.pre-commit-config.yaml`, `requirements*.txt`, `reusable-security-scan.yml:58`, `AGENTS.md:397`, `.claude/CLAUDE.md:462` all check out). Upstream pins and hook-block claims verify against `infiquetra-context-library` `docs/repositories/python-toolchain.md` at `9759385` (2026-08-26). Three blocking problems remain: the U2→U3 order is internally inconsistent with its own verification (P0, D1); the "config never loads" framing mis-describes the actual auto-load behavior of `.bandit` (P1, D2) which in turn hides the coverage regressions in D3/D5; and KTD3's pip-fallback choice contradicts the standard it claims to follow (P1, D4). The plan cannot safely drive implementation until at least D1, D2, D3, and D4 are resolved.

## Residual Risk From Limited Evidence

- Did not run `pre-commit run --all-files` or the full verification battery against `078c310` (would take several minutes and mutate the working tree's pre-commit cache); D1's conflict was verified via direct `bandit -c pyproject.toml` invocation instead.
- Did not verify `uv run pytest -q` behavior at root at `078c310` (D8); the plan itself cites no evidence for this gate.
- `github-oidc-bootstrap/uv.lock` content not diffed; U1 assumes it can be regenerated cleanly, which is plausible but unverified.
- The rubric engine for formal SDLC plan-phase rubrics was unavailable in this installation (see header); if available, its issue-phase rubrics would apply given the plan's `origin: issues/160` link.

## Override Routing

Per `/work` integration: unresolved P0/P1 findings block `/work` execution unless explicitly overridden. If overriding, carry this review's D1 (reorder or merge U2/U3) and D4 (pip decision) as the rationale items that must be recorded in the PR body or in a comment on issue #160.
