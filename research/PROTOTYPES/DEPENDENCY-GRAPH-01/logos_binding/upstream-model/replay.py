#!/usr/bin/env python3
"""Check the shared LLMLang scalar evaluator against pinned Logos model semantics."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
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


def rebuild_kernel_witness(checkout, library, environment):
    verification = checkout / "verification"
    config = tomllib.loads((verification / "lakefile.toml").read_text(encoding="utf-8"))
    package = next(item for item in config["lean_lib"] if item["name"] == "CpcVerification")
    lean = ["lean", f"--root={library}", *config["weakLeanArgs"], *package["moreLeanArgs"]]
    namespace = Path("Cpc/Proofs/TypePreservation")
    old = ("@[simp] theorem native_re_canonical_none :\n"
           "    __smtx_re_canonical native_re_none = true := by\n  native_decide\n")
    new = ("@[simp] theorem native_re_canonical_none :\n"
           "    __smtx_re_canonical native_re_none = true := rfl\n")
    for name in ("Common", "Support", "Model", "Nonvacuity"):
        source = (checkout / namespace / f"{name}.lean").read_text(encoding="utf-8")
        if name == "Common":
            if source.count(old) != 1:
                raise ValueError("Expected exactly one pinned empty-regex canonicity proof")
            source = source.replace(old, new)
        target = library / namespace / f"{name}.lean"
        # The shared library entries are symlinks. Unlink every artifact for
        # this module before Lean writes its alternate build products.
        for artifact in target.parent.glob(f"{name}.*"):
            artifact.unlink()
        target.write_text(source, encoding="utf-8")
        subprocess.run([*lean, "-o", str(target.with_suffix(".olean")), str(target)],
                       cwd=verification, env=environment, check=True, timeout=600)


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


def replay(checkout, mode="scalar"):
    revision = capture(["git", "rev-parse", "HEAD"], checkout).strip()
    if revision != LOGOS_REVISION or capture(
        ["git", "status", "--porcelain", "--untracked-files=no"], checkout,
    ).strip():
        raise ValueError("Expected a clean checkout of the pinned Logos revision")

    verification = checkout / "verification"
    version = capture(["lean", "--version"], verification).strip()
    if LEAN_REVISION not in version:
        raise ValueError(f"Expected the pinned Logos verification Lean 4.34.0, got {version}")

    targets = ["Cpc.SmtModel"]
    if mode in {"extension", "kernel-extension", "refutation"}:
        targets.append("Cpc.Proofs.TypePreservation.Nonvacuity")
    if mode == "refutation":
        targets.append("Cpc.Spec")
    subprocess.run(["bash", "scripts/build.sh", *targets], cwd=checkout,
                   check=True, stdout=subprocess.DEVNULL)
    lake_path = capture(["lake", "env", "printenv", "LEAN_PATH"], verification).strip()
    with TemporaryDirectory(prefix="llmlang-logos-upstream-") as tmp:
        directory = Path(tmp)
        paths = [str(directory)]
        builds_program = mode in {"program", "refutation"}
        if builds_program:
            paths.append(str(build_program_workspace(checkout, directory / "llmlang")))
        library = directory / "compiled"
        combine_libraries(checkout, library)
        paths.extend((str(library), lake_path))
        environment = {**os.environ, "LEAN_PATH": os.pathsep.join(paths)}
        if mode == "kernel-extension":
            rebuild_kernel_witness(checkout, library, environment)
        lean = ["lean", "-DwarningAsError=true"]
        if not builds_program:
            capture([*lean, f"--root={HERE.parent}", "-o", str(directory / "LogosScalarEvaluation.olean"),
                     str(HERE.parent / "LogosScalarEvaluation.lean")], verification, environment=environment)
        if mode != "scalar":
            capture([*lean, f"--root={HERE}", "-o", str(directory / "LogosUpstreamScalarModel.olean"),
                     str(HERE / "LogosUpstreamScalarModel.lean")], verification, environment=environment)
        if mode == "refutation":
            for name in ("LogosUpstreamProgram", "LogosModelExtension"):
                capture([*lean, f"--root={HERE}", "-o", str(directory / f"{name}.olean"),
                         str(HERE / f"{name}.lean")], verification, environment=environment)
        theorem = {"scalar": "LogosUpstreamScalarModel.lean", "program": "LogosUpstreamProgram.lean",
                   "extension": "LogosModelExtension.lean", "kernel-extension": "LogosModelExtension.lean",
                   "refutation": "LogosSourceRefutation.lean"}[mode]
        return capture([*lean, str(HERE / theorem)], verification, environment=environment)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--program", dest="mode", action="store_const", const="program",
                       help="check both sides with the upstream kernel")
    modes.add_argument("--model-extension", dest="mode", action="store_const", const="extension",
                       help="check the total well-formed upstream model construction")
    modes.add_argument("--kernel-model-extension", dest="mode", action="store_const", const="kernel-extension",
                       help="rebuild the model witness with a kernel reduction in a temporary library")
    modes.add_argument("--source-refutation", dest="mode", action="store_const", const="refutation",
                       help="check the source refutation theorem under explicit verdict soundness")
    parser.set_defaults(mode="scalar")
    args = parser.parse_args()
    print(replay(args.checkout.resolve(), args.mode), end="")
