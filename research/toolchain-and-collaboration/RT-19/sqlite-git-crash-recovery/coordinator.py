"""Bounded RT-19 acceptance/outbox fixture using SQLite and real Git refs."""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory


# These are the existing, scoped RT-24 closed inventory and RT-23 Git receipt experiments.
sys.path.insert(0, os.environ["LLMLANG_DEPENDENCY_GRAPH_PROTOTYPE"])
from src.candidate_graph_audit import audit_candidate_snapshot_graph
from src.semantic_graph import ContentStore, canonical_bytes, digest
from tests import test_rt23_commit_recovery as receipt
from tests import test_rt24_merge_tree_gate as graph


SCHEMA = """
CREATE TABLE head (singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                   generation INTEGER NOT NULL, root TEXT NOT NULL);
CREATE TABLE object (root TEXT PRIMARY KEY, inventory BLOB NOT NULL);
CREATE TABLE operation (
  key TEXT PRIMARY KEY, request_digest TEXT NOT NULL, generation INTEGER NOT NULL,
  root TEXT NOT NULL REFERENCES object(root), base TEXT NOT NULL, payload BLOB NOT NULL,
  tree TEXT, candidate TEXT, outcome TEXT
);
"""


def crash(selected, point):
    if selected == point:
        os._exit(74)


def connect(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = FULL")
    return db


def semantic_root(files):
    manifest = json.loads(files[graph.MANIFEST])
    paths = manifest["sources"]
    actual_sources = {path for path in files if path.startswith("program/")} - {graph.MANIFEST}
    if (manifest.get("version") != 1 or set(manifest) != {"sources", "version"}
            or not paths or len(paths) != len(set(paths)) or set(paths) != actual_sources):
        raise ValueError("Incomplete or invalid program inventory")
    rows = {}
    for path in paths:
        for row in json.loads(files[path]):
            if row["slot"] in rows or set(row) != {"slot", "declaration"}:
                raise ValueError("Repeated or invalid source slot")
            rows[row["slot"]] = row["declaration"]
    store = ContentStore()
    snapshot = graph.publish_rows(rows, store)
    if not audit_candidate_snapshot_graph(store, snapshot).valid:
        raise ValueError("Invalid fixture snapshot at acceptance")
    return snapshot.root_hash, canonical_bytes(rows)


def accept(db, request, failpoint):
    payload = canonical_bytes(request)
    identity = digest(request)
    key = request["key"]
    db.execute("BEGIN IMMEDIATE")
    crash(failpoint, "begin_accept")
    previous = db.execute("SELECT * FROM operation WHERE key = ?", (key,)).fetchone()
    if previous is not None:
        db.execute("COMMIT")
        if previous["request_digest"] != identity or previous["payload"] != payload:
            return "key-conflict", None
        return "existing", previous
    generation = request["generation"]
    head = db.execute("SELECT generation, root FROM head WHERE singleton = 1").fetchone()
    if (head["generation"], head["root"]) != (generation, request["parent_root"]):
        db.execute("ROLLBACK")
        return "stale-acceptance", None
    try:
        root, inventory = semantic_root(request["files"])
    except (KeyError, TypeError, ValueError):
        db.execute("ROLLBACK")
        return "invalid-inventory", None
    db.execute("INSERT OR IGNORE INTO object VALUES (?, ?)", (root, inventory))
    immutable = db.execute("SELECT inventory FROM object WHERE root = ?", (root,)).fetchone()
    if immutable["inventory"] != inventory:
        raise ValueError("Conflicting immutable object")
    crash(failpoint, "immutable_written")
    advanced = db.execute("UPDATE head SET generation = ?, root = ? WHERE singleton = 1 AND generation = ?",
                          (generation + 1, root, generation))
    if advanced.rowcount != 1:
        raise ValueError("Workspace CAS was lost inside the acceptance transaction")
    db.execute("""INSERT INTO operation (key, request_digest, generation, root, base, payload)
                  VALUES (?, ?, ?, ?, ?, ?)""", (key, identity, generation + 1, root, request["base"], payload))
    db.execute("COMMIT")
    crash(failpoint, "accepted_outbox")
    return "accepted", db.execute("SELECT * FROM operation WHERE key = ?", (key,)).fetchone()


def prepare(repo, request, operation, failpoint):
    with TemporaryDirectory(prefix="rt19-private-", dir=repo.parent) as temp:
        index = Path(temp) / "index"
        graph.git(repo, "read-tree", operation["base"], index=index)
        for position, (name, text) in enumerate(sorted(request["files"].items())):
            oid = graph.git(repo, "hash-object", "-w", "--stdin", stdin=text.encode("utf-8")).decode().strip()
            graph.git(repo, "update-index", "--add", "--cacheinfo", f"100644,{oid},{name}", index=index)
            if position == 0:
                crash(failpoint, "partial_private_index")
        for path in request["delete"]:
            graph.git(repo, "update-index", "--force-remove", "--", path, index=index)
        tree = graph.git(repo, "write-tree", index=index).decode().strip()
    for path, text in request["files"].items():
        if graph.git(repo, "show", f"{tree}:{path}") != text.encode("utf-8"):
            raise ValueError(f"Candidate bytes changed for {path}")
    for path in request["delete"]:
        if graph.git(repo, "ls-tree", tree, "--", path):
            raise ValueError(f"Candidate deletion missing for {path}")
    candidate = receipt.commit_object(repo, tree, (operation["base"],), f"RT-19 fixture {operation['key']}")
    expected = receipt.Prepared(operation["key"], tree, operation["root"], (operation["base"],), candidate)
    if not receipt.matches_candidate(repo, expected):
        raise ValueError("Private tree does not reconstruct the accepted semantic root")
    crash(failpoint, "validated_candidate")
    return expected


def apply(path, repo, request, failpoint):
    with closing(connect(path)) as db:
        disposition, operation = accept(db, request, failpoint)
        if operation is None:
            return {"status": disposition}
        if operation["outcome"] is not None:
            return json.loads(operation["outcome"])
        if operation["candidate"] is None:
            candidate = prepare(repo, request, operation, failpoint)
            db.execute("UPDATE operation SET tree = ?, candidate = ? WHERE key = ? AND candidate IS NULL",
                       (candidate.tree, candidate.candidate, operation["key"]))
            operation = db.execute("SELECT * FROM operation WHERE key = ?", (operation["key"],)).fetchone()
            if (operation["tree"], operation["candidate"]) != (candidate.tree, candidate.candidate):
                raise ValueError("Concurrent preparation changed the exact candidate")
        else:
            candidate = receipt.Prepared(operation["key"], operation["tree"], operation["root"],
                                         (operation["base"],), operation["candidate"])
        crash(failpoint, "prepared_outbox")
        current = receipt.publish(repo, candidate)
        if current not in {"published", "published-branch-moved"}:
            return {"status": current}
        crash(failpoint, "git_published")
        result = {"status": "published", "commit": candidate.candidate, "root": operation["root"],
                  "tree": candidate.tree, "generation": operation["generation"]}
        db.execute("UPDATE operation SET outcome = ? WHERE key = ? AND outcome IS NULL",
                   (json.dumps(result, sort_keys=True), operation["key"]))
        stored = db.execute("SELECT outcome FROM operation WHERE key = ?", (operation["key"],)).fetchone()
        if json.loads(stored["outcome"]) != result:
            raise ValueError("Publication result changed")
        crash(failpoint, "sql_outcome")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("request", type=Path)
    parser.add_argument("--failpoint")
    args = parser.parse_args()
    print(json.dumps(apply(args.database, args.repository, json.loads(args.request.read_bytes()), args.failpoint)))
