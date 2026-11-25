"""Replay optimistic graph edits against two native SQLite connections."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import permutations, product
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier, Event


POLICIES = ("whole-head", "write-only", "exact-read")


@dataclass(frozen=True)
class Edit:
    kind: str
    source: int
    target: int = -1


def fixture_groups(length):
    # Nodes 0 and 1 have a path of variable length via the higher IDs.
    path = (0, *range(4, length + 4), 1)
    backbone = set(zip(path, path[1:]))
    return {
        "independent": (backbone, (Edit("add", 2, 0), Edit("add", 3, 1))),
        "same-write": (backbone, (Edit("add", 2, 0), Edit("add", 2, 0))),
        "endpoint-changed": (backbone, (Edit("add", 2, 3), Edit("disable", 3))),
        "outgoing-edge-phantom": (backbone, (Edit("add", 2, 3), Edit("disable", 2))),
        "cycle-phantom": (backbone, (Edit("add", 1, 2), Edit("add", 2, 0))),
        "overlapping-read": (backbone, (Edit("add", 0, 2), Edit("add", 1, 2))),
    }


def project(db, edit):
    source, target = edit.source, edit.target
    if edit.kind == "disable":
        (active,) = db.execute("SELECT active FROM node WHERE id = ?", (source,)).fetchone()
        incident = db.execute(
            "SELECT EXISTS(SELECT 1 FROM edge WHERE src = ? OR dst = ?)",
            (source, source),
        ).fetchone()[0]
        return (active,), (incident,)

    existence = db.execute("SELECT EXISTS(SELECT 1 FROM edge WHERE src = ? AND dst = ?)",
                           (source, target)).fetchone()[0]
    endpoints = tuple(db.execute("SELECT id, active FROM node WHERE id IN (?, ?) ORDER BY id",
                                 (source, target)))
    creates_cycle = db.execute("""
        WITH RECURSIVE reachable(id) AS (
            VALUES (?) UNION SELECT edge.dst FROM edge JOIN reachable ON edge.src = reachable.id
        )
        SELECT EXISTS(SELECT 1 FROM reachable WHERE id = ?)
    """, (target, source)).fetchone()[0]
    return (existence,), (endpoints, creates_cycle)


def valid_projection(edit, projection):
    write, reads = projection
    if edit.kind == "disable":
        return write == (1,) and reads == (0,)
    endpoints, creates_cycle = reads
    return (
        write == (0,) and len(endpoints) == 2
        and all(active for _, active in endpoints) and not creates_cycle
    )


def worker(path, edit, policy, barrier, first_done, first):
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.execute("BEGIN")
        (base,) = db.execute("SELECT version FROM head").fetchone()
        proposal = project(db, edit)
        assert valid_projection(edit, proposal)
        db.execute("COMMIT")
        barrier.wait(timeout=10)
        if not first and not first_done.wait(timeout=10):
            raise TimeoutError("first writer did not finish")

        db.execute("BEGIN IMMEDIATE")
        (current,) = db.execute("SELECT version FROM head").fetchone()
        actual = project(db, edit)
        matches = {
            "whole-head": current == base,
            "write-only": actual[0] == proposal[0],
            "exact-read": actual == proposal,
        }[policy]
        if not matches:
            db.execute("ROLLBACK")
            return False
        if edit.kind == "add":
            db.execute("INSERT INTO edge VALUES (?, ?)", (edit.source, edit.target))
        else:
            db.execute("UPDATE node SET active = 0 WHERE id = ?", (edit.source,))
        db.execute("UPDATE head SET version = version + 1")
        db.execute("COMMIT")
        return True
    finally:
        db.close()
        if first:
            first_done.set()


def check_graph(active, edges):
    """Independent final-state oracle using endpoint checks and topological removal."""
    if any(src not in active or dst not in active for src, dst in edges):
        return False
    remaining = set(active)
    while remaining:
        incoming = {dst for src, dst in edges if src in remaining and dst in remaining}
        sources = remaining - incoming
        if not sources:
            return False
        remaining -= sources
    return True


def apply(active, edges, edit):
    if edit.kind == "disable":
        return active - {edit.source}, edges
    return active, edges | {(edit.source, edit.target)}


def run_case(path, nodes, initial, edits, order, policy):
    db = sqlite3.connect(path, isolation_level=None)
    journal_mode = db.execute("PRAGMA journal_mode=WAL").fetchone()
    assert journal_mode == ("wal",)
    db.executescript("""
        CREATE TABLE head (version INTEGER NOT NULL);
        INSERT INTO head VALUES (0);
        CREATE TABLE node (id INTEGER PRIMARY KEY, active INTEGER NOT NULL);
        CREATE TABLE edge (src INTEGER, dst INTEGER, PRIMARY KEY (src, dst));
    """)
    db.executemany("INSERT INTO node VALUES (?, 1)", [(node,) for node in sorted(nodes)])
    db.executemany("INSERT INTO edge VALUES (?, ?)", sorted(initial))
    barrier = Barrier(2)
    first_done = Event()
    first, second = (edits[index] for index in order)
    assert check_graph(nodes, initial)
    for edit in edits:
        assert check_graph(*apply(nodes, initial, edit))

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(worker, path, first, policy, barrier, first_done, True)
            two = pool.submit(worker, path, second, policy, barrier, first_done, False)
            first_committed = one.result()
            assert first_committed
            committed = two.result()
        active_after_first, edges_after_first = apply(nodes, initial, first)
        duplicate = second.kind == "add" and (second.source, second.target) in edges_after_first
        combined = apply(active_after_first, edges_after_first, second)
        expected = not duplicate and check_graph(*combined)
        active = {node for (node,) in db.execute("SELECT id FROM node WHERE active")}
        edges = set(db.execute("SELECT src, dst FROM edge"))
        assert (active, edges) == (combined if committed else (active_after_first, edges_after_first))
        assert db.execute("SELECT version FROM head").fetchone() == (1 + committed,)
        return {
            "second_committed": committed,
            "second_permitted": expected,
            "final_graph_valid": check_graph(active, edges),
        }
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    records = []
    for length in (1, 2, 4, 8):
        nodes = set(range(length + 4))
        for (name, (initial, edits)), order, policy in product(
            fixture_groups(length).items(), permutations(range(2)), POLICIES,
        ):
            with TemporaryDirectory(prefix="llmlang-concurrent-graph-") as directory:
                outcomes = run_case(Path(directory) / "graph.db", nodes, initial, edits, order, policy)
            records.append({"intermediate_nodes": length, "fixture": name, "order": order,
                            "policy": policy, **outcomes})
    counts = {}
    for policy in POLICIES:
        rows = [record for record in records if record["policy"] == policy]
        counts[policy] = {
            "schedules": len(rows),
            "incorrect_admissions": sum(r["second_committed"] and not r["second_permitted"] for r in rows),
            "unnecessary_refusals": sum(not r["second_committed"] and r["second_permitted"] for r in rows),
            "invalid_final_graphs": sum(not r["final_graph_valid"] for r in rows),
        }
    for policy, admissions, refusals in (
        ("whole-head", 0, 16), ("write-only", 24, 0), ("exact-read", 0, 0),
    ):
        assert counts[policy] == dict(schedules=48, incorrect_admissions=admissions,
                                     unnecessary_refusals=refusals, invalid_final_graphs=admissions)
    args.output.write_text(json.dumps({"counts": counts, "records": records}, indent=2) + "\n")


if __name__ == "__main__":
    main()
