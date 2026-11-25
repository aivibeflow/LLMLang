"""Normalize all five pinned Lean axiom reports and guard the observed proof boundary."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

THEOREMS = (
    "correct___logos_verdict",
    "correct___logos_check_proof",
    "Smtm.model_wf_nonvacuous",
    "LLMLang.LogosScalarDenotation.pinnedVerdict_noDependence_withBase",
    "LLMLang.LogosScalarDenotation.pinnedVerdict_noDependence",
)
CORE = {"propext", "Classical.choice", "Quot.sound"}


def digest(value):
    return sha256(value).hexdigest()


def audit(output):
    reports = {}
    for line in output.decode("utf-8").splitlines():
        row = json.loads(line)
        name, names = row["name"], row["axioms"]
        if name in reports or len(set(names)) != len(names):
            raise ValueError(f"Repeated theorem or axiom name in {name}")
        reports[name] = set(names)
    if tuple(reports) != THEOREMS:
        raise ValueError("Incomplete Lean axiom transcript")

    verdict, proof, witness, given_base, with_witness = reports.values()
    if verdict != proof or verdict != given_base or verdict != with_witness or not witness < verdict:
        raise ValueError("Unexpected set relationship among compiled proof dependencies")
    if any({name for name in axioms if "._native.native_decide." not in name} != CORE
           for axioms in reports.values()):
        raise ValueError("Unexpected additional axiom, for example sorryAx or a new trust premise")
    if len(verdict - CORE) != 2118 or len(witness - CORE) != 1:
        raise ValueError("Unexpected native axiom counts for the pinned proof")

    return {
        "schema": "llmlang-logos-verdict-axioms/1",
        "lean_stdout_sha256": digest(output),
        "standard_axioms": sorted(CORE),
        "theorems": {name: {
            "total_axioms": len(values),
            "native_decide_axioms": len(values - CORE),
            "set_sha256": digest(("\n".join(sorted(values)) + "\n").encode()),
        } for name, values in reports.items()},
        "witness_native_axioms": sorted(witness - CORE),
        "verdict_native_axioms": sorted(verdict - CORE),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.output.read_bytes()), indent=2, ensure_ascii=False))
