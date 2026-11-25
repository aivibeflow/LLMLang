"""Verify fallback when exact traversal exhausts a semantic-state budget."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DIAMOND = HERE.parent / "DIAMOND-TRAVERSAL-01" / "run.py"
SPEC = spec_from_file_location("diamond_reference_fixture", DIAMOND)
diamond = module_from_spec(SPEC)
SPEC.loader.exec_module(diamond)

DEPTHS = (8, 12, 16, 20)
HISTORIES = (1, 4, 8, 12, 16)
LIMITS = (64, 256, 4096, 65536)


def history_diamonds(depth, bits):
    graph = diamond.diamonds(depth)
    for i in range(depth):
        target, _ = graph[3 * i][1]
        graph[3 * i][1] = (target, (1 << i) if i < bits else 0)
    return graph


def classify(observed, complete, trusted_universe):
    if complete:
        return "exact", frozenset(observed)
    if trusted_universe is not None:
        return "revalidate-broader-scope", trusted_universe
    return "unknown", None


def collect():
    counts = Counter()
    rows = {}
    for depth, bits in product(DEPTHS, HISTORIES):
        graph = history_diamonds(depth, bits)
        expected = frozenset(range(1 << min(depth, bits)))
        inventory = frozenset(range(1 << bits))
        for limit in LIMITS:
            visits, partial, complete = diamond.visit(graph, key="full-state", limit=limit)
            if visits > limit or not set(partial) <= expected:
                raise ValueError((depth, bits, limit, visits, partial[:10]))
            checked = {}
            for scope, universe in (("checked", inventory), ("unavailable", None)):
                decision, outcome = classify(partial, complete, universe)
                if decision == "exact" and (not complete or outcome != expected):
                    raise ValueError("an incomplete prefix was treated as exact")
                if decision == "revalidate-broader-scope" and not expected <= outcome:
                    raise ValueError("the escalation is not a superset")
                if decision == "unknown" and (complete or outcome is not None):
                    raise ValueError("unknown must withhold an outcome set")
                counts[decision] += 1
                checked[scope] = {"decision": decision, "outcome_count": None if outcome is None else len(outcome)}
            counters = {
                "partial_outcomes": len(partial), "exact_outcomes": len(expected),
                "graph_nodes": len(graph), "visits": visits, "complete": complete,
                "coarse_inventory_size": len(inventory), "fallbacks": checked,
            }
            if not complete and set(partial) != expected:
                counts["prefix_only_loses_outcomes"] += 1
            rows[f"{depth}/{bits}/{limit}"] = counters
    if min(counts[name] for name in ("unknown", "revalidate-broader-scope", "prefix_only_loses_outcomes")) < 1:
        raise ValueError("a fallback control did not execute")
    return {"counts": dict(counts), "cases": len(rows), "profiles": rows,
            "sources_sha256": {"diamond_fixture": sha256(DIAMOND.read_bytes()).hexdigest(),
                               "runner": sha256((HERE / "run.py").read_bytes()).hexdigest()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(), indent=2, sort_keys=True) + "\n")
