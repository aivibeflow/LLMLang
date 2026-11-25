"""Measure semantic JSON canonicalization and hashing with explicit immutable reuse."""

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
import subprocess
import sys
from time import perf_counter_ns


HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01" / "src"
sys.path.insert(0, str(GRAPH))
from semantic_graph import canonical_bytes


SIZES = (8, 64, 512)
SHAPES = ("flat", "nested")
ROUNDS = 16
OBJECTS = 4
PROFILE = "semantic-value-json-v1"


def payload(size, shape, offset):
    if shape == "flat":
        return {f"entry/{i:04d}": offset + i for i in reversed(range(size))}
    return {
        f"узел/{i:04d}": {"tag": f"café/{offset}", "optional": None, "flags": [True, False],
                          "edges": [i, i + 7, str(i * offset)]}
        for i in reversed(range(size))
    }


def digest(data):
    return sha256(data).digest()


def timed(function):
    started = perf_counter_ns()
    result = function()
    return result, perf_counter_ns() - started


def probe(shape, size, seed):
    source = tuple(payload(size, shape, offset) for offset in range(OBJECTS))
    keys = tuple((PROFILE, f"revision/{i}", f"object/{i}") for i in range(OBJECTS))
    encoded = tuple(canonical_bytes(value) for value in source)
    control = tuple(canonical_bytes(dict(reversed(tuple(value.items())))) for value in source)
    if encoded != control or len(set(encoded)) != OBJECTS:
        raise ValueError("canonical encoding must preserve keys and ignore insertion order")
    ordered_json = tuple(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() for value in source)
    if any(wrong == right for wrong, right in zip(ordered_json, encoded, strict=True)):
        raise ValueError("insertion-order control failed")

    # Verify the refreshed value and contrast it with an old, logically related object.
    current = payload(size, shape, OBJECTS)
    new_key = (PROFILE, "revision/new", keys[0][2])
    revised = canonical_bytes(current)
    if revised == encoded[0] or new_key in keys:
        raise ValueError("the stale logical-identity control failed")

    expected_bytes = encoded * ROUNDS
    expected_hashes = tuple(map(digest, expected_bytes))
    cache, setup = timed(lambda: {key: canonical_bytes(value) for key, value in zip(keys, source, strict=True)})
    workloads = {
        "encode": (lambda: tuple(canonical_bytes(value) for value in source * ROUNDS), expected_bytes),
        "hash": (lambda: tuple(digest(chunk) for chunk in expected_bytes), expected_hashes),
        "encode_hash": (lambda: tuple(digest(canonical_bytes(value)) for value in source * ROUNDS), expected_hashes),
        "retained_hash": (lambda: tuple(digest(cache[key]) for key in keys * ROUNDS), expected_hashes),
    }
    order = list(workloads)
    Random(seed).shuffle(order)
    result = {}
    for name in order:
        work, want = workloads[name]
        observed, elapsed = timed(work)
        if observed != want:
            raise ValueError((shape, size, name))
        result[f"{name}_ns"] = elapsed
    return {
        "shape": shape, "entries_per_object": size, "invocations_per_scope": OBJECTS * ROUNDS,
        "retained_canonical_bytes": sum(map(len, encoded)), "cache_setup_ns": setup,
        "observation_sha256": sha256(b"".join(expected_hashes)).hexdigest(),
        "phase_order": ",".join(order), **result,
    }


def counters():
    pairs = map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())
    return {key: int(value) for key, value in pairs}


def collect(args):
    if args.cpu not in os.sched_getaffinity(0) or args.trials < 2:
        raise ValueError("select a usable logical CPU and at least two trials")
    os.sched_setaffinity(0, {args.cpu})
    random = Random(args.seed)
    results = []
    signatures = {}
    before = counters()
    for batch in range(args.trials):
        profiles = [(shape, size) for shape in SHAPES for size in SIZES]
        random.shuffle(profiles)
        for position, (shape, size) in enumerate(profiles):
            seed = random.getrandbits(32)
            process = subprocess.run([sys.executable, __file__, "--child", shape, str(size), str(seed)],
                                     check=True, capture_output=True, text=True, timeout=45)
            if process.stderr:
                raise ValueError(process.stderr)
            result = json.loads(process.stdout)
            expected = signatures.setdefault((shape, size), result["observation_sha256"])
            if expected != result["observation_sha256"]:
                raise ValueError("observation ledger changed between trials")
            results.append({"batch": batch, "position": position, "seed": seed, **result})
    after = counters()
    args.output.mkdir(parents=True, exist_ok=False)
    fields = ("batch", "position", "seed", "shape", "entries_per_object", "invocations_per_scope",
              "retained_canonical_bytes", "cache_setup_ns", "observation_sha256", "phase_order",
              "encode_ns", "hash_ns", "encode_hash_ns", "retained_hash_ns")
    with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    config = {
        "cpu": args.cpu, "kernel": platform.release(), "python": platform.python_version(),
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "trials": args.trials, "seed": args.seed, "encoding_profile": PROFILE,
        "cpu_counter_delta": {key: after[key] - before[key] for key in before},
        "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in (HERE / "measure.py",
                                                                           GRAPH / "semantic_graph.py")},
    }
    (args.output / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--child":
        print(json.dumps(probe(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--cpu", required=True, type=int)
        parser.add_argument("--seed", required=True, type=int)
        parser.add_argument("--trials", required=True, type=int)
        parser.add_argument("--output", required=True, type=Path)
        collect(parser.parse_args())
