"""Check Task Context revision and prerequisite settlement in SQLite WAL."""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
from tempfile import TemporaryDirectory

BASELINE = "8e28c7cd4447ea22b49ba3ada613be574e266e57"
POLICIES = ("stationary-task", "task-cas", "exact-prerequisites")
SCHEMA = """
CREATE TABLE tasks (
    id TEXT PRIMARY KEY, epoch INTEGER NOT NULL, revision TEXT NOT NULL,
    owner TEXT NOT NULL, baseline TEXT NOT NULL, state TEXT NOT NULL
);
CREATE TABLE child_receipts (
    id TEXT PRIMARY KEY, epoch INTEGER NOT NULL, state TEXT NOT NULL, artifact TEXT
);
CREATE TABLE completions (
    request_id TEXT PRIMARY KEY, binding TEXT NOT NULL, outcome TEXT NOT NULL
);
INSERT INTO tasks VALUES
    ('parent', 1, 'r1', 'worker-a', 'snapshot-7', 'active'),
    ('other', 1, 'r1', 'worker-b', 'snapshot-7', 'active');
INSERT INTO child_receipts VALUES ('child', 1, 'satisfied', 'checked-artifact-1');
"""


def connect(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    return db


def row(db, query, value):
    result = db.execute(query, (value,)).fetchone()
    return dict(result) if result is not None else None


def task(db):
    return row(db, "SELECT * FROM tasks WHERE id = ?", "parent")


def child(db):
    return row(db, "SELECT * FROM child_receipts WHERE id = ?", "child")


def observe_request(db):
    db.execute("BEGIN")
    try:
        parent, prerequisite = task(db), child(db)
        assert parent["state"] == "active" and prerequisite["state"] == "satisfied"
        return {"request_id": "finish-1", "task": parent, "child": prerequisite,
                "proposed_result": "checked-parent-candidate"}
    finally:
        db.execute("ROLLBACK")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def complete(db, policy, request, interrupt=False):
    db.execute("BEGIN IMMEDIATE")
    try:
        expected, required = request["task"], request["child"]
        prior = row(db, "SELECT * FROM completions WHERE request_id = ?", request["request_id"])
        binding = digest(request)
        if prior is not None:
            if prior["binding"] != binding:
                return "request-id-conflict"
            assert prior["outcome"] == "completed"
            return "recorded"
        live = task(db)
        if live["state"] != "active":
            return "task-not-active"
        if policy != "stationary-task" and live != expected:
            return "stale-task"
        if policy == "exact-prerequisites" and child(db) != required:
            return "stale-prerequisite"

        db.execute("UPDATE tasks SET state = 'completed' WHERE id = 'parent'")
        if interrupt:
            # Let the caller close this connection with the write transaction still open.
            return "interrupted-before-receipt"
        db.execute("INSERT INTO completions VALUES (?, ?, 'completed')",
                   (request["request_id"], binding))
        db.execute("COMMIT")
        return "completed"
    finally:
        if db.in_transaction and not interrupt:
            db.execute("ROLLBACK")


def peer_change(peer, schedule):
    operations = {
        "same": (),
        "revised": ("UPDATE tasks SET revision='r2', epoch=2 WHERE id='parent'",),
        "reassigned": ("UPDATE tasks SET owner='worker-b', epoch=2 WHERE id='parent'",),
        "aba-task": ("UPDATE tasks SET revision='r2', epoch=2 WHERE id='parent'",
                     "UPDATE tasks SET revision='r1', epoch=3 WHERE id='parent'"),
        "cancelled": ("UPDATE tasks SET state='cancelled', epoch=2 WHERE id='parent'",),
        "replacement-child": ("UPDATE child_receipts SET epoch=2 WHERE id='child'",),
        "reopened-child": (
            "UPDATE child_receipts SET epoch=2, state='active', artifact=NULL WHERE id='child'",
        ),
        "child-aba": (
            "UPDATE child_receipts SET epoch=2, state='active', artifact=NULL WHERE id='child'",
            "UPDATE child_receipts SET epoch=3, state='satisfied', artifact='checked-artifact-1' "
            "WHERE id='child'",
        ),
        "unrelated-task": ("UPDATE tasks SET revision='r3', epoch=3 WHERE id='other'",),
    }
    peer.execute("BEGIN IMMEDIATE")
    for statement in operations[schedule]:
        peer.execute(statement)
    peer.execute("COMMIT")


def initialize(path):
    with closing(connect(path)) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        db.executescript(SCHEMA)


def completion_rows(db):
    return [dict(row) for row in db.execute("SELECT * FROM completions ORDER BY request_id")]


def run_case(path, policy, schedule):
    initialize(path)
    with closing(connect(path)) as worker, closing(connect(path)) as peer:
        request = observe_request(worker)
        peer_change(peer, schedule)
        before = {"task": task(peer), "child": child(peer)}
        outcome = complete(worker, policy, request)
        receipts = completion_rows(peer)
        expected = before["task"] == request["task"] and before["child"] == request["child"]
        if policy == "exact-prerequisites":
            assert (outcome == "completed") == expected
        assert len(receipts) == int(outcome == "completed")
        assert task(peer)["state"] == ("completed" if receipts else before["task"]["state"])
        return {"checked_request": request, "state_at_settlement": before,
                "outcome": outcome, "receipts": receipts, "oracle_should_complete": expected}


def interrupted_retry(path):
    initialize(path)
    with closing(connect(path)) as worker:
        request = observe_request(worker)
        outcome = complete(worker, "exact-prerequisites", request, interrupt=True)
        assert outcome == "interrupted-before-receipt" and task(worker)["state"] == "completed"
        with closing(connect(path)) as observer:
            assert task(observer)["state"] == "active" and completion_rows(observer) == []
    with closing(connect(path)) as reopened:
        unchanged_after_rollback = task(reopened)
        assert unchanged_after_rollback["state"] == "active" and completion_rows(reopened) == []
        assert complete(reopened, "exact-prerequisites", request) == "completed"
    with closing(connect(path)) as retry:
        assert complete(retry, "exact-prerequisites", request) == "recorded"
        changed = request | {"proposed_result": "new-candidate"}
        assert complete(retry, "exact-prerequisites", changed) == "request-id-conflict"
        assert complete(retry, "exact-prerequisites", request | {"request_id": "finish-2"}) == "task-not-active"
        receipts = completion_rows(retry)
        assert len(receipts) == 1 and receipts[0]["binding"] == digest(request)
        return {
            "before_close": outcome, "reopened_after_close": unchanged_after_rollback,
            "fresh_retry": "completed", "repeat_after_fresh_open": "recorded",
            "same_key_other_request": "request-id-conflict", "new_key_closed_task": "task-not-active",
            "final_receipts": receipts,
        }


def main():
    names = ("same", "revised", "reassigned", "aba-task", "cancelled", "replacement-child",
             "reopened-child", "child-aba", "unrelated-task")
    with TemporaryDirectory(prefix="llmlang-task-context-") as temporary:
        directory = Path(temporary)
        rows = {
            name: {
                policy: run_case(directory / f"{name}-{policy}.db", policy, name)
                for policy in POLICIES
            }
            for name in names
        }
        retry = interrupted_retry(directory / "retry.db")
    invalid = {
        policy: sum(result[policy]["outcome"] == "completed" and not result[policy]["oracle_should_complete"]
                    for result in rows.values())
        for policy in POLICIES
    }
    assert invalid == {"stationary-task": 6, "task-cas": 3, "exact-prerequisites": 0}
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "invalid_completions": invalid, "schedules": rows, "transaction_retry": retry,
    }, indent=2))


if __name__ == "__main__":
    main()
