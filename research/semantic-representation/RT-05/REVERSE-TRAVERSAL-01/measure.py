"""Measure repeated reverse traversal on the existing immutable content graph."""

import argparse
import csv
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
import resource
import subprocess
import sys
from time import perf_counter_ns
import tracemalloc


HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01" / "src"
sys.path.insert(0, str(GRAPH))
from semantic_graph import ContentStore, Dependency


SIZES = (1024, 8192)
SHAPES = ("chain", "star", "layered-eight")
FIELDS = ("build_ns", "index_ns", "rebuild_batch_ns", "retained_batch_ns",
          "process_peak_kib", "live_store_bytes", "live_index_bytes")


class RetainedView:
    """Reuse the prototype's unmodified traversal over one frozen index."""

    dependents = ContentStore.dependents

    def __init__(self, index):
        self.index = index

    def reverse_dependencies(self):
        return self.index


def parents(shape, size):
    if shape == "chain":
        return [()] + [(i - 1,) for i in range(1, size)]
    if shape == "star":
        return [()] + [(0,) for _ in range(1, size)]
    return [tuple(range(offset - 8, offset)) if offset else ()
            for offset in (8 * (i // 8) for i in range(size))]


def build(adjacency):
    store = ContentStore()
    hashes = []
    for i, deps in enumerate(adjacency):
        links = [Dependency("requires", hashes[parent], "linked") for parent in deps]
        hashes.append(store.put("unit", {"unit": i}, links))
    return store, hashes


def expected(adjacency, hashes, query):
    # Each node's parents occur earlier by construction, so one forward pass suffices.
    reachable = {query}
    for i, dependencies in enumerate(adjacency):
        if any(parent in reachable for parent in dependencies):
            reachable.add(i)
    reachable.remove(query)
    return {hashes[i] for i in reachable}


def timed(function):
    start = perf_counter_ns()
    value = function()
    return value, perf_counter_ns() - start


def probe(shape, size, seed):
    adjacency = parents(shape, size)
    queries = (0, size // 8, size // 4, size // 2, 3 * size // 4, size - 1)
    (store, hashes), build_ns = timed(lambda: build(adjacency))
    index, index_ns = timed(store.reverse_dependencies)
    view = RetainedView(index)
    choices = [("rebuild_batch_ns", store), ("retained_batch_ns", view)]
    Random(seed).shuffle(choices)
    rows = {}
    for name, candidate in choices:
        rows[name] = timed(lambda: [candidate.dependents(hashes[query], transitive=True) for query in queries])
    oracle = [expected(adjacency, hashes, q) for q in queries]
    if any(result != oracle for result, _ in rows.values()):
        raise ValueError("a graph traversal disagreed with forward topological reachability")
    observation_hash = sha256(json.dumps([sorted(result) for result in oracle]).encode()).hexdigest()
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    payload_bytes = sum(len(store.get(key).payload_json.encode()) for key in hashes)

    # Measure live Python allocations in a separate untimed build.
    tracemalloc.start()
    memory_store, _ = build(adjacency)
    gc.collect()
    live_store, _ = tracemalloc.get_traced_memory()
    memory_index = memory_store.reverse_dependencies()
    live_store_and_index, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if len(memory_index) != size or live_store_and_index <= live_store:
        raise ValueError("missing retained reverse-index memory")
    return {
        "shape": shape, "nodes": size, "edges": sum(map(len, adjacency)),
        "queries": len(queries), "payload_bytes": payload_bytes,
        "observations_sha256": observation_hash,
        "route_order": ",".join(name for name, _ in choices),
        "build_ns": build_ns, "index_ns": index_ns,
        "rebuild_batch_ns": rows["rebuild_batch_ns"][1],
        "retained_batch_ns": rows["retained_batch_ns"][1], "process_peak_kib": peak_rss,
        "live_store_bytes": live_store, "live_index_bytes": live_store_and_index - live_store,
    }


def group_counters():
    return dict((key, int(value)) for key, value in
                map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines()))


def collect(args):
    if args.trials < 2 or args.cpu not in os.sched_getaffinity(0):
        raise ValueError("invalid trial count or CPU outside the current affinity")
    os.sched_setaffinity(0, {args.cpu})
    random = Random(args.seed)
    rows = []
    controls = {}
    before = group_counters()
    for block in range(args.trials):
        combinations = [(shape, size) for shape in SHAPES for size in SIZES]
        random.shuffle(combinations)
        for position, (shape, size) in enumerate(combinations):
            seed = random.getrandbits(32)
            process = subprocess.run([sys.executable, __file__, "--child", shape, str(size), str(seed)],
                                     check=True, text=True, capture_output=True, timeout=45)
            if process.stderr:
                raise ValueError(process.stderr)
            row = json.loads(process.stdout)
            expected = controls.setdefault((shape, size), row["observations_sha256"])
            if expected != row["observations_sha256"]:
                raise ValueError("semantic observation changed between trials")
            rows.append({"block": block, "position": position, "seed": seed, **row})
    after = group_counters()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "samples.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    paths = (HERE / "measure.py", GRAPH / "semantic_graph.py")
    config = {
        "python": sys.version.split()[0], "cpu": args.cpu, "kernel": platform.release(),
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "counter_delta": {key: value - before[key] for key, value in after.items() if key in before},
        "trials": args.trials, "seed": args.seed,
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
    }
    (args.output / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--child":
        print(json.dumps(probe(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--cpu", required=True, type=int)
        parser.add_argument("--trials", required=True, type=int)
        parser.add_argument("--seed", required=True, type=int)
        parser.add_argument("--output", required=True, type=Path)
        collect(parser.parse_args())
