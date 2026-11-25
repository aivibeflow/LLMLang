"""Check which role-labeled cycles belong to the semantic hash projection."""

from collections import Counter
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from pathlib import Path
import subprocess


BASE = "9e8644f39c6b3ba650bcf2e48e81363dd3d701bb"
RT05 = "research/semantic-representation/RT-05"
NODES = (0, 1, 2)
DIRECTED = tuple(permutations(NODES, 2))
ROLES = ("absent", "semantic", "build", "proof", "source", "description")
VIEWS = {
    "semantic": {"semantic"},
    "build": {"semantic", "build"},
    "proof": {"semantic", "proof"},
    "source": {"semantic", "source"},
    "description": {"description"},
}


def projection(graph, view):
    return {edge: role for edge, role in graph.items() if role in VIEWS[view]}


def component_pairs(edges):
    reach = set(edges) | {(node, node) for node in NODES}
    for middle in NODES:
        extra = {(source, dest) for source, dest in product(NODES, repeat=2)
                 if (source, middle) in reach and (middle, dest) in reach}
        reach |= extra
    return {(a, b) for a, b in combinations(NODES, 2) if (a, b) in reach and (b, a) in reach}


def semantic_oracle(values):
    accepted = set()
    for first, second in combinations(NODES, 2):
        other, = set(NODES) - {first, second}

        def reaches(source, target):
            return (values[source, target] == "semantic"
                    or values[source, other] == values[other, target] == "semantic")

        if reaches(first, second) and reaches(second, first):
            accepted.add((first, second))
    return accepted


def run_cases():
    totals = Counter()
    for roles in product(ROLES, repeat=len(DIRECTED)):
        entries = dict(zip(DIRECTED, roles, strict=True))
        graph = {edge: role for edge, role in entries.items() if role != "absent"}
        expected = semantic_oracle(entries)
        semantic = component_pairs(projection(graph, "semantic"))
        assert semantic == expected
        all_edges = component_pairs(graph)
        assert semantic <= all_edges
        totals["graphs"] += 1
        totals["with_semantic_cycle"] += bool(semantic)
        totals["with_any_cycle"] += bool(all_edges)
        totals["universal_projection_overgroups"] += semantic != all_edges
        for name in ("build", "proof", "source"):
            assert projection(graph, name).keys() >= projection(graph, "semantic").keys()
    semantic_forward = {(0, 1): "semantic"}
    effects = {}
    for role in ROLES[1:]:
        graph = {**semantic_forward, (1, 0): role}
        changed_views = [view for view in VIEWS if projection(graph, view) != projection(semantic_forward, view)]
        assert changed_views == (["semantic", "build", "proof", "source"] if role == "semantic" else [role])
        assert bool(component_pairs(projection(graph, "semantic"))) == (role == "semantic")
        effects[role] = changed_views
    return {"counts": dict(totals), "reverse_edge_changed_views": effects}


def pinned_input_ledgers():
    result = {}
    for fixture in ("TYPED-EDGE-PROJECTIONS-01", "RECURSIVE-TOPOLOGY-EDITS-01", "RECURSIVE-BOUNDARY-01"):
        path = f"{RT05}/{fixture}/evidence.json"
        raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
        assert isinstance(json.loads(raw), dict)
        result[fixture] = sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_ledger_sha256": pinned_input_ledgers(), **run_cases(),
    }, sort_keys=True, indent=2))
