"""Enumerate finite equality and hash combinations and check general key laws in Lean."""

import argparse
from collections import Counter
import hashlib
import itertools
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = "35f553ae1cd9fdd71c5f882f97a2586424af7be9"
DOMAIN = (0, 1, 2)
PAIRS = tuple(itertools.combinations(DOMAIN, 2))
ORDERS = tuple(itertools.permutations(DOMAIN))


def partition(order, related, hashes):
    groups = []
    for value in order:
        for group in groups:
            rep = group[0]
            if hashes[rep] == hashes[value] and related(rep, value):
                group.append(value)
                break
        else:
            groups.append([value])
    return tuple(sorted(tuple(sorted(group)) for group in groups))


def enumerate_models():
    cases = []
    counts = Counter()
    for selected in itertools.product((False, True), repeat=len(PAIRS)):
        edges = dict(zip(PAIRS, selected, strict=True))

        def related(left, right):
            return left == right or edges[tuple(sorted((left, right)))]

        triples = [
            (x, y, z) for x, y, z in itertools.product(DOMAIN, repeat=3)
            if related(x, y) and related(y, z) and not related(x, z)
        ]
        for hashes in itertools.product(DOMAIN, repeat=3):
            mismatches = [(x, y) for x, y in PAIRS if related(x, y) and hashes[x] != hashes[y]]
            observations = [partition(order, related, hashes) for order in ORDERS]
            pair_contracts = not mismatches
            global_laws = pair_contracts and not triples
            order_dependent = len(set(observations)) > 1
            assert not global_laws or not order_dependent
            assert not pair_contracts or bool(triples) == order_dependent
            counts["typed"] += 1
            counts["typed_but_order_dependent"] += order_dependent
            counts["pair_contracts"] += pair_contracts
            counts["global_laws"] += global_laws
            counts["pair_contracts_but_order_dependent"] += pair_contracts and order_dependent
            cases.append({
                "edges": selected, "hashes_by_value": hashes, "different_hash_equal_pairs": mismatches,
                "transitivity_failures": triples, "partitions_by_order": observations,
                "pair_contracts": pair_contracts, "global_laws": global_laws,
            })
    assert counts == {"typed": 216, "typed_but_order_dependent": 9,
                      "pair_contracts": 66, "global_laws": 57,
                      "pair_contracts_but_order_dependent": 9}
    witness = next(row for row in cases if row["edges"] == (True, False, True)
                   and row["hashes_by_value"] == (0, 0, 0))
    assert len({len(groups) for groups in witness["partitions_by_order"]}) == 2
    return dict(counts), cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    args = parser.parse_args()
    lean = args.lean.resolve()
    version = subprocess.check_output([lean, "--version"], text=True, timeout=10).strip()
    assert "version 4.36.0" in version and "611c117bfaf7" in version, version
    proof = subprocess.check_output([lean, "EqualityLaws.lean"], cwd=HERE, text=True, timeout=20)
    statements = ("keyEqualityLaws", "compatibleProjectedHash", "nearReflexive",
                  "nearSymmetric", "nearCounterexample")
    lines = proof.splitlines()
    assert lines == [f"'{name}' does not depend on any axioms" for name in statements], lines
    counts, cases = enumerate_models()
    metadata = {
        "baseline": BASELINE, "python": platform.python_version(), "lean": version,
        "source_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("run.py", "EqualityLaws.lean")
        },
        "axiom_report": lines, "domain": DOMAIN, "pairs": PAIRS, "orders": ORDERS,
        "counts": counts,
    }
    header = json.dumps(metadata, indent=2).removesuffix("\n}")
    print(header + ',\n  "cases": [')
    print(",\n".join("    " + json.dumps(row) for row in cases))
    print("  ]\n}")


if __name__ == "__main__":
    main()
