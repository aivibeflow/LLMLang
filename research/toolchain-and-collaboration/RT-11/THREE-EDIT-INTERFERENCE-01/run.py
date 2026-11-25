#!/usr/bin/env python3
"""Detect third-order effects despite exact single and pairwise checks."""

from collections import Counter
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
EDITS = (1, 2, 4)
STATE = range(8)


def apply(state, edits):
    # Every edit changes a different Boolean field.
    for edit in edits:
        state ^= edit
    return state


def observed(table, state):
    return bool(table & (1 << state))


def compare():
    counters = Counter()
    digest = sha256()
    for table, baseline in product(range(1 << len(STATE)), STATE):
        before = observed(table, baseline)
        subsets = {
            edits: observed(table, apply(baseline, edits)) == before
            for count in range(4) for edits in combinations(EDITS, count)
        }
        singles = all(subsets[(edit,)] for edit in EDITS)
        pairs = singles and all(subsets[pair] for pair in combinations(EDITS, 2))
        final = subsets[EDITS]
        closed = all(subsets.values())
        order_results = []
        for order in permutations(EDITS):
            current = baseline
            observations = [before]
            for edit in order:
                current ^= edit
                observations.append(observed(table, current))
            # Independent endpoint computation from the disjoint field mask.
            if current != baseline ^ 7 or final != (observations[-1] == before):
                raise AssertionError((table, baseline, order))
            uniform = all(value == before for value in observations)
            order_results.append(uniform)
            counters["ordered_schedules"] += 1
            counters["verified_schedule_preserves_every_prefix"] += uniform
        if closed != all(order_results):
            raise AssertionError((table, baseline, closed, order_results))
        counters["table_and_baseline_profiles"] += 1
        counters["single_edit_gate_admitted"] += singles
        counters["single_edit_gate_false_final_admissions"] += singles and not final
        counters["pairwise_gate_admitted"] += pairs
        counters["pairwise_gate_false_final_admissions"] += pairs and not final
        counters["some_schedule_preserves_prefixes"] += any(order_results)
        counters["every_schedule_preserves_prefixes"] += closed
        counters["some_but_not_every_schedule_preserves_prefixes"] += any(order_results) and not closed
        digest.update(bytes((table, baseline, singles, pairs, final, closed, *order_results)))

    witness = {str(state): observed(128, state) for state in STATE}
    assert sum(witness.values()) == 1 and witness["7"]
    assert counters["pairwise_gate_false_final_admissions"] == 16
    return counters, witness, digest.hexdigest()


if __name__ == "__main__":
    counts, witness, digest = compare()
    print(json.dumps({
        "schema": "llmlang-three-edit-noninterference/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("Noninterference.lean", "run.py", "axioms.txt")},
        "counts": counts, "all_three_true_witness": witness, "ordered_rows_sha256": digest,
    }, indent=2))
