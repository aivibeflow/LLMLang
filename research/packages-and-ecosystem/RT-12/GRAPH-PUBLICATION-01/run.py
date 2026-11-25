"""Check graph, index and receipt publication under real process exit."""

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
GRAPHS = {
    "old": {"nodes": ["caller", "alpha"], "edges": [["caller", "alpha", "invoke"]]},
    "new": {"nodes": ["caller", "beta"], "edges": [["caller", "beta", "invoke"]]},
}
EXIT_CODES = {
    "atomic_before_commit": 41,
    "atomic_after_commit": 42,
    "split_head_first": 43,
    "prepared_before_head": 44,
    "stale_epoch": 45,
    "wrong_receipt": 46,
}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def identity(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


ROOTS = {label: identity(value) for label, value in GRAPHS.items()}


def stage(db, label, *, complete=True, receipt_root=None):
    graph = GRAPHS[label]
    root = ROOTS[label]
    db.execute("INSERT INTO graph VALUES (?,?)", (root, encode(graph)))
    if complete:
        edges = sorted(graph["edges"], key=lambda edge: (edge[1], edge[0], edge[2]))
        db.execute("INSERT INTO reverse_projection VALUES (?,?)", (root, encode(edges)))
        db.execute("INSERT INTO receipt VALUES (?,?,?)", (root, receipt_root or root, "checked-fixture"))


def ready(db, root):
    graph = db.execute("SELECT payload FROM graph WHERE root=?", (root,)).fetchone()
    projection = db.execute("SELECT rows FROM reverse_projection WHERE root=?", (root,)).fetchone()
    receipt = db.execute("SELECT checked_root,status FROM receipt WHERE root=?", (root,)).fetchone()
    if graph is None or projection is None or receipt != (root, "checked-fixture"):
        return False
    value = json.loads(graph[0])
    expected = sorted(value["edges"], key=lambda edge: (edge[1], edge[0], edge[2]))
    return identity(value) == root and json.loads(projection[0]) == expected


def change_head(db, root, old, epoch):
    return db.execute(
        "UPDATE head SET root=?, epoch=epoch+1 WHERE slot=1 AND root=? AND epoch=?",
        (root, old, epoch)
    ).rowcount == 1


def initialize(path, *, old_epoch=0):
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        db.executescript(
            "CREATE TABLE graph(root TEXT PRIMARY KEY NOT NULL,payload TEXT NOT NULL);"
            "CREATE TABLE reverse_projection(root TEXT PRIMARY KEY NOT NULL,rows TEXT NOT NULL);"
            "CREATE TABLE receipt(root TEXT PRIMARY KEY NOT NULL,checked_root TEXT NOT NULL,status TEXT NOT NULL);"
            "CREATE TABLE head(slot INTEGER PRIMARY KEY,root TEXT NOT NULL,epoch INTEGER NOT NULL);"
        )
        stage(db, "old")
        db.execute("INSERT INTO head VALUES (1,?,?)", (ROOTS["old"], old_epoch))
        db.commit()
        assert ready(db, ROOTS["old"])


def worker(path, mode):
    db = sqlite3.connect(path)
    db.execute("BEGIN IMMEDIATE")
    candidate = ROOTS["new"]
    stale = mode == "stale_epoch"
    wrong = mode == "wrong_receipt"
    split = mode == "split_head_first"
    stage(db, "new", complete=not split, receipt_root=ROOTS["old"] if wrong else None)
    if wrong:
        assert not ready(db, candidate)
        db.rollback()
    elif mode == "prepared_before_head":
        assert ready(db, candidate)
        db.commit()
    elif stale:
        assert ready(db, candidate)
        assert not change_head(db, candidate, ROOTS["old"], 0)
        db.rollback()
    else:
        assert ready(db, candidate) == (not split)
        assert change_head(db, candidate, ROOTS["old"], 0)
        if mode != "atomic_before_commit":
            db.commit()
    os._exit(EXIT_CODES[mode])


def observe(path):
    with closing(sqlite3.connect(path)) as db:
        root, epoch = db.execute("SELECT root,epoch FROM head WHERE slot=1").fetchone()
        return {
            "selected": next(label for label, address in ROOTS.items() if address == root),
            "epoch": epoch, "selected_complete": ready(db, root),
            "candidate_present": db.execute("SELECT 1 FROM graph WHERE root=?", (ROOTS["new"],)).fetchone() is not None,
            "candidate_complete": ready(db, ROOTS["new"]),
        }


def main():
    results = {}
    with TemporaryDirectory(prefix="llmlang-graph-publication-") as scratch:
        for mode, code in EXIT_CODES.items():
            path = Path(scratch) / f"{mode}.sqlite"
            initialize(path, old_epoch=1 if mode == "stale_epoch" else 0)
            process = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(path), mode],
                                     capture_output=True, text=True, timeout=20)
            assert process.returncode == code, (mode, process.stderr)
            results[mode] = observe(path) | {"process_exit": code}
    expected = {
        "atomic_before_commit": ("old", 0, True, False, False),
        "atomic_after_commit": ("new", 1, True, True, True),
        "split_head_first": ("new", 1, False, True, False),
        "prepared_before_head": ("old", 0, True, True, True),
        "stale_epoch": ("old", 1, True, False, False),
        "wrong_receipt": ("old", 0, True, False, False),
    }
    for mode, values in expected.items():
        assert tuple(value for field, value in results[mode].items() if field != "process_exit") == values
    print(json.dumps({
        "schema": "llmlang-rt12-graph-publication/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "journal_mode": "wal",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "graphs": GRAPHS, "roots": ROOTS, "results": results,
    }, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), sys.argv[3])
    else:
        main()
