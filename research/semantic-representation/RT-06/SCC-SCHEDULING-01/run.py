#!/usr/bin/env python3
"""Validate exact SCC schedules and mutation-driven recomputation."""

from collections import Counter
from graphlib import TopologicalSorter
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
ARCHIVE = "c3e6060d7397074544020fed78ae5597d697a0bc"
PROTOTYPE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src"
NODES = ("a", "b", "c")
EDGES = tuple(product(NODES, repeat=2))


def build(mask):
    edges = {node: set() for node in NODES}
    for pos, (left, right) in enumerate(EDGES):
        if mask & (1 << pos):
            edges[left].add(right)
    return edges


def reachability(graph):
    reach = {node: set(targets) | {node} for node, targets in graph.items()}
    for middle in NODES:
        for start in NODES:
            if middle in reach[start]:
                reach[start].update(reach[middle])
    return reach


def oracle(reaches, seed):
    return {node: sum(1 << i for i, target in enumerate(NODES)
                      if target in reaches[node] and seed & (1 << i))
            for node in NODES}


def schedule(graph, components):
    groups = sorted(tuple(sorted(members)) for members in components(graph))
    owner = {member: group for group in groups for member in group}
    dependencies = {
        group: sorted({owner[target] for member in group for target in graph[member]
                       if owner[target] != group}) for group in groups
    }
    return tuple(TopologicalSorter(dependencies).static_order())


def scan(edges, order, seed):
    values = {}
    incomplete = False
    own_fact = {node: (1 << i) & seed for i, node in enumerate(NODES)}
    for group in order:
        incomplete |= any(target not in group and target not in values
                          for node in group for target in edges[node])
        local = {node: own_fact[node] for node in group}
        while True:
            updated = {}
            for node in group:
                combined = own_fact[node]
                for target in edges[node]:
                    combined |= local[target] if target in group else values.get(target, 0)
                updated[node] = combined
            if updated == local:
                break
            local = updated
        values.update(local)
    return incomplete, values


def compare(components):
    graphs = [build(mask) for mask in range(1 << len(EDGES))]
    reaches = [reachability(graph) for graph in graphs]
    schedules = [schedule(graph, components) for graph in graphs]
    counts, witnesses = Counter(), {}
    rows = sha256()

    for mask, graph in enumerate(graphs):
        plan = schedules[mask]
        independent = {frozenset(other for other in reaches[mask][node]
                                 if node in reaches[mask][other]) for node in graph}
        if {frozenset(group) for group in plan} != independent:
            raise AssertionError((mask, independent, plan))
        reverse_insertion = dict(reversed(list(graph.items())))
        if schedule(reverse_insertion, components) != plan:
            raise AssertionError("Scheduler depends on declaration insertion order")
        counts["graph_partitions"] += 1
        for seed in range(1 << len(NODES)):
            incomplete, current = scan(graph, plan, seed)
            expected = oracle(reaches[mask], seed)
            if incomplete or current != expected:
                raise AssertionError((mask, seed, plan, expected, current))
            counts["fixed_point_comparisons"] += 1

        for offset, (consumer, _) in enumerate(EDGES):
            updated = mask ^ (1 << offset)
            newer, new_reach, new_plan = graphs[updated], reaches[updated], schedules[updated]
            affected = {node for node, targets in new_reach.items() if consumer in targets}
            counts["directed_graph_edits"] += 1
            counts["changed_partitions"] += set(plan) != set(new_plan)
            for seed in range(1 << len(NODES)):
                original_value = oracle(reaches[mask], seed)
                expected = oracle(new_reach, seed)
                if any(original_value[node] != expected[node] for node in NODES if node not in affected):
                    raise AssertionError(f"Changed analysis outside the reverse cone: {mask}, {offset}")
                incomplete, stale = scan(newer, plan, seed)
                if not incomplete and stale != expected:
                    raise AssertionError("An admitted old plan yielded a stale fixed point")
                counts["edited_fixed_point_comparisons"] += 1
                counts["old_plan_requires_reschedule"] += incomplete
                counts["old_plan_false_results_if_missing_inputs_are_empty"] += stale != expected
                if stale != expected:
                    witnesses.setdefault("stale_schedule_loses_dependency", {
                        "old_mask": mask, "new_mask": updated, "edited_edge": EDGES[offset],
                        "facts_seed": seed, "old_order": plan, "new_order": new_plan,
                        "incorrect": stale, "expected": expected,
                    })
                rows.update(bytes((seed, incomplete, *[expected[node] for node in NODES])))
    assert witnesses
    return counts, witnesses, rows.hexdigest()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        archive = subprocess.check_output(["git", "archive", ARCHIVE, PROTOTYPE])
        with open_tar(fileobj=BytesIO(archive), mode="r:") as source:
            source.extractall(directory, filter="data")
        archived = Path(directory) / PROTOTYPE
        sys.path.insert(0, str(archived.parent))
        from src.recursive_identity import _components
        counts, witnesses, digest = compare(_components)
        checker = sha256((archived / "recursive_identity.py").read_bytes()).hexdigest()
    print(json.dumps({
        "schema": "llmlang-scc-scheduling/1", "python": platform.python_version(),
        "archived_revision": ARCHIVE, "components_source_sha256": checker, "edge_order": EDGES,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Closure.lean", "axioms.txt")},
        "counts": counts, "witnesses": witnesses, "ordered_rows_sha256": digest,
    }, indent=2))
