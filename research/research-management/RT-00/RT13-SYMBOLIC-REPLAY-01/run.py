#!/usr/bin/env python3
"""Check additional ground witnesses against the pinned RT-13 predicates."""

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
SYMBOLIC = ROOT / "compiler-and-translation" / "RT-13" / "LLVM-CHECKED-ADD-SYMBOLIC-01"
SPEC = spec_from_file_location("symbolic_checked_add", SYMBOLIC / "run.py")
symbolic = module_from_spec(SPEC)
SPEC.loader.exec_module(symbolic)

# The overflowing inputs encode INT32_MIN + (-1). The event-order control
# disables arithmetic and provides distinct observable payloads.
INPUTS = {
    "drop_overflow": (2**31, 2**32 - 1, 7),
    "reverse_effects": (9, 4, 0),
    "store_on_error": (2**31, 2**32 - 1, 7),
}


def run(args):
    previous = symbolic.previous
    version = previous.invoke([args.lean, "--version"]).stdout.strip()
    if previous.LEAN_COMMIT not in version:
        raise ValueError("Expected pinned Lean 4.36.0")
    goals, records, _ = previous.inputs(args)
    cases = {}
    declarations = ["set_option sat.solver \"/llmlang-fixture-no-solver\"\n"]
    for variant, witness in INPUTS.items():
        for level in (0, 3):
            key = f"{variant}_O{level}"
            if witness == tuple(records[key]["witness"]["input"]):
                raise ValueError(f"Expected a new witness for {key}")
            for profile, goal, mismatch in (
                ("mutant", f"{key}_witness", True),
                ("preserving", f"preserving_O{level}_complete_mismatch", False),
            ):
                name = f"{key}_{profile}"
                cases[name] = {"input_u32": witness, "complete_mismatch": mismatch}
                predicate, _, _ = goals[goal]
                declarations.append(previous.proposition(name, predicate, witness, mismatch))
                declarations.extend(("  decide", f"#print axioms {name}"))

    source = "\n".join(declarations) + "\n"
    with TemporaryDirectory(prefix="llmlang-rt13-witness-") as directory:
        path = Path(directory) / "Ground.lean"
        path.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [args.lean, "-DwarningAsError=true", str(path)],
            capture_output=True, check=True, text=True, timeout=60,
        )
    axioms = previous.audit(result.stdout)
    if list(axioms) != list(cases) or result.stderr:
        raise RuntimeError(f"Unexpected Lean audit:\n{result.stdout}{result.stderr}")
    if any(set(dependencies) - previous.CORE_AXIOMS for dependencies in axioms.values()):
        raise RuntimeError(f"Unexpected Lean audit:\n{result.stdout}{result.stderr}")
    return {
        "schema": "llmlang-rt13-symbolic-replay-controls/1",
        "lean": version,
        "lean_module_sha256": previous.digest(source),
        "cases": {
            name: {**case, "axioms": axioms[name]} for name, case in cases.items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--opt", default="opt")
    parser.set_defaults(cross_check=False)
    print(json.dumps(run(parser.parse_args()), indent=2))
