#!/usr/bin/env python3
"""Measure three Git storage layouts over variable-size, divergent graph histories."""

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import runpy
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import time
import tracemalloc

HERE = Path(__file__).resolve().parent
BASE = runpy.run_path(str(HERE.parent / "GIT-CLOSED-REPRESENTATION-01/run.py"))
encode, digest, closure = (BASE[name] for name in ("encode", "digest", "closure"))
layouts = ("stable-shards", "immutable-segments", "content-defined-chunks")
SLOTS = 384
SHARDS = 8
HISTORY_LENGTHS = (20, 6)


def tool_env():
    return {
        "PATH": os.environ["PATH"], "LANG": "C", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    }


def git(repository, *args):
    return subprocess.run(["git", *args], cwd=repository, env=tool_env(), check=True,
                          capture_output=True).stdout


class Meter:
    def __init__(self, directory):
        self.binary = directory / "measure"
        self.output = directory / "measurement"
        subprocess.run(
            ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", str(HERE / "measure.c"),
             "-o", str(self.binary)], check=True, capture_output=True,
        )

    def git(self, repository, *args):
        result = subprocess.run(
            [str(self.binary), str(self.output), "git", *args], cwd=repository,
            env=tool_env(), check=True, capture_output=True,
        )
        wall, cpu, rss = map(int, self.output.read_text().split())
        return result.stdout, {"wall_ns": wall, "cpu_ns": cpu, "max_rss_kib": rss}


def fixture():
    global_records = {}

    def node(kind, value, dependencies=()):
        raw = encode({"kind": kind, "value": value, "references": dependencies})
        address = digest(raw)
        global_records[address] = raw
        return address

    common = [node("contract", {"arity": lane + 1, "effects": ["read", "write"][: lane % 3]})
              for lane in range(16)]

    def body(slot, revision):
        seed = digest(f"{slot}/{revision}".encode())
        repeat = 1 + int(seed[:4], 16) % 80
        text = ("input fold compare selected return " * repeat) + seed + (" λ" * (slot % 4))
        targets = [common[(slot + index) % len(common)] for index in range(1 + slot % 4)]
        return node("implementation", {"slot": slot, "profile": revision, "expr": text}, targets)

    active = {slot: body(slot, "base") for slot in range(SLOTS)}

    def freeze(slots):
        entries = [address for _, address in sorted(slots.items())]
        root = node("snapshot", {"slots": len(slots)}, entries)
        reachable = closure(root, global_records.__getitem__)
        ordering = {root: -1, **{address: index for index, address in enumerate(common, 1000)}}
        ordering.update({address: slot for slot, address in slots.items()})
        assert len(ordering) == len(reachable)
        return {"root": root, "records": reachable, "order": ordering}

    def mutate(slots, label, index, salt):
        sequence = sorted(slots)
        changed = [sequence[(salt + index * 7 + step * 53) % len(sequence)] for step in range(1 + index % 5)]
        for slot in changed:
            slots[slot] = body(slot, label)
        if index % 4 == 0:
            del slots[changed[0]]
            new_slot = salt * 1000 + index + 10_000
            slots[new_slot] = body(new_slot, label)
        return freeze(slots)

    common_path = [freeze(active)]
    for index in range(1, HISTORY_LENGTHS[0] + 1):
        common_path.append(mutate(active, f"common/{index}", index, 13))
    arms = []
    for salt, name in ((17, "primary"), (23, "alternate")):
        copy = active.copy()
        arms.append([mutate(copy, f"{name}/{index}", index, salt) for index in range(1, HISTORY_LENGTHS[1] + 1)])
    assert arms[0][-1]["root"] != arms[1][-1]["root"]
    return common_path, *arms


def row_data(entries):
    return b"".join(encode([address, raw.decode()]) + b"\n" for address, raw in entries)


def placement(layout, view, old, compact):
    records = view["records"]
    ordered = sorted(records, key=lambda address: view["order"][address])
    if layout == "stable-shards":
        buckets = [[] for _ in range(SHARDS)]
        for address in ordered:
            buckets[view["order"][address] % SHARDS].append((address, records[address]))
        return {f"shard-{number:02d}": row_data(values) for number, values in enumerate(buckets) if values}
    if layout == "immutable-segments":
        seen = {} if compact else old
        prior = set().union(*(inventory(raw) for raw in seen.values()))
        additions = [(address, records[address]) for address in ordered if address not in prior]
        if not additions:
            return seen.copy()
        raw = row_data(additions)
        return seen | {"segment-" + digest(raw): raw}
    assert layout == "content-defined-chunks"
    files = {}
    cursor = []
    for address in ordered:
        cursor.append((address, records[address]))
        if len(cursor) == 64 or (len(cursor) >= 16 and int(address[:4], 16) < 2048):
            raw = row_data(cursor)
            files["chunk-" + digest(raw)] = raw
            cursor = []
    if cursor:
        raw = row_data(cursor)
        files["chunk-" + digest(raw)] = raw
    return files


def inventory(raw):
    return {json.loads(line)[0] for line in raw.splitlines()}


def write_rev(repository, layout, view, old, *, compact=False):
    files = placement(layout, view, old, compact)
    folder = repository / "records"
    folder.mkdir(exist_ok=True)
    for name in old.keys() - files.keys():
        (folder / name).unlink()
    for name, raw in files.items():
        if old.get(name) != raw:
            (folder / name).write_bytes(raw)
    manifest = {"version": 1, "layout": layout, "root": view["root"],
                "inventory": sorted(view["records"]),
                "files": {filename: digest(raw) for filename, raw in files.items()}}
    (repository / "manifest.json").write_bytes(encode(manifest))
    return files


def read_view(repository, pin):
    manifest = json.loads(git(repository, "show", pin + ":manifest.json"))
    buffers = {}
    process = subprocess.run(["git", "archive", "--format=tar", pin], cwd=repository, env=tool_env(),
                             check=True, capture_output=True)
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(process.stdout), mode="r:") as source:
        for entry in source:
            if entry.isfile() and entry.name.startswith("records/"):
                buffers[entry.name.split("/", 1)[1]] = source.extractfile(entry).read()
    return manifest, buffers


def rebuild(manifest, buffers):
    assembled = {}
    assert manifest["version"] == 1 and set(manifest["files"]) == set(buffers)
    for name, expected in manifest["files"].items():
        raw = buffers[name]
        assert digest(raw) == expected
        for line in raw.splitlines():
            address, text = json.loads(line)
            value = text.encode()
            assert digest(value) == address and address not in assembled
            assembled[address] = value
    graph = closure(manifest["root"], assembled.__getitem__)
    assert sorted(graph) == manifest["inventory"]
    return graph


def commit(repository, label):
    git(repository, "add", "-A")
    git(repository, "-c", "commit.gpgsign=false", "commit", "--quiet", "--allow-empty", "-m", label)
    return git(repository, "rev-parse", "HEAD").decode().strip()


def settings(repo):
    for config, value in (("pack.threads", "1"), ("pack.window", "10"), ("pack.depth", "50"),
                          ("pack.compression", "6"), ("gc.auto", "0")):
        git(repo, "config", config, value)


def pack(repo, meter):
    _, measurement = meter.git(repo, "repack", "-ad")
    paths = sorted((repo / ".git" / "objects" / "pack").glob("*.idx"))
    assert len(paths) == 1
    index = paths[0]
    census = git(repo, "verify-pack", "-v", str(index)).decode().splitlines()
    delta_sizes = []
    depths = []
    entries = 0
    for text in census:
        parts = text.split()
        if parts and len(parts[0]) == 40:
            entries += 1
            if len(parts) == 7:
                delta_sizes.append(int(parts[3]))
                depths.append(int(parts[5]))
    return {"pack_and_index_bytes": index.stat().st_size + index.with_suffix(".pack").stat().st_size,
            "objects": entries, "deltas": len(depths), "max_delta_depth": max(depths, default=0),
            "delta_packed_bytes": sum(delta_sizes)}, measurement


def repo_bytes(repository):
    return sum(path.stat().st_size for path in (repository / "records").iterdir())


def test_layout(work, layout, dataset, meter):
    repo = work / "source"
    alternate = work / "alternate"
    consumer = work / "consumer"
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet", "-b", "research/all", "--object-format=sha1")
    settings(repo)
    common, primary, other = dataset
    all_pins = []
    old = {}
    maximum_files = maximum_bytes = 0

    def extend(target, branch, start, label):
        nonlocal maximum_files, maximum_bytes
        previous = start
        for number, view in enumerate(branch):
            previous = write_rev(target, layout, view, previous)
            all_pins.append((commit(target, f"{label} {number}"), view))
            maximum_files = max(maximum_files, len(previous))
            maximum_bytes = max(maximum_bytes, repo_bytes(target))
        return previous

    common_payload = extend(repo, common, old, "common")
    common_pin = all_pins[-1][0]
    common_pack, common_measure = pack(repo, meter)
    _, cloned = meter.git(work, "clone", "--quiet", "--no-local", str(repo), str(consumer))
    _, _ = meter.git(work, "clone", "--quiet", "--no-local", str(repo), str(alternate))
    settings(alternate)
    primary_payload = extend(repo, primary, common_payload, "primary")
    primary_pin = all_pins[-1][0]
    extend(alternate, other, common_payload, "alternate")
    other_pin = all_pins[-1][0]
    git(repo, "fetch", "--quiet", str(alternate), "refs/heads/research/all:refs/tags/alternate-tip")
    assert git(repo, "merge-base", primary_pin, other_pin).decode().strip() == common_pin
    pre_compaction_payload = repo_bytes(repo)
    pre_compaction_pack, pre_measure = pack(repo, meter)

    compact = primary[-1]
    write_rev(repo, layout, compact, primary_payload, compact=True)
    compact_pin = commit(repo, "compact active graph")
    all_pins.append((compact_pin, compact))
    final_pack, final_measure = pack(repo, meter)
    git(repo, "fsck", "--full")
    _, fetched = meter.git(consumer, "fetch", "--quiet", "--tags", "origin")
    _, checked_out = meter.git(consumer, "checkout", "--quiet", "--detach", compact_pin)
    git(consumer, "fsck", "--full")
    git(consumer, "remote", "remove", "origin")
    repo.rename(work / "origin-unavailable")
    alternate.rename(work / "alternate-unavailable")
    for pin, expected in all_pins:
        manifest, buffers = read_view(consumer, pin)
        assert manifest["root"] == expected["root"] and rebuild(manifest, buffers) == expected["records"]

    _, read_metrics = meter.git(consumer, "archive", "--format=tar", compact_pin)
    manifest, buffers = read_view(consumer, compact_pin)
    start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    assert rebuild(manifest, buffers) == compact["records"]
    reconstruction = {"wall_ns": time.perf_counter_ns() - start,
                      "cpu_ns": time.process_time_ns() - cpu_start}
    tracemalloc.start()
    assert rebuild(manifest, buffers) == compact["records"]
    _, reconstruction["peak_traced_bytes"] = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "layout": layout, "common_pack": common_pack, "pre_compaction_pack": pre_compaction_pack,
        "final_pack": final_pack, "maximum_tracked_record_files": maximum_files,
        "maximum_active_bytes": maximum_bytes, "before_compaction_bytes": pre_compaction_payload,
        "after_compaction_bytes": sum(len(raw) for raw in buffers.values()),
        "restored_commits": len(all_pins), "selected_roots": [item["root"] for _, item in all_pins],
        "pins": {"common": common_pin, "primary": primary_pin, "alternate": other_pin, "compact": compact_pin},
    }, {
        "layout": layout, "clone": cloned, "fetch": fetched, "checkout": checked_out,
        "common_repack": common_measure, "pre_compaction_repack": pre_measure,
        "repack": final_measure, "read_git_archive": read_metrics, "reconstruct": reconstruction,
    }


def experiment(work, trials):
    dataset = fixture()
    meter = Meter(work)
    exact = {}
    samples = []
    for index in range(trials):
        for layout in layouts:
            record, measurement = test_layout(work / f"{index}-{layout}", layout, dataset, meter)
            if index:
                assert record == exact[layout]
            else:
                exact[layout] = record
            samples.append({"trial": index + 1, **measurement})
    assert len({tuple(item["selected_roots"]) for item in exact.values()}) == 1
    sizes = [len(raw) for branch in dataset for view in branch for raw in view["records"].values()]
    return {
        "format": "divergent-git-history-01",
        "git": git(work, "--version").decode().strip(),
        "payload_range_bytes": [min(sizes), max(sizes)],
        "initial_reachable_objects": len(dataset[0][0]["records"]),
        "layouts": exact,
        "declared_history": {"common_extensions": HISTORY_LENGTHS[0], "per_divergent_arm": HISTORY_LENGTHS[1]},
    }, samples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact", type=Path, required=True)
    parser.add_argument("--samples", type=Path)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    assert args.trials >= 1
    with TemporaryDirectory(prefix="llmlang-git-history-") as directory:
        record, samples = experiment(Path(directory), args.trials)
    args.exact.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if args.samples:
        args.samples.write_text(json.dumps(samples, sort_keys=True, indent=2) + "\n", encoding="utf-8")
