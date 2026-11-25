#!/usr/bin/env python3
"""Compare immutable projections for execution, verification and navigation."""

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
DEMANDS = ("implementation", "verification", "navigation")
POLICIES = {
    "exact": (1, 3, 5, 7),
    "bounded": (2, 4, 6, 8),
}
INPUTS = tuple(range(4))
PROJECTIONS = ("snapshot", "implementation_for_all", "metadata_without_subject", "typed")


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class Node:
    payload: object
    identity_edges: tuple = ()
    lookup_edges: tuple = ()


def graph_identity(graph, name, *, all_edges=False, active=()):
    if name in active:
        raise ValueError("cyclic identity dependency: " + " -> ".join((*active, name)))
    node = graph[name]
    edges = node.identity_edges + node.lookup_edges if all_edges else node.identity_edges
    references = [
        (role, graph_identity(graph, target, all_edges=all_edges, active=(*active, name)))
        for role, target in sorted(edges)
    ]
    return digest((name, node.payload, references))


def source_record(delta, indented):
    prefix = "# λ scope\n  " if indented else ""
    source = f"{prefix}return helper(x) + {delta}\n".encode("utf-8")
    start = source.index(b"helper")
    return source, (start, start + len(b"helper"))


def generate_case(delta, factor, stated_policy, indented, display, verifier):
    source, span = source_record(delta, indented)
    graph = {
        "implementation": Node({"delta": delta}, (("callee", "helper"),),
                               (("documentation", "description"), ("verification_lookup", "verification"),
                                ("source_lookup", "navigation"))),
        "helper": Node({"factor": factor}),
        "verification": Node(
            {"verifier": verifier, "input_domain": INPUTS},
            (("obligation", "policy"), ("subject", "implementation")),
        ),
        "navigation": Node({"span": span}, (("source", "source"), ("subject", "implementation"))),
        "policy": Node({"bounds": POLICIES[stated_policy]}),
        "source": Node({"utf8_sha256": sha256(source).hexdigest()}),
        "description": Node({"display": display}),
    }
    identities = {name: graph_identity(graph, name) for name in DEMANDS}
    snapshot = digest({
        name: (node.payload, node.identity_edges, node.lookup_edges) for name, node in graph.items()
    })
    without_subject = {
        name: digest((name, graph[name].payload,
                      [(role, graph_identity(graph, target)) for role, target in graph[name].identity_edges
                       if role != "subject"]))
        for name in ("verification", "navigation")
    }
    executed = bytes(factor * x + delta for x in INPUTS)
    limit = POLICIES[stated_policy]
    checked = (tuple(x <= bound for x, bound in zip(executed, limit, strict=True))
               if verifier == "v1-inclusive" else
               tuple(x < bound for x, bound in zip(executed, limit, strict=True)))
    # Independent reuse obligations, given by exact interpreter inputs and observable records.
    expected = {
        "implementation": tuple(executed),
        "verification": (tuple(executed), limit, verifier, checked),
        "navigation": (source.hex(), span, ("helper", factor), tuple(executed)),
    }
    keys = {
        "snapshot": dict.fromkeys(DEMANDS, snapshot),
        "implementation_for_all": dict.fromkeys(DEMANDS, identities["implementation"]),
        "metadata_without_subject": {"implementation": identities["implementation"], **without_subject},
        "typed": identities,
    }
    return {"coordinates": [delta, factor, stated_policy, indented, display, verifier],
            "expected": expected, "keys": keys}, graph


def comparisons(cases):
    result = {projection: {
        demand: {"valid_reuse": 0, "invalid_reuse": 0, "missed_reuse": 0}
        for demand in DEMANDS
    } for projection in PROJECTIONS}
    for left, right in combinations(cases, 2):
        for projection in PROJECTIONS:
            for demand in DEMANDS:
                eligible = left["expected"][demand] == right["expected"][demand]
                reused = left["keys"][projection][demand] == right["keys"][projection][demand]
                disposition = {
                    (True, True): "valid_reuse",
                    (False, True): "invalid_reuse",
                    (True, False): "missed_reuse",
                }.get((eligible, reused))
                if disposition:
                    result[projection][demand][disposition] += 1
    return result


def results():
    coordinates = list(product((1, 2), (2, 3), POLICIES, (False, True),
                               ("original", "renamed"), ("v1-inclusive", "v2-strict")))
    cases, graphs = zip(*(generate_case(*case) for case in coordinates), strict=True)
    result = comparisons(cases)
    if any(counts["invalid_reuse"] or counts["missed_reuse"] for counts in result["typed"].values()):
        raise AssertionError("Typed projections disagree with the independent reuse obligations")
    try:
        graph_identity(graphs[0], "implementation", all_edges=True)
    except ValueError as error:
        cycle = str(error)
    else:
        raise AssertionError("The unrestricted identity walk should encounter a cycle")
    return {
        "schema": "llmlang-typed-edge-projections/1", "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "inputs": INPUTS, "coordinates": ["delta", "helper_factor", "obligation", "format", "display", "verifier"],
        "case_count": len(cases), "pair_count": len(cases) * (len(cases) - 1) // 2,
        "unrestricted_cycle": cycle, "comparisons": result, "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
