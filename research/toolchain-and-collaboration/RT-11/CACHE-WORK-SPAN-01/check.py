"""Check the analytical reuse equation against serial work and ideal parallel span."""

from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import subprocess


BASE = "2c7e8914f77e97617bcb883e4c01fa85df49974d"
ROOT = "research/toolchain-and-collaboration/RT-11"
NODES = (0, 1, 2, 3)
EDGES = tuple(combinations(NODES, 2))
COSTS = (3, 7, 11, 19)
RESTORE = (1, 8, 2, 20)


def critical_path(edges, weights):
    finish = []
    for node, duration in enumerate(weights):
        before = max((finish[source] for source, dest in edges if dest == node), default=0)
        finish.append(before + duration)
    return max(finish)


def paths_oracle(edges, weights):
    return max(sum(weights[node] for node in path) for size in range(1, 5)
               for path in combinations(NODES, size)
               if all(edge in edges for edge in zip(path, path[1:])))


def direction(before, after):
    return "faster" if after < before else "slower" if after > before else "equal"


def check():
    pairs = Counter()
    witnesses = {}
    sum_costs = sum(COSTS)
    for edge_mask in product((False, True), repeat=len(EDGES)):
        topology = {edge for edge, active in zip(EDGES, edge_mask, strict=True) if active}
        cold_span = critical_path(topology, COSTS)
        assert cold_span == paths_oracle(topology, COSTS)
        for hits in product((False, True), repeat=len(NODES)):
            avoided = sum(value for value, hit in zip(COSTS, hits, strict=True) if hit)
            restore_cost = sum(value for value, hit in zip(RESTORE, hits, strict=True) if hit)
            warm_weights = [RESTORE[node] if hits[node] else COSTS[node] for node in NODES]
            warm_work = sum(warm_weights)
            estimated_speedup = 1 / (1 - Fraction(avoided, sum_costs) + Fraction(restore_cost, sum_costs))
            assert estimated_speedup == Fraction(sum_costs, warm_work)
            warm_span = critical_path(topology, warm_weights)
            assert warm_span == paths_oracle(topology, warm_weights)
            disposition = direction(sum_costs, warm_work), direction(cold_span, warm_span)
            pairs[disposition] += 1
            if disposition[0] != disposition[1] and disposition not in witnesses:
                witnesses[disposition] = {
                    "edges": sorted(topology), "hits": hits, "cold_work": sum_costs, "warm_work": warm_work,
                    "cold_span": cold_span, "warm_span": warm_span,
                }
    return {"counts": {"/".join(pair): count for pair, count in sorted(pairs.items())},
            "witnesses": {"/".join(pair): witness for pair, witness in sorted(witnesses.items())},
            "modeled_costs": {"cold": COSTS, "restoring_hit": RESTORE}}


def archives():
    result = {}
    for name in ("PAIRED-CACHE-SPEEDUP-01", "BUILD-PHASE-OVERHEAD-01", "MULTI-ACTION-HITS-01"):
        path = f"{ROOT}/{name}/evidence.json"
        raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
        result[name] = sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps({
        "baseline": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archive_sha256": archives(), "result": check(),
    }, sort_keys=True, indent=2))
