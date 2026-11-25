#!/usr/bin/env python3
"""Compare coarse maximal outcomes and terminal-only refinement."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
TRANSIENT = ("entry", "step")
TERMINAL = ("return", "error")
STATES = TRANSIENT + TERMINAL
EDGES = tuple(product(TRANSIENT, STATES))


def adjacency(mask):
    return {
        source: tuple(target for i, (left, target) in enumerate(EDGES)
                      if left == source and mask & (1 << i))
        for source in TRANSIENT
    }


def paths(graph, start, prefix=()):
    if start in TERMINAL:
        return {start}
    if start in prefix:
        return {"diverge"}
    if not graph[start]:
        return {"deadlock"}
    return set().union(*(paths(graph, item, (*prefix, start)) for item in graph[start]))


def closure(graph, start):
    reach = {(left, right) for left, successors in graph.items() for right in successors}
    for middle in STATES:
        reach |= {(left, right) for left, target in reach if target == middle
                  for source, right in reach if source == middle}
    reachable = {start} | {target for left, target in reach if left == start}
    observed = reachable.intersection(TERMINAL)
    if any((state, state) in reach for state in reachable):
        observed.add("diverge")
    if any(not graph[state] for state in reachable.intersection(TRANSIENT)):
        observed.add("deadlock")
    return observed


def compare():
    outcomes = []
    for mask in range(1 << len(EDGES)):
        graph = adjacency(mask)
        for entry in TRANSIENT:
            observed = paths(graph, entry)
            if observed != closure(graph, entry):
                raise AssertionError(f"Mismatched maximal observations for {mask}, {entry}")
            outcomes.append((mask, entry, observed, observed.intersection(TERMINAL)))

    count, witnesses = Counter(), {}
    for original, replacement in product(outcomes, repeat=2):
        old, new = original[2], replacement[2]
        exact = new <= old
        projected = replacement[3] <= original[3]
        count["explicit_refinement"] += exact
        count["terminal_refinement"] += projected
        if exact and not projected:
            raise AssertionError("Projection cannot lose a valid complete refinement")
        if projected and not exact:
            count["unsound_projected_admission"] += 1
            lost = new - old
            if not replacement[3]:
                count["of_which_no_terminal_replacement"] += 1
            if old == {"return"}:
                for category in sorted(lost):
                    witnesses.setdefault(category, {
                        "original": [original[0], original[1], sorted(old)],
                        "replacement": [replacement[0], replacement[1], sorted(new)],
                    })
    looping_with_exit = adjacency((1 << EDGES.index(("entry", "entry"))) |
                                  (1 << EDGES.index(("entry", "return"))))
    may_return_but_not_must = paths(looping_with_exit, "entry")
    if may_return_but_not_must != {"return", "diverge"}:
        raise AssertionError("Expected possible termination and divergence")
    return {
        "schema": "llmlang-nondeterministic-refinement/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Refinement.lean", "axioms.txt")},
        "edge_order": EDGES, "graph_count": 1 << len(EDGES), "initial_states": len(outcomes),
        "ordered_comparisons": len(outcomes) ** 2, "counts": count, "witnesses": witnesses,
        "possible_return_and_divergence": sorted(may_return_but_not_must),
        "finite_outcomes": [[mask, entry, sorted(result)] for mask, entry, result, _ in outcomes],
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
