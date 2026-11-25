#!/usr/bin/env python3
"""Fail-closed checks for the repository's agreed top-level layout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath
from typing import Iterable


REQUIRED_FILES = {
    "README.md",
    "PLAN.md",
    "RESEARCH.md",
    "research/README.md",
    "examples/README.md",
    "examples/TEMPLATE.md",
    "examples/0001-hello-world.md",
    "examples/0002-echo.md",
    "examples/0003-calculator.md",
    "draft/.gitkeep",
    "draft/README.md",
    "draft/GLOSSARY.md",
    "draft/examples/README.md",
    "draft/examples/0001-hello-world/main.llmlang",
    "draft/examples/0002-echo/main.llmlang",
    "draft/examples/0003-calculator/main.llmlang",
    ".github/workflows/logos-binding.yml",
    ".github/workflows/qf-lia-profile.yml",
    ".github/workflows/repository-structure.yml",
}

REQUIRED_PREFIXES = ("research/", "examples/", "draft/")
FORBIDDEN_ROOT_PREFIXES = ("PROTOTYPES/",)
FORBIDDEN_ROOT_FILE_PREFIXES = ("RESEARCH-", "RFC-", "PROTOTYPE-")


def validate_paths(paths: Iterable[str]) -> list[str]:
    """Return layout violations for a collection of Git-tracked paths."""
    tracked = {str(PurePosixPath(path)) for path in paths if path}
    errors: list[str] = []

    for required in sorted(REQUIRED_FILES):
        if required not in tracked:
            errors.append(f"required file is missing: {required}")

    for prefix in REQUIRED_PREFIXES:
        if not any(path.startswith(prefix) for path in tracked):
            errors.append(f"required directory has no tracked files: {prefix[:-1]}/")

    for prefix in FORBIDDEN_ROOT_PREFIXES:
        misplaced = sorted(path for path in tracked if path.startswith(prefix))
        errors.extend(f"misplaced path at repository root: {path}" for path in misplaced)

    for path in sorted(tracked):
        if "/" not in path and path.startswith(FORBIDDEN_ROOT_FILE_PREFIXES):
            errors.append(f"research document must be under research/: {path}")

    if not any(path.startswith("research/") and path.endswith(".md") for path in tracked):
        errors.append("research/ must contain at least one Markdown research document")

    return errors


def git_tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    try:
        errors = validate_paths(git_tracked_paths())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"repository structure check could not inspect Git index: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("Repository structure check failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Repository structure check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
