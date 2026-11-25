"""Measure traversal with path histories, exact state coalescing and an invalid cheaper key."""

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import random
from statistics import median, quantiles
from time import get_clock_info, perf_counter_ns

BASELINE = "5619c764c399c25453730cd93d50515dd6eb7ba2"
DEPTHS = (4, 8, 12, 16, 20)
TRIALS = 9
SEED = 32
FALLBACK_THRESHOLD = 4096


def diamonds(depth):
    edges = [[] for _ in range(1 + 3 * depth)]
    for step in range(depth):
        left, right, join = 3 * step + 1, 3 * step + 2, 3 * step + 3
        edges[3 * step].extend(((left, 0), (right, 1)))
        edges[left].append((join, 0))
        edges[right].append((join, 0))
    return edges


def visit(edges, key=None, limit=None):
    stack = [(0, 0)]
    seen = set()
    visits = 0
    outcomes = set()
    while stack:
        node, parity = stack.pop()
        if key == "full-state":
            identity = node, parity
        else:
            identity = node
        if key is not None:
            if identity in seen:
                continue
            seen.add(identity)
        if limit is not None and visits == limit:
            return visits, sorted(outcomes), False
        visits += 1
        successors = edges[node]
        if not successors:
            outcomes.add(parity)
        for target, flip in successors:
            stack.append((target, parity ^ flip))
    return visits, sorted(outcomes), True


def measure(edges, depths, iterations, calibration):
    rows = {method: [] for method in ("paths", "full-state")}
    for order in calibration:
        for method in order:
            key = None if method == "paths" else method
            count = iterations[method]
            start = perf_counter_ns()
            for _ in range(count):
                observed = visit(edges, key)
            elapsed = perf_counter_ns() - start
            assert observed == depths[method]
            rows[method].append(elapsed)
    return rows


def analyze(depth, repetitions, orderings):
    edges = diamonds(depth)
    expected = {"paths": ((1 << (depth + 2)) - 3, [0, 1], True),
                "full-state": (6 * depth - 1, [0, 1], True)}
    assert visit(edges) == expected["paths"]
    assert visit(edges, "full-state") == expected["full-state"]
    assert visit(edges, "node-only") == (3 * depth + 1, [depth % 2], True)
    visits, results, finished = visit(edges, limit=FALLBACK_THRESHOLD)
    exported = results if finished else visit(edges, "full-state")[1]
    assert exported == [0, 1]

    measurement = measure(edges, expected, repetitions, orderings)
    elapsed = {}
    for method, samples in measurement.items():
        adjusted = [total / repetitions[method] for total in samples]
        q1, _, q3 = quantiles(adjusted, n=4, method="inclusive")
        elapsed[method] = {"raw_total_ns": samples, "traversals_per_trial": repetitions[method],
                           "median_ns_per_traversal": median(adjusted),
                           "q1_ns_per_traversal": q1, "q3_ns_per_traversal": q3}
    return {
        "depth": depth, "graph_nodes": len(edges), "graph_edges": sum(map(len, edges)),
        "complete_visits": {method: observed[0] for method, observed in expected.items()},
        "node_only_outcomes": [depth % 2], "exact_outcomes": [0, 1],
        "path_prefix": {"visits": visits, "terminal_outcomes": results, "complete": finished,
                        "exact_worklist_used": not finished, "exported_outcomes": exported},
        "trial_order": orderings, "elapsed": elapsed,
    }


def get_cpu_model():
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "model name":
            return value.strip()
    raise ValueError("CPU model not found")


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--cpu", type=int, required=True)
    config = args.parse_args()
    assert config.cpu in os.sched_getaffinity(0)
    os.sched_setaffinity(0, {config.cpu})
    gc.disable()
    rng = random.Random(SEED)
    rows = []
    for depth in DEPTHS:
        orderings = []
        for _ in range(TRIALS):
            order = ["paths", "full-state"]
            rng.shuffle(order)
            orderings.append(order)
        repetitions = {"paths": 20 if depth <= 8 else 2 if depth <= 12 else 1,
                       "full-state": 200}
        rows.append(analyze(depth, repetitions, orderings))
    clock = get_clock_info("perf_counter")
    print(json.dumps({
        "baseline": BASELINE, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(), "kernel": platform.release(),
        "system": platform.system(), "target": platform.machine(),
        "cpu_model": get_cpu_model(), "pinned_cpu": config.cpu, "trial_seed": SEED,
        "trials_per_profile": TRIALS, "cyclic_gc_enabled": gc.isenabled(),
        "clock": {"implementation": clock.implementation, "resolution_seconds": clock.resolution},
        "path_prefix_limit": FALLBACK_THRESHOLD,
        "rows": rows,
    }, indent=2))


if __name__ == "__main__":
    main()
