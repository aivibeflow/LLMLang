"""Replay three archive layouts against exact bytes and a small observation oracle."""

import json

from archive import Archive, PROFILES, encode_graph, restore
from src.persistence import dumps_graph
from src.semantic_graph import RelationStore
from src.spg_representation import Implementation, Operation, Program, compile_program, observe


CASES = ("baseline", "rename-parameter", "one-body-edit", "helper-edit", "rebind", "effect-order")
SIZES = (12, 32, 64)
INPUTS = (-2, 0, 5)


def fixture(size, case):
    parameter = "renamed" if case == "rename-parameter" else "x"
    operations = {"provider": Operation("Provider", ("Int",), "Int", "quiet")}
    implementations = {
        "left": Implementation("provider", (parameter,), parameter + (" + 12" if case == "helper-edit" else " + 11")),
        "right": Implementation("provider", (parameter,), parameter + " + 22"),
    }
    term = parameter
    for offset in range(1, 5):
        term = f"(({term} + {offset}) - {offset})"
    for i in range(size):
        slot = f"entry_{i}"
        operations[slot] = Operation(f"Entry{i}", ("Int",), "Int", "ordered")
        target = ("left", "right", "provider")[i % 3]
        name = "op" if target == "provider" else "pin"
        argument = f'{name}("{target}", emit("first", {term}))'
        bias = 6 if case == "one-body-edit" and i == 0 else 5
        side = f'emit("last", {bias})'
        body = f"{side} + {argument}" if case == "effect-order" and i == 0 else f"{argument} + {side}"
        implementations[slot] = Implementation(slot, (parameter,), body)
    return Program({"quiet": ((),), "ordered": (("first", "last"), ("last", "first"))},
                   operations, implementations, {"provider": "right" if case == "rebind" else "left"})


def oracle(case, entry, value):
    right = entry % 3 == 1 or (entry % 3 == 2 and case == "rebind")
    delta = 22 if right else 12 if case == "helper-edit" else 11
    bias = 6 if case == "one-body-edit" and entry == 0 else 5
    events = ("last", "first") if case == "effect-order" and entry == 0 else ("first", "last")
    return value + delta + bias, events


def measure(archive, baseline):
    current = archive.blobs.keys()
    known = baseline.blobs.keys()
    added = current - known
    return {
        "objects": len(current),
        "raw_bytes": sum(map(len, archive.blobs.values())),
        "changed_objects": len(added),
        "new_raw_bytes": sum(len(archive.blobs[key]) for key in added),
        "archive_root": archive.root,
    }


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def negative_cases(archive, graph):
    rows = (graph.store.get(graph.snapshot.mapping[f"implementation:entry_{i}"]).payload for i in (0, 1))
    left, right = rows
    require(left[2] == right[2] and left[3] != right[3], "Expected equal open templates and distinct pins")
    require(observe(graph, "entry_0", (0,)) != observe(graph, "entry_1", (0,)),
            "The same structural expression should have different observations under these bindings")
    blobs = archive.blobs
    manifest = json.loads(blobs[archive.root])
    keys = {graph.snapshot.mapping[f"implementation:entry_{i}"] for i in (0, 1)}
    roots = [row["payload"][2]["expression_root"]
             for row in map(lambda name: json.loads(blobs[name]), manifest["value_rows"])
             if row["value_hash"] in keys]
    require(len(roots) == 2 and roots[0] == roots[1], "Expected physical sharing of the open expression")
    subexpr = roots[0]
    for changed in ({name: value for name, value in blobs.items() if name != subexpr},
                    {**blobs, subexpr: b"{}"}):
        try:
            restore(Archive(archive.root, changed), "expression")
        except (KeyError, ValueError):
            continue
        raise AssertionError("Archive accepted a missing or corrupt expression")
    return {"same_open_template_distinct_calls": True, "missing_and_corrupt_blobs_rejected": 2}


def run():
    observed = 0
    samples = []
    controls = None
    for size in SIZES:
        baseline = {}
        for case in CASES:
            graph = compile_program(fixture(size, case))
            expected = dumps_graph(graph.store, RelationStore(), [graph.snapshot])
            for profile in PROFILES:
                archive = encode_graph(graph, profile)
                if case == "baseline":
                    baseline[profile] = archive
                restored, exact = restore(archive, profile)
                require(exact == expected, "Archive did not restore byte-exact graph")
                for i in range(size):
                    for value in INPUTS:
                        require(observe(restored, f"entry_{i}", (value,)) == oracle(case, i, value),
                                f"Observation mismatch at {size} {case} {profile} {i} {value}")
                        observed += 1
                if case == "rename-parameter":
                    require(archive == baseline[profile], "Parameter rename affected archive bytes")
                if size == SIZES[0] and case == "baseline" and profile == "expression":
                    controls = negative_cases(archive, graph)
                samples.append({"entries": size, "case": case, "profile": profile,
                                **measure(archive, baseline[profile])})
    return {"observations": observed, "exact_round_trips": len(samples), "controls": controls, "samples": samples}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
