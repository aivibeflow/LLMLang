#!/usr/bin/env python3
"""Kernel-check ownership properties and replay the exact Rust observation vectors."""

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[2] / "semantic-representation" / "RT-05" / "PARTIAL-RECORD-01" / "evidence.json"
NATIVE_SHA256 = "74590da73dcb4216f0e9d14463362cc3059a1a810410f758a1fe0a0cde701336"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
SLOT = {"alpha": 0, "beta": 1, "gamma": 2}
STANDARD_AXIOMS = {"propext", "Quot.sound", "Classical.choice"}
FALSE_APPLICATIONS = {
    "wrong_declared_owner": """example : (completedRelease (α := Nat) none [0, 2]).Perm [0, 1] :=
  completionConservesAcquired none (List.Perm.refl [0, 2])""",
    "moved_slot_still_in_record": """example : (0 : Nat) ∈ recordRelease (some 0) [0, 1] :=
  movedSlotAbsentFromRecord 0 [0, 1]""",
}


def checksum(data):
    return sha256(data).hexdigest()


def lean_call(lean, *arguments, directory, check=True):
    env = {**os.environ, "LEAN_PATH": str(directory)}
    return subprocess.run([lean, "-DwarningAsError=true", *arguments],
                          env=env, cwd=directory, capture_output=True, check=check, text=True, timeout=60)


def audit(text):
    axioms = {}
    for line in text.splitlines():
        matched = re.fullmatch(r"'RecordOwnership\.(\w+)' (.*)", line)
        assert matched, line
        theorem, detail = matched.groups()
        assert theorem not in axioms
        if detail == "does not depend on any axioms":
            axioms[theorem] = []
        else:
            statement = re.fullmatch(r"depends on axioms: \[(.*)\]", detail)
            assert statement, detail
            axioms[theorem] = statement[1].split(", ")
        assert set(axioms[theorem]) <= STANDARD_AXIOMS
    assert len(axioms) == 14
    return axioms


def lean_list(values):
    return "[" + ", ".join(map(str, values)) + "]"


def lean_vectors(native_rows):
    cases = []
    claims = []
    for row in native_rows:
        decl = lean_list(SLOT[field] for field in row["declaration"])
        init = lean_list(SLOT[field] for field in row["initializer"])
        pair = f"({decl}, {init})"
        cases.append(f"  {pair}")
        outcomes = lean_list(f"({status}, {lean_list(events)})" for status, events in row["observations"])
        theorem = f"archiveCase{row['case']}"
        claims.extend([f"theorem {theorem} : observe {pair} = {outcomes} := by rfl",
                       f"#print axioms {theorem}"])
    generated = """import Ownership
open RecordOwnership

def replayCases : List (List Nat × List Nat) := [
""" + ",\n".join(cases) + """
]

def observe (orders : List Nat × List Nat) : List (Nat × List Int) :=
  (List.range 8).flatMap fun mask =>
    (List.range 4).map fun keep =>
      execute orders.1 orders.2 mask (if keep < 3 then some keep else none)

#eval IO.println (Lean.Json.compress (Lean.toJson (replayCases.map observe)))
"""
    return generated, "\n".join(claims) + "\n"


def run(lean, directory):
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in version
    source = HERE / "Ownership.lean"
    axioms = audit(lean_call(lean, f"--root={HERE}", "-o", str(directory / "Ownership.olean"),
                            str(source), directory=directory).stdout)
    native_bytes = NATIVE.read_bytes()
    assert checksum(native_bytes) == NATIVE_SHA256
    native = json.loads(native_bytes)
    generated, equalities = lean_vectors(native["observations"])
    path = directory / "Replay.lean"
    path.write_text(generated + equalities, encoding="utf-8")
    output = lean_call(lean, str(path), directory=directory).stdout.splitlines()
    actual = json.loads(output[0])
    expected_audit = [f"'archiveCase{row['case']}' depends on axioms: [propext]"
                      for row in native["observations"]]
    assert output[1:] == expected_audit
    expected = [record["observations"] for record in native["observations"]]
    assert actual == expected
    outcome_counts = Counter("completed" if status == 0 else "early_exit"
                             for case in actual for status, _ in case)
    rejected = {}
    for name, claim in FALSE_APPLICATIONS.items():
        bad_path = directory / f"{name}.lean"
        bad_path.write_text("import Ownership\nopen RecordOwnership\n\n" + claim + "\n", encoding="utf-8")
        result = lean_call(lean, str(bad_path), directory=directory, check=False)
        assert result.returncode == 1 and "type mismatch" in (result.stdout + result.stderr).lower(), (name, result.stdout, result.stderr)
        rejected[name] = "type_mismatch"
    return {
        "schema": "llmlang-rt32-record-ownership/1",
        "python": platform.python_version(), "lean": version,
        "ownership_source_sha256": checksum(source.read_bytes()),
        "runner_sha256": checksum(Path(__file__).read_bytes()),
        "generated_lean_replay_sha256": checksum((generated + equalities).encode()),
        "archive_equalities": len(expected_audit), "archive_equality_axioms": ["propext"],
        "native_ledger_sha256": NATIVE_SHA256,
        "checked_theorems": axioms, "rejected_proof_applications": rejected,
        "source_cases": len(expected), "oracle_vectors": sum(outcome_counts.values()),
        "phase_counts": dict(sorted(outcome_counts.items())),
        "native_measurements_represented": native["native_observations"],
        "matched_vector_sha256": checksum(json.dumps(actual, separators=(",", ":")).encode()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-record-ownership-lean-") as scratch:
        evidence = run(args.lean, Path(scratch))
    print(json.dumps(evidence, indent=2))
