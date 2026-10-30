"""Observe pinned scanners' real planning before executing their unchanged CLI.

This adapter runs in each scanner's installed Python environment. Semgrep uses
the same pysemgrep entry point to which its 1.183.0 console script delegates.
The planner and engine share the actual resolved rules, including auto config;
there is no second registry lookup or replacement rule selection.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

VERSIONS = {"bandit": "1.9.4", "semgrep": "1.183.0", "checkov": "3.4.0"}


class PlanningComplete(SystemExit):
    """Stop a bounded discovery probe before any security checks execute."""


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def local_path(value: str) -> str:
    return Path(value).resolve(strict=True).relative_to(Path.cwd().resolve()).as_posix()


def record(tool: str, paths: list[str], **details: Any) -> None:
    targets = sorted({local_path(path) for path in paths})
    value = {
        "schema": 1,
        "tool": tool,
        "version": VERSIONS[tool],
        "argv": sys.argv[1:],
        "root": str(Path.cwd().resolve()),
        "mode": os.environ.get("CI_SCANNER_MODE", "scan"),
        "targets": targets,
        "target_sha256": {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in targets
        },
        **details,
    }
    destination = Path(os.environ["CI_SCANNER_PLAN"])
    destination.write_text(json.dumps(value, indent=2) + "\n")
    if value["mode"] == "plan":
        raise PlanningComplete(0)


def bandit() -> None:
    cli = importlib.import_module("bandit.cli.main")
    manager_type = importlib.import_module("bandit.core.manager").BanditManager

    original = manager_type.discover_files

    def discover(manager: Any, *args: Any, **kwargs: Any) -> Any:
        result = original(manager, *args, **kwargs)
        record(
            "bandit",
            manager.files_list,
            config_sha256=hashlib.sha256(
                Path("pyproject.toml").read_bytes()
            ).hexdigest(),
            discovery="BanditManager.discover_files",
        )
        return result

    with patch.object(manager_type, "discover_files", discover):
        cli.main()


def semgrep() -> None:
    runner_type = importlib.import_module("semgrep.core_runner").CoreRunner
    cli = importlib.import_module("semgrep.main")

    original = runner_type.plan_core_run

    def plan(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        # Ignore display-only plans; this call builds the actual engine input.
        if kwargs.get("all_targets") is not None:
            rules = [rule._raw for rule in result.rules]
            record(
                "semgrep",
                [str(task.path.fpath) for task in result.target_mappings],
                discovery="CoreRunner.plan_core_run (engine input)",
                rules_sha256=digest(rules),
                rule_ids=[rule.id for rule in result.rules],
                rule_targets=[
                    {
                        "path": local_path(str(task.path.fpath)),
                        "language": str(task.analyzer),
                        "rules": [result.rules[i].id for i in task.rule_nums],
                    }
                    for task in result.target_mappings
                ],
            )
        return result

    with patch.object(runner_type, "plan_core_run", staticmethod(plan)):
        cli.main()


def checkov() -> None:
    cfn_registry = importlib.import_module(
        "checkov.cloudformation.checks.resource.registry"
    ).cfn_registry
    context_parser = importlib.import_module(
        "checkov.cloudformation.context_parser"
    ).ContextParser
    runner_type = importlib.import_module("checkov.cloudformation.runner").Runner
    registry_type = importlib.import_module(
        "checkov.common.checks.base_check_registry"
    ).BaseCheckRegistry
    cli_type = importlib.import_module("checkov.main").Checkov

    original = runner_type.check_definitions
    original_run = registry_type.run_check
    evaluations = []
    errors = []

    def execute(
        registry: Any,
        check: Any,
        configuration: Any,
        name: str,
        kind: str,
        file: str,
        skip_info: Any,
    ) -> Any:
        identity = [file.removeprefix("/"), f"{kind}.{name}", check.id]
        run = check.run

        def observed(*args: Any, **kwargs: Any) -> Any:
            try:
                return run(*args, **kwargs)
            except Exception:
                # Checkov's registry converts exceptions into UNKNOWN. Keep
                # those distinct from legitimate unsupported property shapes.
                errors.append(identity)
                raise

        with patch.object(check, "run", observed):
            result = original_run(
                registry, check, configuration, name, kind, file, skip_info
            )
        evaluations.append([*identity, result["result"].name])
        return result

    def definitions(
        runner: Any, root_folder: str, runner_filter: Any, report: Any
    ) -> Any:
        resources = []
        checks = []
        for path, definition in runner.definitions.items():
            relative = Path(path).relative_to(root_folder).as_posix()
            for name, resource in definition.get("Resources", {}).items():
                identity = context_parser.extract_cf_resource_id(resource, name)
                if not identity:
                    continue
                resources.append([relative, identity])
                context = runner.context[path]["Resources"][name]
                if not (
                    context["start_line"]
                    and context["end_line"]
                    and context["code_lines"]
                ):
                    raise ValueError("CloudFormation resource has no checkable context")
                for check in cfn_registry.get_checks(resource["Type"]):
                    if runner_filter.should_run_check(
                        check,
                        report_type=cfn_registry.report_type,
                        file_origin_paths=["/" + relative],
                    ):
                        checks.append([relative, identity, check.id])
        runner.graph_registry.load_checks()
        graph_ids = [check.id for check in runner.graph_registry.checks]
        record(
            "checkov",
            list(runner.definitions),
            discovery="CloudFormation parsed definitions and resource check registry",
            resources=sorted(resources),
            checks=sorted(checks),
            graph_rule_ids=sorted(graph_ids),
            graph_coverage_limit=(
                "Graph-check per-resource applicability is not independently planned; "
                "only resource registry checks have exact independent check coverage."
            ),
        )
        result = original(runner, root_folder, runner_filter, report)
        destination = Path(os.environ["CI_SCANNER_PLAN"])
        scope = json.loads(destination.read_text())
        scope.update(evaluations=evaluations, evaluation_errors=errors)
        destination.write_text(json.dumps(scope, indent=2) + "\n")
        return result

    with (
        patch.object(runner_type, "check_definitions", definitions),
        patch.object(registry_type, "run_check", execute),
    ):
        raise SystemExit(cli_type().run())


def main() -> None:
    tool = sys.argv.pop(1)
    if importlib.metadata.version(tool) != VERSIONS[tool]:
        raise ValueError("unsupported scanner planning API version")
    sys.argv[0] = tool
    with contextlib.suppress(PlanningComplete):
        {"bandit": bandit, "semgrep": semgrep, "checkov": checkov}[tool]()


if __name__ == "__main__":
    main()
