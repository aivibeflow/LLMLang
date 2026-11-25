#!/usr/bin/env python3
"""Compare mutable reference topology and native observations under graph normalization."""

from collections import Counter, deque
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
POLICIES = ("physical_ids", "root_local", "shared_graph")
A, B, C = ((slot, 0) for slot in range(3))
AN, BN, CN = ((slot, 1) for slot in range(3))
ANN, BNN, CNN = ((slot, 2) for slot in range(3))
RECIPES = (
    (("read", B), ("add", A, 1), ("read", B), ("read", C), ("same", A, B)),
    (("add", AN, 2), ("read", A), ("read", B), ("read", CN), ("same", AN, CN)),
    (("link", B, A), ("add", BN, 3), ("read", A), ("read", C), ("same", BN, CN)),
    (("add", CNN, 4), ("read", C), ("read", AN), ("read", BNN), ("same", CNN, C)),
    (("link", A, C), ("link", C, A), ("add", ANN, 5), ("read", B), ("same", AN, C)),
    (("read", AN), ("read", BN), ("read", CN), ("same", A, CN), ("same", B, ANN)),
)


def dumps(value):
    return json.dumps(value, separators=(",", ":"))


def digest(data):
    return sha256(data).hexdigest()


def key(graph):
    return digest(b"rt05-mutable-reference-topology/1\0" + dumps(graph).encode())


def inventory(graph):
    rows = graph["cells"]
    cells = {node: (value, next_id) for node, value, next_id in rows}
    if len(cells) != len(rows):
        raise ValueError("duplicate")
    if any(node not in cells for node in graph["roots"]):
        raise ValueError("missing-root")
    if any(next_id is not None and next_id not in cells for _, next_id in cells.values()):
        raise ValueError("missing-target")
    return cells


def traversal(cells, roots):
    pending = deque(roots)
    names = {}
    while pending:
        node = pending.popleft()
        if node in names:
            continue
        names[node] = len(names)
        next_id = cells[node][1]
        if next_id is not None:
            pending.append(next_id)
    return names


def project(cells, roots, order, offset=0):
    names = {node: index + offset for node, index in order.items()}
    return [names[node] for node in roots], [
        [names[node], cells[node][0], names.get(cells[node][1])] for node in order
    ]


def normalize(graph, policy):
    cells = inventory(graph)
    roots = graph["roots"]
    admitted = traversal(cells, roots)
    if admitted.keys() != cells.keys():
        raise ValueError("unreachable")
    if policy == "physical_ids":
        return {"roots": roots, "cells": sorted(graph["cells"])}
    if policy == "shared_graph":
        normalized, rows = project(cells, roots, admitted)
        return {"roots": normalized, "cells": rows}
    normalized = []
    rows = []
    for root in roots:
        local_root, local_rows = project(cells, [root], traversal(cells, [root]), offset=len(rows))
        normalized.extend(local_root)
        rows.extend(local_rows)
    return {"roots": normalized, "cells": rows}


def rekey(graph, labels, reverse=False):
    mapping = dict(zip(sorted(row[0] for row in graph["cells"]), labels, strict=True))
    rows = [[mapping[node], value, mapping.get(next_id)] for node, value, next_id in graph["cells"]]
    return {"roots": [mapping[node] for node in graph["roots"]], "cells": sorted(rows, reverse=reverse)}


def exhaustive_key(graph):
    """Use every numeric renaming as an independent finite isomorphism oracle."""
    return min(dumps(rekey(graph, labels)) for labels in permutations(range(len(graph["cells"]))))


def candidates():
    for size in range(1, 4):
        for tail in product(range(size), repeat=2):
            roots = [0, *tail]
            for edges in product([None, *range(size)], repeat=size):
                reached = set(roots)
                for _ in range(size):
                    reached.update(edges[node] for node in tuple(reached) if edges[node] is not None)
                if len(reached) == size:
                    yield {"roots": roots, "cells": [[node, 10, next_id] for node, next_id in enumerate(edges)]}


class Cell:
    def __init__(self, value):
        self.value = value
        self.next = None


def observe_python(graph, recipe):
    cells = {node: Cell(value) for node, value, _ in graph["cells"]}
    for node, _, next_id in graph["cells"]:
        cells[node].next = cells.get(next_id)
    roots = [cells[node] for node in graph["roots"]]

    def resolve(path):
        slot, depth = path
        cell = roots[slot]
        for _ in range(depth):
            if cell is None:
                break
            cell = cell.next
        return cell

    trace = []
    for operation, path, *args in recipe:
        cell = resolve(path)
        if operation == "same":
            trace.append(cell is not None and cell is resolve(args[0]))
        elif cell is None:
            trace.append(None)
        elif operation == "read":
            trace.append(cell.value)
        elif operation == "add":
            cell.value += args[0]
            trace.append(cell.value)
        else:
            assert operation == "link"
            cell.next = resolve(args[0])
            trace.append(cell.next is not None)
    return trace


def observe_node(graphs):
    args = {"graphs": graphs, "recipes": RECIPES}
    result = subprocess.run(["node", str(HERE / "observe.js")], input=dumps(args),
                            text=True, capture_output=True, check=True, timeout=30)
    return json.loads(result.stdout)


def controls():
    invalid = (
        ({"roots": [0, 0, 0], "cells": [[0, 10, None], [0, 10, None]]}, "duplicate"),
        ({"roots": [0, 1, 0], "cells": [[0, 10, None]]}, "missing-root"),
        ({"roots": [0, 0, 0], "cells": [[0, 10, 1]]}, "missing-target"),
        ({"roots": [0, 0, 0], "cells": [[0, 10, None], [1, 10, 1]]}, "unreachable"),
    )
    report = []
    for graph, expected in invalid:
        results = {}
        for policy in POLICIES:
            try:
                normalize(graph, policy)
            except ValueError as error:
                results[policy] = str(error)
            assert results.get(policy) == expected
        report.append({"graph": graph, "results": results})
    return report


def run():
    admitted = list(candidates())
    oracle = {}
    for graph in admitted:
        oracle.setdefault(exhaustive_key(graph), graph)
    graphs = list(oracle.values())
    labels = (17, 31, 43)
    variants = []
    for graph in graphs:
        group = []
        for names in permutations(labels[:len(graph["cells"])]):
            for reverse in (False, True):
                variant = rekey(graph, names, reverse=reverse)
                projections = [normalize(variant, policy) for policy in POLICIES]
                group.append((variant, projections))
        variants.append(group)
    samples = [sample for group in variants for variant, projections in group for sample in (variant, *projections)]
    node = iter(observe_node(samples))
    metrics = {policy: Counter({"trace_drift": 0, "changed_key": 0, "false_identity_pairs": 0,
                                "false_identity_observation_pairs": 0}) for policy in POLICIES}
    rows = []
    for graph, group in zip(graphs, variants, strict=True):
        reference = [observe_python(graph, recipe) for recipe in RECIPES]
        expected_keys = [key(normalize(graph, policy)) for policy in POLICIES]
        observations = []
        for variant, projected_graphs in group:
            assert next(node) == reference == [observe_python(variant, recipe) for recipe in RECIPES]
            projections = {}
            for policy, expected, projected in zip(POLICIES, expected_keys, projected_graphs, strict=True):
                assert normalize(projected, policy) == projected
                observed = next(node)
                assert observed == [observe_python(projected, recipe) for recipe in RECIPES]
                address = key(projected)
                differences = [[index, trace] for index, trace in enumerate(observed) if trace != reference[index]]
                metrics[policy]["trace_drift"] += len(differences)
                metrics[policy]["changed_key"] += address != expected
                projections[policy] = {"key": address, "trace_differences": differences}
            observations.append({"wire": variant, "projections": projections})
        first_keys = {policy: row["key"] for policy, row in observations[0]["projections"].items()}
        rows.append({"graph": graph, "trace": reference, "keys": first_keys, "variants": observations})
    assert next(node, None) is None
    variant_count = sum(map(len, variants))
    for left, right in combinations(rows, 2):
        for policy in POLICIES:
            if left["keys"][policy] == right["keys"][policy]:
                metrics[policy]["false_identity_pairs"] += 1
                metrics[policy]["false_identity_observation_pairs"] += left["trace"] != right["trace"]
    assert not any(metrics["shared_graph"].values())
    assert metrics["root_local"]["trace_drift"] and metrics["root_local"]["false_identity_observation_pairs"]
    assert metrics["physical_ids"]["changed_key"] == variant_count
    native_node = subprocess.check_output(["node", "--version"], text=True).strip()
    native_v8 = subprocess.check_output(["node", "-p", "process.versions.v8"], text=True).strip()
    return {"schema": "llmlang-rt05-mutable-reference-topology/1", "python": platform.python_version(),
            "node": native_node, "v8": native_v8,
            "sources": {name: digest((HERE / name).read_bytes()) for name in ("run.py", "observe.js")},
            "generated_graphs": len(admitted), "isomorphism_classes": len(graphs),
            "relabelings_and_row_orders": variant_count, "recipes": RECIPES,
            "native_recipe_vectors_per_runtime": len(samples) * len(RECIPES), "metrics": metrics,
            "controls": controls(), "observations": rows}


if __name__ == "__main__":
    result = run()
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + dumps(row) for row in observations))
    print("  ]\n}")
