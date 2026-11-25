"""Check metadata-only backup and self-contained graph restoration."""

from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory

BASELINE = "bf043f1ccba812cd422c2ac9c2b33f592e0d3cf4"


class RestoreError(ValueError):
    pass


def encode(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data):
    return sha256(data).hexdigest()


def database(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS selection (name TEXT PRIMARY KEY, root TEXT NOT NULL)")
    return db


def root(db):
    return db.execute("SELECT root FROM selection WHERE name='current'").fetchone()[0]


def select(db, address):
    db.execute("INSERT INTO selection VALUES ('current', ?) ON CONFLICT(name) DO UPDATE SET root=excluded.root", (address,))


def blob_address(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise RestoreError("invalid address")
    return value


def put(directory, raw):
    address = digest(raw)
    path = directory / address
    if path.exists():
        if path.read_bytes() != raw:
            raise RestoreError("corrupt existing object")
    else:
        path.write_bytes(raw)
    return address


def closure(start, load):
    pending = [start]
    payloads = {}
    while pending:
        address = blob_address(pending.pop())
        if address in payloads:
            continue
        try:
            raw = load(address)
        except (FileNotFoundError, KeyError) as error:
            raise RestoreError("missing object") from error
        if digest(raw) != address:
            raise RestoreError("object digest mismatch")
        record = json.loads(raw)
        if set(record) != {"kind", "value", "references"} or not isinstance(record["references"], list):
            raise RestoreError("unexpected object shape")
        if encode(record) != raw:
            raise RestoreError("noncanonical object")
        payloads[address] = raw
        pending.extend(record["references"])
    return payloads


def restore(bundle, expected, db, directory, *, interrupt=False):
    data = json.loads(bundle)
    if data.get("schema") != "fixture-closed-graph-v1" or data.get("root") != expected:
        raise RestoreError("different selected root or schema")
    objects = {address: payload.encode("utf-8") for address, payload in data["objects"].items()}
    verified = closure(expected, objects.__getitem__)
    if set(verified) != set(objects):
        raise RestoreError("extra entries outside the selected closure")
    for raw in verified.values():
        put(directory, raw)
    db.execute("BEGIN IMMEDIATE")
    try:
        select(db, expected)
        if interrupt:
            raise RestoreError("interrupted before publication")
    except Exception:
        db.rollback()
        raise
    db.commit()
    return verified


def run():
    cases = []
    with TemporaryDirectory(prefix="llmlang-graph-backup-") as temp:
        work = Path(temp)
        origin = work / "origin-blobs"
        origin.mkdir()
        primary = database(work / "origin.db")

        def new(kind, value, references=()):
            return put(origin, encode({"kind": kind, "value": value, "references": references}))

        shared = new("contract", {"result": "ok"})
        leaf_a = new("implementation", {"body": "a"}, (shared,))
        leaf_b = new("implementation", {"body": "b"}, (shared,))
        first = new("snapshot", {"revision": 1}, (leaf_a,))
        second = new("snapshot", {"revision": 2}, (leaf_b,))
        select(primary, first)
        original = closure(first, lambda identity: (origin / identity).read_bytes())
        bundle = encode({"schema": "fixture-closed-graph-v1", "root": first,
                         "objects": {address: payload.decode("utf-8") for address, payload in original.items()}})
        backup = sqlite3.connect(work / "index-backup.db")
        primary.backup(backup)
        select(primary, second)
        for discarded in (first, leaf_a):
            (origin / discarded).unlink()
        assert root(backup) == first and root(primary) == second
        assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)

        def ensure(label, expected, operation):
            try:
                operation()
            except RestoreError as error:
                assert str(error) == expected, (label, str(error), expected)
            else:
                assert expected == "restored", label
            cases.append({"case": label, "outcome": expected})

        ensure("metadata-only archive after collection", "missing object",
               lambda: closure(root(backup), lambda address: (origin / address).read_bytes()))
        fresh = work / "restored-blobs"
        fresh.mkdir()
        reader = database(work / "restored.db")
        select(reader, second)
        for address in closure(second, lambda item: (origin / item).read_bytes()):
            shutil.copyfile(origin / address, fresh / address)

        def mutate(operation):
            data = json.loads(bundle)
            operation(data)
            return encode(data)

        ensure("expected root differs from bundle", "different selected root or schema",
               lambda: restore(bundle, second, reader, fresh))
        ensure("dangling dependency in otherwise intact index", "missing object",
               lambda: restore(mutate(lambda data: data["objects"].pop(shared)), first, reader, fresh))
        ensure("corrupt immutable object bytes", "object digest mismatch",
               lambda: restore(mutate(lambda data: data["objects"].update({leaf_a: "{}"})), first, reader, fresh))
        ensure("unexpected unrelated payload", "extra entries outside the selected closure",
               lambda: restore(mutate(lambda data: data["objects"].update({second: (origin / second).read_text()})),
                               first, reader, fresh))
        assert root(reader) == second
        ensure("failure before root publication", "interrupted before publication",
               lambda: restore(bundle, first, reader, fresh, interrupt=True))
        assert root(reader) == second
        ensure("retry exact graph restore", "restored", lambda: restore(bundle, first, reader, fresh))
        assert root(reader) == first
        assert closure(first, lambda address: (fresh / address).read_bytes()) == original
        assert reader.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        offline = database(work / "standalone.db")
        empty = work / "standalone-blobs"
        empty.mkdir()
        ensure("restore into empty independent store", "restored", lambda: restore(bundle, first, offline, empty))
        assert root(offline) == first and closure(first, lambda address: (empty / address).read_bytes()) == original
        offline.close()
        version = reader.execute("SELECT sqlite_source_id()").fetchone()[0]
        primary.close()
        backup.close()
        reader.close()
    return {
        "schema": "rt12-closed-graph-backup-controls-v1", "baseline": BASELINE,
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "sqlite_source_id": version,
        "runner_sha256": digest(Path(__file__).read_bytes()), "portable_bundle_sha256": digest(bundle),
        "restored_root": first, "restored_objects": sorted(original), "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
