"""Measure checked and wrapping reassociation in a strict expression fragment."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
LOW, HIGH = -8, 7
LEFT = ((0, 1), 2)
RIGHT = (0, (1, 2))


def within(value):
    return LOW <= value <= HIGH


def evaluate(tree, values, *, wrapping):
    inspected = []

    def visit(node):
        if isinstance(node, int):
            inspected.append(node)
            return values[node]
        first = visit(node[0])
        second = visit(node[1])
        total = first + second
        if wrapping:
            return ((total - LOW) % (HIGH - LOW + 1)) + LOW
        if not within(total):
            raise ArithmeticError("checked addition outside range")
        return total

    try:
        value = visit(tree)
    except ArithmeticError:
        value = None
    return {"value": value, "trace": inspected}


def observe():
    counts = Counter()
    first = {}
    for values in product(range(LOW, HIGH + 1), repeat=3):
        a, b, c = values
        left_partial, right_partial, total = within(a + b), within(b + c), within(a + b + c)
        left = evaluate(LEFT, values, wrapping=False)
        right = evaluate(RIGHT, values, wrapping=False)
        value_agrees = left["value"] == right["value"]
        complete_agrees = left == right
        assert value_agrees == (not total or left_partial == right_partial)
        assert complete_agrees == (left_partial and (right_partial or not total))
        assert evaluate(LEFT, values, wrapping=True) == evaluate(RIGHT, values, wrapping=True)
        props = {
            "triples": True, "wrapping_agreement": True,
            "checked_value_mismatches": not value_agrees,
            "checked_complete_mismatches": not complete_agrees,
            "same_value_or_failure_but_different_trace": value_agrees and not complete_agrees,
            "both_partial_sums_in_range": left_partial and right_partial,
            "both_partial_sums_in_range_with_final_failure": left_partial and right_partial and not total,
        }
        for name, holds in props.items():
            counts[name] += holds
            if holds and name.endswith(("mismatches", "different_trace")) and name not in first:
                first[name] = {"values": values, "left": left, "right": right}
    assert counts["triples"] == 4096
    assert counts["checked_complete_mismatches"] == (
        counts["checked_value_mismatches"] + counts["same_value_or_failure_but_different_trace"]
    )
    return dict(counts), first


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    args = parser.parse_args()
    lean = args.lean.resolve()
    proof = HERE / "Reassociate.lean"
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    proofs = subprocess.check_output([lean, "-DwarningAsError=true", proof], text=True).splitlines()
    expected_axioms = {"guardedReassociation", "exactObservedCondition", "exactValueCondition"}
    expected_no_axioms = {"resultCounterexample", "sameFailureDifferentTrace"}
    assert set(proofs) == ({f"'{name}' depends on axioms: [propext]" for name in expected_axioms}
                           | {f"'{name}' does not depend on any axioms" for name in expected_no_axioms})
    counts, witnesses = observe()
    print(json.dumps({
        "schema": "llmlang-rt05-reassociation/1", "python": platform.python_version(),
        "lean": version, "axioms": proofs, "signed_domain": [LOW, HIGH],
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (Path(__file__), proof)},
        "counts": counts, "first_witnesses": witnesses,
    }, indent=2))


if __name__ == "__main__":
    main()
