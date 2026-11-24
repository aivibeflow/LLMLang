"""Compare stable refinement, exhaustive relabeling and exact search for unordered SCCs."""

import argparse
from collections import Counter
from dataclasses import dataclass
from itertools import combinations, permutations
import json
from pathlib import Path
from random import Random
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import digest


@dataclass(frozen=True)
class Graph:
    colors: tuple[str, ...]
    neighbors: tuple[frozenset[int], ...]

    @property
    def order(self):
        return len(self.colors)


def build(order, edges, colors=None):
    if order < 1:
        raise ValueError("empty component")
    neighbors = [set() for _ in range(order)]
    for a, b in edges:
        if not 0 <= a < order or not 0 <= b < order or a == b:
            raise ValueError("edge outside the simple symmetric profile")
        neighbors[a].add(b)
        neighbors[b].add(a)
    reached = {0}
    pending = [0]
    while pending:
        for neighbor in neighbors[pending.pop()] - reached:
            reached.add(neighbor)
            pending.append(neighbor)
    if len(reached) != order:
        raise ValueError("graph must be one connected symmetric component")
    tags = ("node",) * order if colors is None else tuple(colors)
    if len(tags) != order:
        raise ValueError("expected one color per node")
    return Graph(tags, tuple(frozenset(group) for group in neighbors))


def initial_partition(graph):
    return tuple(tuple(i for i, color in enumerate(graph.colors) if color == tag)
                 for tag in sorted(set(graph.colors)))


def signature(graph, node, partition):
    adjacent = graph.neighbors[node]
    return tuple(sum(other in adjacent for other in cell) for cell in partition)


def refine(graph, partition):
    """Split each cell by its vector of exact neighbor counts into ordered cells."""
    while True:
        groups = []
        cells_of = {node: index for index, cell in enumerate(partition) for node in cell}
        for cell in partition:
            bins = {}
            for node in cell:
                counts = [0] * len(partition)
                for neighbor in graph.neighbors[node]:
                    counts[cells_of[neighbor]] += 1
                bins.setdefault(tuple(counts), []).append(node)
            groups.extend(tuple(bins[key]) for key in sorted(bins))
        result = tuple(groups)
        if len(result) == len(partition):
            return result
        partition = result


def weak_key(graph):
    cells = refine(graph, initial_partition(graph))
    return tuple((graph.colors[cell[0]], len(cell), signature(graph, cell[0], cells)) for cell in cells)


def encode(graph, order):
    return (tuple(graph.colors[node] for node in order),
            tuple(b in graph.neighbors[a] for a, b in combinations(order, 2)))


def exhaustive(graph):
    """Independent reference that enumerates all bijections, then retains the least bytes."""
    return min(encode(graph, order) for order in permutations(range(graph.order)))


def canonical(graph, *, budget=250_000):
    visits = 0
    twin_pruned = 0

    def search(partition):
        nonlocal visits, twin_pruned
        visits += 1
        if visits > budget:
            raise ValueError("exact canonicalization budget exhausted")
        cells = refine(graph, partition)
        split = next((index for index, cell in enumerate(cells) if len(cell) > 1), None)
        if split is None:
            return encode(graph, tuple(cell[0] for cell in cells))
        cell = cells[split]
        representatives = []
        best = None
        for node in cell:
            # Same color and identical external neighborhoods imply a transposition automorphism.
            if any(graph.neighbors[node] - {other} == graph.neighbors[other] - {node}
                   for other in representatives):
                twin_pruned += 1
                continue
            representatives.append(node)
            rest = tuple(other for other in cell if other != node)
            answer = search(cells[:split] + ((node,), rest) + cells[split + 1:])
            best = answer if best is None else min(best, answer)
        return best

    result = search(initial_partition(graph))
    return result, {"visited_partitions": visits, "transpositions_pruned": twin_pruned}


def edges(graph):
    return ((a, b) for a, group in enumerate(graph.neighbors) for b in sorted(group) if a < b)


def relabel(graph, old_to_new):
    tags = [""] * graph.order
    for old, new in enumerate(old_to_new):
        tags[new] = graph.colors[old]
    return build(graph.order, ((old_to_new[a], old_to_new[b]) for a, b in edges(graph)), tags)


def census():
    by_order = {}
    reference_to_new = {}
    new_to_reference = {}
    byte_differences = 0
    for size in range(1, 6):
        admitted = 0
        pairs = tuple(combinations(range(size), 2))
        for mask in range(1 << len(pairs)):
            selected = [edge for position, edge in enumerate(pairs) if mask & (1 << position)]
            try:
                graph = build(size, selected)
            except ValueError:
                continue
            reference = exhaustive(graph)
            result, _ = canonical(graph)
            if reference_to_new.setdefault(reference, result) != result:
                raise AssertionError("Equivalent graphs received distinct exact keys")
            if new_to_reference.setdefault(result, reference) != reference:
                raise AssertionError("Different exact classes share a key")
            byte_differences += reference != result
            admitted += 1
        by_order[size] = admitted
    return {"labeled_connected_graphs": sum(by_order.values()), "admitted_by_order": by_order,
            "isomorphism_classes": len(reference_to_new), "different_reference_encodings": byte_differences}


def circulant(size, differences):
    return build(size, ((i, (i + d) % size) for i in range(size) for d in differences))


def lattice(neighborhood):
    modular = {(x, y) for x in range(4) for y in range(4)}

    def index(x, y):
        return x * 4 + y

    return build(16, ((index(x, y), index((x + dx) % 4, (y + dy) % 4))
                      for x, y in sorted(modular) for dx, dy in neighborhood))


def variants():
    prism = build(6, ((0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3),
                      (0, 3), (1, 4), (2, 5)))
    bipartite = build(6, ((a, b) for a in range(3) for b in range(3, 6)))
    shrikhande = lattice(((1, 0), (0, 1), (1, 1)))
    rook = lattice(((1, 0), (2, 0), (0, 1), (0, 2)))
    cycle = circulant(64, (1,))
    complete = build(24, combinations(range(24), 2))
    with_color = build(6, edges(prism), ("entry", "node", "node", "node", "node", "node"))
    return {"triangular_prism": prism, "complete_bipartite_3_3": bipartite,
            "rook": rook, "shrikhande": shrikhande, "cycle_64": cycle, "complete_24": complete,
            "colored_prism": with_color}


def verify():
    rng = Random(310341)
    records = {}
    graphs = variants()
    for label, graph in graphs.items():
        exact, search = canonical(graph)
        weak = weak_key(graph)
        permutation = list(range(graph.order))
        for _ in range(7):
            rng.shuffle(permutation)
            transformed = relabel(graph, permutation)
            if canonical(transformed)[0] != exact or weak_key(transformed) != weak:
                raise AssertionError(("relabeling", label, permutation))
        cliques = {size: sum(all(b in graph.neighbors[a] for a, b in combinations(group, 2))
                             for group in combinations(range(graph.order), size)) for size in (3, 4)}
        common_counts = Counter(
            (b in graph.neighbors[a], len(graph.neighbors[a] & graph.neighbors[b]))
            for a, b in combinations(range(graph.order), 2)
        )
        records[label] = {"nodes": graph.order, "weak": digest(weak), "exact": digest(exact),
                          "cliques": cliques, "common_neighbor_pairs": sorted(common_counts.items()),
                          "degree_multiset": sorted(Counter(map(len, graph.neighbors)).items()),
                          "relabelings": 7, **search}
    for a, b in (("triangular_prism", "complete_bipartite_3_3"), ("rook", "shrikhande")):
        if records[a]["weak"] != records[b]["weak"] or records[a]["exact"] == records[b]["exact"]:
            raise AssertionError(("refinement collision", a, b))
    if records["triangular_prism"]["cliques"][3] != 2 or records["complete_bipartite_3_3"]["cliques"][3]:
        raise AssertionError("Expected independent triangle distinction")
    if records["rook"]["common_neighbor_pairs"] != records["shrikhande"]["common_neighbor_pairs"]:
        raise AssertionError("Expected identical common-neighbor distributions")
    if records["rook"]["cliques"][4] != 8 or records["shrikhande"]["cliques"][4]:
        raise AssertionError("Expected independent 4-clique distinction")
    if records["colored_prism"]["exact"] == records["triangular_prism"]["exact"]:
        raise AssertionError("A semantic node color must change its exact key")
    for name, action in (
        ("disconnected", lambda: build(4, ((0, 1), (2, 3)))),
        ("self_loop", lambda: build(1, ((0, 0),))),
        ("budget_exhausted", lambda: canonical(graphs["cycle_64"], budget=1)),
    ):
        try:
            action()
        except ValueError:
            continue
        raise AssertionError(f"Outside-profile case accepted: {name}")
    return {"format": "rt05-unordered-recursive/1", "python": sys.version.split()[0],
            "census": census(), "comparison": records,
            "rejected": ["disconnected", "self_loop", "budget_exhausted"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
