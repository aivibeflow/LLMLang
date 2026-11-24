"""Independently distinguish structural recursion from declaration identity."""

from hashlib import sha256
from itertools import combinations_with_replacement, product
import json

from types_graph import Node, canonicalize, encode, nominal_value, validate


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def equivalent(left, left_root, right, right_root):
    """Direct product traversal of root paths, without quotienting either graph."""
    todo = [(left_root, right_root)]
    seen = set()
    while todo:
        pair = todo.pop()
        if pair in seen:
            continue
        seen.add(pair)
        a, b = left[pair[0]], right[pair[1]]
        if a.label != b.label or len(a.children) != len(b.children):
            return False
        todo.extend(zip(a.children, b.children))
    return True


def finite_corpus():
    graphs = []
    for labels in product((("record", "left", "right"), ("record", "in", "out")), repeat=2):
        for targets in product(("x", "y"), repeat=4):
            graph = {"x": Node(labels[0], ("box0", "box1")),
                     "y": Node(labels[1], ("box2", "box3"))}
            graph.update({f"box{i}": Node(("box",), (target,)) for i, target in enumerate(targets)})
            graphs.extend((graph, root, canonicalize(graph, root).data) for root in ("x", "y"))
    checks = equal = 0
    for (left, a, x), (right, b, y) in combinations_with_replacement(graphs, 2):
        expected = equivalent(left, a, right, b)
        require((x == y) == expected, "Quotient encoding disagrees with product oracle")
        checks += 1
        equal += expected
    return {"rooted_types": len(graphs), "pair_checks": checks, "equal_pairs": equal,
            "distinct_structural_values": len({entry[2] for entry in graphs})}


def guard_and_identity_controls():
    standard = {"list": Node(("record", "head", "tail"), ("value", "pointer")),
                "value": Node(("int",)),
                "pointer": Node(("box",), ("list",))}
    unfolded = {**standard,
                "pointer": Node(("box",), ("copy",)),
                "copy": Node(("record", "head", "tail"), ("value", "pointer"))}
    a, b = canonicalize(standard, "list"), canonicalize(unfolded, "list")
    require(a.data == b.data, "Unfolded graph has a different structural type")
    require(encode(standard, "list") != encode(unfolded, "list"), "Unfolding should change the raw graph")
    require(nominal_value("a/List", a) == nominal_value("a/List", b),
            "Same nominal identity and shape should survive unfolding")
    require(nominal_value("a/List", a) != nominal_value("b/List", a),
            "Independent nominal declarations should remain distinct")

    ordered = {**standard, "list": Node(("record", "tail", "head"), ("pointer", "value"))}
    borrowed = {**standard, "pointer": Node(("borrow",), ("list",))}
    other_value = {**standard, "value": Node(("bool",))}
    other_version = nominal_value("a/List", canonicalize(other_value, "list"))
    original_version = nominal_value("a/List", a)
    require(other_version["nominal_identity"] == original_version["nominal_identity"]
            and other_version["structural_sha256"] != original_version["structural_sha256"],
            "Nominal family should not erase a structural revision")
    for graph in (ordered, borrowed, other_value):
        candidate = canonicalize(graph, "list")
        require(candidate.data != a.data and not equivalent(standard, "list", graph, "list"),
                "Erased constructor or field distinction")

    invalid = {
        "unguarded": {"root": Node(("record", "self"), ("root",))},
        "mixed_guard": {"root": Node(("record", "self", "guarded"), ("root", "box")),
                        "box": Node(("box",), ("root",))},
        "dangling": {"root": Node(("box",), ("absent",))},
        "arity": {"root": Node(("record", "x"), ())},
        "duplicate_field": {"root": Node(("record", "x", "x"), ("leaf", "leaf")),
                            "leaf": Node(("int",))},
    }
    rejected = {}
    for name, graph in invalid.items():
        try:
            validate(graph, "root")
        except ValueError as error:
            rejected[name] = str(error)
            continue
        raise AssertionError(f"Accepted malformed type: {name}")
    return {"equirecursive_payload_sha256": sha256(a.data).hexdigest(),
            "unfolded_before_quotient": b.reachable_nodes, "unfolded_after_quotient": b.quotient_nodes,
            "graph_only_isomorphism_distinguishes_unfolding": True,
            "nominal_wrappers_distinct": True, "nominal_value_revision_distinct": True,
            "preserved_field_constructor_and_scalar_distinctions": 3,
            "rejections": rejected}


def scale():
    records = []
    for size, marked in product((6, 16, 32, 64, 128), (False, True)):
        graph = {
            f"r{i}": Node(("record", "marked" if i == 0 and marked else "next"), (f"b{i}",))
            for i in range(size)
        }
        graph.update({f"b{i}": Node(("box",), (f"r{(i + 1) % size}",)) for i in range(size)})
        result = canonicalize(graph, "r0")
        rename = {name: f"renamed/{i}" for i, name in enumerate(reversed(graph))}
        renamed = {rename[name]: Node(node.label, tuple(rename[child] for child in node.children))
                   for name, node in reversed(graph.items())}
        require(canonicalize(renamed, rename["r0"]) == result, "Canonical result changed after relabeling")
        require(result.quotient_nodes == (2 * size if marked else 2), "Unexpected quotient size")
        records.append({"marked": marked, "reachable_nodes": result.reachable_nodes,
                        "quotient_nodes": result.quotient_nodes, "refinement_rounds": result.refinement_rounds,
                        "payload_sha256": sha256(result.data).hexdigest()})
    return records


if __name__ == "__main__":
    print(json.dumps({"exhaustive": finite_corpus(), "controls": guard_and_identity_controls(),
                      "scale": scale()}, sort_keys=True, indent=2))
