"""Compare non-interference decisions for disjoint edits in a finite model."""

import argparse
from collections import Counter
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
VARIABLES = tuple(range(3))


def observed(function, state):
    return (function >> state) & 1


def compare():
    counts = Counter()
    first_false = None
    for function, base, edits in product(range(256), range(8), combinations(VARIABLES, 2)):
        i, j = edits
        left = base ^ (1 << i)
        right = base ^ (1 << j)
        final = left ^ (1 << j)
        before, first, second, after = (observed(function, state) for state in (base, left, right, final))
        direct = before == after
        base_local = before == first == second
        sequential = before == first == after
        contextual = before == first == second == after
        assert not sequential or direct
        assert not contextual or direct
        flags = {
            "cases": True,
            "direct": direct,
            "base_local": base_local,
            "base_local_false_reuse": base_local and not direct,
            "sequential": sequential,
            "contextual": contextual,
            "direct_safe_but_sequential_blocks": direct and not sequential,
        }
        for name, enabled in flags.items():
            counts[name] += enabled
        if flags["base_local_false_reuse"] and first_false is None:
            first_false = {"truth_table_mask": function, "base": base, "edit_bits": edits,
                           "states": [base, left, right, final], "outcomes": [before, first, second, after]}
    assert counts == {
        "cases": 6144, "direct": 3072, "base_local": 1536, "base_local_false_reuse": 768,
        "sequential": 1536, "contextual": 768, "direct_safe_but_sequential_blocks": 1536,
    }
    return dict(counts), first_false


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    args = parser.parse_args()
    lean = args.lean.resolve()
    source = HERE / "Composition.lean"
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    audit = subprocess.check_output([lean, "-DwarningAsError=true", source], text=True).splitlines()
    assert audit == [f"'{name}' does not depend on any axioms" for name in (
        "sequentialEquality", "uniformNonInterference", "disjointSeparateEditsInsufficient"
    )]
    counts, witness = compare()
    print(json.dumps({
        "schema": "llmlang-rt11-composed-noninterference/1", "python": platform.python_version(),
        "lean": version, "axioms": audit,
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (Path(__file__), source)},
        "counts": counts, "first_false_reuse": witness,
    }, indent=2))


if __name__ == "__main__":
    main()
