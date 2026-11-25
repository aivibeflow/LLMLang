#!/usr/bin/env python3
"""Compare existing recursive addresses with exact rooted-closure equality."""

from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))
from src.recursive_identity import Call, Definition, publish_definitions
from src.semantic_graph import ContentStore

RECURSIVE_SLOTS = ("a", "b", "c")
EDGES = tuple(product(RECURSIVE_SLOTS, repeat=2))
ROOTS = ("entry", *RECURSIVE_SLOTS, "independent")
POLICIES = ("keyed", "structural", "body-only", "snapshot")
DEPTH = 4


def ordered_graph(mask):
    graph = {"entry": ("a",), "independent": ()}
    for slot in RECURSIVE_SLOTS:
        graph[slot] = tuple(target for bit, (source, target) in enumerate(EDGES)
                            if slot == source and mask & (1 << bit))
    return graph


def reachable(graph, root):
    reached = {root}
    for _ in graph:
        reached = reached | {target for source in reached for target in graph[source]}
    return reached


def partitions(reach):
    return {
        frozenset(other for other in reach[slot] if slot in reach[other])
        for slot in RECURSIVE_SLOTS
    }


def observe(graph, root, fuel):
    if fuel == 0:
        return ()
    return root, tuple(observe(graph, target, fuel - 1) for target in graph[root])


def state(store, mask):
    graph = ordered_graph(mask)
    definitions = {
        slot: Definition(("slot", slot, *map(Call, refs)), slot_key=slot)
        for slot, refs in graph.items()
    }
    reach = {slot: reachable(graph, slot) for slot in graph}
    keys = {mode: publish_definitions(store, definitions, mode) for mode in ("keyed", "structural")}
    keys["body-only"] = {root: (root, graph[root]) for root in ROOTS}
    keys["snapshot"] = dict.fromkeys(ROOTS, mask)
    return {
        "keys": keys, "partition": partitions(reach),
        "closure": {
            root: tuple((slot, graph[slot]) for slot in sorted(reach[root])) for root in ROOTS
        },
        "trace": {root: observe(graph, root, DEPTH) for root in ROOTS},
    }


def transitions(states):
    policy_counts = {policy: {"retained": 0, "invalidations": 0, "stale": 0,
                              "stale_with_different_trace": 0, "unnecessary": 0} for policy in POLICIES}
    topology_counts = {kind: {"edits": 0, "roots_with_changed_closure": 0}
                       for kind in ("merge", "split", "same")}
    example = None
    for mask, before in enumerate(states):
        for bit, edge in enumerate(EDGES):
            new_mask = mask ^ (1 << bit)
            after = states[new_mask]
            delta = len(before["partition"]) - len(after["partition"])
            kind = "merge" if delta > 0 else "split" if delta < 0 else "same"
            topology_counts[kind]["edits"] += 1
            for root in ROOTS:
                changed = before["closure"][root] != after["closure"][root]
                topology_counts[kind]["roots_with_changed_closure"] += changed
                different_trace = before["trace"][root] != after["trace"][root]
                for policy in POLICIES:
                    changed_key = before["keys"][policy][root] != after["keys"][policy][root]
                    if changed:
                        field = "invalidations" if changed_key else "stale"
                    else:
                        field = "unnecessary" if changed_key else "retained"
                    policy_counts[policy][field] += 1
                    if field == "stale" and different_trace:
                        policy_counts[policy]["stale_with_different_trace"] += 1
                if example is None and kind == "merge" and root == "entry" and different_trace:
                    example = {
                        "before_mask": mask, "after_mask": new_mask, "edge": edge, "root": root,
                        "old_closure": before["closure"][root], "new_closure": after["closure"][root],
                        "old_addresses": {mode: before["keys"][mode][root] for mode in POLICIES},
                        "new_addresses": {mode: after["keys"][mode][root] for mode in POLICIES},
                        "old_trace": before["trace"][root], "new_trace": after["trace"][root],
                    }
    return policy_counts, topology_counts, example


def file_digest(path):
    return sha256(path.read_bytes()).hexdigest()


def results():
    store = ContentStore()
    states = [state(store, mask) for mask in range(1 << len(EDGES))]
    counts, topologies, example = transitions(states)
    for policy in ("keyed", "structural"):
        if counts[policy]["stale"] or counts[policy]["unnecessary"]:
            raise AssertionError(f"{policy} disagrees with exact rooted closure")
    if not example or not counts["body-only"]["stale_with_different_trace"] or not counts["snapshot"]["unnecessary"]:
        raise AssertionError("Missing a discriminating control")
    addresses = {address for item in states for policy in ("keyed", "structural")
                 for address in item["keys"][policy].values()}
    if not all(store.get(address).value_hash == address for address in addresses):
        raise AssertionError("A prior exact address did not resolve")
    return {
        "schema": "llmlang-recursive-topology-edits/1", "python": platform.python_version(),
        "source_sha256": {"runner": file_digest(Path(__file__)),
                          **{file: file_digest(PROTOTYPE / "src" / file)
                             for file in ("recursive_identity.py", "semantic_graph.py")}},
        "roots": ROOTS, "ordered_possible_edges": EDGES, "graphs": len(states),
        "directed_transitions": len(states) * len(EDGES), "interpreter_fuel": DEPTH,
        "compared_root_pairs": len(states) * len(EDGES) * len(ROOTS),
        "retrievable_root_addresses": len(addresses), "stored_objects": len(store),
        "topology_counts": topologies, "policies": counts, "merge_witness": example,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
