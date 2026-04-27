# Onboarding Documentation

Welcome to the `infiquetra-aws-infra` repository. This directory is for **first-time contributors** — whether that's a new team member, a future-you returning after a long break, or anyone who needs the "how do I get started" walkthrough.

> Audience: Newcomer with general software/AWS familiarity. For deeper operator-focused detail, see [`../ops/`](../ops/).

## What this repo is

`infiquetra-aws-infra` is the **infrastructure-as-code repository** for Infiquetra LLC's AWS footprint. It defines the AWS account organization (Organizations OUs, Service Control Policies) and the human/CI access model (Identity Center permission sets, GitHub Actions OIDC role) using AWS CDK in Python.

It is **not** application code. Application code for individual products (Media, Apps, Consulting business units) lives in separate repositories that deploy into the AWS accounts this repo provisions.

## What's in this repo (high-level)

```
infiquetra-aws-infra/
├── infiquetra_aws_infra/         ← The two main CDK stacks
│   ├── organization_stack.py     ← AWS Organizations OUs + SCPs
│   └── sso_stack.py              ← Identity Center permission sets
├── github-oidc-bootstrap/        ← Separate one-time CDK app for the GHA role
├── .github/workflows/            ← CI/CD pipelines (modular, reusable)
├── docs/
│   ├── ops/                      ← Comprehensive current-state docs (for the operator)
│   ├── onboarding/               ← You are here
│   └── learnings/                ← Knowledge base (LEARNINGS, DECISIONS, QUEUED, ARCHIVE)
├── app.py                        ← CDK app entry point
└── pyproject.toml                ← Python dependencies (managed by uv)
```

## Sections in this onboarding

| # | Section | When to read it |
|---|---|---|
| 01 | [Getting AWS Access](01-getting-aws-access.md) | First time you need to run anything against AWS |
| 02 | [Local Development Setup](02-local-dev-setup.md) | Before writing or running any code |
| 03 | [Making Changes](03-making-changes.md) | When you have a change to ship — branch, PR, deploy flow |
| 04 | [Troubleshooting](04-troubleshooting.md) | When something breaks (it will) |

## In a hurry?

Minimum viable path to "I can ship a one-line CDK change":

```bash
# 1. Get AWS access (see 01-getting-aws-access.md, requires admin to assign you)
aws sso login --profile infiquetra-root
aws sts get-caller-identity --profile infiquetra-root   # verify

# 2. Local setup (see 02-local-dev-setup.md)
git clone git@github.com:infiquetra/infiquetra-aws-infra.git
cd infiquetra-aws-infra
uv sync
brew install graphviz                                    # only if regenerating diagrams
npm install -g aws-cdk

# 3. Verify everything works
uv run cdk synth --all --quiet --profile infiquetra-root

# 4. Make a change, push, PR (see 03-making-changes.md)
git checkout main && git pull origin main
git checkout -b your-feature-branch
# ... edit code ...
ruff check . && ruff format . && mypy . && cdk synth --all
git commit -am "feat: your change"
git push -u origin your-feature-branch
gh pr create --fill
```

Once the PR's validation pipeline passes and a reviewer approves, merge to `main` triggers an automatic AWS deploy.

## Key things to know before you start

- **You can only do anything against AWS once an admin (currently `jefcox`) assigns you a permission set.** No self-service.
- **All deploys go through the CI/CD pipeline.** Local `cdk deploy` is allowed for debugging, but the source of truth is what `main` deploys.
- **The `main` branch auto-deploys to production.** Be deliberate about merges. Use the PR flow.
- **There are two separate CDK apps in this repo.** The main one at the root deploys org structure + SSO. The one at `github-oidc-bootstrap/` is a one-time-only app for setting up the GHA role and is not part of the regular CI/CD flow.
- **Knowledge captured in `docs/learnings/`.** When you discover something non-obvious, add an entry per the rules in `.claude/CLAUDE.md`.
