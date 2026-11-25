"""Audit the built pinned Logos verdict proof with and without the published model witness."""
import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
MODEL = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01" / "logos_binding" / "upstream-model"
spec = spec_from_file_location("model_replay", MODEL / "replay.py")
prior = module_from_spec(spec)
spec.loader.exec_module(prior)


def replay(checkout, complete_build):
    verification = checkout / "verification"
    commit = prior.capture(["git", "rev-parse", "HEAD"], checkout).strip()
    if commit != prior.LOGOS_REVISION or prior.capture(
        ["git", "status", "--porcelain", "--untracked-files=no"], checkout,
    ).strip():
        raise ValueError("Expected an unmodified pinned Logos checkout")
    version = prior.capture(["lean", "--version"], verification)
    if prior.LEAN_REVISION not in version:
        raise ValueError("Expected pinned Lean 4.34.0")

    manifest = json.loads((verification / "lake-manifest.json").read_text(encoding="utf-8"))
    mathlib, = (package["rev"] for package in manifest["packages"] if package["name"] == "mathlib")
    if mathlib != "5ed2965256430c3649e86755f9576b54eca72435":
        raise ValueError("Expected the pinned verification Mathlib revision")
    environment = {**os.environ, "LEAN_NUM_THREADS": "1"}

    if complete_build:
        subprocess.run(["bash", "scripts/build-all-cpc-rules.sh", "--batch-size", "1", "-j1"],
                       cwd=checkout, env=environment, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["lake", "build", "Cpc.ApiCorrect"], cwd=verification, env=environment,
                       check=True, stdout=subprocess.DEVNULL)

    upstream = prior.capture(["lake", "env", "printenv", "LEAN_PATH"], verification).strip()
    with TemporaryDirectory(prefix="llmlang-logos-verdict-proof-") as directory:
        directory = Path(directory)
        compiled = directory / "compiled"
        prior.combine_libraries(checkout, compiled)
        if not (compiled / "Cpc" / "ApiCorrect.olean").exists():
            raise ValueError("Build the exact Cpc.ApiCorrect module before auditing")
        program = prior.build_program_workspace(checkout, directory / "program")
        environment["LEAN_PATH"] = os.pathsep.join(map(str, (directory, program, compiled, upstream)))
        lean = ["lean", "-DwarningAsError=true"]
        for module in ("LogosUpstreamScalarModel", "LogosUpstreamProgram", "LogosModelExtension",
                       "LogosSourceRefutation"):
            prior.capture([*lean, f"--root={MODEL}", "-o", str(directory / f"{module}.olean"),
                           str(MODEL / f"{module}.lean")], verification, environment=environment)
        return prior.capture([*lean, str(HERE / "CheckedVerdict.lean")], verification,
                             environment=environment)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--complete-build", action="store_true")
    args = parser.parse_args()
    try:
        print(replay(args.checkout.resolve(), args.complete_build), end="")
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr or error.stdout or str(error)) from error
