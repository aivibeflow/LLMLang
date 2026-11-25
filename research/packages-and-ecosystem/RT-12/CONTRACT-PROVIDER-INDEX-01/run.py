"""Reconcile snapshot-bound SQLite contract/provider discovery with an exact oracle."""

import hashlib
import json
import platform
import sqlite3
import tempfile
from itertools import product
from pathlib import Path

BASELINE = "c3b56825b682650082fb71eee7e99c2223254547"

SCHEMA = """
CREATE TABLE snapshot (root TEXT PRIMARY KEY, count INTEGER NOT NULL, digest TEXT NOT NULL);
CREATE TABLE head (singleton INTEGER PRIMARY KEY CHECK (singleton=1), root TEXT NOT NULL REFERENCES snapshot);
CREATE TABLE discovery (
  root TEXT NOT NULL REFERENCES snapshot,
  scope TEXT NOT NULL,
  contract TEXT NOT NULL,
  target TEXT NOT NULL,
  provider TEXT NOT NULL,
  PRIMARY KEY (root, scope, contract, target, provider)
) WITHOUT ROWID;
CREATE TABLE latest (
  scope TEXT NOT NULL, contract TEXT NOT NULL, target TEXT NOT NULL, provider TEXT NOT NULL,
  PRIMARY KEY (scope, contract, target, provider)
) WITHOUT ROWID;
"""

CATALOGS = (
    (
        ("app", "v1", "linux", "legacy"),
        ("app", "v1", "linux", "portable"),
        ("app", "v1", "wasm", "portable-wasm"),
        ("other", "v1", "linux", "private"),
    ),
    (
        ("app", "v1", "linux", "portable"),
        ("app", "v1", "linux", "new-native"),
        ("app", "v2", "wasm", "new-wasm"),
        ("other", "v1", "linux", "private"),
    ),
    (
        ("app", "v2", "linux", "native-v2"),
        ("app", "v2", "wasm", "new-wasm"),
        ("other", "v1", "linux", "private"),
    ),
)
QUERIES = tuple(product(("app", "other"), ("v1", "v2", "absent"), ("linux", "wasm", "aarch64")))


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def connect(file):
    db = sqlite3.connect(file, isolation_level=None)
    db.execute("PRAGMA foreign_keys = ON")
    return db


def publish(db, rows):
    rows = tuple(sorted(rows))
    root = digest(("closed-catalog/1", rows))
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("INSERT INTO snapshot VALUES (?, ?, ?)", (root, len(rows), digest(rows)))
        db.executemany("INSERT INTO discovery VALUES (?, ?, ?, ?, ?)",
                       ((root, *row) for row in rows))
        db.execute("DELETE FROM latest")
        db.executemany("INSERT INTO latest VALUES (?, ?, ?, ?)", rows)
        db.execute("INSERT INTO head VALUES (1, ?) ON CONFLICT(singleton) DO UPDATE SET root=excluded.root",
                   (root,))
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return root


def head(db):
    return db.execute("SELECT root FROM head WHERE singleton=1").fetchone()[0]


def point_query(db, root, query):
    return tuple(row[0] for row in db.execute(
        "SELECT provider FROM discovery WHERE root=? AND scope=? AND contract=? AND target=? ORDER BY provider",
        (root, *query),
    ))


def latest_query(db, query):
    return tuple(row[0] for row in db.execute(
        "SELECT provider FROM latest WHERE scope=? AND contract=? AND target=? ORDER BY provider", query,
    ))


def oracle(manifest, query):
    return tuple(sorted(provider for scope, contract, target, provider in manifest
                        if (scope, contract, target) == query))


def inspect_inventory(db, root, expected_rows):
    actual = tuple(db.execute(
        "SELECT scope,contract,target,provider FROM discovery WHERE root=? ORDER BY scope,contract,target,provider",
        (root,),
    ))
    expected_rows = tuple(sorted(expected_rows))
    expected_root = digest(("closed-catalog/1", expected_rows))
    declared_count, declared_digest = db.execute(
        "SELECT count,digest FROM snapshot WHERE root=?", (root,),
    ).fetchone()
    return {
        "count_matches": declared_count == len(actual) == len(expected_rows),
        "digest_matches": declared_digest == digest(actual) == digest(expected_rows),
        "exact_admission": root == expected_root and actual == expected_rows
        and declared_count == len(actual) and declared_digest == digest(actual),
    }


def experiment(file):
    writer, reader = connect(file), connect(file)
    try:
        assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        writer.executescript(SCHEMA)
        old = publish(writer, CATALOGS[0])
        query = ("app", "v1", "linux")
        unfenced_head = head(reader)
        reader.execute("BEGIN")
        assert head(reader) == old
        new = publish(writer, CATALOGS[1])
        pinned_answer = latest_query(reader, query)
        assert pinned_answer == oracle(CATALOGS[0], query)
        reader.commit()
        unfenced_answer = latest_query(reader, query)
        bound_answer = point_query(reader, unfenced_head, query)
        assert head(reader) == new
        assert unfenced_answer == oracle(CATALOGS[1], query) != bound_answer
        assert bound_answer == pinned_answer
        newest = publish(writer, CATALOGS[2])

        roots = (old, new, newest)
        for root, catalog in zip(roots, CATALOGS, strict=True):
            assert inspect_inventory(reader, root, catalog)["exact_admission"]
            for requested in QUERIES:
                assert point_query(reader, root, requested) == oracle(catalog, requested)
        primary_key_plan = reader.execute(
            "EXPLAIN QUERY PLAN SELECT provider FROM discovery WHERE root=? AND scope=? AND contract=? AND target=? ORDER BY provider",
            (old, *query),
        ).fetchone()[3]
        assert "SEARCH" in primary_key_plan and "PRIMARY KEY" in primary_key_plan

        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE discovery SET provider='wrong-provider' WHERE root=? AND provider='new-native'", (new,))
        assert inspect_inventory(reader, new, CATALOGS[1])["exact_admission"]
        writer.commit()
        substituted = inspect_inventory(reader, new, CATALOGS[1])
        assert substituted == {"count_matches": True, "digest_matches": False, "exact_admission": False}
        writer.execute("UPDATE snapshot SET digest=? WHERE root=?", ("incorrect-digest", new))
        assert not inspect_inventory(reader, new, CATALOGS[1])["exact_admission"]
        return {
            "snapshot_roots": roots, "exact_queries": len(roots) * len(QUERIES),
            "query_plan": primary_key_plan, "wal_control": {
                "selected_old_root": unfenced_head, "new_root": new, "request": query,
                "one_read_transaction": pinned_answer, "unscoped_lookup_after_publish": unfenced_answer,
                "generation_bound_after_publish": bound_answer,
            },
            "same_count_substitution": substituted,
        }
    finally:
        reader.close()
        writer.close()


def main():
    with tempfile.TemporaryDirectory(prefix="llmlang-contract-index-") as temporary:
        result = experiment(Path(temporary) / "index.sqlite")
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_catalogs": CATALOGS, "queries": QUERIES,
    } | result, indent=2))


if __name__ == "__main__":
    main()
