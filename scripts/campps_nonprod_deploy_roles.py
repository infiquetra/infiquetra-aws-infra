#!/usr/bin/env python3
"""Check and deploy CamppsNonProdDeployRolesStack, and nothing else, from the Mac.

This file is both the deploy script and the shared module the live diff test
(``tests/live/test_deploy_roles_stack_diff_live.py``) loads by path, so the gate's
checks and the deploy cannot drift apart (OD-20, plan issue 164 unit U8).

One action, no options::

    uv run python scripts/campps_nonprod_deploy_roles.py deploy

Every constant is fixed here, so no invocation can name ``--all``, the default
``app.py`` (``cdk.json``'s app, which targets the management account) or another
stack. Each run:

1. loads the ``campps-nonprod`` SSO credentials in-process from a boto3 session
   and hands them to child processes through their environment only, with
   ``AWS_PROFILE`` removed; the values are never printed and never put on a
   command line;
2. asserts the session's account is the CAMPPS nonprod account;
3. checks the pinned CDK CLI's version and that its ``diff`` accepts ``--method``
   (an older CLI silently ignores it and creates a change set);
4. synthesizes the stack into a temporary directory and compares its resources
   with the deployed template (CloudFormation ``GetTemplate``, read-only),
   ignoring ``AWS::CDK::Metadata``.

``deploy`` refuses any changed resource other than the one expected policy,
deploys nothing when nothing changed, re-checks the account immediately before
deploying, deploys the checked assembly, and then requires the changed set to be
empty.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3

ACCOUNT_ID = "477152411873"
PROFILE = "campps-nonprod"
REGION = "us-east-1"
APP = "python3 app_campps_bootstrap.py"
STACK = "CamppsNonProdDeployRolesStack"
EXPECTED_CHANGED_RESOURCE = "TenantSetupE2eCredentialsPolicyAC488617"
CDK_VERSION = "2.1144.0"
CDK_COMMAND: tuple[str, ...] = ("npx", "-y", f"aws-cdk@{CDK_VERSION}")
IGNORED_RESOURCE_TYPES = frozenset({"AWS::CDK::Metadata"})
REPO_ROOT = Path(__file__).resolve().parent.parent

_PROFILE_VARIABLES = ("AWS_PROFILE", "AWS_DEFAULT_PROFILE")
_CREDENTIAL_VARIABLES = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
)


class DeployRolesError(RuntimeError):
    """A check failed; nothing after it ran."""


@dataclass(frozen=True)
class Prepared:
    """The state every check and the deploy start from."""

    session: Any
    child_env: dict[str, str]
    assembly_dir: Path
    synthesized: dict[str, Any]
    changed: frozenset[str]


def load_session() -> Any:
    """Build the boto3 session for the nonprod SSO profile."""
    return boto3.Session(profile_name=PROFILE, region_name=REGION)


def assert_account(session: Any) -> None:
    """Fail unless the session's credentials belong to the nonprod account."""
    account = session.client("sts", region_name=REGION).get_caller_identity()["Account"]
    if account != ACCOUNT_ID:
        raise DeployRolesError(
            f"credentials are for account {account}, not {ACCOUNT_ID}; "
            "refusing before any CDK call"
        )
    print(f"account: {account}")


def child_env(session: Any, base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a child environment carrying the session's frozen credentials.

    ``AWS_PROFILE`` is removed, because the CDK CLI fails to assume the SSO
    profile's role while boto3 resolves it, and the region variables are pinned.
    """
    env = dict(os.environ if base is None else base)
    for name in _PROFILE_VARIABLES + _CREDENTIAL_VARIABLES:
        env.pop(name, None)
    credentials = session.get_credentials()
    if credentials is None:
        raise DeployRolesError(f"no credentials resolved for profile {PROFILE}")
    frozen = credentials.get_frozen_credentials()
    env["AWS_ACCESS_KEY_ID"] = frozen.access_key
    env["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
    if frozen.token:
        env["AWS_SESSION_TOKEN"] = frozen.token
    for name in ("AWS_REGION", "AWS_DEFAULT_REGION", "CDK_DEFAULT_REGION"):
        env[name] = REGION
    return env


def run_cdk(
    args: Sequence[str],
    env: Mapping[str, str],
    *,
    repo_root: Path = REPO_ROOT,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the pinned CDK CLI; credentials travel only in ``env``."""
    # Fixed argv, no shell; the arguments come from this module's constants.
    return subprocess.run(  # nosec B603
        [*CDK_COMMAND, *args],
        cwd=repo_root,
        env=dict(env),
        check=False,
        text=True,
        capture_output=capture,
    )


def check_cli(env: Mapping[str, str], *, repo_root: Path = REPO_ROOT) -> None:
    """Fail unless the pinned CLI runs and its ``diff`` accepts ``--method``."""
    version = run_cdk(["--version"], env, repo_root=repo_root, capture=True)
    reported = version.stdout.strip()
    if version.returncode != 0 or not reported.startswith(CDK_VERSION):
        raise DeployRolesError(
            f"CDK CLI reported {reported!r} (exit {version.returncode}); "
            f"expected {CDK_VERSION}"
        )
    print(f"cdk cli: {reported}")
    help_text = run_cdk(["diff", "--help"], env, repo_root=repo_root, capture=True)
    if help_text.returncode != 0 or "--method" not in help_text.stdout:
        raise DeployRolesError(
            "the pinned CDK CLI's diff does not list --method; refusing, because "
            "a CLI that ignores it would create a change set"
        )


def synthesize(
    env: Mapping[str, str], assembly_dir: Path, *, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    """Synthesize the stack into ``assembly_dir`` and return its template."""
    result = run_cdk(
        ["synth", "--app", APP, STACK, "--quiet", "-o", str(assembly_dir)],
        env,
        repo_root=repo_root,
    )
    if result.returncode != 0:
        raise DeployRolesError(f"cdk synth exited {result.returncode}")
    manifest = json.loads((assembly_dir / "manifest.json").read_text())
    artifact = manifest.get("artifacts", {}).get(STACK)
    if artifact is None:
        raise DeployRolesError(f"{STACK} is not in the synthesized assembly")
    template_file = artifact["properties"]["templateFile"]
    template: dict[str, Any] = json.loads((assembly_dir / template_file).read_text())
    return template


def deployed_template(session: Any) -> dict[str, Any]:
    """Read the deployed template, read-only."""
    body = session.client("cloudformation", region_name=REGION).get_template(
        StackName=STACK, TemplateStage="Original"
    )["TemplateBody"]
    template: dict[str, Any] = json.loads(body) if isinstance(body, str) else body
    return template


def changed_resources(
    synthesized: Mapping[str, Any], deployed: Mapping[str, Any]
) -> frozenset[str]:
    """Return the logical ids added, removed or changed, ignoring CDK metadata."""

    def resources(template: Mapping[str, Any]) -> dict[str, Any]:
        return {
            logical_id: resource
            for logical_id, resource in template.get("Resources", {}).items()
            if resource.get("Type") not in IGNORED_RESOURCE_TYPES
        }

    left, right = resources(synthesized), resources(deployed)
    return frozenset(
        logical_id
        for logical_id in left.keys() | right.keys()
        if left.get(logical_id) != right.get(logical_id)
    )


def prepare(assembly_dir: Path, *, repo_root: Path = REPO_ROOT) -> Prepared:
    """Credentials, account, pinned CLI, then the changed set."""
    session = load_session()
    assert_account(session)
    env = child_env(session)
    check_cli(env, repo_root=repo_root)
    synthesized = synthesize(env, assembly_dir, repo_root=repo_root)
    changed = changed_resources(synthesized, deployed_template(session))
    print(f"changed set: {sorted(changed)}")
    return Prepared(session, env, assembly_dir, synthesized, changed)


def run_template_diff(
    prepared: Prepared, *, fail: bool, repo_root: Path = REPO_ROOT
) -> subprocess.CompletedProcess[str]:
    """Run ``cdk diff --method=template`` (no change set) and print its output."""
    args = ["diff", "--app", APP, STACK, "--method=template"]
    if fail:
        args.append("--fail")
    result = run_cdk(args, prepared.child_env, repo_root=repo_root, capture=True)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return result


def pre_deploy_check(*, repo_root: Path = REPO_ROOT) -> frozenset[str]:
    """Pass only when exactly the one expected policy resource changes."""
    with tempfile.TemporaryDirectory(prefix="campps-deploy-roles-") as tmp:
        prepared = prepare(Path(tmp), repo_root=repo_root)
        if prepared.changed != {EXPECTED_CHANGED_RESOURCE}:
            raise DeployRolesError(
                f"expected exactly {{{EXPECTED_CHANGED_RESOURCE}}} to change, got "
                f"{sorted(prepared.changed)}; anything else is unapplied drift"
            )
        result = run_template_diff(prepared, fail=False, repo_root=repo_root)
        if result.returncode != 0:
            raise DeployRolesError(f"cdk diff exited {result.returncode}")
        return prepared.changed


def _git(args: Sequence[str], repo_root: Path) -> str:
    # Fixed argv, no shell; git is resolved from PATH like every repo tool.
    result = subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=repo_root, check=False, text=True, capture_output=True
    )
    if result.returncode != 0:
        raise DeployRolesError(f"git {' '.join(args)} exited {result.returncode}")
    return result.stdout.strip()


def assert_head_is_origin_main(repo_root: Path = REPO_ROOT) -> str:
    """Fail unless this worktree's HEAD is the freshly fetched origin/main."""
    _git(["fetch", "origin"], repo_root)
    head = _git(["rev-parse", "HEAD"], repo_root)
    main = _git(["rev-parse", "origin/main"], repo_root)
    if head != main:
        raise DeployRolesError(
            f"HEAD {head} is not origin/main {main}; only a worktree of merged "
            "main can prove the deployed stack equals main"
        )
    print(f"head: {head} (origin/main)")
    return head


def post_merge_check(*, repo_root: Path = REPO_ROOT) -> None:
    """Pass only when HEAD is origin/main and the deployed stack equals it."""
    assert_head_is_origin_main(repo_root)
    with tempfile.TemporaryDirectory(prefix="campps-deploy-roles-") as tmp:
        prepared = prepare(Path(tmp), repo_root=repo_root)
        if prepared.changed:
            raise DeployRolesError(
                f"deployed stack differs from main: {sorted(prepared.changed)}"
            )
        result = run_template_diff(prepared, fail=True, repo_root=repo_root)
        if result.returncode != 0:
            raise DeployRolesError(
                f"cdk diff --method=template --fail exited {result.returncode}"
            )


def deploy(*, repo_root: Path = REPO_ROOT) -> None:
    """Deploy the checked assembly of the one stack, or nothing."""
    with tempfile.TemporaryDirectory(prefix="campps-deploy-roles-") as tmp:
        prepared = prepare(Path(tmp), repo_root=repo_root)
        if not prepared.changed:
            print("nothing changed; deploying nothing")
            return
        if prepared.changed != {EXPECTED_CHANGED_RESOURCE}:
            raise DeployRolesError(
                f"refusing to deploy: changed set {sorted(prepared.changed)} is not "
                f"exactly {{{EXPECTED_CHANGED_RESOURCE}}}"
            )
        assert_account(prepared.session)
        result = run_cdk(
            [
                "deploy",
                "--app",
                str(prepared.assembly_dir),
                STACK,
                "--require-approval",
                "never",
            ],
            prepared.child_env,
            repo_root=repo_root,
        )
        if result.returncode != 0:
            raise DeployRolesError(f"cdk deploy exited {result.returncode}")
        after = changed_resources(
            prepared.synthesized, deployed_template(prepared.session)
        )
        print(f"changed set after deploy: {sorted(after)}")
        if after:
            raise DeployRolesError(
                f"deployed stack still differs after deploy: {sorted(after)}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["deploy"]:
        print("usage: campps_nonprod_deploy_roles.py deploy", file=sys.stderr)
        return 2
    try:
        deploy()
    except DeployRolesError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
