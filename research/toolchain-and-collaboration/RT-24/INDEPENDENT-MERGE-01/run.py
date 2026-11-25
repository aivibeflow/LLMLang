"""Enumerate a finite merge matrix and check universal independence lemmas."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
BASELINE = "568e1e1927b4f2bb3461e95584b703f52557cd7e"
STATES = tuple(product(range(3), repeat=3))


@dataclass(frozen=True)
class Edit:
    target: int
    source: int | None
    literal: int = 0

    @property
    def reads(self):
        return () if self.source is None else (self.source,)

    def value(self, state):
        return self.literal if self.source is None else state[self.source]

    def apply(self, state):
        return tuple(self.value(state) if i == self.target else item for i, item in enumerate(state))


def independent(left, right):
    return left.target != right.target and left.target not in right.reads and right.target not in left.reads


def capacity(state):
    return sum(state) <= 2


def replay(lean):
    tool = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in tool
    axioms = subprocess.check_output([lean, "-DwarningAsError=true", HERE / "Independence.lean"], text=True).splitlines()
    assert len(axioms) == 3 and all("sorryAx" not in row for row in axioms)
    edits = [Edit(target, None, literal) for target, literal in product(range(3), (0, 1))]
    edits += [Edit(target, source) for target, source in product(range(3), repeat=2) if target != source]
    counts, examples = Counter(), {}
    for left, right, base in product(edits, edits, STATES):
        parents = left.apply(base), right.apply(base)
        forward = right.apply(parents[0])
        backward = left.apply(parents[1])
        if independent(left, right):
            assert forward == backward
            counts["proven_shape"] += 1
            if capacity(base) and all(map(capacity, parents)):
                counts["independent_with_valid_parents"] += 1
                if not capacity(forward):
                    counts["merged_capacity_violation"] += 1
                    examples.setdefault("valid_parents_invalid_candidate", {
                        "base": base, "left": asdict(left), "right": asdict(right),
                        "parents": parents, "candidate": forward,
                    })
        else:
            counts["needs_review"] += 1
            if forward != backward:
                counts["order_difference"] += 1
                examples.setdefault("overlapping_edits_with_order_difference", {
                    "base": base, "left": asdict(left), "right": asdict(right),
                    "forward": forward, "backward": backward,
                })
    base = (1, 0, 0)
    left = Edit(0, None, 0)
    right = Edit(1, 0)
    after_left = left.apply(base)
    assert base[0] == 1 and after_left[0] == 0
    assert right.apply(after_left) != left.apply(right.apply(base))
    assert not independent(left, right)
    examples["omitted_read_would_appear_disjoint"] = {
        "base": base, "claimed_right_reads": (), "actual_right_reads": right.reads,
        "forward": right.apply(after_left), "backward": left.apply(right.apply(base)),
    }
    return {
        "schema": "rt24-independent-edits-v1", "baseline": BASELINE,
        "python": platform.python_version(), "lean": tool, "axioms": axioms,
        "checks": len(edits) ** 2 * len(STATES), "states": len(STATES), "edits": len(edits),
        "counts": dict(counts), "examples": examples,
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "Independence.lean")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.lean), sort_keys=True, indent=2))
