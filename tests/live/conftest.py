"""Live nonprod checks: with CAMPPS_LIVE_IAM_CHECK=1 a skip is a failure.

The live tests skip unless ``CAMPPS_LIVE_IAM_CHECK=1``, so the repo's plain
``uv run pytest`` and CI never reach AWS. When the variable is set the run is a
gate, and a missing credential, an expired SSO session or an unreadable resource
must fail it rather than pass it vacuously as a skip.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest

LIVE_FLAG = "CAMPPS_LIVE_IAM_CHECK"


def live_check_enabled() -> bool:
    return os.environ.get(LIVE_FLAG) == "1"


def _fail_skip(report: Any) -> None:
    if live_check_enabled() and report.skipped and not hasattr(report, "wasxfail"):
        reason = report.longrepr
        report.outcome = "failed"
        report.longrepr = (
            f"{LIVE_FLAG}=1 is set, so a skip is a failure "
            f"(missing credentials never pass the gate): {reason}"
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, Any]:
    outcome = yield
    _fail_skip(outcome.get_result())


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, Any]:
    outcome = yield
    _fail_skip(outcome.get_result())
