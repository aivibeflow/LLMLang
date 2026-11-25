"""Compare fixed and content-defined record boundaries in actual Git packs."""
import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
spec = spec_from_file_location("sharded", HERE.parent / "SHARDED-HISTORY-01" / "run.py")
sharded = module_from_spec(spec)
spec.loader.exec_module(sharded)
from src.semantic_graph import ContentStore, canonical_bytes
from tests.test_rt24_merge_tree_gate import git

RECORDS = 4_096
TARGET = 64
MINIMUM = 24
MAXIMUM = 128
ANCHOR_THRESHOLD = 65_536 // 48
LAYOUTS = ("fixed", "content-defined")
EDITS = ("early-insert", "middle-delete", "same-rank-replace", "aligned-insert", "anchor-free-insert")
KIND = sharded.KIND


def is_anchor(address):
    return int(address[:4], 16) < ANCHOR_THRESHOLD


def without_anchor(store, slot):
    for revision in range(64):
        record = sharded.item(store, slot, revision)
        if not is_anchor(record[0]):
            return record
    raise AssertionError("fixture could not find a non-anchor")


def content_chunks(values, layout):
    chunk = []
    for slot, record in sorted(values.items()):
        chunk.append(sharded.row(slot, record))
        count = len(chunk)
        if layout == "fixed":
            boundary = count == TARGET
        else:
            boundary = count == MAXIMUM or (count >= MINIMUM and is_anchor(record[0]))
        if boundary:
            yield b"".join(chunk), count
            chunk = []
    if chunk:
        yield b"".join(chunk), len(chunk)


def serialize(repo, values, layout):
    directory = repo / "chunks"
    directory.mkdir(exist_ok=True)
    chunks = {}
    for data, records in content_chunks(values, layout):
        key = sha256(data).hexdigest()
        assert key not in chunks
        path = directory / key
        if path.exists():
            assert path.read_bytes() == data
        else:
            path.write_bytes(data)
        chunks[key] = {"records": records, "bytes": len(data)}
    for path in directory.iterdir():
        if path.name not in chunks:
            path.unlink()
    manifest = {"format": "rt27-chunk-boundaries/1", "count": len(values),
                "root": sharded.root(values), "ordered_chunks": list(chunks)}
    body = canonical_bytes(manifest) + b"\n"
    (repo / "manifest.json").write_bytes(body)
    return chunks, len(body)


def restore(manifest, read_chunk):
    values = {}
    previous_slot = -1
    store = ContentStore()
    for key in manifest["ordered_chunks"]:
        data = read_chunk(key)
        if sha256(data).hexdigest() != key:
            raise ValueError("wrong chunk digest")
        for raw in data.splitlines():
            slot, address, payload = json.loads(raw)
            if slot <= previous_slot:
                raise ValueError("records out of strict logical order")
            if store.put(KIND, payload) != address:
                raise ValueError("wrong semantic address")
            values[slot] = address, payload
            previous_slot = slot
    root = sharded.root(values)
    if len(values) != manifest["count"] or root != manifest["root"]:
        raise ValueError("wrong semantic count or root")
    return root


def from_git(repo, pin, *, negative=False):
    manifest = json.loads(git(repo, "show", f"{pin}:manifest.json"))
    buffers = {key: git(repo, "show", f"{pin}:chunks/{key}") for key in manifest["ordered_chunks"]}
    if negative:
        scrambled = {**manifest, "ordered_chunks": list(reversed(manifest["ordered_chunks"]))}
        damaged = buffers.copy()
        first = manifest["ordered_chunks"][0]
        damaged[first] += b"\n"
        for candidate, reader, error in (
            (scrambled, buffers, "records out of strict logical order"),
            (manifest, damaged, "wrong chunk digest"),
        ):
            try:
                restore(candidate, reader.__getitem__)
            except ValueError as exc:
                assert str(exc) == error
            else:
                raise AssertionError("accepted invalid chunk layout")
    return restore(manifest, buffers.__getitem__)


def edited(base, case):
    store = ContentStore()
    values = base.copy()
    if case == "early-insert":
        values[1] = sharded.item(store, 1, 0)
    elif case == "anchor-free-insert":
        values[1] = without_anchor(store, 1)
    elif case == "middle-delete":
        del values[100 * (RECORDS // 2)]
    elif case == "same-rank-replace":
        slot = 100 * (RECORDS // 4)
        values[slot] = sharded.item(store, slot, 1)
    elif case == "aligned-insert":
        first = 100 * (TARGET - 1) + 1
        values.update({slot: sharded.item(store, slot, 0) for slot in range(first, first + TARGET)})
    else:
        raise ValueError(case)
    return values


def trial(directory, layout, case, base, values):
    repo, clone = directory / "repo", directory / "clone"
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
    for key, value in (("pack.threads", "1"), ("pack.window", "10"), ("pack.depth", "50"),
                       ("pack.compression", "6"), ("core.bigFileThreshold", "512m"),
                       ("gc.aggressiveWindow", "10"), ("gc.aggressiveDepth", "50")):
        git(repo, "config", key, value)
    original, original_manifest_bytes = serialize(repo, base, layout)
    first = sharded.commit(repo, "stable logical order")
    current, manifest_bytes = serialize(repo, values, layout)
    last = sharded.commit(repo, "change active immutable values")
    added = set(current) - set(original)
    removed = set(original) - set(current)
    reused = set(original) & set(current)
    lengths = [row["records"] for row in current.values()]
    assert max(lengths) <= (TARGET if layout == "fixed" else MAXIMUM)
    if layout == "content-defined":
        assert min(lengths[:-1]) >= MINIMUM
    packed = sharded.baseline.pack_metrics(repo, "git")
    git(repo, "fsck", "--full")
    git(directory, "clone", "--quiet", "--no-local", str(repo), str(clone))
    git(clone, "fsck", "--full")
    roots = [from_git(clone, first), from_git(clone, last, negative=case == "early-insert")]
    assert roots == [sharded.root(base), sharded.root(values)]
    return {
        "before_chunks": len(original), "after_chunks": len(current),
        "reused_chunks": len(reused), "added_chunks": len(added), "removed_chunks": len(removed),
        "new_chunk_bytes": sum(current[key]["bytes"] for key in added),
        "active_chunk_bytes": sum(row["bytes"] for row in current.values()),
        "active_chunk_record_counts": lengths,
        "manifest_bytes": [original_manifest_bytes, manifest_bytes],
        "pack_bytes": packed["pack_bytes"], "index_bytes": packed["index_bytes"],
        "pack_plus_index_bytes": packed["pack_and_index_bytes"],
        "delta_entries": sum(pack["deltas"] for pack in packed["verify_pack"]),
        "delta_representation_bytes": sum(pack["delta_representation_bytes"] for pack in packed["verify_pack"]),
        "max_delta_depth": max(pack["max_delta_depth"] for pack in packed["verify_pack"]),
        "commits": [first, last], "roots": roots,
        "reconstruction_controls_rejected": 2 if case == "early-insert" else 0,
    }


def run(directory):
    version = git(directory, "--version").decode().strip()
    assert version == "git version 2.52.0"
    store = ContentStore()
    slots = range(0, 100 * RECORDS, 100)
    base = {slot: sharded.item(store, slot, 0) for slot in slots}
    cases = {}
    for case in EDITS:
        initial = {slot: without_anchor(store, slot) for slot in slots} if case == "anchor-free-insert" else base
        values = edited(initial, case)
        cases[case] = {layout: trial(directory / f"{case}-{layout}", layout, case, initial, values)
                       for layout in LAYOUTS}
        assert cases[case]["fixed"]["roots"] == cases[case]["content-defined"]["roots"]
    assert cases["aligned-insert"]["fixed"]["added_chunks"] == 1
    assert not cases["anchor-free-insert"]["content-defined"]["reused_chunks"]
    assert cases["early-insert"]["content-defined"]["reused_chunks"] > cases["early-insert"]["fixed"]["reused_chunks"]
    return {
        "format": "rt27-chunk-boundaries/1", "records": RECORDS, "python": sys.version.split()[0],
        "git": version, "target_records": TARGET, "minimum_anchor_records": MINIMUM,
        "maximum_anchor_records": MAXIMUM, "anchor_threshold": ANCHOR_THRESHOLD, "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-chunk-boundaries-") as scratch:
        evidence = run(Path(scratch))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
