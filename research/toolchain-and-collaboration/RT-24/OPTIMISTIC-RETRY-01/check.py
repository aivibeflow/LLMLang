"""Check exactly-once SQLite graph edit settlement across process exits and retries."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
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


HERE = Path(__file__).resolve().parent
BASE = {"actor": "alice", "request_id": "edit-1", "node": "leaf", "delta": 3}


def fingerprint(intent):
    fields = ("actor", "request_id", "node", "delta")
    return sha256(json.dumps([intent[field] for field in fields], separators=(",", ":")).encode()).hexdigest()


def connect(path):
    return sqlite3.connect(path, isolation_level=None, timeout=5)


def initialize(path):
    with closing(connect(path)) as conn:
        conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE nodes (name TEXT PRIMARY KEY, weight INTEGER NOT NULL, contract TEXT NOT NULL);
            INSERT INTO nodes VALUES ('leaf', 0, 'capacity:10'), ('independent', 0, 'capacity:10');
            CREATE TABLE receipts (
                actor TEXT NOT NULL, request_id TEXT NOT NULL, request TEXT NOT NULL,
                resulting_weight INTEGER NOT NULL,
                PRIMARY KEY(actor, request_id)
            );
        """)


def read_projection(conn, node):
    return conn.execute("SELECT weight, contract FROM nodes WHERE name = ?", (node,)).fetchone()


def publish(path, intent, projection, crash=None):
    digest = fingerprint(intent)
    with closing(connect(path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            prior = conn.execute(
                "SELECT request, resulting_weight FROM receipts WHERE actor = ? AND request_id = ?",
                (intent["actor"], intent["request_id"]),
            ).fetchone()
            if prior is not None:
                status = ("replayed", prior[1]) if prior[0] == digest else ("id-conflict", None)
                conn.rollback()
                return status
            current = read_projection(conn, intent["node"])
            if current != projection:
                conn.rollback()
                return ("stale", None)
            weight, contract = current
            maximum = int(contract.split(":")[1])
            updated = weight + intent["delta"]
            if not 0 <= updated <= maximum:
                conn.rollback()
                return ("contract-refused", None)
            conn.execute("UPDATE nodes SET weight = ? WHERE name = ?", (updated, intent["node"]))
            conn.execute("INSERT INTO receipts VALUES (?,?,?,?)",
                         (intent["actor"], intent["request_id"], digest, updated))
            if crash == "before-commit":
                os._exit(73)
            conn.commit()
            if crash == "after-commit":
                os._exit(73)
            return ("applied", updated)
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise


def history(path):
    with closing(connect(path)) as conn:
        return (dict(conn.execute("SELECT name, weight FROM nodes")),
                tuple(conn.execute("SELECT actor, request_id, resulting_weight FROM receipts ORDER BY actor, request_id")))


def launch(path, intent, projection, crash):
    return subprocess.run([sys.executable, HERE / "check.py", "--child", path, crash],
                          input=json.dumps([intent, projection]), text=True, capture_output=True, timeout=10)


def schedules(scratch):
    counts = Counter()
    sizes = Counter()
    rows = []
    for crash, peer_node, peer_same_actor, retry_change in product(
        ("before-commit", "after-commit", "ordinary"),
        ("leaf", "independent"), (False, True), (False, True)
    ):
        path = scratch / f"edit-{len(rows)}.sqlite"
        initialize(path)
        first = launch(path, BASE, (0, "capacity:10"), crash)
        if crash == "ordinary":
            assert (first.returncode, json.loads(first.stdout)) == (0, ["applied", 3])
        else:
            assert first.returncode == 73 and not first.stdout and not first.stderr
        persisted = crash != "before-commit"
        weights, receipts = history(path)
        assert weights["leaf"] == (3 if persisted else 0)
        assert len(receipts) == int(persisted)
        peer = {**BASE, "actor": "alice" if peer_same_actor else "bob",
                "request_id": "edit-2", "node": peer_node, "delta": 2}
        with closing(connect(path)) as conn:
            projection = read_projection(conn, peer_node)
        peer_outcome = publish(path, peer, projection)
        assert peer_outcome == ("applied", projection[0] + 2)
        retry = {**BASE, "delta": 4} if retry_change else BASE
        result, receipt = publish(path, retry, (0, "capacity:10"))
        if persisted:
            assert (result, receipt) == (("id-conflict", None) if retry_change else ("replayed", 3))
        elif peer_node == "leaf":
            assert (result, receipt) == ("stale", None)
            if not retry_change:
                assert publish(path, BASE, (2, "capacity:10")) == ("applied", 5)
        else:
            assert (result, receipt) == ("applied", retry["delta"])
        post_weight, committed = history(path)
        expected_leaf = ((3 if persisted else 0) + (2 if peer_node == "leaf" else 0)
                         + (0 if persisted or (peer_node == "leaf" and retry_change) else retry["delta"]))
        assert post_weight == {"leaf": expected_leaf, "independent": 2 if peer_node == "independent" else 0}
        assert len(committed) == (1 if peer_node == "leaf" and retry_change and not persisted else 2)
        counts[result] += 1
        sizes[crash] += 1
        rows.append({"exit_point": crash, "peer_node": peer_node, "same_actor": peer_same_actor,
                     "different_retry_intent": retry_change, "retry": result, "weights": post_weight,
                     "receipts": committed})

    path = scratch / "contract-update.sqlite"
    initialize(path)
    with closing(connect(path)) as conn:
        conn.execute("UPDATE nodes SET contract = 'capacity:1' WHERE name = 'leaf'")
    assert publish(path, BASE, (0, "capacity:10")) == ("stale", None)
    assert publish(path, BASE, (0, "capacity:1")) == ("contract-refused", None)
    assert history(path) == ({"leaf": 0, "independent": 0}, ())
    path = scratch / "duplicate-inflight.sqlite"
    initialize(path)
    parallel = []
    with ThreadPoolExecutor(max_workers=2) as workers:
        pending = [workers.submit(launch, path, BASE, (0, "capacity:10"), "ordinary")
                   for _ in range(2)]
        for job in pending:
            result = job.result()
            assert result.returncode == 0 and not result.stderr
            parallel.append(json.loads(result.stdout))
    parallel.sort()
    assert parallel == [["applied", 3], ["replayed", 3]]
    assert history(path)[1] == (("alice", "edit-1", 3),)
    assert publish(path, {**BASE, "actor": "bob"}, (3, "capacity:10")) == ("applied", 6)
    assert history(path)[1] == (("alice", "edit-1", 3), ("bob", "edit-1", 6))
    return {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "concurrent_duplicate": parallel, "same_id_different_actor": "applied",
            "retry_outcomes": counts, "process_exit_profiles": sizes, "scenarios": rows,
            "contract_change": ["stale", "contract-refused"],
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        requested, expected = json.load(sys.stdin)
        print(json.dumps(publish(sys.argv[2], requested, tuple(expected), sys.argv[3])))
    else:
        with TemporaryDirectory(prefix="rt24-optimistic-retry-") as work:
            print(json.dumps(schedules(Path(work)), sort_keys=True, indent=2))
