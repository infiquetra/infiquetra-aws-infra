"""Live template diffs of CamppsNonProdDeployRolesStack (plan issue 164 unit U8).

Read-only. Both cases go through the shared module in
``scripts/campps_nonprod_deploy_roles.py``, the same code the deploy runs:

- ``-k pre_deploy``: passes only when exactly
  ``TenantSetupE2eCredentialsPolicyAC488617`` differs from the deployed stack;
- ``-k post_merge``: passes only when this worktree's HEAD is ``origin/main``,
  nothing differs, and ``cdk diff --method=template --fail`` exits 0.

Skips unless ``CAMPPS_LIVE_IAM_CHECK=1``; with it set, ``tests/live/conftest.py``
turns any skip into a failure, and nothing here catches a credential error.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "campps_nonprod_deploy_roles.py"
)

pytestmark = pytest.mark.skipif(
    os.environ.get("CAMPPS_LIVE_IAM_CHECK") != "1",
    reason="live template diff; set CAMPPS_LIVE_IAM_CHECK=1 with nonprod SSO",
)


@pytest.fixture(scope="module")
def deploy_roles() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "campps_nonprod_deploy_roles", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pre_deploy_diff_changes_only_the_policy(deploy_roles: ModuleType) -> None:
    changed = deploy_roles.pre_deploy_check()
    assert changed == {deploy_roles.EXPECTED_CHANGED_RESOURCE}


def test_post_merge_deployed_stack_equals_main(deploy_roles: ModuleType) -> None:
    deploy_roles.post_merge_check()
