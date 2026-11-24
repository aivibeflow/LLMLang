"""Measure Git pack and new blob bytes for stable SPG shards and immutable segments."""
import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
from random import Random
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, canonical_bytes, make_snapshot
from tests.test_rt24_merge_tree_gate import git

benchmark_path = HERE.parents[1] / "benchmarks" / "git_binary_spg" / "run_benchmark.py"
spec = spec_from_file_location("pack_baseline", benchmark_path)
baseline = module_from_spec(spec)
spec.loader.exec_module(baseline)

COUNT = 10_000
BUCKETS = 32
KIND = "rt27-sharding-fixture-v1"
LAYOUTS = ("monolith", "module-shards", "hash-shards", "segments")
PLACEMENTS = ("spread", "concentrated")
COUNTS = (1, 100, 1000)


def item(store, slot, revision):
    key = f"{slot}:{revision}".encode()
    length = 4 + sha256(key).digest()[0] % 12
    value = {"module": slot % BUCKETS, "text": "normalized effect " * length,
             "fingerprint": sha256(key).hexdigest()}
    address = store.put(KIND, value)
    return address, value


def base_values():
    store = ContentStore()
    return {slot: item(store, slot, 0) for slot in range(COUNT)}


def changed(placement, count):
    rng = Random(2717)
    modules = list(range(4 if placement == "concentrated" else BUCKETS))
    rng.shuffle(modules)
    each, extra = divmod(count, len(modules))
    selected = []
    for index, module in enumerate(modules):
        selected.extend(rng.sample(range(module, COUNT, BUCKETS), each + int(index < extra)))
    assert len({slot % BUCKETS for slot in selected}) == min(count, len(modules))
    return sorted(selected)


def root(items):
    return make_snapshot({f"slot-{slot}": value[0] for slot, value in items.items()}).root_hash


def payload_path(layout, slot, address):
    if layout in {"monolith", "segments"}:
        return "objects/00.jsonl"
    shard = slot % BUCKETS if layout == "module-shards" else int(address[:2], 16) % BUCKETS
    return f"objects/{shard:02d}.jsonl"


def row(slot, record):
    address, value = record
    return canonical_bytes([slot, address, value]) + b"\n"


def serialize(repo, layout, active, *, old=None, replacements=None):
    buckets = {}
    tombstones = []
    if layout == "segments" and old is not None:
        assert replacements is not None
        buckets["objects/00.jsonl"] = None
        buckets["objects/01.jsonl"] = [row(slot, active[slot]) for slot in sorted(replacements)]
        tombstones = sorted(old[slot][0] for slot in replacements)
    else:
        for slot, record in sorted(active.items()):
            path = payload_path(layout, slot, record[0])
            buckets.setdefault(path, []).append(row(slot, record))
    (repo / "objects").mkdir(exist_ok=True)
    for existing in (repo / "objects").iterdir():
        if str(existing.relative_to(repo)) not in buckets:
            existing.unlink()
    for name, rows in sorted(buckets.items()):
        if rows is not None:
            (repo / name).write_bytes(b"".join(rows))
    data = {"format": "rt27-sharding-fixture/1", "files": sorted(buckets), "tombstones": tombstones,
            "root": root(active)}
    (repo / "manifest.json").write_bytes(canonical_bytes(data) + b"\n")


def reconstructed(repo, pin):
    store = ContentStore()
    manifest = json.loads(git(repo, "show", f"{pin}:manifest.json"))
    dropped = set(manifest["tombstones"])
    found_drops = set()
    entries = {}
    for path in manifest["files"]:
        for raw in git(repo, "show", f"{pin}:{path}").splitlines():
            slot, address, value = json.loads(raw)
            if store.put(KIND, value) != address:
                raise ValueError("wrong canonical value address")
            if address in dropped:
                found_drops.add(address)
            elif slot not in entries:
                entries[slot] = (address, value)
            else:
                raise ValueError("more than one active selection per slot")
    assert found_drops == dropped
    result = root(entries)
    assert manifest["root"] == result and len(entries) == COUNT
    return result


def commit(repo, label):
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", label)
    return git(repo, "rev-parse", "HEAD").decode().strip()


def trial(layout, placement, count, initial, active, replacements):
    with TemporaryDirectory(prefix="rt27-sharded-history-") as directory:
        directory = Path(directory)
        repo, clone = directory / "repo", directory / "clone"
        repo.mkdir()
        git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
        for key, value in (("pack.threads", "1"), ("pack.window", "10"), ("pack.depth", "50"),
                           ("pack.compression", "6"), ("core.bigFileThreshold", "512m"),
                           ("gc.aggressiveWindow", "10"), ("gc.aggressiveDepth", "50")):
            git(repo, "config", key, value)
        serialize(repo, layout, initial)
        first = commit(repo, "original fixture")
        serialize(repo, layout, active, old=initial, replacements=replacements)
        last = commit(repo, "replace immutable values")
        paths = git(repo, "diff", "--name-only", first, last, "--", "objects/").decode().splitlines()
        changed_paths = [repo / path for path in paths if (repo / path).is_file()]
        active_bytes = sum(path.stat().st_size for path in (repo / "objects").iterdir())
        changed_bytes = sum(path.stat().st_size for path in changed_paths)
        metrics = baseline.pack_metrics(repo, "git")
        git(repo, "fsck", "--full")
        git(directory, "clone", "--quiet", "--no-local", str(repo), str(clone))
        git(clone, "fsck", "--full")
        actual = [reconstructed(clone, pin) for pin in (first, last)]
        assert actual == [root(initial), root(active)]
        manifest = (repo / "manifest.json").stat().st_size
        compaction = None
        if (layout, placement, count) == ("segments", "concentrated", 1000):
            serialize(repo, layout, active)
            compacted = commit(repo, "compact active segments")
            new_size = sum(path.stat().st_size for path in (repo / "objects").iterdir())
            compact_metrics = baseline.pack_metrics(repo, "git")
            git(repo, "fsck", "--full")
            git(clone, "fetch", "--quiet", "origin")
            git(clone, "fsck", "--full")
            assert reconstructed(clone, compacted) == actual[-1]
            assert new_size < active_bytes
            compaction = {"commit": compacted, "active_payload_bytes": new_size,
                          "pack_plus_index_bytes": compact_metrics["pack_and_index_bytes"]}
        return {"layout": layout, "placement": placement, "replacement_count": count,
                "payload_blobs_changed": len(changed_paths), "new_payload_blob_bytes": changed_bytes,
                "worktree_payload_bytes": active_bytes, "manifest_bytes": manifest,
                "pack_plus_index_bytes": metrics["pack_and_index_bytes"],
                "delta_entries": sum(row["deltas"] for row in metrics["verify_pack"]),
                "commits": [first, last], "roots": actual, "compaction": compaction}


def run():
    initial = base_values()
    store = ContentStore()
    cases = []
    for placement, count in product(PLACEMENTS, COUNTS):
        replacements = changed(placement, count)
        active = {**initial, **{slot: item(store, slot, 1) for slot in replacements}}
        result = [trial(layout, placement, count, initial, active, replacements) for layout in LAYOUTS]
        assert len({tuple(item["roots"]) for item in result}) == 1
        cases.extend(result)
    return {"format": "rt27-sharded-history/1", "records": COUNT, "shards": BUCKETS,
            "python": sys.version.split()[0], "git": git(Path.cwd(), "--version").decode().strip(),
            "counts": COUNTS, "seed": 2717, "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
