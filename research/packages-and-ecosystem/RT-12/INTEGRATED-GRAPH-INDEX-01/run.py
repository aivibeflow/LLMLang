#!/usr/bin/env python3
"""Compare SQLite projections and independent exact graph queries in one generation."""

from contextlib import closing
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

SCHEMA = """
CREATE TABLE heads (name TEXT PRIMARY KEY, generation TEXT NOT NULL);
CREATE TABLE edges (generation TEXT, source TEXT, target TEXT, role TEXT, occurrence INTEGER,
    PRIMARY KEY (generation, source, occurrence));
CREATE INDEX reverse_index ON edges (generation, target, role, source, occurrence);
CREATE TABLE contracts (generation TEXT, identity TEXT, shape TEXT, budget INTEGER,
    PRIMARY KEY (generation, identity));
CREATE TABLE providers (generation TEXT, contract TEXT, target TEXT, abi TEXT, artifact TEXT,
    PRIMARY KEY (generation, contract, target, abi, artifact));
"""
QUERIES = tuple(product(("entry", "worker", "absent"), ("linux", "wasi"), ("public", "private")))
BASE = {
    "edges": [
        ("entry", "worker", "call", 0), ("entry", "worker", "call", 1),
        ("worker", "entry", "call", 0), ("worker", "c1", "contract", 1),
        ("worker", "c1", "document", 2), ("sandbox", "c2", "contract", 0),
    ],
    "contracts": [("c1", "finite-result", 5), ("c2", "finite-result", 7)],
    "providers": [
        ("c1", "linux", "public", "provider-a"), ("c1", "linux", "private", "restricted-a"),
        ("c1", "wasi", "public", "portable"), ("c2", "linux", "public", "unrelated-b"),
    ],
}
NEW = {
    "edges": list(BASE["edges"]) + [("entry", "sandbox", "call", 2)],
    "contracts": [("c1", "finite-result", 3), ("c2", "finite-result", 7)],
    "providers": [
        ("c1", "linux", "public", "provider-b"), ("c1", "linux", "private", "restricted-a"),
        ("c1", "wasi", "public", "portable"), ("c2", "linux", "public", "unrelated-b"),
    ],
}


def identity(obj):
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalized(inventory):
    return {name: sorted(rows) for name, rows in inventory.items()}


def prepare(path):
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.executescript(SCHEMA)


def publish(connection, generation, views):
    assert set(views) == set(BASE)
    with connection:
        for name, rows in views.items():
            connection.execute(f"DELETE FROM {name} WHERE generation = ?", (generation,))
            fields = 4 if name == "contracts" else 5
            placeholder = ", ".join(["?"] * fields)
            connection.executemany(
                f"INSERT INTO {name} VALUES ({placeholder})",
                ((generation, *row) for row in rows),
            )
        connection.execute(
            "INSERT INTO heads VALUES ('current', ?) ON CONFLICT(name) DO UPDATE SET generation = excluded.generation",
            (generation,),
        )


def actual_view(connection, generation):
    return {
        name: sorted(connection.execute(f"SELECT * FROM {name} WHERE generation = ?", (generation,)).fetchall())
        for name in BASE
    }


def verify(connection, generation, authoritative):
    source = {kind: [(generation, *row) for row in rows] for kind, rows in normalized(authoritative).items()}
    return identity(actual_view(connection, generation)) == identity(source)


def sql_query(connection, generation, start, target, abi):
    adj = connection.execute("""
        WITH RECURSIVE reach(node) AS (
          SELECT ?
          UNION
          SELECT edges.target FROM edges JOIN reach ON edges.source = reach.node
          WHERE edges.generation = ? AND edges.role IN ('call', 'contract')
        )
        SELECT node FROM reach ORDER BY node
    """, (start, generation)).fetchall()
    reachable = [node for node, in adj]
    reverse = connection.execute("""
        SELECT source, occurrence FROM edges
        WHERE generation = ? AND target = ? AND role = 'call' ORDER BY source, occurrence
    """, (generation, start)).fetchall()
    contracts = []
    providers = []
    for node in reachable:
        contract = connection.execute("""
            SELECT identity, shape, budget FROM contracts WHERE generation = ? AND identity = ?
        """, (generation, node)).fetchone()
        if contract is None:
            continue
        contracts.append(contract)
        providers.extend(connection.execute("""
            SELECT contract, artifact FROM providers
            WHERE generation = ? AND contract = ? AND target = ? AND abi = ?
            ORDER BY contract, artifact
        """, (generation, node, target, abi)).fetchall())
    return {"reachable": reachable, "reverse": reverse, "contracts": contracts, "providers": providers}


def scan(view, start, target, abi):
    reachable = {start}
    while True:
        advanced = reachable | {
            destination for source, destination, role, _ in view["edges"]
            if source in reachable and role in {"call", "contract"}
        }
        if advanced == reachable:
            break
        reachable = advanced
    contracts = sorted(row for row in view["contracts"] if row[0] in reachable)
    selected = {row[0] for row in contracts}
    return {
        "reachable": sorted(reachable),
        "reverse": sorted((origin, occurrence) for origin, dest, role, occurrence in view["edges"]
                          if dest == start and role == "call"),
        "contracts": contracts,
        "providers": sorted((contract, artifact) for contract, triple, kind, artifact in view["providers"]
                            if contract in selected and triple == target and kind == abi),
    }


def head(connection):
    return connection.execute("SELECT generation FROM heads WHERE name='current'").fetchone()[0]


def experiment(work):
    old = identity(normalized(BASE))
    latest = identity(normalized(NEW))
    empty = {name: [] for name in BASE}
    cases = {
        "exact": NEW,
        "reordered": {name: rows[::-1] for name, rows in NEW.items()},
        "old-providers-relabelled": NEW | {"providers": BASE["providers"]},
        "old-contracts-relabelled": NEW | {"contracts": BASE["contracts"]},
        "old-edges-relabelled": NEW | {"edges": BASE["edges"]},
        "wrong-role": NEW | {
            "edges": [("entry", "worker", "document", 0), *NEW["edges"][1:]]
        },
        "missing-providers": NEW | {"providers": []},
        "missing-complete-view": empty,
    }
    comparisons = []
    for name, view in cases.items():
        path = work / f"{name}.db"
        prepare(path)
        with closing(sqlite3.connect(path)) as connection:
            publish(connection, latest, view)
            assert head(connection) == latest
            admitted = verify(connection, latest, NEW)
            assert admitted == (name in {"exact", "reordered"})
            mismatches = {key: 0 for key in ("reachable", "reverse", "contracts", "providers")}
            for arguments in QUERIES:
                oracle = scan(NEW, *arguments)
                raw = sql_query(connection, latest, *arguments)
                validated = raw if admitted else scan(NEW, *arguments)
                assert validated == oracle
                for metric in mismatches:
                    mismatches[metric] += raw[metric] != oracle[metric]
            if not admitted:
                assert sum(mismatches.values()) > 0
            comparisons.append({
                "projection": name, "admitted": admitted, "queries": len(QUERIES),
                "fallback": "qualified-source-scan" if not admitted else "indexed",
                "raw_mismatches": mismatches,
            })

    path = work / "reader.db"
    prepare(path)
    with closing(sqlite3.connect(path)) as writer, closing(sqlite3.connect(path)) as reader:
        publish(writer, old, BASE)
        reader.execute("BEGIN")
        assert head(reader) == old and verify(reader, old, BASE)
        first = ("entry", "linux", "public")
        old_query = sql_query(reader, old, *first)
        publish(writer, latest, NEW)
        assert head(reader) == old and sql_query(reader, head(reader), *first) == old_query
        reader.rollback()
        assert head(reader) == latest
        assert sql_query(reader, old, *first) == old_query
        unsafe = sql_query(reader, head(reader), *first)
        assert unsafe != old_query
        mixed = old_query | {"providers": unsafe["providers"]}
        assert mixed != old_query and mixed != unsafe
        assert verify(reader, latest, NEW)
        exact_generation = {"pinned": old_query, "fresh": unsafe, "cross-generation": mixed}

    return {"format": "integrated-graph-index-01", "sqlite": sqlite3.sqlite_version,
            "generations": [old, latest], "comparison": comparisons, "wal": exact_generation}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-graph-index-") as directory:
        result = experiment(Path(directory))
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
