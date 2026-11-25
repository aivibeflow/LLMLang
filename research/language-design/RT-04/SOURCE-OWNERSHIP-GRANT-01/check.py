"""Bind restricted-source ownership observations to a current authority chain."""

import ast
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
CFG = HERE.parents[1] / "RT-03" / "SOURCE-CLEANUP-CFG-01"
sys.path.insert(0, str(CFG))
import flow
import reference
from run import CONDITIONS, make_source


BASE = "71dfa62a963c771cfed808e542f08716c28a7413"
GRANTS = (("issuer", 7, True), ("root", 5, True), ("leaf", 12, True))
CALL_KINDS = {"probe": "probe", "open_slot": "open_slot", "emit": "emit",
              "stage": "stage", "close_slot": "close", "fail": "fail"}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ast_inventory(source):
    calls = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            span = node.lineno, node.end_lineno, node.col_offset, node.end_col_offset
            calls.append((span, CALL_KINDS[node.func.id]))
    return set(calls)


def graph_inventory(graph):
    return {(node.span, node.kind) for node in graph[1]
            if node.span is not None and node.kind in CALL_KINDS.values()}


def receipt(source, graph, snapshot):
    return digest([sha256(source.encode()).hexdigest(), snapshot,
                   graph[0], [asdict(node) for node in graph[1]], sorted(graph_inventory(graph))])


def admit(source, graph, snapshot, submitted, granted, current):
    try:
        expected_graph = flow.lower(source)
    except (flow.UnsupportedSource, SyntaxError):
        return "unknown-coverage"
    if (ast_inventory(source) != graph_inventory(graph) or graph != expected_graph
            or submitted != receipt(source, graph, snapshot)):
        return "unknown-coverage"
    if current != granted or not all(live for _, _, live in current):
        return "authority-unavailable"
    return "admit"


def check():
    outcomes = Counter()
    disposition = Counter()
    inputs = 0
    cubes = {}
    for guard_name, condition in CONDITIONS.items():
        source = make_source(condition, 'return stage("handle")', 'fail("primary")')
        graph = flow.lower(source)
        assert graph_inventory(graph) == ast_inventory(source)
        proved = receipt(source, graph, "snapshot-1")
        projected = defaultdict(list)
        for x, y, err_inner, err_outer in product((False, True), repeat=4):
            flags = {"x": x, "y": y}
            errors = {"inner": err_inner, "outer": err_outer}
            observation = flow.execute(graph, flags, errors)
            assert observation == reference.execute(source, flags, errors)
            trace = tuple((event[1], event[2]) for event in observation["trace"])
            signature = trace, observation["handle"], tuple(observation["errors"])
            projected[signature].append([x, y, err_inner, err_outer])
            disposition[observation["handle"]] += 1
            inputs += 1
        assert len(projected) > 1 and sum(map(len, projected.values())) == 16
        cubes[guard_name] = [{"trace": trace, "handle": handle, "errors": errors, "cubes": values}
                             for (trace, handle, errors), values in projected.items()]

        lost = next(i for i, node in enumerate(graph[1]) if node.kind == "probe")
        damaged = (graph[0], [replace(node, span=None) if i == lost else node for i, node in enumerate(graph[1])])
        eager = flow.lower(source, eager=True)
        assert graph_inventory(eager) == graph_inventory(graph)
        options = {
            "exact": (source, graph, "snapshot-1", proved, GRANTS, "admit"),
            "wrong-snapshot": (source, graph, "snapshot-2", proved, GRANTS, "unknown-coverage"),
            "source-edited": ("# same behavior\n" + source, graph, "snapshot-1", proved, GRANTS, "unknown-coverage"),
            "omitted-use": (source, damaged, "snapshot-1", receipt(source, damaged, "snapshot-1"),
                            GRANTS, "unknown-coverage"),
            "wrong-continuation": (source, eager, "snapshot-1", receipt(source, eager, "snapshot-1"),
                                   GRANTS, "unknown-coverage"),
            "unknown-source": (source.replace('emit("selected")', 'outside("selected")'),
                               graph, "snapshot-1", proved, GRANTS, "unknown-coverage"),
            "parent-revoked": (source, graph, "snapshot-1", proved,
                               (GRANTS[0], ("root", 6, False), GRANTS[2]), "authority-unavailable"),
            "issuer-replaced": (source, graph, "snapshot-1", proved,
                                (("issuer", 8, True), *GRANTS[1:]), "authority-unavailable"),
        }
        for label, (src, candidate, snapshot, coverage, current, expected) in options.items():
            actual = admit(src, candidate, snapshot, coverage, GRANTS, current)
            assert actual == expected, label
            outcomes[actual] += 1
    return {"source_inputs": inputs, "handle_disposition": dict(disposition),
            "admission_cases": dict(outcomes), "path_conditions": cubes}


def earlier():
    paths = (
        "research/language-design/RT-03/SOURCE-CLEANUP-CFG-01/evidence.json",
        "research/language-design/RT-04/GRANT-REVOCATION-01/evidence.json",
        "research/semantic-representation/RT-06/SPG-GUARDED-DISCOVERY-01/evidence.json",
    )
    return {path: sha256(subprocess.check_output(["git", "show", f"{BASE}:{path}"])).hexdigest()
            for path in paths}


if __name__ == "__main__":
    print(json.dumps({
        "baseline": BASE, "prior_ledgers": earlier(), "results": check(),
        "sources": {p.name: sha256(p.read_bytes()).hexdigest()
                    for p in (Path(__file__), CFG / "flow.py", CFG / "reference.py", CFG / "run.py")},
    }, sort_keys=True, indent=2))
