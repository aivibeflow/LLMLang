#!/usr/bin/env python3
"""Measure native add/remove-only history using existing typed SPG prototype records."""

from dataclasses import replace
import json
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.path.insert(0, str(PROJECT / "PROTOTYPES/DEPENDENCY-GRAPH-01"))

from src.persistence import dumps_graph, loads_graph
from src.semantic_graph import RelationStore, canonical_bytes, digest as graph_digest, make_snapshot
from src.spg_admission import validate
from src.spg_representation import Graph, Program, compile_program, observe
from tests.test_spg_representation import dispatch_program

HISTORY = runpy.run_path(str(HERE.parent / "DIVERGENT-GIT-HISTORY-01/run.py"))
encode, digest, closure = (HISTORY[name] for name in ("encode", "digest", "closure"))


def program(modules):
    template = dispatch_program()
    contracts = dict(template.contracts)
    operations = {}
    implementations = {}
    bindings = {}
    for module, variant in sorted(modules.items()):
        provider = f"m{module}_provider"
        primary = f"m{module}_primary"
        alternate = f"m{module}_alternate"
        for key, operation in template.operations.items():
            operations[f"m{module}_{key}"] = replace(operation, export=f"M{module}{operation.export}")
        for key, implementation in template.implementations.items():
            body = implementation.body
            if key == "primary":
                body = f'emit("first", emit("last", n + {1 + variant}))'
            elif key == "alternate":
                body = f'emit("first", emit("last", n + {2 + variant}))'
            elif key == "late":
                body = body.replace('"provider"', f'"{provider}"')
            elif key == "direct":
                body = body.replace('"primary"', f'"{primary}"')
            implementations[f"m{module}_{key}"] = replace(
                implementation, operation=f"m{module}_{implementation.operation}", body=body,
            )
        bindings[provider] = primary if variant % 2 == 0 else alternate
    return Program(contracts, operations, implementations, bindings)


def carrier(modules, parent):
    source = program(modules)
    first = compile_program(source)
    snapshot = make_snapshot(first.snapshot.mapping, () if parent is None else (parent,))
    graph = Graph(first.store, snapshot)
    validate(graph)
    archived = dumps_graph(graph.store, RelationStore(), (snapshot,))
    serialized = json.loads(archived)["payload"]
    values = {row["value_hash"]: row for row in serialized.pop("values")}
    withdrawn = set(values)
    translated = {}
    raw_objects = {}

    def physical(kind, value, links):
        raw = encode({"kind": kind, "value": value, "references": links})
        address = digest(raw)
        raw_objects[address] = raw
        return address

    while withdrawn:
        progressed = []
        for address in sorted(withdrawn):
            value = values[address]
            required = [edge["target_hash"] for edge in value["dependencies"]]
            if all(child in translated for child in required):
                translated[address] = physical(value["kind"], value, [translated[x] for x in required])
                progressed.append(address)
        assert progressed
        withdrawn.difference_update(progressed)
    root = physical("prototype-document", serialized, sorted(translated.values()))
    expected = closure(root, raw_objects.__getitem__)
    template = json.loads(expected[root])["value"]
    materialized = template | {"values": sorted(
        [json.loads(raw)["value"] for address, raw in expected.items() if address != root],
        key=lambda row: row["value_hash"],
    )}
    recovered, relations, selected_list = loads_graph(
        canonical_bytes({"payload": materialized, "checksum": graph_digest(materialized)}) + b"\n"
    )
    selected, = selected_list
    rebuilt = Graph(recovered, selected)
    validate(rebuilt)
    assert selected == snapshot and dumps_graph(recovered, relations, (selected,)) == archived
    first_module = min(modules)
    amount = modules[first_module]
    observed = [observe(rebuilt, f"m{first_module}_late", (n,)) for n in (-2, 0, 31)]
    assert observed == [(n + amount + (1 if amount % 2 == 0 else 2), ("first", "last")) for n in (-2, 0, 31)]
    slots = sorted(values)
    object_order = {
        translated[address]: int.from_bytes(bytes.fromhex(address)[:8], "big") for address in slots
    }
    assert len(set(object_order.values())) == len(object_order)
    return {
        "root": root, "records": expected, "order": object_order | {root: -1},
        "exact_spg_root": snapshot.root_hash, "semantic_values": len(values),
        "value_range": [min(len(canonical_bytes(value)) for value in values.values()),
                        max(len(canonical_bytes(value)) for value in values.values())],
    }


def dataset():
    modules = dict.fromkeys(range(12), 0)
    common = [carrier(modules, None)]
    for step in range(1, 9):
        modules[step % 12] = step
        if step == 2:
            modules[12] = 0
        if step == 4:
            del modules[10]
        common.append(carrier(modules, common[-1]["exact_spg_root"]))
    arms = []
    for variant in (17, 23):
        selection = dict(modules)
        parent = common[-1]["exact_spg_root"]
        chain = []
        for step in range(3):
            selection[step] = variant + step
            if step == 0:
                selection[variant] = 1
            if step == 1:
                del selection[9]
            row = carrier(selection, parent)
            parent = row["exact_spg_root"]
            chain.append(row)
        arms.append(chain)
    return (common, *arms)


def experiment(directory):
    corpus = dataset()
    exact = {}
    meter = HISTORY["Meter"](directory)
    for layout in HISTORY["layouts"]:
        result, _ = HISTORY["test_layout"](directory / layout, layout, corpus, meter)
        assert result["restored_commits"] == 16
        exact[layout] = result
    assert len({tuple(row["selected_roots"]) for row in exact.values()}) == 1
    mutations = []
    for branch, chain in enumerate(corpus):
        previous = set() if branch == 0 else set(corpus[0][-1]["records"])
        for frame in chain:
            current = set(frame["records"])
            mutations.append({
                "arm": branch, "prototype_root": frame["exact_spg_root"],
                "transport_root": frame["root"], "prototype_values": frame["semantic_values"],
                "value_range": frame["value_range"], "added": len(current - previous),
                "retired": len(previous - current),
            })
            previous = current
    assert any(row["added"] > row["retired"] > 0 for row in mutations)
    assert any(row["retired"] > row["added"] > 0 for row in mutations)
    return {
        "format": "prototype-spg-packs-01",
        "git": HISTORY["git"](directory, "--version").decode().strip(),
        "layouts": exact, "typed_revisions": mutations,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-typed-spg-packs-") as directory:
        ref = experiment(Path(directory))
    text = json.dumps(ref, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
