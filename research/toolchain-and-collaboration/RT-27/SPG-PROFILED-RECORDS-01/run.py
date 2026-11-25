#!/usr/bin/env python3
"""Restore the existing typed SPG prototype from cache-first Git record containers."""

from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
sys.path.insert(0, str(RESEARCH / "PROTOTYPES/DEPENDENCY-GRAPH-01"))
from src.persistence import dumps_graph, loads_graph
from src.semantic_graph import canonical_bytes, Dependency, RelationStore, SemanticValue, make_snapshot
from src.spg_admission import validate
from src.spg_representation import Graph, compile_program, observe
from tests.test_spg_representation import dispatch_program

git = runpy.run_path(str(HERE.parent / "GIT-CLOSED-REPRESENTATION-01/run.py"))["git"]
PROFILE = "prototype-spg-fixed-buckets/1"
BUCKETS = 4


class Refusal(ValueError):
    pass


def digest(raw):
    return sha256(raw).hexdigest()


def row_bytes(value):
    return (
        b'{"dependencies":' + canonical_bytes([dep.record() for dep in value.dependencies])
        + b',"kind":' + canonical_bytes(value.kind)
        + b',"payload":' + value.payload_json.encode("utf-8")
        + b',"value_hash":' + canonical_bytes(value.value_hash) + b"}"
    )


def metadata_document(graph, relations):
    return json.loads(dumps_graph(graph.store, relations, (graph.snapshot,)))["payload"]


def reverse_projection(store):
    return sorted([[dep.target_hash, source, occurrence, dep.relation, dep.role]
                   for source in store.hashes()
                   for occurrence, dep in enumerate(store.get(source).dependencies)])


def serialize(graph, relations, workers):
    expected = metadata_document(graph, relations)
    values = [graph.store.get(address) for address in reversed(sorted(graph.store.hashes()))]

    def prepare(value):
        return value.value_hash, row_bytes(value)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        encoded = dict(task.result() for task in as_completed([pool.submit(prepare, value) for value in values]))
    cursors = [bytearray() for _ in range(BUCKETS)]
    locations = {}
    for address, record in sorted(encoded.items()):
        bucket = int(address[0], 16) % BUCKETS
        current = cursors[bucket]
        locations[address] = [bucket, len(current), len(record), digest(record)]
        current.extend(record)
    files = {f"records/{bucket}.bin": bytes(raw) for bucket, raw in enumerate(cursors) if raw}
    manifest = {
        "profile": PROFILE, "schema_version": expected["schema_version"],
        "format": expected["format"], "snapshots": expected["snapshots"],
        "relations": expected["relations"],
    }
    return files | {
        "manifest.json": canonical_bytes(manifest),
        "locations.json": canonical_bytes(locations),
        "reverse.json": canonical_bytes(reverse_projection(graph.store)),
    }


def verify_metadata(repo, pin, name):
    raw = (repo / name).read_bytes()
    if raw != git(repo, "show", f"{pin}:{name}"):
        raise Refusal(f"metadata differs from pinned Git blob: {name}")
    decoded = json.loads(raw)
    if canonical_bytes(decoded) != raw:
        raise Refusal("metadata bytes are noncanonical")
    return decoded


def load(repo, pin, cached):
    manifest = verify_metadata(repo, pin, "manifest.json")
    if manifest["profile"] != PROFILE:
        raise Refusal("unsupported serialization profile")
    locations = verify_metadata(repo, pin, "locations.json")
    reverse = verify_metadata(repo, pin, "reverse.json")
    tally = {"hits": 0, "reads": 0, "record_decodes": 0, "payload_bytes": 0}
    values = {}
    for address, (bucket, position, length, expected) in sorted(locations.items()):
        if address in cached:
            value = cached[address]
            if value.value_hash != address or digest(row_bytes(value)) != expected:
                raise Refusal("cached record differs from exact indexed identity")
            tally["hits"] += 1
        else:
            with (repo / "records" / f"{bucket}.bin").open("rb") as stream:
                stream.seek(position)
                raw = stream.read(length)
            tally["reads"] += 1
            tally["payload_bytes"] += len(raw)
            if len(raw) != length or digest(raw) != expected:
                raise Refusal("physical record digest mismatch")
            decoded = json.loads(raw)
            tally["record_decodes"] += 1
            value = SemanticValue(
                decoded["value_hash"], decoded["kind"], canonical_bytes(decoded["payload"]).decode(),
                tuple(Dependency(**entry) for entry in decoded["dependencies"]),
            )
            if value.value_hash != address or row_bytes(value) != raw:
                raise Refusal("noncanonical record or wrong identity")
        values[address] = value

    # Reconstruct through the existing exact persistence validator after
    # measuring the acquisition path. The decoder may reconstruct its own values.
    payload = (
        b'{"format":' + canonical_bytes(manifest["format"])
        + b',"relations":' + canonical_bytes(manifest["relations"])
        + b',"schema_version":' + canonical_bytes(manifest["schema_version"])
        + b',"snapshots":' + canonical_bytes(manifest["snapshots"])
        + b',"values":[' + b",".join(row_bytes(value) for value in values.values()) + b"]}"
    )
    envelope = b'{"checksum":' + canonical_bytes(digest(payload)) + b',"payload":' + payload + b"}\n"
    return envelope, reverse, values, tally


def checked_graph(recovered):
    archived, reverse, values, counts = recovered
    result, relations, snapshots = loads_graph(archived)
    snapshot, = snapshots
    validate(Graph(result, snapshot))
    assert values.keys() == result.hashes()
    assert reverse_projection(result) == reverse
    return result, relations, snapshot, counts


def fixtures():
    initial = dispatch_program()
    base = compile_program(initial)
    altered = compile_program(replace(initial, bindings={"provider": "alternate"}))
    second = Graph(altered.store, make_snapshot(altered.snapshot.mapping, (base.snapshot.root_hash,)))
    for graph in (base, second):
        validate(graph)
    result = []
    for graph in (base, second):
        relations = RelationStore()
        relations.add("declared-unit", "fixture-provider", graph.snapshot.root_hash, "research-provenance")
        body = serialize(graph, relations, 1)
        assert serialize(graph, relations, 2) == serialize(graph, relations, 4) == body
        result.append((graph, relations, body))
    return result


def experiment(directory):
    revisions = fixtures()
    source = directory / "source"
    clone = directory / "offline"
    source.mkdir()
    git(source, "init", "-q", "-b", "research/all", "--object-format=sha256")
    pins = []
    previous = set()
    for count, (graph, relations, files) in enumerate(revisions, 1):
        for stale in previous - set(files):
            (source / stale).unlink()
        for name, raw in files.items():
            path = source / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
        git(source, "add", "-A")
        git(source, "-c", "commit.gpgsign=false", "commit", "-m", f"SPG candidate {count}")
        pins.append(git(source, "rev-parse", "HEAD").decode().strip())
        previous = set(files)
    git(directory, "clone", "--quiet", "--no-local", str(source), str(clone))
    git(clone, "remote", "remove", "origin")
    git(clone, "fsck", "--full")
    source.rename(directory / "source-offline")
    cases = []
    cache = {}

    for pin, (graph, relation, files) in zip(pins, revisions, strict=True):
        git(clone, "checkout", "--quiet", "--detach", pin)
        assert len(files) < len(graph.store)
        expected = dumps_graph(graph.store, relation, (graph.snapshot,))
        tracked = len(git(clone, "ls-tree", "-r", "-z", pin).split(b"\0")) - 1
        assert tracked == len(files)
        cold = load(clone, pin, {})
        reused = load(clone, pin, cache)
        assert cold[0] == reused[0] == expected
        rebuilt, rebuilt_relation, actual, counts = checked_graph(cold)
        original = [observe(graph, "late", (n,)) for n in (-3, 0, 7)]
        observed = [observe(Graph(rebuilt, actual), "late", (n,)) for n in (-3, 0, 7)]
        assert observed == original and actual == graph.snapshot
        assert dumps_graph(rebuilt, rebuilt_relation, (actual,)) == expected
        assert counts["record_decodes"] == counts["reads"] == len(rebuilt)
        assert reused[-1]["hits"] + reused[-1]["reads"] == len(rebuilt)
        cache = cold[2]
        payload_paths = sorted((clone / "records").iterdir())
        saved = {path: path.read_bytes() for path in payload_paths}
        for path in payload_paths:
            path.unlink()
        hot = load(clone, pin, cache)
        assert hot[0] == expected and hot[-1] == {
            "reads": 0, "payload_bytes": 0, "record_decodes": 0, "hits": len(rebuilt),
        }
        for path, raw in saved.items():
            path.write_bytes(raw)
        cases.append({
            "commit": pin, "semantic_root": actual.root_hash, "tracked_files": tracked,
            "content_values": len(rebuilt), "cold": counts, "warm_from_prior": reused[-1],
            "full_cache": hot[-1], "observations": observed,
            "index_files": {name: digest(raw) for name, raw in files.items()},
        })

    last = pins[-1]
    refusals = []

    def refuse(label, reason, operation):
        try:
            operation()
        except Refusal as error:
            assert str(error) == reason
        else:
            raise AssertionError(label)
        refusals.append({"case": label, "decision": reason})

    index = clone / "locations.json"
    exact_index = index.read_bytes()
    index.write_bytes(revisions[0][2]["locations.json"])
    assert index.read_bytes() != exact_index
    refuse("stale locations with full cache", "metadata differs from pinned Git blob: locations.json",
           lambda: load(clone, last, cache))
    index.write_bytes(exact_index)
    target, other, *_ = sorted(cache)
    refuse("wrong cached value under exact address", "cached record differs from exact indexed identity",
           lambda: load(clone, last, cache | {target: cache[other]}))
    bucket, position, _, _ = json.loads(exact_index)[target]
    path = clone / "records" / f"{bucket}.bin"
    with path.open("r+b") as file:
        file.seek(position)
        byte = file.read(1)
        file.seek(position)
        file.write(bytes([byte[0] ^ 1]))
    refuse("corrupt record on cold read", "physical record digest mismatch", lambda: load(clone, last, {}))
    assert load(clone, last, cache)[-1]["payload_bytes"] == 0
    return {
        "format": PROFILE, "git": git(directory, "--version").decode().strip(),
        "workers": [1, 2, 4], "fixed_buckets": BUCKETS, "revisions": cases, "refusals": refusals,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-spg-git-records-") as temp:
        result = experiment(Path(temp))
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
