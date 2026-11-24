#!/usr/bin/env python3
"""Check the shared LLMLang scalar evaluator against pinned Logos model semantics."""

import argparse
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
LOGOS_REVISION = "cf18742973861b3718d04c5f25775448098ff474"
LEAN_REVISION = "293d5d0c0c3f3dded4688b3ccd6a33939ac5102b"


def capture(command, directory, *, environment=None):
    return subprocess.run(
        command, cwd=directory, env=environment, check=True, text=True,
        capture_output=True, timeout=120,
    ).stdout


def combine_libraries(checkout, destination):
    # Logos splits runtime and model modules across packages under the same
    # Cpc namespace. The standalone Lean invocation needs one search root.
    for project in (checkout / "verification", checkout):
        library = project / ".lake" / "build" / "lib" / "lean"
        for module in library.rglob("*"):
            if module.is_file():
                link = destination / module.relative_to(library)
                link.parent.mkdir(parents=True, exist_ok=True)
                if not link.exists():
                    link.symlink_to(module)


def replay(checkout):
    revision = capture(["git", "rev-parse", "HEAD"], checkout).strip()
    if revision != LOGOS_REVISION or capture(
        ["git", "status", "--porcelain", "--untracked-files=no"], checkout,
    ).strip():
        raise ValueError("Expected a clean checkout of the pinned Logos revision")

    verification = checkout / "verification"
    version = capture(["lean", "--version"], verification).strip()
    if LEAN_REVISION not in version:
        raise ValueError(f"Expected the pinned Logos verification Lean 4.34.0, got {version}")

    subprocess.run(["bash", "scripts/build.sh", "Cpc.SmtModel"], cwd=checkout,
                   check=True, stdout=subprocess.DEVNULL)
    lake_path = capture(["lake", "env", "printenv", "LEAN_PATH"], verification).strip()
    with TemporaryDirectory(prefix="llmlang-logos-upstream-") as tmp:
        directory = Path(tmp)
        library = directory / "compiled"
        combine_libraries(checkout, library)
        environment = {**os.environ, "LEAN_PATH": os.pathsep.join((str(directory), str(library), lake_path))}
        capture(["lean", f"--root={HERE.parent}", "-DwarningAsError=true", "-o",
                 str(directory / "LogosScalarEvaluation.olean"), str(HERE.parent / "LogosScalarEvaluation.lean")],
                verification, environment=environment)
        return capture(["lean", "-DwarningAsError=true", str(HERE / "LogosUpstreamScalarModel.lean")],
                       verification, environment=environment)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    args = parser.parse_args()
    print(replay(args.checkout.resolve()), end="")
