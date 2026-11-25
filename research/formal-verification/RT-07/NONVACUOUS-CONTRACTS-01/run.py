#!/usr/bin/env python3
"""Check per-branch coverage and test coarse substitutes."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
FIRST = (("continue", 0), ("continue", 1), ("error", 0), ("diverge", 0), ("cancel", 0))
NEXT = ("return", "error", "diverge", "cancel")


def select(values, mask):
    return tuple(value for bit, value in enumerate(values) if mask & (1 << bit))


def execute(prefix, admitted, suffixes):
    outcomes = set()
    holes = set()
    if not prefix:
        holes.add("empty prefix")
    for tag, state in prefix:
        if tag != "continue":
            outcomes.add((tag, ("prefix",)))
        elif not admitted & (1 << state):
            holes.add(f"state {state} inadmissible")
        elif not suffixes[state]:
            holes.add(f"state {state} missing outcome")
        else:
            for suffix in suffixes[state]:
                outcomes.add((suffix, (f"prefix success {state}", f"suffix {suffix}")))
    return outcomes, holes


def compare():
    counts = Counter()
    controls = {}
    names = {
        (0, 0, 0, 3): "empty_prefix",
        (5, 0, 0, 3): "prefix_error_hides_uncovered_success",
        (1, 4, 0, 1): "reachable_explicit_divergence",
        (1, 1, 0, 0): "out_of_domain_suffix_rows",
    }
    rows = sha256()
    for prefix_mask, left_mask, right_mask, admitted in product(
        range(1 << len(FIRST)), range(1 << len(NEXT)), range(1 << len(NEXT)), range(4)
    ):
        prefix = select(FIRST, prefix_mask)
        suffixes = select(NEXT, left_mask), select(NEXT, right_mask)
        actual, holes = execute(prefix, admitted, suffixes)
        reached = prefix_mask & 3
        available = (int(bool(left_mask)) | (int(bool(right_mask)) << 1)) & admitted
        covered = bool(prefix_mask) and reached & ~available == 0
        if covered != (not holes) or covered and not actual:
            raise AssertionError((prefix_mask, left_mask, right_mask, admitted))

        counts["cases"] += 1
        counts["covered"] += covered
        counts["covered_without_possible_return"] += covered and not any(
            tag == "return" for tag, _ in actual)
        counts["not_covered"] += not covered
        counts["nonempty_composite_hides_holes"] += bool(actual) and not covered
        counts["admitted_branches_hide_holes"] += reached & ~admitted == 0 and not covered
        terminal_without_error = all(tag != "error" for tag, _ in actual)
        counts["uncovered_passes_universal_no_error"] += terminal_without_error and not covered
        counts["empty_composite_passes_universal_no_error"] += terminal_without_error and not actual
        rows.update(json.dumps([prefix_mask, left_mask, right_mask, admitted,
                                sorted(actual), sorted(holes), covered]).encode())

        key = (prefix_mask, left_mask, right_mask, admitted)
        if key in names:
            controls[names[key]] = {"input": key, "covered": covered,
                                    "outcomes": sorted(actual), "holes": sorted(holes)}
    assert controls["reachable_explicit_divergence"]["covered"]
    assert len(controls["reachable_explicit_divergence"]["outcomes"]) == 1
    assert not controls["prefix_error_hides_uncovered_success"]["covered"]
    assert controls["prefix_error_hides_uncovered_success"]["outcomes"]
    return counts, controls, rows.hexdigest()


if __name__ == "__main__":
    counts, controls, digest = compare()
    print(json.dumps({
        "schema": "llmlang-nonvacuous-contracts/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Compose.lean", "axioms.txt")},
        "prefix_order": FIRST, "suffix_order": NEXT,
        "counts": counts, "controls": controls, "rows_sha256": digest,
    }, indent=2))
