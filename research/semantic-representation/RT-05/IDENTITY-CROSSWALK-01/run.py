#!/usr/bin/env python3
"""Replay the identity evidence cohort and check crosswalk discriminators."""

from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = (
    "NATIVE-IMPLEMENTATION-IDENTITY-01", "TYPED-EDGE-PROJECTIONS-01", "OPERATION-IDENTITY-01",
    "CONFORMANCE-CLASS-IDENTITY-01", "RECURSIVE-TOPOLOGY-EDITS-01", "OPERATION-LIFETIME-01",
    "CANONICAL-WIRE-01", "DEPENDENCY-PROPAGATION-01", "PROVIDED-CONTRACT-IDENTITY-01",
    "DIGEST-MIGRATION-01", "GUARDED-DISPATCH-IDENTITY-01",
)
PROOFS = {
    "TYPED-EDGE-PROJECTIONS-01": "Observation.lean",
    "OPERATION-IDENTITY-01": "Contract.lean",
    "DEPENDENCY-PROPAGATION-01": "Propagation.lean",
    "PROVIDED-CONTRACT-IDENTITY-01": "Admission.lean",
}


def replay():
    archive, proofs = {}, {}
    for fixture in FIXTURES:
        path = ROOT / fixture
        expected = (path / "evidence.json").read_bytes()
        args = [sys.executable, "-B", str(path / "run.py")]
        if fixture == "GUARDED-DISPATCH-IDENTITY-01":
            with TemporaryDirectory(prefix="llmlang-identity-crosswalk-") as directory:
                output = Path(directory) / "evidence.json"
                subprocess.run([*args, "--output", str(output)], check=True, timeout=60)
                actual = output.read_bytes()
        else:
            actual = subprocess.check_output(args, timeout=60)
        if actual != expected:
            raise AssertionError(f"Ledger did not replay byte for byte for {fixture}")
        archive[fixture] = expected
    for fixture, filename in PROOFS.items():
        root = ROOT / fixture
        checked = subprocess.check_output(["lean", "-DwarningAsError=true", root / filename], timeout=60)
        if checked != (root / "axioms.txt").read_bytes():
            raise AssertionError(f"Axiom output changed for {fixture}")
        proofs[fixture] = sha256(checked).hexdigest()
    return archive, proofs


def controls(archive):
    native, edges, operation, classes, topology, lifetime, wire, calls, provided, migration, dispatch = (
        json.loads(archive[name]) for name in FIXTURES
    )
    initial, expanded = (classes["candidate_snapshots"][name] for name in ("initial", "expanded"))
    values = [
        ("Build request differs while caller bytes and resolved identity agree",
         native["distinct_marker_recipe_pairs"], 4),
        ("Identical caller bytes with different provider observations",
         native["pairs_with_same_key_and_distinct_observations"]["caller_only_key"], 8),
        ("One implementation key reuses stale verification or navigation",
         [edges["comparisons"]["implementation_for_all"][role]["invalid_reuse"]
          for role in ("verification", "navigation")], [384, 256]),
        ("One operation has admissible providers with distinct observations and bindings",
         sum(pair["same_contract_key"] and not pair["same_binding"] and bool(pair["different_input_count"])
             for pair in operation["same_contract_distinct_providers"]), 6),
        ("Changing discovery retains the class while adding a candidate",
         [initial["class_hash"] == expanded["class_hash"] == classes["classes"]["wrap-general"]["class_hash"],
          len(expanded["members"]) - len(initial["members"]),
          initial["candidate_set_hash"] != expanded["candidate_set_hash"]],
         [True, 1, True]),
        ("The exact class and implementation leave evidence inputs unresolved",
         classes["distinct_disposition_pairs_with_same_key"]["class_and_implementation"], 100),
        ("Direct recursive propagation agrees with exact rooted closure",
         [topology["policies"][mode]["stale"] + topology["policies"][mode]["unnecessary"]
          for mode in ("keyed", "structural")], [0, 0]),
        ("Alias lookup can admit an old pin outside its execution policy",
         lifetime["resolution_comparison"]["original_alias"]["unexpected_execution"], 8),
        ("Digest-correct wrong-domain frame",
         next(case["expected"] for case in wire["cases"] if case["name"] == "wrong-domain"),
         ["domain", "domain", "accept"]),
        ("Exact implementation without resolved abstract binding can be stale",
         calls["comparison"]["exact_subject"]["stale_reuse"], 128),
        ("Keeping executable and public identity can hide provided-contract change",
         provided["distinct_judgment_pairs_sharing_key"]["executable_and_public"], 29),
        ("Rewriting digest references changes the receipt subject",
         migration["receipt"]["old_exact_binding"] != migration["receipt"]["new_exact_binding"], True),
        ("Equal provider sets can hide changed state-to-provider dispatch",
         dispatch["counts"]["target-set"]["stale_reuse"], 1708),
    ]
    for label, observed, expected in values:
        if observed != expected:
            raise AssertionError(f"{label}: {observed!r} != {expected!r}")
    return {label: value for label, value, _ in values}


def results():
    archive, proofs = replay()
    return {
        "schema": "llmlang-identity-crosswalk/1",
        "python": platform.python_version(),
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "lean": subprocess.check_output(["lean", "--version"], text=True).strip(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "replayed_ledger_sha256": {name: sha256(raw).hexdigest() for name, raw in archive.items()},
        "replayed_axiom_output_sha256": proofs,
        "crosswalk_controls": controls(archive),
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
