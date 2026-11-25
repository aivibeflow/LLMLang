#!/usr/bin/env python3
"""Compare generation checks and rebuild/update strategies on a real SQLite FTS index."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

NS = "work/a"
OTHER = "work/b"
GATES = ("pinned_only", "current_root", "fresh_rows", "complete_key")
CHANGES = ("none", "root", "revoke", "expand", "model", "schema", "description")
STAGES = ("after_query", "authority_only", "atomic_abort", "split_abort", "after_publish")
SCHEMA = """
CREATE TABLE authority (
    namespace TEXT PRIMARY KEY, root TEXT, descriptions TEXT, policy INTEGER, schema_version INTEGER, model INTEGER
);
CREATE TABLE source (
    namespace TEXT, name TEXT, hash TEXT, phrase TEXT, visible INTEGER,
    PRIMARY KEY(namespace, name)
);
CREATE TABLE published (
    namespace TEXT PRIMARY KEY, root TEXT, descriptions TEXT, policy INTEGER,
    schema_version INTEGER, model INTEGER, ready INTEGER
);
CREATE TABLE projection (
    rowid INTEGER PRIMARY KEY, namespace TEXT, name TEXT, hash TEXT, tokens TEXT,
    UNIQUE(namespace, name)
);
CREATE VIRTUAL TABLE search USING fts5(tokens, content='projection', content_rowid='rowid');
CREATE TRIGGER projection_insert AFTER INSERT ON projection BEGIN
    INSERT INTO search(rowid, tokens) VALUES (new.rowid, new.tokens);
END;
CREATE TRIGGER projection_delete AFTER DELETE ON projection BEGIN
    INSERT INTO search(search, rowid, tokens) VALUES ('delete', old.rowid, old.tokens);
END;
CREATE TRIGGER projection_update AFTER UPDATE ON projection BEGIN
    INSERT INTO search(search, rowid, tokens) VALUES ('delete', old.rowid, old.tokens);
    INSERT INTO search(rowid, tokens) VALUES (new.rowid, new.tokens);
END;
"""


def digest(value):
    return sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def connect(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA foreign_keys=ON")
    return db


def selected_root(db, namespace):
    return digest(list(db.execute("SELECT name, hash FROM source WHERE namespace=? ORDER BY name", (namespace,))))


def description_root(db, namespace):
    return digest(list(db.execute("SELECT name, phrase FROM source WHERE namespace=? ORDER BY name", (namespace,))))


def key(db, namespace):
    return db.execute("SELECT root, descriptions, policy, schema_version, model FROM authority WHERE namespace=?",
                      (namespace,)).fetchone()


def header(db, namespace):
    return db.execute("SELECT root, descriptions, policy, schema_version, model, ready FROM published WHERE namespace=?",
                      (namespace,)).fetchone()


def source_rows(db, namespace):
    return db.execute("SELECT name, hash, phrase FROM source WHERE namespace=? AND visible=1 ORDER BY name",
                      (namespace,)).fetchall()


def encode(phrase, schema_version, model):
    # Different versions alter retrieval features without changing exact function identity.
    tokens = phrase if schema_version == 1 else phrase.replace("search", "lookup")
    return tokens if model == 1 else tokens.replace("exact", "approximate")


def expected_projection(db, namespace, scope_key):
    return [(name, artifact, encode(phrase, scope_key[3], scope_key[4]))
            for name, artifact, phrase in source_rows(db, namespace)]


def projected(db, namespace):
    return db.execute("SELECT name, hash, tokens FROM projection WHERE namespace=? ORDER BY name",
                      (namespace,)).fetchall()


def install(db, namespace, strategy, row_limit=None):
    scope_key = key(db, namespace)
    old = {row[0]: row[1:] for row in projected(db, namespace)}
    expected = {row[0]: row[1:] for row in expected_projection(db, namespace, scope_key)}
    removed = sorted(old.keys() - expected.keys())
    writes = [(namespace, name, *value) for name, value in sorted(expected.items())
              if strategy == "rebuild" or old.get(name) != value]
    if strategy == "rebuild":
        db.execute("DELETE FROM projection WHERE namespace=?", (namespace,))
    else:
        db.executemany("DELETE FROM projection WHERE namespace=? AND name=?",
                       [(namespace, name) for name in removed])
    applied = writes if row_limit is None else writes[:row_limit]
    db.executemany("""
        INSERT INTO projection(namespace, name, hash, tokens) VALUES (?,?,?,?)
        ON CONFLICT(namespace, name) DO UPDATE SET hash=excluded.hash, tokens=excluded.tokens
    """, applied)
    return {
        "scope_key": scope_key,
        "comparison_rows": len(old) + len(expected),
        "rows_removed": len(old) if strategy == "rebuild" else len(removed),
        "rows_written": len(applied),
        "logical_write_bytes": sum(len(json.dumps(row, separators=(",", ":")).encode()) for row in applied),
    }


def stamp(db, namespace, scope_key, ready):
    db.execute("INSERT OR REPLACE INTO published VALUES (?,?,?,?,?,?,?)", (namespace, *scope_key, ready))


def publish(db, namespace, strategy):
    db.execute("BEGIN IMMEDIATE")
    metrics = install(db, namespace, strategy)
    scope_key = metrics.pop("scope_key")
    actual = projected(db, namespace)
    expected = expected_projection(db, namespace, scope_key)
    assert actual == expected
    metrics["validation_rows"] = len(actual) + len(expected)
    stamp(db, namespace, scope_key, 1)
    db.execute("COMMIT")
    return metrics


def initialize(path, size):
    db = connect(path)
    assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    db.execute("PRAGMA synchronous=FULL")
    db.executescript(SCHEMA)
    db.execute("BEGIN IMMEDIATE")
    for namespace in (NS, OTHER):
        rows = [(namespace, f"f{index:05}", digest((namespace, index, "body-v1")),
                 "exact search" if index < 4 else f"metadata batch {index}", int(index != 3))
                for index in range(size if namespace == NS else 4)]
        db.executemany("INSERT INTO source VALUES (?,?,?,?,?)", rows)
        db.execute("INSERT INTO authority VALUES (?,?,?,1,1,1)",
                   (namespace, selected_root(db, namespace), description_root(db, namespace)))
    db.execute("COMMIT")
    publish(db, NS, "rebuild")
    publish(db, OTHER, "rebuild")
    return db


def edit(db, kind):
    db.execute("BEGIN IMMEDIATE")
    if kind == "root":
        db.execute("UPDATE source SET hash=? WHERE namespace=? AND name='f00000'",
                   (digest((NS, 0, "body-v2")), NS))
        db.execute("UPDATE authority SET root=? WHERE namespace=?", (selected_root(db, NS), NS))
    elif kind in {"revoke", "expand"}:
        new_visibility, name = (0, "f00000") if kind == "revoke" else (1, "f00003")
        db.execute("UPDATE source SET visible=? WHERE namespace=? AND name=?", (new_visibility, NS, name))
        db.execute("UPDATE authority SET policy=policy+1 WHERE namespace=?", (NS,))
    elif kind == "description":
        db.execute("UPDATE source SET phrase='archived description' WHERE namespace=? AND name='f00000'",
                   (NS,))
        db.execute("UPDATE authority SET descriptions=? WHERE namespace=?", (description_root(db, NS), NS))
    elif kind in {"schema", "model"}:
        column = "schema_version" if kind == "schema" else "model"
        db.execute(f"UPDATE authority SET {column}={column}+1 WHERE namespace=?", (NS,))
    db.execute("COMMIT")


def query(db, namespace):
    return db.execute("""
        SELECT p.name, p.hash FROM search JOIN projection AS p ON search.rowid=p.rowid
        WHERE search MATCH 'exact AND search' AND p.namespace=?
        ORDER BY p.name, p.hash LIMIT 4
    """, (namespace,)).fetchall()


def oracle(db, namespace, scope_key):
    if scope_key[3:] != (1, 1):
        return []
    return [(name, hash_value) for name, hash_value, phrase in source_rows(db, namespace)
            if phrase == "exact search"][:4]


def run_gate(gate, items, observed_key, observed_header, fresh_key, authority):
    if gate == "pinned_only":
        return items if observed_header[:-1] == observed_key else None
    if gate == "current_root":
        return items if observed_header[0] == observed_key[0] == fresh_key[0] else None
    if gate == "fresh_rows":
        return [item for item in items if item in authority]
    return items if observed_header == (*observed_key, 1) and observed_key == fresh_key else None


def aborted_writer(path, mode):
    db = connect(path)
    scope_key = key(db, NS)
    db.execute("BEGIN IMMEDIATE")
    if mode == "split_abort":
        stamp(db, NS, scope_key, 1)
        db.execute("COMMIT")
        db.execute("BEGIN IMMEDIATE")
        # A split rebuild publishes the new header before replacement content.
        db.execute("DELETE FROM projection WHERE namespace=?", (NS,))
        install(db, NS, "delta", row_limit=1)
        db.execute("COMMIT")
    else:
        install(db, NS, "rebuild", row_limit=1)
        stamp(db, NS, scope_key, 1)
    os._exit(71)


def apply(path, db, change, stage):
    edit(db, change)
    if stage in {"atomic_abort", "split_abort"}:
        result = subprocess.run([sys.executable, "-B", __file__, "--abort", str(path), stage], check=False)
        assert result.returncode == 71
    elif stage in {"after_query", "after_publish"}:
        publish(db, NS, "delta")


def scenario(path, change, stage):
    writer = initialize(path, 12)
    reader = connect(path)
    if stage != "after_query":
        apply(path, writer, change, stage)
    reader.execute("BEGIN")
    observed_key = key(reader, NS)
    observed_header = header(reader, NS)
    items = query(reader, NS)
    other_items = query(reader, OTHER)
    if stage == "after_query":
        apply(path, writer, change, stage)
    assert key(reader, NS) == observed_key
    assert query(reader, NS) == items
    reader.execute("COMMIT")
    reader.close()

    fresh_reader = connect(path)
    fresh_reader.execute("BEGIN")
    fresh_key = key(fresh_reader, NS)
    authority = {(name, item_hash) for name, item_hash, _ in source_rows(fresh_reader, NS)}
    reference = oracle(fresh_reader, NS, fresh_key)
    assert query(fresh_reader, OTHER) == other_items == oracle(fresh_reader, OTHER, key(fresh_reader, OTHER))
    fresh_reader.execute("COMMIT")
    fresh_reader.close()
    gates = {}
    for gate in GATES:
        # The split writer deliberately stamps a false ready mark. This control tests that trust assumption.
        accepted = run_gate(gate, items, observed_key, observed_header, fresh_key, authority)
        if accepted is None:
            verdict = "refused"
        elif accepted == reference:
            verdict = "exact"
        elif any(item not in authority for item in accepted):
            verdict = "ineligible"
        else:
            verdict = "stale_or_incomplete"
        gates[gate] = {"verdict": verdict, "items": accepted}

    repair = publish(writer, NS, "delta")
    writer.execute("INSERT INTO search(search, rank) VALUES ('integrity-check', 1)")
    assert header(writer, NS) == (*fresh_key, 1)
    assert query(writer, NS) == reference
    writer.close()
    return {
        "change": change, "stage": stage, "observed_key": observed_key, "current_key": fresh_key,
        "observed_header": observed_header, "oracle": reference, "gates": gates,
        "repair_rows": repair, "other_workspace_unchanged": True,
    }


def measure(path, size, strategy, change):
    db = initialize(path, size)
    edit(db, change)
    metrics = publish(db, NS, strategy)
    scope_key = key(db, NS)
    assert query(db, NS) == oracle(db, NS, scope_key)
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    metrics.update({"size": size, "strategy": strategy, "change": change,
                    "projection_digest": digest(projected(db, NS)),
                    "database_allocated_bytes": path.stat().st_size,
                    "page_size": db.execute("PRAGMA page_size").fetchone()[0]})
    db.close()
    return metrics


def run(directory):
    scenarios = [scenario(directory / f"case-{index}.sqlite", change, stage)
                 for index, (change, stage) in enumerate(product(CHANGES, STAGES))]
    cases = product((64, 256, 1024), ("rebuild", "delta"), ("root", "revoke", "schema", "description"))
    work = [measure(directory / f"cost-{index}.sqlite", *case) for index, case in enumerate(cases)]
    for first, second in product(work, repeat=2):
        if first["size"] == second["size"] and first["change"] == second["change"]:
            assert first["projection_digest"] == second["projection_digest"]

    safe = [row for row in scenarios if row["stage"] != "split_abort"]
    unsafe = [row for row in scenarios if row["stage"] == "split_abort"]
    assert all(row["gates"]["complete_key"]["verdict"] in {"exact", "refused"} for row in safe)
    assert any(row["gates"]["complete_key"]["verdict"] == "stale_or_incomplete" for row in unsafe)
    assert any(row["gates"]["current_root"]["verdict"] == "ineligible" for row in safe)
    assert any(row["gates"]["fresh_rows"]["verdict"] == "stale_or_incomplete" for row in safe)
    with connect(":memory:") as db:
        native = db.execute("SELECT sqlite_source_id(), fts5_source_id()").fetchone()
    aggregate = {gate: dict(sorted(Counter(row["gates"][gate]["verdict"] for row in safe).items()))
                 for gate in GATES}
    split = {gate: dict(sorted(Counter(row["gates"][gate]["verdict"] for row in unsafe).items()))
             for gate in GATES}
    return {
        "schema": "llmlang-rt35-persistent-index/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "sqlite_source": native[0], "fts5_source": native[1],
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "query": "exact AND search",
        "scenario_count": len(scenarios), "protocol_scenarios": len(safe), "split_controls": len(unsafe),
        "protocol_aggregate": aggregate, "split_aggregate": split, "scenarios": scenarios, "maintenance": work,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        aborted_writer(Path(sys.argv[2]), sys.argv[3])
    else:
        with TemporaryDirectory(prefix="llmlang-rt35-index-") as scratch:
            result = run(Path(scratch))
        scenarios = result.pop("scenarios")
        maintenance = result.pop("maintenance")
        print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "scenarios": [')
        print(",\n".join("    " + json.dumps(row) for row in scenarios))
        print('  ],\n  "maintenance": [')
        print(",\n".join("    " + json.dumps(row) for row in maintenance))
        print("  ]\n}")
