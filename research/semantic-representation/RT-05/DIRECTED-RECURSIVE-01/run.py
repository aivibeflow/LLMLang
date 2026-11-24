"""Compare exact identity for directed, role-labeled recursive multigraphs."""
import argparse
from collections import Counter
from dataclasses import dataclass
from itertools import permutations, product
import json
from pathlib import Path
from random import Random
import sys

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import digest


@dataclass(frozen=True)
class Graph:
    colors: tuple[str, ...]
    labels: tuple[tuple[tuple[str, ...], ...], ...]

    @property
    def vertices(self):
        return range(len(self.colors))


def build(colors, edges):
    size = len(colors)
    matrix = [[[] for _ in colors] for _ in colors]
    for start, end, role in edges:
        assert 0 <= start < size and 0 <= end < size and role
        matrix[start][end].append(role)
    graph = Graph(tuple(colors), tuple(tuple(tuple(sorted(roles)) for roles in row) for row in matrix))
    for reversed_edges in (False, True):
        visited = {0}
        pending = [0]
        while pending:
            node = pending.pop()
            for target in graph.vertices:
                roles = graph.labels[target][node] if reversed_edges else graph.labels[node][target]
                if roles and target not in visited:
                    visited.add(target)
                    pending.append(target)
        if len(visited) != size:
            raise ValueError("input is not one strongly connected component")
    return graph


def encode(graph, order):
    return tuple(graph.colors[node] for node in order), tuple(graph.labels[i][j] for i in order for j in order)


def exhaustive(graph):
    return min(encode(graph, layout) for layout in permutations(graph.vertices))


def signature(graph, node, partition):
    view = []
    for cell in partition:
        outgoing = Counter(role for neighbor in cell for role in graph.labels[node][neighbor])
        incoming = Counter(role for neighbor in cell for role in graph.labels[neighbor][node])
        view.append((tuple(sorted(outgoing.items())), tuple(sorted(incoming.items()))))
    return graph.labels[node][node], tuple(view)


def partition(graph):
    return tuple(tuple(node for node in graph.vertices if graph.colors[node] == color)
                 for color in sorted(set(graph.colors)))


def refine(graph, cells):
    while True:
        result = []
        for cell in cells:
            bins = {}
            for node in cell:
                bins.setdefault(signature(graph, node, cells), []).append(node)
            result.extend(tuple(bins[key]) for key in sorted(bins))
        current = tuple(result)
        if len(current) == len(cells):
            return current
        cells = current


def weak(graph):
    cells = refine(graph, partition(graph))
    return tuple((graph.colors[cell[0]], len(cell), signature(graph, cell[0], cells)) for cell in cells)


def transposition_is_automorphism(graph, a, b):
    positions = list(graph.vertices)
    positions[a], positions[b] = b, a
    return all(graph.colors[i] == graph.colors[positions[i]] for i in graph.vertices) and all(
        graph.labels[i][j] == graph.labels[positions[i]][positions[j]]
        for i in graph.vertices for j in graph.vertices
    )


def canonical(graph, budget=20000):
    visited = 0
    pruned = 0

    def search(cells):
        nonlocal visited, pruned
        visited += 1
        if visited > budget:
            raise ValueError("exact identity budget exhausted")
        cells = refine(graph, cells)
        split = next((i for i, cell in enumerate(cells) if len(cell) > 1), None)
        if split is None:
            return encode(graph, tuple(cell[0] for cell in cells))
        candidates = []
        outputs = []
        for node in cells[split]:
            if any(transposition_is_automorphism(graph, node, other) for other in candidates):
                pruned += 1
                continue
            candidates.append(node)
            remaining = tuple(other for other in cells[split] if other != node)
            outputs.append(search(cells[:split] + ((node,), remaining) + cells[split+1:]))
        return min(outputs)

    return search(partition(graph)), visited, pruned


def edges(graph):
    return [(i, j, role) for i in graph.vertices for j in graph.vertices for role in graph.labels[i][j]]


def relabel(graph, mapping):
    colors = [""] * len(graph.colors)
    for old, new in enumerate(mapping):
        colors[new] = graph.colors[old]
    return build(colors, ((mapping[i], mapping[j], role) for i, j, role in edges(graph)))


def project(graph, mode):
    values = edges(graph)
    if mode == "direction":
        values.extend((j, i, label) for i, j, label in values[:] if i != j)
    elif mode == "roles":
        values = [(i, j, "edge") for i, j, _ in values]
    elif mode == "multiplicity":
        values = sorted(set(values))
    return build(graph.colors, values)


def census():
    counts = Counter()
    reference_to_candidate = {}
    candidate_to_reference = {}
    projections = {mode: {} for mode in ("direction", "roles", "multiplicity")}
    ordered_pairs = tuple((a, b) for a in range(3) for b in range(3) if a != b)
    additions = (
        (),
        ((0, 0, "call"), (0, 0, "call"), (1, 1, "read")),
        ((0, 0, "call"), (1, 1, "read")),
    )
    for colors, extra, labels in product(
        (("routine",) * 3, ("routine", "routine", "port")),
        additions, tuple(product(("", "call", "read"), repeat=len(ordered_pairs))),
    ):
        counts["candidate_inputs"] += 1
        supplied = [(i, j, tag) for (i, j), tag in zip(ordered_pairs, labels, strict=True) if tag]
        try:
            graph = build(colors, supplied + list(extra))
        except ValueError:
            continue
        counts["admitted_components"] += 1
        actual, visited, pruned = canonical(graph)
        expected = exhaustive(graph)
        assert reference_to_candidate.setdefault(expected, actual) == actual
        assert candidate_to_reference.setdefault(actual, expected) == expected
        for relabeling in permutations(graph.vertices):
            assert canonical(relabel(graph, relabeling))[0] == actual
            counts["relabeled_checks"] += 1
        counts["different_canonical_bytes"] += actual != expected
        counts["max_search_partitions"] = max(counts["max_search_partitions"], visited)
        counts["pruned_transpositions"] += pruned
        for mode, mapping in projections.items():
            mapping.setdefault(exhaustive(project(graph, mode)), set()).add(expected)
    counts["exact_classes"] = len(reference_to_candidate)
    collisions = {mode: {"collision_classes": sum(len(original) > 1 for original in mapped.values()),
                         "largest_collapsed_family": max(map(len, mapped.values()))}
                  for mode, mapped in projections.items()}
    assert all(stat["collision_classes"] > 0 for stat in collisions.values())
    return dict(counts), collisions


def witnesses():
    graph = build(("input", "output", "loop"), ((0, 1, "call"), (1, 2, "read"), (2, 0, "call")))
    reversed_graph = build(graph.colors, ((j, i, label) for i, j, label in edges(graph)))
    changed_role = build(graph.colors, ((i, j, "entry" if (i, j) == (0, 1) else label)
                                      for i, j, label in edges(graph)))
    duplicate = build(graph.colors, edges(graph) + [(0, 1, "call")])
    pairs = {"direction": (graph, reversed_graph), "roles": (graph, changed_role),
             "multiplicity": (graph, duplicate)}
    result = {}
    for mode, (a, b) in pairs.items():
        a_key, *_ = canonical(a)
        b_key, *_ = canonical(b)
        assert a_key != b_key
        assert exhaustive(project(a, mode)) == exhaustive(project(b, mode))
        result[mode] = {"exact_keys": list(map(digest, (a_key, b_key))),
                        "projected_key": digest(exhaustive(project(a, mode)))}

    # Both directed graphs have uniform in/out role counts. Their transitive triangles differ.
    side = ((0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3))
    prism = (*side, (0, 3), (1, 4), (2, 5))
    bipartite = tuple(product(range(3), range(3, 6)))
    def bidirectional(pairs):
        return build(("routine",) * 6, ((a, b, "call") for i, j in pairs for a, b in ((i, j), (j, i))))
    a, b = map(bidirectional, (prism, bipartite))
    assert weak(a) == weak(b)
    assert exhaustive(a) != exhaustive(b)
    random = Random(20261124)
    details = []
    for item in (a, b):
        key, visits, pruned = canonical(item)
        for _ in range(12):
            mapping = list(item.vertices)
            random.shuffle(mapping)
            assert canonical(relabel(item, mapping))[0] == key
        details.append({"key": digest(key), "visited": visits, "pruned": pruned, "relabeled": 12})
    assert details[0]["key"] != details[1]["key"]
    rejected = False
    try:
        canonical(a, budget=1)
    except ValueError as exc:
        assert str(exc) == "exact identity budget exhausted"
        rejected = True
    assert rejected
    result["typed_refinement"] = {"weak_key": digest(weak(a)), "exact": details, "budget_unknown": rejected}
    return result


def run():
    counts, projections = census()
    return {"format": "rt05-directed-recursive/1", "python": sys.version.split()[0],
            "census": counts, "projections": projections, "witnesses": witnesses()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
