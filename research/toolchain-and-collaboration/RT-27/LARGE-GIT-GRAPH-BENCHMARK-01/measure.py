"""Measure fresh Git reconstruction and exact traversal of dense synthetic graphs."""

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
import struct
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter_ns


SIZE = 65536
WIDTH = 64
SHARD = 512
DEGREES = (2, 32)
ROOTS = (SIZE - 1, 49151, 32767, 16383, 65)
NONE = 0xFFFFFFFF
ENV = {
    **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_AUTHOR_NAME": "Synthetic Graph", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Synthetic Graph", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2026-11-25T00:00:00+00:00", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00+00:00",
    "LC_ALL": "C",
}


def git(cwd, *args):
    result = subprocess.run(("git", "-c", "pack.threads=1", "-c", "protocol.file.allow=always", *args),
                            cwd=cwd, env=ENV, check=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def adjacency(value, degree):
    if value < WIDTH:
        return ()
    layer_beginning = value // WIDTH * WIDTH - WIDTH
    start = (value * 7 + value // WIDTH * 11) % WIDTH
    return tuple(sorted(layer_beginning + (start + i * 19) % WIDTH for i in range(degree)))


def record_format(degree):
    return struct.Struct(f">{degree + 1}I32s")


def write_shard(repo, start, degree, revision):
    packed = record_format(degree)
    shard = bytearray()
    for node in range(start, start + SHARD):
        dependencies = adjacency(node, degree) or (NONE,) * degree
        content = sha256(f"{node}/{revision}".encode()).digest()
        shard.extend(packed.pack(node, *dependencies, content))
    path = repo / f"graph/{start // SHARD:04d}.bin"
    path.write_bytes(shard)


def write_manifest(repo, degree):
    shards = {path.name: sha256(path.read_bytes()).hexdigest()
              for path in sorted((repo / "graph").glob("*.bin"))}
    manifest = {"size": SIZE, "degree": degree, "shard_size": SHARD, "width": WIDTH, "shards": shards}
    document = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (repo / "graph.json").write_bytes(document + b"\n")
    return sha256(document + b"\n").hexdigest()


def prepare(repo, degree):
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=research/all", "--object-format=sha1")
    (repo / "graph").mkdir()
    for start in range(0, SIZE, SHARD):
        write_shard(repo, start, degree, 0)
    original = write_manifest(repo, degree)
    git(repo, "add", "graph", "graph.json")
    git(repo, "commit", "-qm", "Baseline synthetic graph")
    revisions = [original]
    for revision, starts in enumerate(((0, SHARD), (0, SIZE - SHARD)), start=1):
        for start in starts:
            write_shard(repo, start, degree, revision)
        revisions.append(write_manifest(repo, degree))
        git(repo, "add", "graph", "graph.json")
        git(repo, "commit", "-qm", f"Update payloads in synthetic revision {revision}")
    git(repo, "-c", "pack.compression=6", "repack", "-a", "-d")
    return {
        "commits": git(repo, "rev-list", "--reverse", "HEAD").splitlines(),
        "manifest_sha256": revisions, "pack_bytes": sum(path.stat().st_size for path in
                                                         (repo / ".git/objects/pack").glob("*.pack")),
        "checkout_bytes": sum(path.stat().st_size for path in (repo / "graph").glob("*.bin")),
    }


def read_graph(repo, expected_manifest, degree):
    document = (repo / "graph.json").read_bytes()
    if sha256(document).hexdigest() != expected_manifest:
        raise ValueError("wrong checked-out manifest")
    info = json.loads(document)
    if (info["size"], info["degree"], info["shard_size"], info["width"]) != (SIZE, degree, SHARD, WIDTH):
        raise ValueError("wrong fixture profile")
    parents = []
    for name, digest in sorted(info["shards"].items()):
        data = (repo / "graph" / name).read_bytes()
        if sha256(data).hexdigest() != digest:
            raise ValueError((name, "container bytes changed"))
        for node, *rest in record_format(degree).iter_unpack(data):
            dependencies = tuple(rest[:-1])
            if node != len(parents):
                raise ValueError("incorrect node order")
            if node < WIDTH:
                if dependencies != (NONE,) * degree:
                    raise ValueError("first-layer node has a dependency")
                dependencies = ()
            elif len(set(dependencies)) != degree or any(
                    dep // WIDTH != node // WIDTH - 1 for dep in dependencies):
                raise ValueError("incorrect dependency profile")
            parents.append(dependencies)
    if len(parents) != SIZE:
        raise ValueError("incomplete graph")
    return parents


def walk(parents, root):
    seen = {root}
    queue = [root]
    for node in queue:
        for dependency in parents[node]:
            if dependency not in seen:
                seen.add(dependency)
                queue.append(dependency)
    return seen


def reference(degree, root):
    # At each layer, derive the predecessor set directly instead of traversing the decoded graph.
    current = {root}
    closure = current.copy()
    for _ in range(root // WIDTH):
        current = {predecessor for node in current for predecessor in adjacency(node, degree)}
        closure.update(current)
    return closure


def timed(function):
    start = perf_counter_ns()
    result = function()
    return result, perf_counter_ns() - start


def counters():
    return {key: int(number) for key, number in
            map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())}


def collect(args):
    if args.cpu not in os.sched_getaffinity(0) or args.trials < 2:
        raise ValueError("invalid CPU or trials")
    os.sched_setaffinity(0, {args.cpu})
    random = Random(args.seed)
    records = []
    with TemporaryDirectory(prefix="rt27-git-graph-") as temporary:
        stage = Path(temporary)
        repositories = {degree: stage / f"origin-{degree}" for degree in DEGREES}
        identities = {degree: prepare(path, degree) for degree, path in repositories.items()}
        references = {degree: [reference(degree, root) for root in ROOTS] for degree in DEGREES}
        before = counters()
        for trial in range(args.trials):
            order = list(DEGREES)
            random.shuffle(order)
            for position, degree in enumerate(order):
                repo, clone = repositories[degree], stage / "checked-out"
                identity = identities[degree]
                _, clone_ns = timed(lambda: git(stage, "clone", "-q", "--no-local", repo.as_uri(), clone))
                git(clone, "remote", "remove", "origin")
                if git(clone, "rev-list", "--reverse", "HEAD").splitlines() != identity["commits"]:
                    raise ValueError("clean clone lost committed history")
                # Check historical manifest bytes using only the disconnected clone.
                for commit, digest in zip(identity["commits"], identity["manifest_sha256"], strict=True):
                    raw = git(clone, "show", f"{commit}:graph.json").encode() + b"\n"
                    if sha256(raw).hexdigest() != digest:
                        raise ValueError("historic graph identity changed")
                parents, verify_ns = timed(lambda: read_graph(clone, identity["manifest_sha256"][-1], degree))
                scopes, traversal_ns = timed(lambda: [walk(parents, root) for root in ROOTS])
                if scopes != references[degree]:
                    raise ValueError("the decoded graph gives different reachability")
                records.append({"trial": trial, "position": position, "degree": degree,
                                "edges": (SIZE - WIDTH) * degree, "roots": len(ROOTS),
                                "closure_sizes": ",".join(str(len(value)) for value in scopes),
                                "clone_ns": clone_ns, "verify_ns": verify_ns, "traversal_ns": traversal_ns})
                # Only the collector-owned disposable clone is removed.
                subprocess.run(["rm", "-r", "--", clone], check=True, timeout=30)
        after = counters()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "samples.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    settings = {
        "git": git(Path.cwd(), "--version"), "python": platform.python_version(), "cpu": args.cpu,
        "trials": args.trials, "seed": args.seed, "kernel": platform.release(),
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "nodes": SIZE, "roots": ROOTS, "shard": SHARD, "layer_width": WIDTH,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "repositories": identities,
        "counter_delta": {key: after[key] - before[key] for key in before},
    }
    (args.output / "config.json").write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("cpu", "seed", "trials"):
        parser.add_argument(f"--{field}", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    collect(parser.parse_args())
