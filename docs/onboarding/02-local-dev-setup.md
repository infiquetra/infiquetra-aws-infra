# 02 — Local Development Setup

What you need to install and configure to work on this repo.

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | **3.13+** | CDK code targets 3.13 |
| `uv` | latest | Python package + venv manager (replaces `pip`/`venv`/`pyenv`) |
| Node.js | 18+ | AWS CDK CLI is a Node.js tool |
| AWS CDK CLI | 2.x | `npm install -g aws-cdk` |
| AWS CLI | **>= 2.15.0** | Older versions don't refresh SSO tokens correctly |
| `git` | any modern | Source control |
| `gh` | latest | GitHub CLI for PR / workflow operations |
| `graphviz` | any | **Only if you regenerate diagrams** (`brew install graphviz`) |

## Quick install (macOS)

```bash
# Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Tools
brew install uv node awscli gh
npm install -g aws-cdk

# Verify versions
python3 --version          # should print 3.13.x or higher
uv --version
node --version             # 18+
cdk --version              # 2.x
aws --version              # 2.15.0+
gh --version
```

## Quick install (Linux)

```bash
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js
# See https://github.com/nodesource/distributions for distro-specific install

# AWS CDK CLI
npm install -g aws-cdk

# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install

# GitHub CLI
# See https://github.com/cli/cli/blob/trunk/docs/install_linux.md
```

## Clone the repo

```bash
# SSH (preferred if you have an SSH key configured for GitHub)
git clone git@github.com:infiquetra/infiquetra-aws-infra.git
cd infiquetra-aws-infra

# HTTPS alternative
git clone https://github.com/infiquetra/infiquetra-aws-infra.git
cd infiquetra-aws-infra
```

## Set up the Python environment

This repo uses `uv` for everything Python:

```bash
# Creates .venv/ and installs all dependencies (incl. dev)
uv sync

# Verify
uv run python -c "import aws_cdk; print(aws_cdk.__version__)"
```

You don't need to manually `source .venv/bin/activate`. The `uv run` prefix handles venv activation transparently.

If you prefer to activate the venv anyway:

```bash
source .venv/bin/activate
# Now `python`, `cdk`, `pytest`, etc. all use the venv
```

## Pre-commit hooks (recommended)

```bash
uv run pre-commit install
```

This runs ruff, mypy, and bandit on every commit. The same checks run in CI on PRs, so installing locally just gives you faster feedback.

## Set up AWS access

See [`01-getting-aws-access.md`](01-getting-aws-access.md) for the SSO config + login steps. Verify you're in:

```bash
aws sts get-caller-identity --profile infiquetra-root
```

## CDK bootstrap (already done — don't redo)

CDK requires a "bootstrap" deployment per account+region for asset uploads, etc. **This is already done for `645166163764` in `us-east-1`** — you do not need to run `cdk bootstrap`.

You only need to run it if you're deploying to a new AWS account for the first time, which is rare and should be coordinated with the admin.

## Verify everything works end-to-end

```bash
# Synthesize all stacks (no AWS write — just generates CFN templates locally)
uv run cdk synth --all --quiet --profile infiquetra-root
```

Expected: no errors, no output (the `--quiet` flag suppresses success output). If you see an error, check:

1. `aws sts get-caller-identity --profile infiquetra-root` — are you logged in?
2. `uv sync` — are dependencies up to date?
3. `cdk --version` — is CDK CLI installed globally?

Output (CFN templates) goes into `cdk.out/` (gitignored).

## Quality checks

Run all of these before pushing — they're what CI runs:

```bash
# Format and lint
uv run ruff check .
uv run ruff format .

# Type checking
uv run mypy .

# Security scan
uv run bandit -r infiquetra_aws_infra/ github-oidc-bootstrap/

# Or all at once via pre-commit
uv run pre-commit run --all-files
```

## Recommended editor setup

The repo uses ruff for both linting and formatting (replaces black, flake8, isort).

### VS Code

Install:

- **Python** (Microsoft)
- **Ruff** (Astral Software) — provides format-on-save + diagnostic squigglies
- **Pylance** (Microsoft) — type checking integrated with mypy config

The `pyproject.toml` already configures both ruff and mypy; the extensions pick up settings automatically.

### Other editors

ruff is available as an LSP (`ruff server`). Most modern editors with LSP support work — see https://docs.astral.sh/ruff/editors/ for setup.

## What you can do now

| Task | Command |
|---|---|
| Run the full test/lint suite locally | `uv run pre-commit run --all-files` |
| See what CDK would deploy | `uv run cdk synth --all --quiet` |
| See diff vs. live AWS state | `uv run cdk diff --all --profile infiquetra-root` |
| Manually deploy a stack | `uv run cdk deploy InfiquetraOrganizationStack --profile infiquetra-root` |
| Open a PR | `gh pr create --fill` |
| Watch a workflow run | `gh run watch <RUN_ID> --repo infiquetra/infiquetra-aws-infra` |

## Optional: regenerating documentation diagrams

The PNGs in `docs/ops/diagrams/` are committed to git. If you change the diagram source (`docs/ops/diagrams/generate.py`):

```bash
brew install graphviz                              # one-time
uv run python docs/ops/diagrams/generate.py        # regenerates all 5 PNGs
```

Commit the regenerated PNGs alongside any source changes.
