#!/usr/bin/env python3
"""Replay four cache storage roles with persistent SQLite index and payload state."""

from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory


SCHEMA = """
CREATE TABLE attestations (identity TEXT PRIMARY KEY, body BLOB NOT NULL);
CREATE TABLE payloads (identity TEXT PRIMARY KEY, bytes BLOB NOT NULL);
"""
GOOD = b"fixture native-result bytes\n"
OTHER = b"fixture alternate result bytes\n"


def digest(body):
    return sha256(body).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def attestation(issuer, output, generation=4):
    return encode({
        "action": digest(b"exact fixture request and closure"),
        "issuer": issuer, "generation": generation, "output": digest(output),
    })


def connect(path):
    return sqlite3.connect(path)


def initialize(path):
    with closing(connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.executescript(SCHEMA)


def put(connection, rows, data):
    connection.executemany(
        "INSERT OR REPLACE INTO attestations VALUES (?, ?)",
        ((digest(row), row) for row in rows),
    )
    connection.executemany(
        "INSERT OR REPLACE INTO payloads VALUES (?, ?)",
        ((digest(payload), payload) for payload in data),
    )


def publish(path, rows=(), data=()):
    with closing(connect(path)) as connection, connection:
        put(connection, rows, data)


def evict(path, address):
    with closing(connect(path)) as connection, connection:
        connection.execute("DELETE FROM payloads WHERE identity = ?", (address,))


def row_bytes(connection, table, address):
    assert table in ("attestations", "payloads")
    row = connection.execute(
        f"SELECT * FROM {table} WHERE identity = ?", (address,)
    ).fetchone()
    return None if row is None else row[1]


def find(paths, table, address):
    invalid = False
    for name, path in paths.items():
        with closing(connect(path)) as connection:
            body = row_bytes(connection, table, address)
        if body is not None:
            if digest(body) == address:
                return body, name
            invalid = True
    return None, "integrity-error" if invalid else "missing"


def lookup(layers, view, issuers, *, promote=None):
    if view is None:
        return {"decision": "view-unavailable"}
    indexed = {name: path for name, path in layers.items() if name != "global"}
    records = []
    sources = []
    for identity in sorted(view):
        row, location = find(indexed, "attestations", identity)
        if row is None:
            return {"decision": "record-" + location}
        records.append(row)
        sources.append(location)
    applicable = [json.loads(row) for row in records]
    candidates = {
        record["output"] for record in applicable
        if record["issuer"] in issuers
        and record["generation"] == 4
        and record["action"] == digest(b"exact fixture request and closure")
    }
    if not candidates:
        return {"decision": "no-authorized-result", "record_sources": sources}
    if len(candidates) != 1:
        return {"decision": "authorized-conflict", "record_sources": sources}
    address, = candidates
    body, location = find(layers, "payloads", address)
    if body is None:
        return {"decision": "payload-" + location, "record_sources": sources}
    if promote is not None:
        publish(promote, records, (body,))
    return {"decision": "exact-hit", "record_sources": sources,
            "payload_source": location, "output": address}


def experiment(directory):
    paths = {name: directory / f"{name}.sqlite" for name in (
        "local", "workspace", "remote", "global"
    )}
    for path in paths.values():
        initialize(path)
    offline = {name: paths[name] for name in ("local", "workspace")}
    apple = attestation("team-A", GOOD)
    orange = attestation("team-B", GOOD)
    disagreement = attestation("team-B", OTHER)
    issuers = {"team-A", "team-B"}
    view = {digest(apple), digest(orange)}
    address = digest(GOOD)

    # The global tier keeps content by address and intentionally cannot issue index records.
    publish(paths["global"], (apple,), (GOOD,))
    publish(paths["remote"], (apple, orange))
    rows = []

    def check(name, layers, records, expected, *, allowed=issuers, promote=None):
        result = lookup(layers, records, allowed, promote=promote)
        assert result == expected, (name, result)
        rows.append({"case": name, **result})

    def hit(sources, payload):
        return {"decision": "exact-hit", "record_sources": sources,
                "payload_source": payload, "output": address}

    check("unknown-view", paths, None, {"decision": "view-unavailable"})
    check("online-promote-workspace", paths, view, hit(["remote", "remote"], "global"),
          promote=paths["workspace"])
    check("offline-reopen-and-promote-local", offline, view, hit(["workspace", "workspace"], "workspace"),
          promote=paths["local"])
    check("offline-local-first", offline, view, hit(["local", "local"], "local"))
    restarted = subprocess.run(
        [sys.executable, __file__, "--offline", str(directory)],
        check=True, capture_output=True,
    )
    assert json.loads(restarted.stdout) == hit(["local", "local"], "local")
    rows.append({"case": "fresh-process-offline", **json.loads(restarted.stdout)})
    check("promoted-does-not-amplify-authority", offline, view,
          {"decision": "no-authorized-result", "record_sources": ["local", "local"]},
          allowed={"workspace"})

    with closing(connect(paths["local"])) as connection, connection:
        connection.execute("UPDATE payloads SET bytes = ? WHERE identity = ?", (OTHER, address))
    check("corrupt-near-copy-falls-through", offline, view,
          hit(["local", "local"], "workspace"), promote=paths["local"])
    check("verified-promotion-repairs-copy", offline, view, hit(["local", "local"], "local"))

    with closing(connect(paths["workspace"])) as reader:
        reader.execute("BEGIN")
        assert row_bytes(reader, "payloads", address) == GOOD
        evict(paths["workspace"], address)
        assert row_bytes(reader, "payloads", address) == GOOD
        with closing(connect(paths["workspace"])) as fresh:
            assert row_bytes(fresh, "payloads", address) is None
            assert row_bytes(fresh, "attestations", digest(apple)) == apple
        reader.rollback()

    evict(paths["local"], address)
    check("evicted-offline", offline, view,
          {"decision": "payload-missing", "record_sources": ["local", "local"]})
    check("global-byte-rematerialization", paths, view, hit(["local", "local"], "global"),
          promote=paths["workspace"])
    check("global-bytes-do-not-supply-action-authority", {"global": paths["global"]},
          {digest(apple)}, {"decision": "record-missing"})

    publish(paths["remote"], (disagreement,))
    conflict_view = {digest(apple), digest(disagreement)}
    conflict_sources = [
        "local" if identity == digest(apple) else "remote" for identity in sorted(conflict_view)
    ]
    check("missing-disputed-output-is-still-conflict", paths, conflict_view,
          {"decision": "authorized-conflict", "record_sources": conflict_sources})
    check("earlier-tier-cannot-hide-remote-view-gap", offline, conflict_view,
          {"decision": "record-missing"})

    interrupted = attestation("interrupted", OTHER)
    aborted = subprocess.run(
        [sys.executable, __file__, "--interrupt", str(paths["workspace"])],
        check=False, capture_output=True,
    )
    assert aborted.returncode == 23 and not aborted.stdout and not aborted.stderr
    with closing(connect(paths["workspace"])) as after:
        assert row_bytes(after, "attestations", digest(interrupted)) is None
        assert row_bytes(after, "payloads", digest(OTHER)) is None
        assert row_bytes(after, "attestations", digest(apple)) == apple
        assert row_bytes(after, "payloads", address) == GOOD
        assert after.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    return {
        "format": "persistent-layered-cache-01", "sqlite": sqlite3.sqlite_version,
        "layer_order": list(paths), "rows": rows,
        "snapshot_eviction": {
            "old_reader": "exact bytes", "fresh_reader": "no bytes",
            "attestation": "retained", "wal_mode": True,
        },
        "interrupted_promotion": {
            "exit": aborted.returncode, "new_attestation": "absent",
            "new_payload": "absent", "prior_commit": "intact",
        },
    }


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--interrupt":
        connection = connect(sys.argv[2])
        connection.execute("BEGIN IMMEDIATE")
        put(connection, (attestation("interrupted", OTHER),), (OTHER,))
        os._exit(23)
    if len(sys.argv) == 3 and sys.argv[1] == "--offline":
        root = Path(sys.argv[2])
        offline = {name: root / f"{name}.sqlite" for name in ("local", "workspace")}
        issuers = {"team-A", "team-B"}
        view = {digest(attestation(issuer, GOOD)) for issuer in issuers}
        print(json.dumps(lookup(offline, view, issuers)))
        sys.exit()
    with TemporaryDirectory(prefix="llmlang-persistent-cache-") as work:
        result = experiment(Path(work))
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
