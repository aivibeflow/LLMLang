"""Canonical structures for the guarded regular type graph fixture."""

from collections import deque
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from hashlib import sha256
import json


@dataclass(frozen=True)
class Node:
    label: tuple[str, ...]
    children: tuple[str | int, ...] = ()


@dataclass(frozen=True)
class CanonicalType:
    data: bytes
    reachable_nodes: int
    quotient_nodes: int
    refinement_rounds: int


def validate(graph, root):
    if root not in graph:
        raise ValueError("Missing root")
    for node in graph.values():
        kind, *fields = node.label
        if any(name not in graph for name in node.children):
            raise ValueError("Dangling type reference")
        if kind == "record" and len(fields) == len(node.children) and len(set(fields)) == len(fields):
            continue
        if kind in ("box", "borrow") and not fields and len(node.children) == 1:
            continue
        if kind in ("int", "bool") and not fields and not node.children:
            continue
        raise ValueError("Malformed type constructor")
    # A box or borrow is the boundary of by-value containment.
    by_value = {name: node.children if node.label[0] == "record" else ()
                for name, node in graph.items()}
    try:
        TopologicalSorter(by_value).prepare()
    except CycleError as error:
        raise ValueError("Unguarded by-value recursion") from error


def reachable_graph(graph, root):
    reached = {}
    queue = deque([root])
    while queue:
        name = queue.popleft()
        if name not in reached:
            reached[name] = graph[name]
            queue.extend(graph[name].children)
    return reached


def partition(keys):
    labels = {}
    colors = {name: labels.setdefault(key, len(labels)) for name, key in keys.items()}
    return colors, len(labels)


def encode(graph, root):
    ordered = reachable_graph(graph, root)
    positions = {name: index for index, name in enumerate(ordered)}
    rows = [{"constructor": node.label, "arguments": [positions[name] for name in node.children]}
            for node in ordered.values()]
    return json.dumps({"profile": "guarded-types-v1", "nodes": rows},
                      ensure_ascii=False, separators=(",", ":")).encode()


def canonicalize(graph, root):
    validate(graph, root)
    graph = reachable_graph(graph, root)
    colors, classes = partition({name: node.label for name, node in graph.items()})
    rounds = 0
    while True:
        keys = {name: (colors[name], tuple(colors[child] for child in node.children))
                for name, node in graph.items()}
        refined, new_classes = partition(keys)
        rounds += 1
        if new_classes == classes:
            colors = refined
            break
        colors, classes = refined, new_classes

    representatives = {}
    for name, node in graph.items():
        color = colors[name]
        representatives[color] = Node(node.label, tuple(colors[target] for target in node.children))
    return CanonicalType(encode(representatives, colors[root]), len(graph), classes, rounds)


def nominal_value(identity, structural):
    if not identity or "/" not in identity:
        raise ValueError("Expected a qualified fixture identity")
    return {"nominal_identity": identity, "structural_sha256": sha256(structural.data).hexdigest()}
