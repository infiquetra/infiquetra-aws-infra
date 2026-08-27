---
title: Align sub-project floors, pip fallback, and Bandit config with the Python Toolchain Standard
type: fix
status: active
date: 2026-08-27
origin: https://github.com/infiquetra/infiquetra-aws-infra/issues/160
backend: inline
deepened: 2026-08-27
---

# Align sub-project floors, pip fallback, and Bandit config with the Python Toolchain Standard

## Summary

Bring `infiquetra-aws-infra` into real compliance with the published Python Toolchain Standard by closing the three pre-existing gaps left after PR #159: stale sub-project floors, a pip fallback that cannot reproduce the gates, and a curated Bandit config that never loads.

---

## Problem Frame

PR #159 (merged as `078c310`, 2026-08-22) correctly aligned the three root `.pre-commit-config.yaml` hook revisions to the floors in `infiquetra-context-library` at that date (`ruff v0.12.5`, `mypy v1.17.0`, `bandit 1.8.6`). Independent review surfaced three gaps that that narrow bump did not close, filed as issue #160. All three are verified on `origin/main` at `078c310`.

The standard has since moved forward. `infiquetra-context-library` `docs/repositories/python-toolchain.md` (`accepted`, last reviewed `2026-08-26`, commit `9759385`) now publishes exact pins, not floors, and a wired Bandit hook:

| tool | issue #160 floor | current published exact pin | current root `pyproject.toml` | current `github-oidc-bootstrap/pyproject.toml` |
|------|-----------------|-----------------------------|-------------------------------|-----------------------------------------------|
| ruff | `>=0.12.5` | `==0.15.18` | `>=0.12.5` | `>=0.1.0` |
| mypy | `>=1.17.0` | `==2.1.0` | `>=1.17.0` | `>=1.8.0` |
| bandit | `>=1.8.6` | `==1.9.4` | `>=1.8.6` | `>=1.7.5` |

Hook block in the published standard now requires `bandit` args `["--configfile", "pyproject.toml", "--format", "json"]` and `additional_dependencies: ["pbr", "bandit[toml]"]`. The root repo still carries `args: [--format, json]` and `["pbr"]` at `.pre-commit-config.yaml:21-24`.

The three gaps therefore remain, but the target has moved from "at or above the 2026-08-22 floor" to "exactly the 2026-08-26 pin, with the hook wiring the standard prescribes". This plan targets the current published standard and records the drift from the issue's floor wording as corrected evidence. The issue's non-goal "Do NOT change the three root hook revisions" is superseded by the standard's own 2026-08-26 move (`9759385` bumps all three revs); this supersession is recorded here and will be noted on the issue/PR.

**Gap 1 — Sub-project floors stale.** `github-oidc-bootstrap/pyproject.toml:28-30` declares `bandit>=1.7.5`, `mypy>=1.8.0`, `ruff>=0.1.0` while the root hooks already run `0.12.5`/`1.17.0`/`1.8.6` over that directory. Twelve minor versions of ruff skew. Verified by `grep -nE "ruff|mypy|bandit" github-oidc-bootstrap/pyproject.toml`.

**Gap 2 — Pip fallback cannot reproduce the gates.** `requirements.txt:1-4` lists only runtime deps (`aws-cdk-lib`, `constructs`, `boto3`, `python-dotenv`) with no ruff/mypy/bandit entry. `requirements-dev.txt:4` pins `bandit>=1.7.0` below the published pin. `AGENTS.md:397` and `.claude/CLAUDE.md:462` both state `requirements.txt` is maintained for pip compatibility, which the issue files under `CLAUDE.md` (repo-root path in the issue is stale — the file lives at `.claude/CLAUDE.md:462`). Anyone following the documented pip path gets a toolchain that cannot reproduce the gates. Corrected evidence: the `bandit>=1.7.0` pin the issue attributes to `requirements.txt` lives in `requirements-dev.txt:4`. The published standard at `docs/repositories/python-toolchain.md:42` states "Do not use `poetry` or bare `pip` for project dependency management" — bare-pip is not a supported project-management path for the gate tools.

**Gap 3 — Curated TOML Bandit config never loads; ini `.bandit` does.** Two configs exist: `.bandit:1-4` (ini, `skips = B404`, broad `tests =` allowlist of 42 test IDs) and `pyproject.toml:130-135` (`[tool.bandit]` `skips = ["B101","B601"]`, `[tool.bandit.assert_used]`). Verified empirically at bandit 1.8.6: bare `uv run bandit -r . -v` logs `[main] INFO Found project level .bandit file: ./.bandit` and applies its `tests`/`skips` — `.bandit` **does** auto-discover as ini and is the de-facto config in CI (`reusable-security-scan.yml:58` runs `uv run bandit -r . -f json` without `-c`). Conversely `uv run bandit -c pyproject.toml -r . -v` logs `profile exclude tests: B601,B101` but also `Non-exclusive include/exclude test sets: {'B101','B601'}` while `.bandit` exists, because bandit merges the ini's `tests =` allowlist with the TOML's `skips`. The curated TOML config never loads today because `bandit[toml]` is absent from the hook and `-c pyproject.toml` is never passed.

---

## Requirements

R1. `github-oidc-bootstrap/pyproject.toml` dev pins equal the current published exact pins (`ruff==0.15.18`, `mypy==2.1.0`, `bandit==1.9.4`) and its `uv.lock` resolves to those exact versions.

R2. Root `pyproject.toml` dev pins equal the same exact pins, and root `uv.lock` resolves to those exact versions, with `.pre-commit-config.yaml` `rev:` lines equal to the same pins (`ruff-pre-commit v0.15.18`, `mirrors-mypy v2.1.0`, `bandit 1.9.4`).

R3. The docs no longer present `requirements.txt` as a supported install path for the gate toolchain; `uv sync` is the only supported method per the published standard. `requirements.txt` and `requirements-dev.txt` are retained only as legacy runtime manifests or removed, and no longer claim to reproduce the gates.

R4. Exactly one Bandit config is authoritative, it is the `[tool.bandit]` block in `pyproject.toml` matching the published standard and extended for this repo's layout (`exclude_dirs` covers `tests`, `.venv`, `build`, `cdk.out`, `node_modules` and basename-excludes `tests` at any depth, preserving the hook's `github-oidc-bootstrap/tests` coverage), `.bandit` is removed, every Bandit invocation (pre-commit hook and CI) passes `--configfile pyproject.toml` with `bandit[toml]` installed, and the comparison scan between the old and new configs is recorded.

R5. `uv run bandit -c pyproject.toml -r .` runs with the curated excludes demonstrably applied (evidence is `exclude tests: B101,B601` in bandit verbose output and exit 0, with the `Non-exclusive` error absent after `.bandit` deletion).

R6. Full CI green on the PR: `ruff check`, `ruff format --check`, `mypy`, `bandit -c pyproject.toml -r .`, `pre-commit run --all-files`, `uv run pytest -q` (verified to pass at `078c310` on 2026-08-27 — this gate is not pre-existing broken), `cdk synth --all --quiet`, and the pull-request-validation workflow.

---

## Key Technical Decisions

KTD1. Target the current published exact pins (`ruff==0.15.18`, `mypy==2.1.0`, `bandit==1.9.4`), not the issue's floor wording (`>=0.12.5` etc.): the standard now enforces equality via `scripts/check_docs.py`, and `uv.lock` can only guarantee local-hook/CI agreement when the pin is exact. The issue's floor language is stale by five days; carrying a `>=` floor while the hook runs an exact `rev:` reintroduces the local-versus-gate skew the consistency rule exists to prevent. This supersedes the issue's "floors at or above" acceptance wording and its "do NOT change revs" non-goal, with the supersession linked to context-library commit `9759385` (2026-08-26).

KTD2. Authoritative Bandit config is `[tool.bandit]` in `pyproject.toml`; delete `.bandit`: the published standard's Bandit block is `[tool.bandit]` in `pyproject.toml`, CI and pre-commit already run from the repo root where `pyproject.toml` lives, and `bandit[toml]` is the mechanism that makes TOML parsing work. `.bandit` is ini-shaped, diverges (`skips = B404` vs `B101,B601`, inclusive `tests` allowlist of 42 IDs vs curated excludes), merges with the TOML config to produce `Non-exclusive include/exclude` (verified by `uv run bandit -c pyproject.toml -r .` exiting 2 while `.bandit` exists), and would re-enable ~40 checks if silently dropped. Deleting `.bandit` first and extending the TOML `exclude_dirs` removes the ambiguity the issue asks to resolve, but the coverage delta must be comparison-scanned before deleting (KTD4).

KTD3. Drop the pip fallback as a supported gate-toolchain path; `uv sync` is the only supported method: the published standard forbids bare-pip for project dependency management, and the issue itself offers "stop presenting it as a supported install path" as the second branch. Keeping a pip path that carries gate pins contradicts the standard without benefit, since CI and local hooks both use `uv`. `requirements.txt`/`requirements-dev.txt` are left as legacy runtime manifests (or removed) and the docs are updated to state `uv sync --dev` is required; this is scope-preserving because the issue explicitly allows this branch, and it aligns with the standard.

KTD4. Wire the config explicitly in both call sites — pre-commit hook `args: [--configfile, pyproject.toml, --format, json]` and `reusable-security-scan.yml` `uv run bandit -c pyproject.toml -r .` — and add `bandit[toml]` to the hook's `additional_dependencies`, **and** extend `pyproject.toml` `exclude_dirs` to `["tests", ".venv", "build", "cdk.out", "node_modules", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"]` while **retaining** the pre-commit hook's `exclude: ^(tests/|github-oidc-bootstrap/tests/)` (pre-commit-level file exclusion, distinct from bandit's `exclude_dirs`). Bandit only reads TOML when `bandit[toml]` is installed and `-c` is passed; without both, the curated `skips` silently do not apply. The hook's `exclude` covers `github-oidc-bootstrap/tests` at the pre-commit layer, and the TOML's `tests` basename covers it at the CI layer (any directory named `tests` is excluded). A one-time comparison scan (`uv run bandit -r . --format json` on the old tree vs `uv run bandit -c pyproject.toml -r .` after the change) is recorded as verification that the deletion does not silently introduce unexpected new findings.

KTD5. Keep `github-oidc-bootstrap` as a separate `uv` project with its own `pyproject.toml`/`uv.lock`, but align its gate pins to the same exact versions: the sub-project is intentionally separate (different `requires-python = ">=3.11"` at `github-oidc-bootstrap/pyproject.toml:14`, different `target-version = "py311"`). Aligning the gate pins does not require merging the projects; it reuses the existing `uv.lock` per project. A follow-up to unify on `>=3.13` is deferred (scope boundary).

KTD6. No drift-guard script in this change; verification is the three grep commands from the issue plus `pre-commit run --all-files` and CI: a mechanical `scripts/check_toolchain.py` equality guard is valuable but is a new gate with its own lifecycle — adding it here widens scope. Note it as a follow-up and rely on the published `check_docs.py` pattern for the next bump.

---

## Implementation Units

### U1. Align sub-project gate pins and lockfile

Bring the secondary Python project into exact agreement with the published standard.

**Goal:** Update `github-oidc-bootstrap/pyproject.toml` and its `uv.lock` so its gate tool versions exactly match the root and the published pins.

**Requirements:** R1.

**Dependencies:** None.

**Files:** `github-oidc-bootstrap/pyproject.toml`, `github-oidc-bootstrap/uv.lock`.

**Approach:** In `github-oidc-bootstrap/pyproject.toml:22-32` replace the dev group entries `ruff>=0.1.0`, `mypy>=1.8.0`, `bandit>=1.7.5` with `ruff==0.15.18`, `mypy==2.1.0`, `bandit==1.9.4`. Keep `requires-python = ">=3.11"` and `target-version = "py311"` unchanged (KTD5). Run `uv lock` inside `github-oidc-bootstrap/` to regenerate `uv.lock` and verify `grep -nE "ruff|mypy|bandit" github-oidc-bootstrap/pyproject.toml` shows the exact pins.

**Patterns to follow:** Root `pyproject.toml:16-38` dev group shape; `infiquetra-context-library` `docs/repositories/python-toolchain.md` Toolchain Version Pins block.

**Test scenarios:** No new unit test — verification is command output. `grep -nE "ruff|mypy|bandit" github-oidc-bootstrap/pyproject.toml` must show `==0.15.18`, `==2.1.0`, `==1.9.4`. `uv sync --dev` inside the sub-project must succeed. Existing bootstrap tests `uv run pytest` inside `github-oidc-bootstrap/` must still pass.

**Verification:** `grep -nE "ruff|mypy|bandit" github-oidc-bootstrap/pyproject.toml` and `grep -AE2 'name = "ruff"|name = "mypy"|name = "bandit"' github-oidc-bootstrap/uv.lock | head`.

---

### U2. Align root gate pins, hook revs, and lockfile

Close the root-side drift that appeared when the published standard moved forward after PR #159. Ordering is load-bearing: this unit's verification assumes `.bandit` is already deleted (U3), per D1.

**Goal:** Make root `pyproject.toml`, `uv.lock`, and `.pre-commit-config.yaml` exactly equal to the published pins, so local hooks and CI run the same versions.

**Requirements:** R2, R5, R6.

**Dependencies:** U1, U3.

**Files:** `pyproject.toml`, `.pre-commit-config.yaml`, `uv.lock`.

**Approach:** In `pyproject.toml:16-38` replace `ruff>=0.12.5`, `mypy>=1.17.0`, `bandit>=1.8.6` with `ruff==0.15.18`, `mypy==2.1.0`, `bandit==1.9.4`. In `.pre-commit-config.yaml:1-24` set `astral-sh/ruff-pre-commit` rev to `v0.15.18`, `pre-commit/mirrors-mypy` rev to `v2.1.0`, `PyCQA/bandit` rev to `1.9.4`, and update the bandit hook per U3 wiring (retain `exclude: ^(tests/|github-oidc-bootstrap/tests/)` while adding `--configfile`). Run `uv lock` at repo root and `uv sync --dev`. Confirm `grep -nE "ruff|mypy|bandit" pyproject.toml` and hook `rev:` lines match the pins. This unit must not be verified until U3 has deleted `.bandit`, otherwise `uv run bandit -c pyproject.toml -r .` fails with `Non-exclusive include/exclude` (D1).

**Patterns to follow:** Published standard Pre-commit Hooks block (`ruff v0.15.18`, `mypy v2.1.0`, `bandit 1.9.4`); `scripts/check_docs.py` equality enforcement in context-library.

**Test scenarios:** `pre-commit run --all-files` passes with the new revs (after U3). `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` pass. `uv run bandit -c pyproject.toml -r .` exits 0 with `profile exclude tests: B101,B601` and no `Non-exclusive` error. `cdk synth --all --quiet` produces templates (no infra change expected, but synth must not break). `uv run pytest -q` passes (verified at `078c310` on 2026-08-27).

**Verification:** `grep -nE "ruff|mypy|bandit" pyproject.toml`, `grep -nE "rev:|bandit" .pre-commit-config.yaml`, `uv run ruff --version`, `uv run mypy --version`, `uv run bandit --version`.

---

### U3. Make Bandit config authoritative and wire it into every invocation

Resolve the "curated config that never loads" gap. This unit must run before U2's verification (D1).

**Goal:** Delete the auto-discovered `.bandit` ini, extend `[tool.bandit]` in `pyproject.toml` to preserve intended exclusions, and pass it explicitly everywhere bandit runs.

**Requirements:** R4, R5.

**Dependencies:** None.

**Files:** `.bandit` (delete), `pyproject.toml` (extend `[tool.bandit]` `exclude_dirs`), `.pre-commit-config.yaml` (wire `--configfile` and `bandit[toml]`; retain `exclude: ^(tests/|github-oidc-bootstrap/tests/)`), `.github/workflows/reusable-security-scan.yml` (wire `--configfile`).

**Approach:** First run a comparison capture: `uv run bandit -r . -f json -o /tmp/bandit-before.json` and `uv run bandit -r . -v 2>&1 | head -20` to freeze the 42-test allowlist behavior, then after wiring run `uv run bandit -c pyproject.toml -r . -f json -o /tmp/bandit-after.json` and diff the finding counts to assess the coverage delta from deleting the allowlist (D5); record the before/after counts in the PR body (not just `/tmp`, which is ephemeral). Delete `.bandit`. Extend `pyproject.toml:130-135` `exclude_dirs` from `["tests", ".venv", "build"]` to `["tests", ".venv", "build", "cdk.out", "node_modules", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"]` — `tests` as a basename already excludes `github-oidc-bootstrap/tests` at any depth, and `cdk.out`/`node_modules` restore the `.bandit` `exclude =` coverage that the minimal standard omits (D3). In `.pre-commit-config.yaml:19-24` change the bandit hook from `args: [--format, json]` / `additional_dependencies: ["pbr"]` to `args: [--configfile, pyproject.toml, --format, json]` and `additional_dependencies: ["pbr", "bandit[toml]"]` per the published hook block, preserving `exclude: ^(tests/|github-oidc-bootstrap/tests/)`. In `reusable-security-scan.yml:58` change `uv run bandit -r . -f json -o bandit-report.json` to `uv run bandit -c pyproject.toml -r . -f json -o bandit-report.json`. Confirm `uv run bandit -c pyproject.toml -r . -v 2>&1 | head -20` shows `profile exclude tests: B601,B101` and no `Non-exclusive` error after deletion.

**Patterns to follow:** Published standard Pre-commit Hooks bandit block; `pyproject.toml:130-135` existing bandit block (extend, do not replace).

**Test scenarios:** `uv run bandit -c pyproject.toml -r .` exits 0 and reports `B101,B601` excludes. The comparison `before` vs `after` JSON shows the allowlist-to-curated delta is understood (new findings triaged as expected or TOML `skips` extended). `pre-commit run --all-files` bandit step shows the curated skips applied (verbose log when run with `-v`). `grep -n "bandit" .pre-commit-config.yaml` shows `--configfile` and `bandit[toml]`.

**Verification:** `ls .bandit` must report missing, `grep -A6 "tool.bandit" pyproject.toml` shows extended `exclude_dirs` and `skips = ["B101", "B601"]`, `grep -n "bandit" .pre-commit-config.yaml` shows `--configfile`, `grep -n "bandit" .github/workflows/reusable-security-scan.yml` shows `-c pyproject.toml`.

---

### U4. Remove pip fallback as a supported gate-toolchain path and clarify the docs

Align the docs with the standard's prohibition on bare-pip for project management.

**Goal:** Make `uv sync` the only documented supported method for the gate toolchain, and stop presenting `requirements.txt` as a way to reproduce the gates.

**Requirements:** R3, R6.

**Dependencies:** U2, U3.

**Files:** `requirements.txt`, `requirements-dev.txt` (if retained), `.claude/CLAUDE.md`, `AGENTS.md`, `README.md` (if it mentions pip).

**Approach:** In `.claude/CLAUDE.md:462` and `AGENTS.md:397` change the "Package Management — Primary: uv, Fallback: pip (requirements.txt maintained for compatibility)" wording to state `uv` is required and `requirements.txt`/`requirements-dev.txt` are not supported for gate-toolchain reproduction (they remain only as legacy runtime manifests or are removed; do not add gate pins to them). If the files are retained, add a header comment `# Legacy runtime manifest — not the gate toolchain. Use: uv sync --dev` and do not add `ruff`/`mypy`/`bandit` pins to them. Record the branch choice explicitly as the issue's second branch ("stop presenting it") and the standard's `Do not use bare pip` rule (KTD3).

**Patterns to follow:** `pyproject.toml:16-38` dev group is the source of truth; `docs/repositories/python-toolchain.md:42` prohibition.

**Test scenarios:** `grep -n "requirements.txt" .claude/CLAUDE.md AGENTS.md` shows the updated wording with no claim of pip compatibility for the gates. `grep -nE "ruff|mypy|bandit" requirements.txt` shows no gate pins (or the file is absent).

**Verification:** `grep -nE "ruff|mypy|bandit" requirements.txt`, `grep -nE "ruff|mypy|bandit" requirements-dev.txt`, `grep -n "requirements.txt" .claude/CLAUDE.md AGENTS.md`.

---

## Verification Gates

Local verification must be run and its output recorded on the PR.

```bash
# 1. Sub-project floors now meet the standard
grep -nE "ruff|mypy|bandit" github-oidc-bootstrap/pyproject.toml

# 2. Root floors and hook revs meet the standard
grep -nE "ruff|mypy|bandit" pyproject.toml
grep -nE "rev:|bandit" .pre-commit-config.yaml

# 3. The pip path is no longer presented as supported for the gates
grep -n "requirements.txt" .claude/CLAUDE.md AGENTS.md
grep -nE "ruff|mypy|bandit" requirements.txt; echo "requirements exit: $?"

# 4. The Bandit config actually loads (should reflect curated skips, not defaults)
uv run bandit -c pyproject.toml -r . -v 2>&1 | head -20
echo "bandit exit: $?"
ls .bandit 2>&1; echo "ls exit: $?"

# 5. Coverage delta understood
# (run before/after JSON captures as described in U3 Approach and record counts)

# 6. Full local gates
pre-commit run --all-files
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run bandit -c pyproject.toml -r .
uv run pytest -q
uv run cdk synth --all --quiet
```

CI expectation: `pull-request-validation.yml` code-quality, security-scan, and cdk-synthesis jobs green. `uv run pytest -q` was pre-verified to pass at `078c310` on 2026-08-27.

---

## Risks & Dependencies

| risk | impact | mitigation |
|------|--------|------------|
| Bumping root pins from `>=0.12.5` to `==0.15.18` surfaces new ruff/mypy findings | PR appears to introduce lint/type errors unrelated to the gap | Run `ruff check --fix` and `ruff format` after bump; `pre-commit run --all-files` must be green before pushing — new findings are real and must be fixed, not suppressed |
| `uv.lock` not regenerated after pin edit | Local `uv run` still resolves old versions while hooks run new ones — reintroduces the skew the plan closes | Run `uv lock` in both the root and `github-oidc-bootstrap/` and commit both lockfiles; verify with `uv run ruff --version` etc. |
| Deleting `.bandit` without comparison scan re-enables ~40 checks silently | Unexpected new bandit findings in PR | U3 requires before/after JSON comparison; extend TOML `skips` if findings are intentional noise, otherwise fix the code |
| `bandit[toml]` missing from hook deps causes TOML parse to still be inert | `--configfile pyproject.toml` silently ignored | Add `bandit[toml]` to hook `additional_dependencies`; verify verbose log shows `profile exclude tests: B101,B601` after deletion |
| `exclude_dirs` extension misses a directory that `.bandit` used to exclude | Bandit scans `cdk.out`/`node_modules` and reports large noise | Extended `exclude_dirs` restores `.bandit` coverage; verify with `uv run bandit -c pyproject.toml -r . -v` that excluded dirs are skipped |
| `requirements.txt` and `pyproject.toml` diverge again after this fix | Pip fallback drifts from uv source of truth | Follow-up: consider generating `requirements.txt` from `pyproject.toml` via `uv pip compile` or removing the pip fallback entirely; for now the docs state `uv` is required |
| Unit ordering still races | Verification fails because `.bandit` not yet deleted | U3 (`None`) → U2 (`U1,U3`) → U4 (`U2,U3`) dependency chain ensures deletion before verification; U1 and U3 may run in parallel (disjoint trees) but U2 waits for both |
| Concurrent mutation during execution | A second work thread mutating the same files mid-execution reintroduces the deleted `.bandit` or half-written `pyproject.toml` and fails the gates (observed during round-2 review) | Execute on a clean feature branch from a fresh `main` per `AGENTS.md` Mandatory Workflow; no concurrent thread mutates the same files during the run |

---

## Scope Boundaries

This plan does not re-open or amend PR #159's merge commit (`078c310`) — it builds on top of it.

This plan supersedes issue #160's "Do NOT change the three root hook revisions" non-goal and its "floors at or above `>=0.12.5`" acceptance wording: both are superseded by the published standard's own 2026-08-26 exact-pin move at `9759385`. The supersession is recorded here and must be noted on the issue/PR.

This plan does not fix `infiquetra-context-library` #87 (canonical mypy hook omits `pytest`); that defect is tracked upstream and is the reason the published standard's mypy hook now lists `pytest` and `types-pyyaml` — this plan adopts that list as published without re-deriving it.

This plan does not change `github-oidc-bootstrap` `requires-python = ">=3.11"` or `target-version = "py311"` — only the gate pins move.

This plan does not add a mechanical drift-guard script (`scripts/check_toolchain.py`); that is a deliberate follow-up (KTD6) to keep this change to dependency and config wiring only.

This plan does not migrate `flake8`/`black`/`isort` pins in `requirements-dev.txt` or `pyproject.toml` beyond the three gate tools — those remain as-is except for removing any claim that they reproduce the gates.

---

## Sources / Research

| source | evidence |
|--------|----------|
| `infiquetra-context-library` `docs/repositories/python-toolchain.md` (accepted, 2026-08-26, `9759385`) | Exact pins `bandit==1.9.4`, `mypy==2.1.0`, `ruff==0.15.18`; hook block with `bandit --configfile pyproject.toml`; `check_docs.py` equality enforcement; `Do not use bare pip` at line 42 |
| `origin/main` `078c310` | PR #159 diff: exactly three `rev:` lines changed in `.pre-commit-config.yaml`; `uv run pytest -q` verified passing at `078c310` on 2026-08-27 |
| `.pre-commit-config.yaml:1-24` | Current hook revs `v0.12.5`/`v1.17.0`/`1.8.6`, missing `--configfile`; `exclude: ^(tests/|github-oidc-bootstrap/tests/)` is pre-commit-level, distinct from bandit `exclude_dirs` |
| `pyproject.toml:16-38` vs `github-oidc-bootstrap/pyproject.toml:22-32` | Root at `>=0.12.5` etc., sub-project at `>=0.1.0`/`>=1.8.0`/`>=1.7.5` — twelve minor ruff gap |
| `requirements.txt:1-4`, `requirements-dev.txt:4`, `.claude/CLAUDE.md:462`, `AGENTS.md:397` | Pip fallback has no gate pins; dev file has `bandit>=1.7.0` below floor; std forbids bare pip |
| `.bandit:1-4` vs `pyproject.toml:130-135` | `.bandit` auto-discovers as ini (verified `Found project level .bandit file`) with 42-test allowlist; `[tool.bandit]` never loads; `bandit -c pyproject.toml` merges to `Non-exclusive include/exclude` while `.bandit` exists |
| `.github/workflows/reusable-security-scan.yml:58` | CI bandit invocation without `-c` |
| Direct runs 2026-08-27 | `uv run bandit -c pyproject.toml -r .` exits 2 while `.bandit` exists; exit 0 after deletion; `uv run bandit -r . -v` proves auto-discover |
| Issue #160 body + comments | Three P3 advisory gaps, out-of-scope list, acceptance criteria, four verification commands |
| PR #159 discussion + `gh pr view 159` | "The revisions are not hand-picked" — they mirror the published floors |
| Doc review `docs/reviews/2026-08-27-toolchain-subproject-pip-bandit-plan-review.md` | D1 P0 ordering, D2-D4 P1s, D5-D8 P2s; pins and line numbers verified |

---

## Open Questions

None — scope and target pins are settled by the current published standard. If the operator prefers to keep the issue's original floor target (`>=0.12.5`) and defer the exact-pin bump to a follow-up, say so and the plan will be trimmed to floors only.

