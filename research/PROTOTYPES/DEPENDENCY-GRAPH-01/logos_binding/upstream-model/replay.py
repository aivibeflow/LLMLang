#!/usr/bin/env python3
"""Check the shared LLMLang scalar evaluator against pinned Logos model semantics."""

import argparse
import json
import os
from pathlib import Path
import shutil
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


def build_program_workspace(checkout, destination):
    destination.mkdir()
    for source in HERE.parent.glob("*.lean"):
        shutil.copyfile(source, destination / source.name)
    config = destination / "lakefile.lean"
    text = config.read_text(encoding="utf-8")
    dependency = f'require Cpc from git\n  "https://github.com/cvc5/logos" @ "{LOGOS_REVISION}"'
    if text.count(dependency) != 1:
        raise ValueError("Expected the pinned Logos dependency in the LLMLang Lake file")
    text = text.replace(dependency, f"require Cpc from {json.dumps(str(checkout))}")
    config.write_text(text, encoding="utf-8")
    shutil.copyfile(checkout / "verification" / "lean-toolchain", destination / "lean-toolchain")
    capture(["lake", "update", "--keep-toolchain"], destination)
    subprocess.run(["lake", "build", "LLMLangLogosBinding"], cwd=destination,
                   check=True, stdout=subprocess.DEVNULL)
    return destination / ".lake" / "build" / "lib" / "lean"


def replay(checkout, program=False):
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
        paths = [str(directory)]
        if program:
            paths.append(str(build_program_workspace(checkout, directory / "llmlang")))
        library = directory / "compiled"
        combine_libraries(checkout, library)
        paths.extend((str(library), lake_path))
        environment = {**os.environ, "LEAN_PATH": os.pathsep.join(paths)}
        lean = ["lean", "-DwarningAsError=true"]
        if program:
            capture([*lean, f"--root={HERE}", "-o", str(directory / "LogosUpstreamScalarModel.olean"),
                     str(HERE / "LogosUpstreamScalarModel.lean")], verification, environment=environment)
            theorem = "LogosUpstreamProgram.lean"
        else:
            capture([*lean, f"--root={HERE.parent}", "-o", str(directory / "LogosScalarEvaluation.olean"),
                     str(HERE.parent / "LogosScalarEvaluation.lean")], verification, environment=environment)
            theorem = "LogosUpstreamScalarModel.lean"
        return capture([*lean, str(HERE / theorem)], verification, environment=environment)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--program", action="store_true", help="check both sides with the upstream kernel")
    args = parser.parse_args()
    print(replay(args.checkout.resolve(), args.program), end="")
