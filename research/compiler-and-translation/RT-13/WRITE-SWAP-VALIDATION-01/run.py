"""Compare a checked write-swap rule with finite source/target validation."""

import argparse
import hashlib
import json
import platform
import subprocess
from itertools import product
from pathlib import Path

BASELINE = "5ad921e8656559108ccd211f658704c89360d73f"
HERE = Path(__file__).resolve().parent
WRITES = tuple(product(range(2), (-1, 1), (False, True)))
HEAPS = tuple(product((-1, 1), repeat=2))
PROFILE = "final-heap-and-ordered-visible-writes"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def observation(program, initial):
    heap = list(initial)
    events = []
    for slot, value, visible in program:
        heap[slot] = value
        if visible:
            events.append((slot, value))
    return tuple(heap), tuple(events)


def static_guard(a, b):
    first, second = a[:2], b[:2]
    same_heap = a[0] != b[0] or a[1] == b[1]
    same_events = not (a[2] and b[2]) or first == second
    return same_heap and same_events


def validate(source, target):
    witness = None
    for heap in HEAPS:
        left, right = observation(source, heap), observation(target, heap)
        if left != right and witness is None:
            witness = {"input_heap": heap, "source": left, "target": right}
    return witness


def key(source, target, profile):
    return digest(json.dumps([profile, source, target], separators=(",", ":")).encode())


def experiment():
    comparisons = []
    for a, b in product(WRITES, repeat=2):
        source, target = (a, b), (b, a)
        counterexample = validate(source, target)
        admissible = static_guard(a, b)
        assert (counterexample is None) == admissible
        state_only = all(observation(source, heap)[0] == observation(target, heap)[0] for heap in HEAPS)
        comparisons.append({
            "source": source, "swap_target": target, "swap_safe": admissible,
            "final_state_only_passes": state_only, "swap_counterexample": counterexample,
            "drop_first_counterexample": validate(source, (b,)),
        })
    a, b = (0, 1, False), (1, -1, False)
    source, valid, wrong = (a, b), (b, a), (b,)
    assert static_guard(a, b) and validate(source, valid) is None
    witness = validate(source, wrong)
    assert witness and key(source, valid, PROFILE) != key(source, wrong, PROFILE)
    assert key(source, valid, PROFILE) != key(source, valid, "final-heap-only")
    return {
        "ordered_write_pairs": len(comparisons),
        "initial_heaps_per_pair": len(HEAPS),
        "guard_admits_swaps": sum(row["swap_safe"] for row in comparisons),
        "state_only_false_admissions": sum(row["final_state_only_passes"] and not row["swap_safe"]
                                           for row in comparisons),
        "drop_first_admissions": sum(row["drop_first_counterexample"] is None for row in comparisons),
        "drop_first_admissions_when_swap_unsafe": sum(
            row["drop_first_counterexample"] is None and not row["swap_safe"] for row in comparisons
        ),
        "wrong_target_control": {
            "source": source, "checked_swap": valid, "actual_target": wrong,
            "source_target_receipt": key(source, valid, PROFILE),
            "actual_target_receipt_key": key(source, wrong, PROFILE),
            "counterexample": witness,
        },
        "comparisons": comparisons,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    args = parser.parse_args()
    lean = args.lean.resolve(strict=True)
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    source = HERE / "Swap.lean"
    axioms = subprocess.check_output([lean, "-DwarningAsError=true", source], text=True, timeout=30).splitlines()
    assert len(axioms) == 3 and all(line.endswith("depends on axioms: [propext]") for line in axioms)
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "lean": version,
        "source_sha256": digest(source.read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "axioms": axioms, "profile": PROFILE,
    } | experiment(), indent=2))


if __name__ == "__main__":
    main()
