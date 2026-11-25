#!/usr/bin/env python3
"""Check discriminating bound-method probes and the exact C/Rust projection archive."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import importlib.util
from itertools import batched
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[2] / "semantic-representation" / "RT-05" / "STATEFUL-BOUND-METHOD-01"
NATIVE_DIGEST = "c8676019a02362fa156d2d1039b7a4281a1de586535b9b191ba1dc1d8e143abd"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
MODES = ("raw", "code_only", "values_only", "exact")
PROBES = (((0, 0, 0),), ((0, 1, 0),), ((1, 0, 0),), ((1, 1, 0),),
          ((2, 0, 0), (0, 1, 0)), ((2, 0, 1), (0, 1, 0)))


def digest(data):
    return sha256(data).hexdigest()


def lean_call(lean, directory, *arguments):
    return subprocess.run([lean, "-DwarningAsError=true", *arguments], cwd=directory, capture_output=True,
                          text=True, timeout=60, env={**os.environ, "LEAN_PATH": str(directory)})


def audit(result, prefix):
    assert result.returncode == 0, result.stdout + result.stderr
    declarations = {}
    for line in result.stdout.splitlines():
        row = re.fullmatch(rf"'{re.escape(prefix)}([\w.]+)' depends on axioms: \[(.*)\]", line)
        if row:
            name, entries = row.groups()
            axioms = entries.split(", ")
        else:
            row = re.fullmatch(rf"'{re.escape(prefix)}([\w.]+)' does not depend on any axioms", line)
            assert row, line
            name, axioms = row[1], []
        assert name not in declarations and set(axioms) <= {"propext", "Classical.choice", "Quot.sound"}, line
        declarations[name] = axioms
    return declarations


def list_of(items):
    return "[" + ", ".join(items) + "]"


def lean_action(item):
    kind, side, argument = item
    role = (".left", ".right")[side]
    if kind == 0:
        assert argument == 0
        return f".read {role}"
    operation = {1: "add", 2: "replace"}[kind]
    return f".{operation} {role} ({argument})"


def lean_context(context):
    shared, first, second, left, right = context
    if shared:
        assert first == second
        storage = f".shared ({first})"
    else:
        storage = f".separate ({first}) ({second})"
    return f"⟨({left}), ({right}), {storage}⟩"


def lean_trace(vec):
    assert len(vec) % 2 == 0
    return list_of(f"(({left}), ({right}))" for left, right in zip(vec[::2], vec[1::2], strict=True))


def load_archive(native):
    data = (native / "evidence.json").read_bytes()
    assert digest(data) == NATIVE_DIGEST
    archive = json.loads(data)
    for name, expected in archive["sources"].items():
        assert digest((native / name).read_bytes()) == expected, name
    spec = importlib.util.spec_from_file_location("native_bound_method_projections", native / "run.py")
    projections = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(projections)
    return archive, projections


def new_native_probes(directory, archive, projections):
    rows = [(example["context"], recipe) for example in archive["observations"] for recipe in PROBES]
    profiles = projections.native(directory, rows)
    assert list(profiles) == archive["profiles"]
    assert all(values == profiles["c_O0"] for values in profiles.values())
    assert projections.command(directory, "gcc", "--version").splitlines()[0] == archive["gcc"]
    assert projections.command(directory, "rustc", "-vV").splitlines() == archive["rustc"]
    traces = (tuple(row[2:]) for row in profiles["c_O0"])
    groups = list(batched(traces, len(PROBES)))
    assert len(set(groups)) == len(groups) == archive["contexts"]
    return groups


def replay_code(archive, model, probe_results, interval):
    recipes = list_of(list_of(map(lean_action, recipe)) for recipe in archive["recipes"])
    chunks = ["import Receiver", "open BoundMethod", "set_option maxHeartbeats 1000000",
              f"def recipes : List (List Action) := {recipes}",
              "def replay (context : Context) := recipes.map (trace context)"]
    for index in interval:
        example = archive["observations"][index]
        native_probes = probe_results[index]
        context = example["context"]
        original = example["reference"]
        native_vectors = [original]
        reconstructed = [context]
        for policy in MODES[1:]:
            row = example["choices"][policy]
            assert model.identity(model.descriptor(policy, context)) == row["key"]
            reconstructed.append(model.projection(policy, context))
            diffs = dict(row["differences"])
            assert diffs.keys() <= set(range(len(original)))
            native_vectors.append([diffs.get(index, vector) for index, vector in enumerate(original)])
        left = ", ".join(f"replay {lean_context(ctx)}" for ctx in reconstructed)
        right = ", ".join(list_of(map(lean_trace, vectors)) for vectors in native_vectors)
        chunks.extend([f"theorem archiveCase{index} : ({left}) = ({right}) := by rfl",
                       f"#print axioms archiveCase{index}"])
        expected = list_of(map(lean_trace, native_probes))
        chunks.extend([f"theorem probeCase{index} : signature {lean_context(context)} = {expected} := by rfl",
                       f"#print axioms probeCase{index}"])
    return "\n".join(chunks) + "\n"


def verify_replay_shards(lean, directory, archive, projections, probe_results):
    amount = archive["contexts"]
    shard_size = 12
    sources = {}
    for start in range(0, amount, shard_size):
        replay = directory / f"Replay{start}.lean"
        contents = replay_code(archive, projections, probe_results, range(start, min(start + shard_size, amount)))
        replay.write_text(contents, encoding="utf-8")
        sources[replay] = digest(contents.encode())

    def verify(replay):
        return audit(lean_call(lean, directory, str(replay)), "")

    equalities = {}
    with ThreadPoolExecutor(max_workers=3) as workers:
        for checked in workers.map(verify, sources):
            assert not set(equalities) & set(checked)
            equalities.update(checked)
    return equalities, {path.name: content for path, content in sources.items()}


def run(lean, native, directory):
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in version
    source = HERE / "Receiver.lean"
    kernel = lean_call(lean, directory, f"--root={HERE}", "-o", str(directory / "Receiver.olean"), str(source))
    model = audit(kernel, "BoundMethod.")
    assert len(model) == 7
    archive, projections = load_archive(native)
    assert len(archive["observations"]) == archive["contexts"] == 108
    probe_results = new_native_probes(directory, archive, projections)
    equalities, generated = verify_replay_shards(lean, directory, archive, projections, probe_results)
    expected = {f"{prefix}{index}" for index in range(archive["contexts"]) for prefix in ("archiveCase", "probeCase")}
    assert set(equalities) == expected
    archived = {name: axioms for name, axioms in equalities.items() if name.startswith("archiveCase")}
    new_probes = {name: axioms for name, axioms in equalities.items() if name.startswith("probeCase")}
    negative = directory / "Incorrect.lean"
    negative.write_text("""import Receiver
open BoundMethod
example : signature ⟨0, 0, .shared 0⟩ = signature ⟨0, 0, .separate 0 0⟩ := by rfl
""", encoding="utf-8")
    refused = lean_call(lean, directory, str(negative))
    assert refused.returncode == 1 and "not definitionally equal" in (refused.stdout + refused.stderr).lower()
    return {"schema": "llmlang-rt32-bound-method-observations/1", "python": platform.python_version(), "lean": version,
            "sources": {name: digest((HERE / name).read_bytes()) for name in ("Receiver.lean", "run.py")},
            "native_archive_sha256": NATIVE_DIGEST, "generated_replay_sha256": generated,
            "native_optimization_profiles": archive["profiles"], "fixed_discriminating_probes": len(PROBES),
            "native_distinct_full_probe_signatures": len(set(probe_results)),
            "native_distinct_short_probe_signatures": len({group[:5] for group in probe_results}),
            "native_probe_vectors": len(probe_results) * len(PROBES) * len(archive["profiles"]),
            "model_theorem_axioms": model, "archive_equalities": archived, "native_probe_equalities": new_probes,
            "archive_modes": MODES, "archive_recipes": len(archive["recipes"]), "false_equivalence": "rejected"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--native-dir", type=Path, default=NATIVE)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-rt32-bound-method-") as scratch:
        print(json.dumps(run(args.lean, args.native_dir.resolve(), Path(scratch)), indent=2))
