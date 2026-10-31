"""Admit only this checkout's locked CDK executable, then preserve its argv/cwd."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def checked_binary(root: Path) -> Path:
    """Validate local state without invoking npm, CDK, caches or PATH lookup."""
    root = root.resolve(strict=True)
    manifest = json.loads((root / "package.json").read_text())
    lock = json.loads((root / "package-lock.json").read_text())
    version = manifest["devDependencies"]["aws-cdk"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("CDK manifest must pin an exact version")
    if (
        lock["packages"][""]["devDependencies"]["aws-cdk"] != version
        or lock["packages"]["node_modules/aws-cdk"]["version"] != version
    ):
        raise ValueError("CDK manifest and lock disagree")
    package = root / "node_modules/aws-cdk"
    target = package / "bin/cdk"
    binary = root / "node_modules/.bin/cdk"
    if package.resolve(strict=True) != package or target.resolve(strict=True) != target:
        raise ValueError("CDK package/target must stay at its canonical local path")
    installed = json.loads((package / "package.json").read_text())
    if (
        installed.get("name") != "aws-cdk"
        or installed.get("version") != version
        or installed.get("bin", {}).get("cdk") != "bin/cdk"
    ):
        raise ValueError("Installed CDK does not match the committed lock")
    if binary.resolve(strict=True) != target or not target.is_file():
        raise ValueError("CDK bin must resolve to the canonical local target")
    if not os.access(binary, os.X_OK):
        raise ValueError("Local CDK binary is not executable")
    return target


def main() -> None:
    """Refuse before launch on missing/mismatched local state; never fall back."""
    try:
        binary = checked_binary(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Locked local CDK refused: {type(exc).__name__}") from exc
    os.execv(str(binary), [str(binary), *sys.argv[1:]])  # nosec B606


if __name__ == "__main__":
    main()
