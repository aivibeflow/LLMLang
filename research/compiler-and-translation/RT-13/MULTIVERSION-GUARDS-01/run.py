"""Check priority changes and fail-closed multiversion coverage in a finite fixture."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
MINIMUM = -(1 << 31)
MAXIMUM = (1 << 31) - 1
LANES = ("zero-right", "small-nonnegative", "baseline")
VALUES = (MINIMUM, MINIMUM + 1, -128, -1, 0, 1, 63, 127, 128, MAXIMUM - 1, MAXIMUM)


def source(a, b):
    value = a + b
    return ("result", value) if MINIMUM <= value <= MAXIMUM else ("overflow", None)


def choose(order, states, a, b, *, ignore_domain=False, ignore_evidence=False):
    for lane in order:
        state = states[lane]
        if state == "unavailable" or (state == "unchecked" and not ignore_evidence):
            continue
        if lane == "zero-right" and (ignore_domain or b == 0):
            return lane, ("result", a)
        if lane == "small-nonnegative" and (ignore_domain or 0 <= min(a, b) <= max(a, b) <= 127):
            return lane, ("result", a + b)
        if lane == "baseline":
            return lane, source(a, b)
    return None, ("unavailable", None)


def matrix():
    dispositions = ("ready", "unavailable", "unchecked")
    counts = Counter()
    controls = {}
    for statuses, a, b in product(product(dispositions, repeat=3), VALUES, VALUES):
        states = dict(zip(LANES, statuses, strict=True))
        candidates = {"baseline"}
        if b == 0:
            candidates.add("zero-right")
        if all(value in range(128) for value in (a, b)):
            candidates.add("small-nonnegative")
        eligible = candidates & {lane for lane, state in states.items() if state == "ready"}
        expected = source(a, b) if eligible else ("unavailable", None)
        for order in permutations(LANES):
            lane, observed = choose(order, states, a, b)
            if observed != expected or (lane not in eligible if eligible else lane is not None):
                raise ValueError((states, order, a, b, lane, observed, expected, eligible))
            counts["decisions"] += 1
            counts[observed[0]] += 1
            counts["multiple_eligible"] += len(eligible) > 1
            wrong_lane, wrong_value = choose(order, states, a, b, ignore_domain=True)
            counts["guardless_invalid_selection"] += wrong_lane is not None and wrong_lane not in eligible
            counts["guardless_reported_result_differs"] += wrong_value != expected
            unchecked_lane, _ = choose(order, states, a, b, ignore_evidence=True)
            counts["evidence_free_selects_unchecked"] += unchecked_lane is not None and states[unchecked_lane] == "unchecked"
            if statuses == ("ready", "ready", "unavailable") and (a, b) in ((63, 0), (MAXIMUM, 1)):
                label = f"{a}/{b}/" + ",".join(order)
                controls[label] = {"selected": lane, "observed": observed}
    return dict(counts), controls


def lean_check(lean):
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    process = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Multiversion.lean")],
                             check=True, text=True, capture_output=True, timeout=30)
    names = ("guarded_refinement", "choice_matches_reference", "priority_invariant", "unavailable_exactly_when_no_eligible")
    expected = [f"'{name}' depends on axioms: [propext, Classical.choice, Quot.sound]" for name in names]
    if process.stderr or process.stdout.splitlines() != expected:
        raise ValueError((process.stdout, process.stderr))
    return {"version": version, "axioms": process.stdout.splitlines()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    counts, controls = matrix()
    result = {
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Multiversion.lean", "run.py")},
        "lean": lean_check(args.lean), "counts": counts, "controls": controls,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
