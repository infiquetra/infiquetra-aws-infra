"""Offline tests for the nonprod deploy-roles shared module and deploy script.

boto3 and every subprocess are stubbed; nothing here reaches AWS, git or npx.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "campps_nonprod_deploy_roles.py"
)
SENTINEL_ACCESS_KEY = "AKIASENTINELACCESS000"
SENTINEL_SECRET_KEY = "sentinel-secret-key-value-do-not-leak"  # noqa: S105
SENTINEL_TOKEN = "sentinel-session-token-value-do-not-leak"  # noqa: S105
POLICY_ID = "TenantSetupE2eCredentialsPolicyAC488617"
OTHER_ID = "IdentityAccessDeployRole0123ABCD"
METADATA_ID = "CDKMetadata"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "campps_nonprod_deploy_roles_under_test", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def template(**resources: dict[str, Any]) -> dict[str, Any]:
    return {"Resources": copy.deepcopy(resources)}


def policy(*secrets: str) -> dict[str, Any]:
    return {
        "Type": "AWS::IAM::ManagedPolicy",
        "Properties": {"PolicyDocument": {"Statement": [{"Resource": list(secrets)}]}},
    }


ROLE = {"Type": "AWS::IAM::Role", "Properties": {"RoleName": "r"}}
DEPLOYED = template(
    **{
        POLICY_ID: policy("old-a", "old-b"),
        OTHER_ID: ROLE,
        METADATA_ID: {"Type": "AWS::CDK::Metadata", "Properties": {"v": "1"}},
    }
)
WITH_POLICY_CHANGE = template(
    **{
        POLICY_ID: policy("store", "old-a", "old-b"),
        OTHER_ID: ROLE,
        METADATA_ID: {"Type": "AWS::CDK::Metadata", "Properties": {"v": "1"}},
    }
)


@dataclass
class FakeAws:
    accounts: list[str]
    deployed: dict[str, Any]
    calls: list[str] = field(default_factory=list)

    def session(self, **kwargs: Any) -> FakeSession:
        assert kwargs == {"profile_name": "campps-nonprod", "region_name": "us-east-1"}
        return FakeSession(self)


@dataclass
class FakeFrozen:
    access_key: str = SENTINEL_ACCESS_KEY
    secret_key: str = SENTINEL_SECRET_KEY
    token: str = SENTINEL_TOKEN


class FakeCredentials:
    def get_frozen_credentials(self) -> FakeFrozen:
        return FakeFrozen()


class FakeSession:
    def __init__(self, aws: FakeAws) -> None:
        self.aws = aws

    def get_credentials(self) -> FakeCredentials:
        return FakeCredentials()

    def client(self, service: str, **_: Any) -> Any:
        aws = self.aws

        class Client:
            def get_caller_identity(self) -> dict[str, str]:
                aws.calls.append("sts")
                accounts = aws.accounts
                account = accounts.pop(0) if len(accounts) > 1 else accounts[0]
                return {"Account": account}

            def get_template(self, **kwargs: Any) -> dict[str, Any]:
                assert kwargs == {
                    "StackName": "CamppsNonProdDeployRolesStack",
                    "TemplateStage": "Original",
                }
                aws.calls.append("get_template")
                return {"TemplateBody": copy.deepcopy(aws.deployed)}

        assert service in {"sts", "cloudformation"}
        return Client()


@dataclass
class FakeRunner:
    aws: FakeAws
    synthesized: dict[str, Any]
    version: str = "2.1144.0 (build abc)"
    diff_help: str = "Options:\n  --method  How to perform the diff\n"
    diff_rc: int = 0
    head: str = "a" * 40
    origin_main: str = "a" * 40
    argvs: list[list[str]] = field(default_factory=list)
    envs: list[dict[str, str] | None] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], **kwargs: Any) -> Any:
        argv = list(argv)
        self.argvs.append(argv)
        self.envs.append(kwargs.get("env"))
        if argv[0] == "git":
            self.aws.calls.append("git " + " ".join(argv[1:]))
            outputs = {
                "rev-parse HEAD": self.head,
                "rev-parse origin/main": self.origin_main,
            }
            out = outputs.get(" ".join(argv[1:]), "")
            return subprocess.CompletedProcess(argv, 0, out + "\n", "")
        assert argv[:3] == ["npx", "-y", "aws-cdk@2.1144.0"], argv
        command = argv[3]
        self.aws.calls.append(f"cdk {command}")
        if command == "--version":
            return subprocess.CompletedProcess(argv, 0, self.version + "\n", "")
        if command == "diff" and "--help" in argv:
            return subprocess.CompletedProcess(argv, 0, self.diff_help, "")
        if command == "synth":
            outdir = Path(argv[argv.index("-o") + 1])
            (outdir / "manifest.json").write_text(
                json.dumps(
                    {
                        "artifacts": {
                            "CamppsNonProdDeployRolesStack": {
                                "properties": {
                                    "templateFile": (
                                        "CamppsNonProdDeployRolesStack.template.json"
                                    )
                                }
                            }
                        }
                    }
                )
            )
            (outdir / "CamppsNonProdDeployRolesStack.template.json").write_text(
                json.dumps(self.synthesized)
            )
            return subprocess.CompletedProcess(argv, 0, None, None)
        if command == "diff":
            rc = self.diff_rc if "--fail" in argv else 0
            return subprocess.CompletedProcess(argv, rc, "Stack diff output\n", "")
        if command == "deploy":
            self.aws.deployed = copy.deepcopy(self.synthesized)
            return subprocess.CompletedProcess(argv, 0, None, None)
        raise AssertionError(f"unexpected command {argv}")

    def cdk_argvs(self) -> list[list[str]]:
        return [argv for argv in self.argvs if argv[0] != "git"]

    def cdk(self, command: str) -> list[list[str]]:
        return [
            argv
            for argv in self.cdk_argvs()
            if argv[3] == command and "--help" not in argv
        ]


@pytest.fixture
def harness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[ModuleType, FakeAws, FakeRunner]:
    module = load_module()
    aws = FakeAws(accounts=["477152411873"], deployed=copy.deepcopy(DEPLOYED))
    runner = FakeRunner(aws=aws, synthesized=copy.deepcopy(WITH_POLICY_CHANGE))
    monkeypatch.setattr(module.boto3, "Session", aws.session)
    monkeypatch.setattr(module.subprocess, "run", runner)
    monkeypatch.setenv("AWS_PROFILE", "campps-nonprod")
    monkeypatch.setenv("AWS_DEFAULT_PROFILE", "campps-nonprod")
    return module, aws, runner


def test_refuses_wrong_account(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, aws, runner = harness
    aws.accounts = ["645166163764"]
    for action in (module.deploy, module.pre_deploy_check, module.post_merge_check):
        with pytest.raises(module.DeployRolesError, match="645166163764"):
            action()
    assert runner.cdk_argvs() == []
    assert module.main(["deploy"]) == 1
    assert runner.cdk_argvs() == []


def test_credentials_never_in_argv_or_output(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
    capsys: pytest.CaptureFixture[str],
) -> None:
    module, _, runner = harness
    module.pre_deploy_check()
    assert module.main(["deploy"]) == 0
    runner.diff_rc = 0
    module.post_merge_check()
    captured = capsys.readouterr()
    sentinels = (SENTINEL_ACCESS_KEY, SENTINEL_SECRET_KEY, SENTINEL_TOKEN)
    for argv in runner.argvs:
        for sentinel in sentinels:
            assert all(sentinel not in arg for arg in argv), argv
    for sentinel in sentinels:
        assert sentinel not in captured.out
        assert sentinel not in captured.err
    cdk_envs = [
        env
        for argv, env in zip(runner.argvs, runner.envs, strict=True)
        if argv[0] != "git"
    ]
    assert cdk_envs
    for env in cdk_envs:
        assert env is not None
        assert env["AWS_ACCESS_KEY_ID"] == SENTINEL_ACCESS_KEY
        assert env["AWS_SECRET_ACCESS_KEY"] == SENTINEL_SECRET_KEY
        assert env["AWS_SESSION_TOKEN"] == SENTINEL_TOKEN


def test_aws_profile_removed_from_child_env(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    module.pre_deploy_check()
    cdk_envs = [
        env
        for argv, env in zip(runner.argvs, runner.envs, strict=True)
        if argv[0] != "git"
    ]
    assert cdk_envs
    for env in cdk_envs:
        assert env is not None
        assert "AWS_PROFILE" not in env
        assert "AWS_DEFAULT_PROFILE" not in env
        assert env["AWS_REGION"] == "us-east-1"
        assert env["AWS_DEFAULT_REGION"] == "us-east-1"
        assert env["CDK_DEFAULT_REGION"] == "us-east-1"


def test_cdk_cli_version_is_pinned(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    module.pre_deploy_check()
    module.deploy()
    module.post_merge_check()
    assert runner.cdk_argvs()
    for argv in runner.cdk_argvs():
        assert argv[:3] == ["npx", "-y", "aws-cdk@2.1144.0"], argv
        assert "--all" not in argv
        assert "app.py" not in " ".join(argv).replace("app_campps_bootstrap.py", "")


def test_cdk_cli_wrong_version_refused(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    runner.version = "2.1029.1 (build 1)"
    with pytest.raises(module.DeployRolesError, match=r"2\.1144\.0"):
        module.deploy()
    assert runner.cdk("synth") == []
    assert runner.cdk("deploy") == []


def test_cdk_cli_without_method_option_refused(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    runner.diff_help = "Options:\n  --fail\n"
    with pytest.raises(module.DeployRolesError, match="--method"):
        module.pre_deploy_check()
    assert runner.cdk("synth") == []


@pytest.mark.parametrize(
    "synthesized",
    [
        pytest.param(copy.deepcopy(DEPLOYED), id="empty"),
        pytest.param(
            template(
                **{
                    POLICY_ID: policy("old-a", "old-b"),
                    OTHER_ID: {"Type": "AWS::IAM::Role", "Properties": {"x": 1}},
                }
            ),
            id="another-resource",
        ),
        pytest.param(
            template(
                **{
                    POLICY_ID: policy("store", "old-a", "old-b"),
                    OTHER_ID: ROLE,
                    "NewRole": ROLE,
                }
            ),
            id="policy-plus-another",
        ),
    ],
)
def test_pre_deploy_requires_exactly_the_policy_change(
    harness: tuple[ModuleType, FakeAws, FakeRunner], synthesized: dict[str, Any]
) -> None:
    module, _, runner = harness
    runner.synthesized = synthesized
    with pytest.raises(module.DeployRolesError, match="unapplied drift"):
        module.pre_deploy_check()
    assert runner.cdk("diff") == []


def test_pre_deploy_passes_on_the_policy_alone(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
    capsys: pytest.CaptureFixture[str],
) -> None:
    module, _, runner = harness
    assert module.pre_deploy_check() == frozenset({POLICY_ID})
    diffs = runner.cdk("diff")
    assert len(diffs) == 1
    assert "--method=template" in diffs[0]
    assert "--fail" not in diffs[0]
    assert diffs[0][diffs[0].index("--app") + 1] == "python3 app_campps_bootstrap.py"
    assert "CamppsNonProdDeployRolesStack" in diffs[0]
    out = capsys.readouterr().out
    assert "Stack diff output" in out
    assert "account: 477152411873" in out
    assert "cdk cli: 2.1144.0" in out
    assert runner.cdk("deploy") == []


def test_cdk_metadata_difference_ignored(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    synthesized = copy.deepcopy(WITH_POLICY_CHANGE)
    synthesized["Resources"][METADATA_ID]["Properties"]["v"] = "2"
    synthesized["Resources"]["CDKMetadataExtra"] = {
        "Type": "AWS::CDK::Metadata",
        "Properties": {},
    }
    runner.synthesized = synthesized
    assert module.pre_deploy_check() == frozenset({POLICY_ID})
    assert module.changed_resources(synthesized, synthesized) == frozenset()


def test_deploy_refuses_unexpected_change(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    synthesized = copy.deepcopy(WITH_POLICY_CHANGE)
    synthesized["Resources"][OTHER_ID] = {"Type": "AWS::IAM::Role", "Properties": {}}
    runner.synthesized = synthesized
    with pytest.raises(module.DeployRolesError, match="refusing to deploy"):
        module.deploy()
    assert runner.cdk("deploy") == []
    assert module.main(["deploy"]) == 1


def test_deploy_uses_the_checked_assembly_and_only_the_stack(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, aws, runner = harness
    module.deploy()
    synths = runner.cdk("synth")
    deploys = runner.cdk("deploy")
    assert len(synths) == 1
    assert len(deploys) == 1
    assembly_dir = synths[0][synths[0].index("-o") + 1]
    deploy_argv = deploys[0]
    assert deploy_argv[deploy_argv.index("--app") + 1] == assembly_dir
    stack_args = [arg for arg in deploy_argv[4:] if arg.endswith("Stack")]
    assert stack_args == ["CamppsNonProdDeployRolesStack"]
    assert "--all" not in deploy_argv
    assert deploy_argv[-2:] == ["--require-approval", "never"]
    assert aws.calls.count("get_template") == 2


def test_deploy_fails_when_stack_still_differs_after_deploy(
    harness: tuple[ModuleType, FakeAws, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, _, runner = harness
    real = runner.__call__

    def no_op_deploy(argv: Sequence[str], **kwargs: Any) -> Any:
        if list(argv)[3:4] == ["deploy"]:
            runner.argvs.append(list(argv))
            runner.envs.append(kwargs.get("env"))
            return subprocess.CompletedProcess(list(argv), 0, None, None)
        return real(argv, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", no_op_deploy)
    with pytest.raises(module.DeployRolesError, match="still differs"):
        module.deploy()


def test_account_checked_again_immediately_before_deploy(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, aws, runner = harness
    module.deploy()
    deploy_index = aws.calls.index("cdk deploy")
    assert aws.calls[deploy_index - 1] == "sts"
    assert aws.calls.count("sts") == 2

    aws.calls.clear()
    aws.deployed = copy.deepcopy(DEPLOYED)
    aws.accounts = ["477152411873", "999999999999"]
    runner.argvs.clear()
    with pytest.raises(module.DeployRolesError, match="999999999999"):
        module.deploy()
    assert runner.cdk("deploy") == []


def test_deploy_with_empty_changed_set_deploys_nothing(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
    capsys: pytest.CaptureFixture[str],
) -> None:
    module, _, runner = harness
    runner.synthesized = copy.deepcopy(DEPLOYED)
    assert module.main(["deploy"]) == 0
    assert runner.cdk("deploy") == []
    assert "deploying nothing" in capsys.readouterr().out


def test_main_accepts_only_deploy(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    for argv in ([], ["diff"], ["deploy", "--all"], ["deploy", "extra"]):
        assert module.main(argv) == 2
    assert runner.argvs == []


def test_post_merge_refuses_when_head_is_not_origin_main(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, aws, runner = harness
    runner.synthesized = copy.deepcopy(DEPLOYED)
    runner.head = "b" * 40
    with pytest.raises(module.DeployRolesError, match="not origin/main"):
        module.post_merge_check()
    assert aws.calls[0] == "git fetch origin"
    assert runner.cdk_argvs() == []


def test_post_merge_fails_when_cdk_diff_fail_exits_1(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    runner.synthesized = copy.deepcopy(DEPLOYED)
    runner.diff_rc = 1
    with pytest.raises(module.DeployRolesError, match="--fail exited 1"):
        module.post_merge_check()
    diffs = runner.cdk("diff")
    assert len(diffs) == 1
    assert "--fail" in diffs[0]
    assert "--method=template" in diffs[0]


def test_post_merge_fails_when_changed_set_not_empty(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    with pytest.raises(module.DeployRolesError, match="differs from main"):
        module.post_merge_check()
    assert runner.cdk("diff") == []


def test_post_merge_passes_when_deployed_equals_main(
    harness: tuple[ModuleType, FakeAws, FakeRunner],
) -> None:
    module, _, runner = harness
    runner.synthesized = copy.deepcopy(DEPLOYED)
    module.post_merge_check()
    assert len(runner.cdk("diff")) == 1
