"""Compare cache lookup and payload reads across deterministic Git-backed containers."""
import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
from random import Random
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import zlib

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import ContentStore, canonical_bytes, make_snapshot
from tests.test_rt24_merge_tree_gate import git


COUNT = 256
KIND = "rt27-cache-fixture-v1"
MANIFEST = "manifest.json"
INDEX = "index.json"


class Rejected(ValueError):
    pass


class CountingReader:
    def __init__(self, stream, counters):
        self.stream = stream
        self.counters = counters
        self.phase = "metadata"

    def read(self, size=-1):
        value = self.stream.read(size)
        self.counters[self.phase] += len(value)
        return value

    def __getattr__(self, name):
        return getattr(self.stream, name)


def records():
    rng = Random(2701)
    store = ContentStore()
    snapshot = {}
    payloads = {}
    decoded = {}
    for index in range(COUNT):
        data = {"serial": index, "category": ["interface", "implementation", "contract"][index % 3],
                "code": "ordered-observation " * 8, "variant": rng.randbytes(24).hex()}
        address = store.put(KIND, data)
        snapshot[f"slot-{index:04}"] = address
        payloads[address] = canonical_bytes(data)
        decoded[address] = data
    assert len(payloads) == len(snapshot) == COUNT
    return snapshot, payloads, decoded


def physical(destination, chosen, payloads):
    destination.mkdir()
    manifest = {"format": "rt27-cache-fixture/1", "slots": chosen, "root": make_snapshot(chosen).root_hash}
    (destination / MANIFEST).write_bytes(canonical_bytes(manifest) + b"\n")
    offsets = {}
    with (destination / "container.bin").open("wb") as binary, (destination / "scan.jsonl").open("wb") as scan, \
            ZipFile(destination / "container.zip", "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for address, raw in sorted(payloads.items()):
            encoded = zlib.compress(raw, level=6)
            offsets[address] = [binary.tell(), len(encoded)]
            binary.write(encoded)
            scan.write(raw + b"\n")
            member = ZipInfo(f"{address}.json", date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, ZIP_DEFLATED, compresslevel=6)
    (destination / INDEX).write_bytes(canonical_bytes(offsets) + b"\n")


def blob_id(body):
    return sha1(f"blob {len(body)}\0".encode("ascii") + body).hexdigest()


def metadata(repo, path, exact, counters):
    body = (repo / path).read_bytes()
    counters["metadata"] += len(body)
    if blob_id(body) != exact[path]:
        raise Rejected(f"metadata differs from pinned blob: {path}")
    return json.loads(body)


def checked_decode(store, body, address=None):
    item = json.loads(body)
    found = store.put(KIND, item)
    if address is not None and found != address:
        raise Rejected("record content address mismatch")
    return found, item


def load(repo, exact, layout, seed_cache):
    counted = {"metadata": 0, "payload": 0, "decodes": 0, "cache_hits": 0}
    store = ContentStore()
    manifest = metadata(repo, MANIFEST, exact, counted)
    cached = dict(seed_cache)
    resolved = {}

    def decode(data, address=None):
        counted["decodes"] += 1
        return checked_decode(store, data, address)

    def admit(address, item):
        if store.put(KIND, item) != address:
            raise Rejected("cache value does not match the selected address")
        resolved[address] = item

    addresses = set(manifest["slots"].values())
    for address in sorted(addresses & cached.keys()):
        counted["cache_hits"] += 1
        admit(address, cached[address])
    missing = sorted(addresses - cached.keys())
    if missing and layout == "scan":
        records_by_address = {}
        blob = (repo / "scan.jsonl").read_bytes()
        counted["payload"] += len(blob)
        for body in blob.splitlines():
            address, data = decode(body)
            records_by_address[address] = data
        if records_by_address.keys() != addresses:
            raise Rejected("sequential inventory does not match the manifest")
        resolved.update(records_by_address)
    elif missing and layout == "indexed":
        index = metadata(repo, INDEX, exact, counted)
        if index.keys() != addresses:
            raise Rejected("index membership does not match the manifest")
        with (repo / "container.bin").open("rb") as file:
            for address in missing:
                offset, length = index[address]
                file.seek(offset)
                value = file.read(length)
                counted["payload"] += len(value)
                _, item = decode(zlib.decompress(value), address)
                resolved[address] = item
    elif missing and layout == "zip":
        with (repo / "container.zip").open("rb") as file:
            reader = CountingReader(file, counted)
            with ZipFile(reader) as archive:
                if set(archive.namelist()) != {f"{address}.json" for address in addresses}:
                    raise Rejected("ZIP membership does not match the manifest")
                reader.phase = "payload"
                for address in missing:
                    _, item = decode(archive.read(f"{address}.json"), address)
                    resolved[address] = item
    snapshot = make_snapshot(manifest["slots"])
    if snapshot.root_hash != manifest["root"]:
        raise Rejected("manifest does not reconstruct expected root")
    return snapshot.root_hash, resolved, counted


def check_controls(repo, exact, snapshot, payloads, decoded):
    original = (repo / MANIFEST).read_bytes()
    altered = json.loads(original)
    selected = sorted(altered["slots"])
    first, second = selected[:2]
    altered["slots"][first], altered["slots"][second] = altered["slots"][second], altered["slots"][first]
    altered["root"] = make_snapshot(altered["slots"]).root_hash
    foreign = canonical_bytes(altered) + b"\n"
    (repo / MANIFEST).write_bytes(foreign)
    controls = {}
    try:
        load(repo, exact, "zip", decoded)
    except Rejected as exc:
        assert str(exc) == f"metadata differs from pinned blob: {MANIFEST}"
        controls["changed_manifest_warm"] = str(exc)
    else:
        raise AssertionError("changed manifest accepted")
    admitted, _, _ = load(repo, {**exact, MANIFEST: blob_id(foreign)}, "zip", decoded)
    assert admitted != make_snapshot(snapshot).root_hash
    controls["different_root_when_metadata_is_repinned"] = admitted
    (repo / MANIFEST).write_bytes(original)

    index_path = repo / INDEX
    index_blob = index_path.read_bytes()
    index = json.loads(index_blob)
    address1, address2 = sorted(payloads)[:2]
    index[address1] = index[address2]
    edited = canonical_bytes(index) + b"\n"
    index_path.write_bytes(edited)
    try:
        load(repo, exact, "indexed", {})
    except Rejected as exc:
        assert str(exc) == f"metadata differs from pinned blob: {INDEX}"
        controls["wrong_offset"] = str(exc)
    else:
        raise AssertionError("changed index accepted")
    try:
        load(repo, {**exact, INDEX: blob_id(edited)}, "indexed", {})
    except Rejected as exc:
        assert str(exc) == "record content address mismatch"
        controls["wrong_record_even_with_repin"] = str(exc)
    else:
        raise AssertionError("wrong record accepted")
    index_path.write_bytes(index_blob)
    bad_cache = {**decoded, address1: decoded[address2]}
    try:
        load(repo, exact, "indexed", bad_cache)
    except Rejected as exc:
        assert str(exc) == "cache value does not match the selected address"
        controls["mismatched_cache_value"] = str(exc)
    else:
        raise AssertionError("mismatched cache value accepted")
    return controls


def run():
    chosen, payloads, decoded = records()
    with TemporaryDirectory(prefix="rt27-metadata-first-") as directory:
        directory = Path(directory)
        source, repeat, clone = (directory / part for part in ("source", "repeat", "clone"))
        physical(source, chosen, payloads)
        physical(repeat, dict(reversed(tuple(chosen.items()))), dict(reversed(tuple(payloads.items()))))
        files = {record.name: {"bytes": record.stat().st_size, "sha256": sha256(record.read_bytes()).hexdigest()}
                 for record in source.iterdir()}
        assert all((source / name).read_bytes() == (repeat / name).read_bytes() for name in files)
        git(source, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
        git(source, "add", "--all")
        git(source, "commit", "--quiet", "-m", "cache fixture")
        git(directory, "clone", "--quiet", "--no-local", str(source), str(clone))
        git(clone, "fsck", "--full")
        revision = git(clone, "rev-parse", "HEAD").decode().strip()
        exact = {name: git(clone, "rev-parse", f"{revision}:{name}").decode().strip()
                 for name in (MANIFEST, INDEX)}
        base_root = make_snapshot(chosen).root_hash
        runs = {}
        for layout in ("scan", "indexed", "zip"):
            rates = {}
            for count in (0, COUNT // 2, COUNT):
                keys = sorted(payloads)[:count]
                root, resolved, reads = load(clone, exact, layout, {key: decoded[key] for key in keys})
                assert root == base_root and resolved == decoded
                assert reads["decodes"] == (COUNT if layout == "scan" and count < COUNT else COUNT - count)
                assert reads["cache_hits"] == count
                if count == COUNT:
                    assert reads["payload"] == 0 and reads["metadata"] == files[MANIFEST]["bytes"]
                rates[str(count)] = reads
            runs[layout] = rates
        controls = check_controls(clone, exact, chosen, payloads, decoded)
    return {"format": "rt27-metadata-first/1", "python": sys.version.split()[0],
            "git": git(Path.cwd(), "--version").decode().strip(), "zlib": zlib.ZLIB_RUNTIME_VERSION,
            "records": COUNT, "root": base_root, "commit": revision, "pinned_metadata_blobs": exact,
            "files": files, "runs": runs, "controls": controls}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
