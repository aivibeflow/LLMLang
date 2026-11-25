#!/usr/bin/env python3
"""Check the pinned LLVM predicates by direct signed arithmetic and case analysis."""

import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "LLVM-CHECKED-ADD-LEAN-01"
spec = spec_from_file_location("checked_add_lrat_replay", PREVIOUS / "run.py")
previous = module_from_spec(spec)
spec.loader.exec_module(previous)

HEADER = """\
import Overflow
open CheckedAddition
set_option linter.unusedVariables false
set_option linter.unusedSimpArgs false
set_option sat.solver "/llmlang-fixture-no-solver"

"""
SYMBOLIC = """\
  simp only [← widened_definition, source_overflow, target_overflow, narrow_sum]
  generalize h : a.saddOverflow b = overflow
  cases overflow <;> by_cases he : enabled == (0 : BitVec 32) <;> simp_all [bne]
"""
NORMALIZE = "  bv_normalize\n"


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def exact_theorems(goals, lrat_ledger):
    declarations = [HEADER]
    modes = {}
    for name, claim in goals.items():
        old = lrat_ledger["theorems"][name]["replay"]
        if old == "bv_check":
            modes[name] = "symbolic"
            tactic = SYMBOLIC
        elif old == "bv_normalize":
            modes[name] = "normalize"
            tactic = NORMALIZE
        else:
            raise ValueError(f"Unexpected prior proof route {old}")
        declarations.append(previous.proposition(name, *claim) + "\n" + tactic + "\n")
        declarations.append(f"#print axioms {name}\n\n")
    return "".join(declarations), modes


def invoke(lean, arguments, root):
    return subprocess.run([lean, "-DwarningAsError=true", *arguments], cwd=root,
                          env={**os.environ, "LEAN_PATH": str(root)}, capture_output=True,
                          text=True, timeout=60, check=False)


def success(completed):
    if completed.returncode or completed.stderr:
        raise RuntimeError(completed.stdout + completed.stderr)
    return completed.stdout


def run(args):
    version = previous.invoke([args.lean, "--version"]).stdout.strip()
    if previous.LEAN_COMMIT not in version:
        raise ValueError("Expected pinned Lean 4.36.0")
    goals, records, _ = previous.inputs(SimpleNamespace(opt=args.opt, cross_check=False))
    expected_ledger = PREVIOUS / "evidence.json"
    checked = json.loads(expected_ledger.read_text(encoding="utf-8"))
    if json.loads(json.dumps(records)) != checked["artifacts"]:
        raise ValueError("Prior artifact, query or witness hashes changed")
    generated, modes = exact_theorems(goals, checked)

    with TemporaryDirectory(prefix="llmlang-symbolic-add-") as directory:
        root = Path(directory)
        shutil.copy(HERE / "Overflow.lean", root / "Overflow.lean")
        compiled = success(invoke(args.lean, ["-o", "Overflow.olean", "Overflow.lean"], root))
        model_audit = previous.audit(compiled)
        (root / "Exact.lean").write_text(generated, encoding="utf-8")
        checked_output = success(invoke(args.lean, ["Exact.lean"], root))
        domain_audit = previous.audit(checked_output)

        failures = {}
        for name in ("drop_overflow_O0_witness", "reverse_effects_O0_witness",
                     "store_on_error_O0_witness"):
            predicate, _, _ = goals[name]
            control = HEADER + previous.proposition("incorrectPreservation", predicate, None, False)
            (root / "Control.lean").write_text(control + "\n" + SYMBOLIC, encoding="utf-8")
            rejected = invoke(args.lean, ["Control.lean"], root)
            assert rejected.returncode != 0 and "unsolved goals" in (rejected.stdout + rejected.stderr)
            failures[name] = "refused"

    assert list(domain_audit) == list(goals)
    assert len(model_audit) == 3
    assert all(set(values) <= previous.CORE_AXIOMS for values in (*domain_audit.values(), *model_audit.values()))
    return {
        "schema": "llmlang-llvm-checked-add-symbolic/1", "lean": version,
        "prior_lrat_ledger_sha256": hash_file(expected_ledger),
        "runner_sha256": hash_file(Path(__file__)), "model_sha256": hash_file(HERE / "Overflow.lean"),
        "exact_lean_module_sha256": previous.digest(generated),
        "arithmetic_lemmas": model_audit, "theorems": {
            name: {"mode": modes[name], "axioms": values} for name, values in domain_audit.items()
        },
        "incorrect_whole_domain_claims": failures,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--opt", default="opt")
    print(json.dumps(run(parser.parse_args()), indent=2))
