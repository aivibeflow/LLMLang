"""Compare SPG record encodings in one indexed Git container."""

import argparse
from hashlib import sha256, shake_256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import resource
import struct
import subprocess
import sys
import tempfile
from time import perf_counter
import zlib

from record_codecs import PROFILES, deserialize, logical_bytes, serialize

INDEX = struct.Struct("<QQI32s")  # slot, offset, length, logical content digest
SELECTION = struct.Struct("<Q32s")
HIT_RATES = (0, 50, 90, 99, 100)
EDIT_RATES = (0.01, 1, 10)
BASELINE = "3fcbcc66202c807d87b473bfda748ff04dfb163b"
HERE = Path(__file__).resolve().parent
WORDS = ("load", "store", "guard", "branch", "borrow", "check", "return", "commit")
GIT_ENV = {
    **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z", "LC_ALL": "C",
}


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-c", "gc.auto=0", "-c", "core.bigFileThreshold=512m",
         "-c", "pack.window=10", "-c", "pack.depth=50", "-c", "pack.threads=1",
         "-c", "pack.compression=6", "-c", "user.name=SPG Benchmark",
         "-c", "user.email=spg-benchmark@example.invalid", *args],
        cwd=repo, env=GIT_ENV, stderr=subprocess.PIPE,
    )


def digest(data):
    return sha256(data).digest()


def duration(start):
    return round((perf_counter() - start) * 1000, 3)


def make_record(seed, slot, revision):
    entropy = digest(f"{seed}/{slot}/{revision}".encode())
    length = (24, 80, 192, 640)[min((slot % 100) // 25, 3)]
    prefix = " ".join(WORDS[(slot + i) % len(WORDS)] for i in range(8))
    salt = shake_256(entropy).hexdigest(length // 2)
    body = (prefix * (length // len(prefix) + 1))[:length - length // 4] + salt[:length // 4]
    if slot % 23 == 0:
        body += "\nстрока\u001e"
    i64 = {0: -(1 << 63), 1: (1 << 63) - 1, 2: 0}.get(
        slot % 101, int.from_bytes(entropy[:8], "little", signed=True)
    )
    refs = [slot - distance for distance in (1, 7, 31, 97)[:slot % 5] if slot >= distance]
    return {"kind": slot % 5, "name": f"op/{slot}", "i64": str(i64),
            "refs": refs, "body": body}


def canonical(value):
    return digest(logical_bytes(value))


def file_paths(directory):
    return directory / "objects.idx", directory / "objects.dat"


def write_container(profile, directory, rows):
    index, payload = file_paths(directory)
    digests = sha256()
    offset = 0
    with index.open("wb") as offsets, payload.open("wb") as data:
        for slot, value in sorted(rows):
            encoded = serialize(profile, value)
            address = canonical(value)
            offsets.write(INDEX.pack(slot, offset, len(encoded), address))
            data.write(encoded)
            digests.update(SELECTION.pack(slot, address))
            offset += len(encoded)
    return {"rows": len(rows), "bytes": offset,
            "index_sha256": digest(index.read_bytes()).hex(),
            "root": digests.hexdigest()}


def write_manifest(directory, profile, container):
    manifest = {"version": 1, "profile": profile, **container}
    (directory / "manifest.json").write_bytes(logical_bytes(manifest) + b"\n")
    return manifest


def expected_root(records):
    selected = sha256()
    for slot, value in sorted(records.items()):
        if not all(ref in records for ref in value["refs"]):
            raise ValueError(f"dangling reference in source fixture {slot}")
        selected.update(SELECTION.pack(slot, canonical(value)))
    return selected.hexdigest()


def export(directory, profile, records, reverse=False):
    directory.mkdir(exist_ok=True)
    rows = list(records.items())
    if reverse:
        rows.reverse()
    start = perf_counter()
    container = write_container(profile, directory, rows)
    return write_manifest(directory, profile, container), duration(start)


def tree_digest(directory):
    return digest(b"".join(digest(path.read_bytes()) for path in sorted(directory.iterdir()))).hex()


def index_rows(path, manifest):
    raw = path.read_bytes()
    if digest(raw).hex() != manifest["index_sha256"] or len(raw) != manifest["rows"] * INDEX.size:
        raise ValueError("index digest or size mismatch")
    return list(INDEX.iter_unpack(raw))


def read_record(profile, fd, offset, length, address):
    data = os.pread(fd, length, offset)
    if len(data) != length:
        raise ValueError("incomplete record")
    value = deserialize(profile, data)
    if canonical(value) != address:
        raise ValueError("payload digest mismatch")
    return value


def load(directory, expected, manifest_hash, cached):
    start = perf_counter()
    raw = (directory / "manifest.json").read_bytes()
    if digest(raw) != manifest_hash:
        raise ValueError("manifest mismatch")
    manifest = json.loads(raw)
    if manifest["version"] != 1 or manifest["root"] != expected:
        raise ValueError("invalid snapshot manifest")
    index, payload = file_paths(directory)
    rows = index_rows(index, manifest)
    payload_bytes = decodes = 0
    seen = sha256()
    next_offset = 0
    previous = -1
    fd = None
    try:
        for slot, offset, length, address in rows:
            if offset != next_offset or length == 0 or slot <= previous:
                raise ValueError("invalid record layout")
            next_offset += length
            previous = slot
            if address not in cached:
                if fd is None:
                    fd = os.open(payload, os.O_RDONLY)
                    if os.fstat(fd).st_size != manifest["bytes"]:
                        raise ValueError("payload file size mismatch")
                read_record(manifest["profile"], fd, offset, length, address)
                payload_bytes += length
                decodes += 1
            seen.update(SELECTION.pack(slot, address))
    finally:
        if fd is not None:
            os.close(fd)
    if next_offset != manifest["bytes"] or seen.hexdigest() != expected:
        raise ValueError("selection mismatch")
    return {
        "ms": duration(start), "payload_bytes": payload_bytes, "decodes": decodes,
        "metadata_bytes": len(raw) + len(rows) * INDEX.size,
        "process_high_water_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def random_access(directory, manifest, seed):
    randomizer = random.Random(seed)
    results = {}
    index, payload = file_paths(directory)
    rows = index_rows(index, manifest)
    with payload.open("rb") as data:
        for label, start, stop in (("early", 0.0, 0.1), ("middle", 0.45, 0.55),
                                   ("late", 0.9, 1.0)):
            times = []
            low, high = int(len(rows) * start), int(len(rows) * stop)
            for position in randomizer.sample(range(low, high), min(128, high - low)):
                _, offset, length, address = rows[position]
                begin = perf_counter()
                read_record(manifest["profile"], data.fileno(), offset, length, address)
                times.append(round((perf_counter() - begin) * 1e6, 3))
            results[label] = times
    return results


def must_reject(operation):
    try:
        operation()
    except Exception as error:
        return type(error).__name__
    raise AssertionError("corrupted snapshot accepted")


def negative_controls(snapshot, expected, manifest_hash):
    controls = {}
    for label, path, position in (
        ("manifest", snapshot / "manifest.json", 0),
        ("index", snapshot / "objects.idx", 8),
        ("payload", snapshot / "objects.dat", 0),
    ):
        raw = path.read_bytes()
        path.write_bytes(raw[:position] + bytes([raw[position] ^ 255]) + raw[position + 1:])
        try:
            controls[label] = must_reject(
                lambda: load(snapshot, expected, manifest_hash, frozenset())
            )
        finally:
            path.write_bytes(raw)
    return controls


def pack(repo):
    start = perf_counter()
    git(repo, "repack", "-a", "-d", "-f")
    files = list((repo / ".git/objects/pack").glob("*"))
    return sum(path.stat().st_size for path in files if path.suffix in {".pack", ".idx"}), duration(start)


def commit(repo, message):
    git(repo, "add", "snapshot")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD").decode().strip()


def profile_run(parent, profile, records, args, mutation_slots, root, cache_sets):
    repo = parent / profile
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main", "--object-format=sha1")
    snapshot = repo / "snapshot"
    base, encode_ms = export(snapshot, profile, records)
    repeated = parent / f"{profile}-reordered"
    reordered, encode_reordered_ms = export(repeated, profile, records, reverse=True)
    if base != reordered or tree_digest(snapshot) != tree_digest(repeated) or base["root"] != root:
        raise AssertionError("exports are not deterministic or changed the graph")
    commit_id = commit(repo, "baseline")
    manifest_hash = digest(git(repo, "show", f"{commit_id}:snapshot/manifest.json"))
    base_pack, base_pack_ms = pack(repo)
    baseline_bytes = sum(path.stat().st_size for path in snapshot.iterdir())
    loads = []
    for iteration in range(args.repeats):
        for rate in HIT_RATES if iteration % 2 == 0 else reversed(HIT_RATES):
            cached = cache_sets[rate]
            result = load(snapshot, root, manifest_hash, cached)
            if result["decodes"] != len(records) - len(cached):
                raise AssertionError("cache miss count mismatch")
            loads.append(result | {"iteration": iteration, "cache_percent": rate})
    random_us = random_access(snapshot, base, args.seed)
    reject = negative_controls(snapshot, root, manifest_hash)
    current = records.copy()
    history = [{"edit": "baseline", "commit": commit_id, "pack_bytes": base_pack,
                "pack_ms": base_pack_ms, "root": root}]
    for revision, (edit, changed) in enumerate(mutation_slots, 1):
        if edit == "tail-replacement":
            retired = set(changed)
            for slot in changed:
                del current[slot]
                new_slot = slot + len(changed)
                value = make_record(args.seed, new_slot, revision)
                value["refs"] = [ref for ref in value["refs"] if ref not in retired]
                current[new_slot] = value
        else:
            for slot in changed:
                current[slot] = make_record(args.seed, slot, revision)
        manifest, edit_export_ms = export(snapshot, profile, current)
        expected = expected_root(current)
        if expected != manifest["root"]:
            raise AssertionError("written revision differs from reference graph")
        commit_id = commit(repo, edit)
        names = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r",
                    commit_id).decode().splitlines()
        size, pack_ms = pack(repo)
        history.append({"edit": edit, "commit": commit_id, "root": expected,
                        "slots": len(changed), "changed_files": len(names),
                        "replacement_blob_bytes": sum((repo / name).stat().st_size for name in names),
                        "pack_bytes": size, "pack_ms": pack_ms, "export_ms": edit_export_ms})
    clone = parent / f"{profile}-clone"
    start = perf_counter()
    git(parent, "clone", "--quiet", "--no-local", str(repo), str(clone))
    clone_ms = duration(start)
    git(clone, "remote", "remove", "origin")
    for revision in history:
        git(clone, "checkout", "--quiet", "--detach", revision["commit"])
        pinned = digest(git(clone, "show", f"{revision['commit']}:snapshot/manifest.json"))
        restored = load(clone / "snapshot", revision["root"], pinned, frozenset())
        if restored["decodes"] != len(records):
            raise AssertionError("incomplete cold checkout")
        revision["cold_decode_ms"] = restored["ms"]
    return {
        "profile": profile, "baseline_bytes": baseline_bytes,
        "baseline_payload_bytes": base["bytes"],
        "encode_ms": encode_ms, "encode_reordered_ms": encode_reordered_ms,
        "tree_sha256": tree_digest(snapshot), "baseline_tree_sha256": tree_digest(repeated),
        "clone_checkout_ms": clone_ms, "cache_loads": loads,
        "random_access_us": random_us, "corruption_refusals": reject, "history": history,
    }


def run(args, temporary):
    records = {slot: make_record(args.seed, slot, 0) for slot in range(args.objects)}
    randomizer = random.Random(args.seed)
    shuffled = list(records)
    randomizer.shuffle(shuffled)
    contents = [canonical(records[slot]) for slot in shuffled]
    if len(set(contents)) != len(records):
        raise AssertionError("fixture requires unique content addresses")
    cache_sets = {rate: frozenset(contents[:len(records) * rate // 100]) for rate in HIT_RATES}
    edits = [(f"edit-{rate:g}%", sorted(randomizer.sample(
        range(args.objects), max(1, round(args.objects * rate / 100)))))
             for rate in EDIT_RATES]
    tail = max(1, args.objects // 100)
    edits.append(("tail-replacement", list(range(args.objects - tail, args.objects))))
    root = expected_root(records)
    profiles = []
    for profile in args.profiles:
        print(f"{args.objects} objects: {profile}", file=sys.stderr, flush=True)
        profiles.append(profile_run(temporary, profile, records, args, edits, root, cache_sets))
    if any([row["root"] for row in entry["history"]] !=
           [row["root"] for row in profiles[0]["history"]] for entry in profiles):
        raise AssertionError("profiles measured different histories")
    return {
        "repo_context_revision": BASELINE,
        "source_sha256": {path.name: digest(path.read_bytes()).hex()
                          for path in (HERE / "run.py", HERE / "record_codecs.py",
                                       HERE / "schema.proto", HERE / "schema.fbs",
                                       HERE / "requirements.txt")},
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "visible_cpus": len(os.sched_getaffinity(0)),
                        "cpu_quota": Path("/sys/fs/cgroup/cpu.max").read_text().strip()
                        if Path("/sys/fs/cgroup/cpu.max").exists() else None,
                        "git": git(temporary, "--version").decode().strip(),
                        "zlib": zlib.ZLIB_RUNTIME_VERSION,
                        "packages": {pkg: importlib.metadata.version(pkg) for pkg in
                                     ("cbor2", "protobuf", "flatbuffers")}},
        "objects": args.objects, "history_revisions": len(edits) + 1,
        "baseline_reference_edges": sum(len(item["refs"]) for item in records.values()),
        "baseline_logical_bytes": sum(len(logical_bytes(item)) for item in records.values()),
        "containers": 1, "index_bytes_per_record": INDEX.size,
        "seed": args.seed, "repeats": args.repeats, "workers": 1,
        "edits": [{"name": name, "slot_count": len(slots),
                   "slots_sha256": digest(logical_bytes(slots)).hex()} for name, slots in edits],
        "profiles": profiles,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=27001)
    parser.add_argument("--profiles", choices=PROFILES, nargs="+", default=PROFILES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (160 <= args.objects < 1 << 31) or args.repeats < 1:
        parser.error("require at least 160 records and one repetition")
    if len(set(args.profiles)) != len(args.profiles):
        parser.error("profile names must be unique")
    with tempfile.TemporaryDirectory(prefix="spg-dump-benchmark-") as temp:
        evidence = run(args, Path(temp))
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
