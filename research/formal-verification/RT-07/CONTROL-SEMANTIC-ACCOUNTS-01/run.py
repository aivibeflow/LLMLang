#!/usr/bin/env python3
"""Compare three independent accounts of a bounded family of control graphs."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
INTERNAL = range(3)
RETURN, ERROR = 3, 4
RETURNS, ERRORS, DEADLOCKS, DIVERGES = (1, 2, 4, 8)
ALPHABET = ("return", "error", "deadlock", "diverge")
EDGES = tuple(tuple(i for i in range(5) if mask & (1 << i)) for mask in range(32))


def executions(graph, state, ancestors=0):
    if state in (RETURN, ERROR):
        return 1 << (state - RETURN)
    if ancestors & (1 << state):
        return DIVERGES
    if not graph[state]:
        return DEADLOCKS
    observed = 0
    for child in graph[state]:
        observed |= executions(graph, child, ancestors | (1 << state))
    return observed


def fixed_point(step, start):
    while True:
        next_value = step(start)
        if next_value == start:
            return start
        start = next_value


def merge(masks):
    observed = 0
    for mask in masks:
        observed |= mask
    return observed


def meanings(graph):
    def finite(previous):
        return tuple(merge(previous[child] for child in targets) if targets else DEADLOCKS
                     for targets in graph) + (RETURNS, ERRORS)

    def infinite(previous):
        return tuple(any(previous[child] for child in targets)
                     for targets in graph) + (False, False)

    finite_results = fixed_point(finite, (0, 0, 0, RETURNS, ERRORS))
    infinite_results = fixed_point(infinite, (True, True, True, False, False))
    return tuple(finite_results[state] | (DIVERGES if infinite_results[state] else 0)
                 for state in INTERNAL)


def preconditions(graph, goal, liberal):
    terminal = bool(goal & RETURNS), bool(goal & ERRORS)

    def step(previous):
        return tuple(all(previous[child] for child in targets) if targets
                     else bool(goal & DEADLOCKS) for targets in graph) + terminal

    return fixed_point(step, (liberal,) * len(INTERNAL) + terminal)


def describe(mask):
    return [name for bit, name in enumerate(ALPHABET) if mask & (1 << bit)]


def control(masks, goal):
    graph = tuple(EDGES[mask] for mask in masks)
    return {
        "successor_masks": masks,
        "outcomes": describe(executions(graph, 0)),
        "postcondition": describe(goal),
        "total": preconditions(graph, goal, False)[0],
        "liberal": preconditions(graph, goal, True)[0],
    }


def compare():
    counts = Counter()
    rows = sha256()
    for masks in product(range(len(EDGES)), repeat=len(INTERNAL)):
        graph = tuple(EDGES[mask] for mask in masks)
        outcomes = tuple(executions(graph, state) for state in INTERNAL)
        if outcomes != meanings(graph):
            raise AssertionError((masks, outcomes))
        counts["graphs"] += 1
        counts["outcome_comparisons"] += len(INTERNAL)
        counts["divergent_starts"] += sum(bool(outcome & DIVERGES) for outcome in outcomes)
        counts["deadlocking_starts"] += sum(bool(outcome & DEADLOCKS) for outcome in outcomes)
        rows.update(bytes((*masks, *outcomes)))

        for goal in range(DIVERGES):
            total = preconditions(graph, goal, False)
            liberal = preconditions(graph, goal, True)
            for state, observed in enumerate(outcomes):
                expect_total = observed & ~goal == 0
                expect_liberal = observed & ~(goal | DIVERGES) == 0
                if (total[state], liberal[state]) != (expect_total, expect_liberal):
                    raise AssertionError((masks, state, goal, observed))
                counts["postconditions_per_mode"] += 1
                counts["total_holds"] += total[state]
                counts["liberal_holds"] += liberal[state]
                counts["liberal_only_accepts_with_divergence"] += liberal[state] and not total[state]
                finite_goal_holds = observed & ~(goal | DEADLOCKS | DIVERGES) == 0
                counts["deadlock_hidden_by_return_error_only"] += finite_goal_holds and not liberal[state]
                rows.update(bytes((total[state], liberal[state])))

    controls = {
        "return_with_optional_self_loop": control((9, 0, 0), RETURNS),
        "return_with_optional_deadlock": control((10, 0, 0), RETURNS),
        "allowed_deadlock": control((10, 0, 0), RETURNS | DEADLOCKS),
        "error_is_not_a_loop": control((16, 0, 0), RETURNS),
    }
    assert [(row["total"], row["liberal"]) for row in controls.values()] == [
        (False, True), (False, False), (True, True), (False, False)
    ]
    return {
        "schema": "llmlang-finite-control-semantic-accounts/1",
        "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Accounts.lean", "axioms.txt")},
        "successor_order": ("state-0", "state-1", "state-2", "return", "error"),
        "observation_order": ALPHABET,
        "counts": counts,
        "controls": controls,
        "ordered_comparisons_sha256": rows.hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
