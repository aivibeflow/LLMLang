#!/usr/bin/env python3
"""Kernel-check arbitrary mutable relabeling and the pinned native graph archive."""

import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[2] / "semantic-representation" / "RT-05" / "MUTABLE-REFERENCE-TOPOLOGY-01"
NATIVE_DIGEST = "f5cf419721818a2d256e1fbfbf12a8a8e3583349fc0fadf05f745e7378c25bf1"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"


def digest(data):
    return sha256(data).hexdigest()


def lean_call(lean, directory, *arguments):
    return subprocess.run([lean, "-DwarningAsError=true", *arguments], cwd=directory, capture_output=True,
                          text=True, timeout=60, env={**os.environ, "LEAN_PATH": str(directory)})


def audit(result, prefix):
    assert result.returncode == 0, result.stdout + result.stderr
    theorems = {}
    for line in result.stdout.splitlines():
        row = re.fullmatch(rf"'{re.escape(prefix)}([\w.]+)' depends on axioms: \[(.*)\]", line)
        if row:
            key, entries = row.groups()
            axioms = entries.split(", ")
        else:
            row = re.fullmatch(rf"'{re.escape(prefix)}([\w.]+)' does not depend on any axioms", line)
            assert row, line
            key, axioms = row[1], []
        assert key not in theorems and set(axioms) <= {"propext", "Quot.sound"}
        theorems[key] = axioms
    return theorems


def listing(expressions):
    return "[" + ", ".join(expressions) + "]"


def path(coords):
    return f"({coords[0]}, {coords[1]})"


def action(command):
    operation, origin, *argument = command
    if operation == "read":
        return f".read {path(origin)}"
    if operation == "add":
        return f".add {path(origin)} ({argument[0]})"
    assert operation in ("same", "link")
    return f".{operation} {path(origin)} {path(argument[0])}"


def reply(value):
    if value is None:
        return ".missing"
    if isinstance(value, bool):
        return ".boolean " + str(value).lower()
    return f".value ({value})"


def traces(values):
    return listing(listing(map(reply, vector)) for vector in values)


def lean_graph(graph):
    first, second, third = graph["roots"]
    roots = f"(fun i => if i.val = 0 then {first} else if i.val = 1 then {second} else {third})"
    cells = []
    for key, value, next_cell in graph["cells"]:
        edge = "none" if next_cell is None else f"some {next_cell}"
        cells.append(f"({key}, ({value}), {edge})")
    return f"replay {roots} {listing(cells)}"


def load_archive(native):
    data = (native / "evidence.json").read_bytes()
    assert digest(data) == NATIVE_DIGEST
    archive = json.loads(data)
    for name, expected in archive["sources"].items():
        assert digest((native / name).read_bytes()) == expected
    spec = importlib.util.spec_from_file_location("native_graph_projections", native / "run.py")
    normalizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(normalizer)
    return archive, normalizer


def replay_code(archive, normalizer):
    recipes = listing(listing(map(action, recipe)) for recipe in archive["recipes"])
    chunks = ["import Heap", "open MutableRenaming", "set_option maxHeartbeats 1000000",
              f"def recipes : List (List Action) := {recipes}",
              "def replay (roots : Fin 3 → Nat) (heap : List (Nat × Int × Option Nat)) :=",
              "  recipes.map (runArchive roots heap)"]
    for index, example in enumerate(archive["observations"]):
        reference = example["trace"]
        variant = example["variants"][0]
        graphs = [example["graph"], variant["wire"]]
        expected = [reference, reference]
        for policy in ("shared_graph", "root_local"):
            graph = normalizer.normalize(variant["wire"], policy)
            observed = variant["projections"][policy]
            assert normalizer.key(graph) == observed["key"]
            differences = dict(observed["trace_differences"])
            assert differences.keys() <= set(range(len(reference)))
            graphs.append(graph)
            expected.append([differences.get(case, trace) for case, trace in enumerate(reference)])
        assert expected[2] == reference
        left = ", ".join(map(lean_graph, graphs))
        right = ", ".join(map(traces, expected))
        chunks.extend([f"theorem archiveCase{index} : ({left}) = ({right}) := by rfl",
                       f"#print axioms archiveCase{index}"])
    return "\n".join(chunks) + "\n"


def run(lean, native, directory):
    revision = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in revision
    proof = HERE / "Heap.lean"
    kernel = lean_call(lean, directory, f"--root={HERE}", "-o", str(directory / "Heap.olean"), str(proof))
    theorems = audit(kernel, "MutableRenaming.")
    assert len(theorems) == 10
    archive, normalizer = load_archive(native)
    assert archive["isomorphism_classes"] == len(archive["observations"]) == 184
    emitted = replay_code(archive, normalizer)
    replay = directory / "Replay.lean"
    replay.write_text(emitted, encoding="utf-8")
    equalities = audit(lean_call(lean, directory, str(replay)), "archiveCase")
    assert set(equalities) == {str(index) for index in range(archive["isomorphism_classes"])}
    negative = directory / "Incorrect.lean"
    negative.write_text("""import Heap
open MutableRenaming
example : runArchive (fun _ => 0) oneCell splitControl =
    runArchive Fin.val splitCells splitControl := by rfl
""", encoding="utf-8")
    refused = lean_call(lean, directory, str(negative))
    assert refused.returncode == 1 and "not definitionally equal" in (refused.stdout + refused.stderr).lower()
    return {"schema": "llmlang-rt32-mutable-renaming/1", "python": platform.python_version(), "lean": revision,
            "sources": {name: digest((HERE / name).read_bytes()) for name in ("Heap.lean", "run.py")},
            "generated_replay_sha256": digest(emitted.encode()), "native_archive_sha256": NATIVE_DIGEST,
            "native_python": archive["python"], "native_node": archive["node"], "native_v8": archive["v8"],
            "model_theorem_axioms": theorems, "archive_equalities": equalities, "archived_recipes": len(archive["recipes"]),
            "archive_paths": ["original", "relabelled", "shared_canonical", "separate_roots"],
            "incorrect_split_preservation_proof": "rejected"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--native-dir", type=Path, default=NATIVE)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-rt32-mutable-renaming-") as scratch:
        print(json.dumps(run(args.lean, args.native_dir.resolve(), Path(scratch)), indent=2))
