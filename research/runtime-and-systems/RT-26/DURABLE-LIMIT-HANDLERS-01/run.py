#!/usr/bin/env python3
"""Check a transactional bounded resource ledger and typed handler decisions."""

from contextlib import closing
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


class Action(StrEnum):
    CONTINUE = "continue"
    THROTTLE = "throttle"
    PAUSE = "pause"
    CANCEL = "cancel"
    RETRY = "retry"
    DEGRADE = "degrade"
    SHED = "shed"
    ESCALATE = "escalate"
    TERMINATE = "terminate"
    FAIL = "fail"


@dataclass(frozen=True)
class Event:
    nonce: str
    child: str
    tick: int
    requested: int
    kind: Action
    alternative: int = 0
    optional: bool = False


SCHEMA = """
CREATE TABLE parent (hard INTEGER NOT NULL, tick INTEGER NOT NULL);
CREATE TABLE child (name TEXT PRIMARY KEY, hard INTEGER NOT NULL,
                    state TEXT NOT NULL, reopen INTEGER NOT NULL);
CREATE TABLE claims (nonce TEXT PRIMARY KEY, child TEXT NOT NULL,
                     reserved INTEGER NOT NULL, settled INTEGER);
CREATE TABLE receipts (nonce TEXT PRIMARY KEY, request TEXT NOT NULL, result TEXT NOT NULL);
INSERT INTO parent VALUES (10, 0);
INSERT INTO child VALUES ('A', 7, 'active', 0), ('B', 6, 'active', 0);
"""


def encode(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def link(event):
    return sha256(encode(asdict(event))).hexdigest()


def database(path, timeout=10):
    return sqlite3.connect(path, isolation_level=None, timeout=timeout)


def initialize(path):
    with closing(database(path)) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        db.executescript(SCHEMA)


def usage(db, child=None):
    select = "SELECT COALESCE(SUM(COALESCE(settled, reserved)),0) FROM claims"
    if child is None:
        return db.execute(select).fetchone()[0]
    return db.execute(select + " WHERE child=?", (child,)).fetchone()[0]


def reserve(db, event, maximum, child_hard, parent_hard):
    if maximum < 0 or maximum > event.requested:
        return "invalid-reservation"
    if usage(db, event.child) + maximum > child_hard:
        return "child-hard-limit"
    if usage(db) + maximum > parent_hard:
        return "parent-hard-limit"
    db.execute("INSERT INTO claims VALUES (?, ?, ?, NULL)", (event.nonce, event.child, maximum))
    return "reserved"


def decide(db, event, child_hard, state, reopen, parent_hard):
    match event.kind:
        case Action.CONTINUE | Action.DEGRADE:
            if state in ("cancelled", "terminated", "paused"):
                return "scope-closed-or-paused"
            if event.tick < reopen:
                return "rate-limit-active"
            if event.kind == Action.CONTINUE:
                return reserve(db, event, event.requested, child_hard, parent_hard)
            if not 0 <= event.alternative < event.requested:
                return "invalid-degradation"
            return reserve(db, event, event.alternative, child_hard, parent_hard)
        case Action.THROTTLE:
            if state != "active":
                return "scope-unavailable"
            if event.alternative <= event.tick:
                return "invalid-reopen-time"
            db.execute("UPDATE child SET reopen = MAX(reopen, ?) WHERE name = ?",
                       (event.alternative, event.child))
            return "throttled"
        case Action.PAUSE | Action.CANCEL | Action.TERMINATE:
            if state == "terminated":
                return "already-terminated"
            if state == "cancelled" and event.kind != Action.TERMINATE:
                return "already-cancelled"
            target = {Action.PAUSE: "paused", Action.CANCEL: "cancelled",
                      Action.TERMINATE: "terminated"}[event.kind]
            db.execute("UPDATE child SET state = ? WHERE name = ?", (target, event.child))
            return target
        case Action.RETRY:
            if state in ("cancelled", "terminated"):
                return "scope-closed"
            if event.tick < reopen:
                return "rate-limit-active"
            db.execute("UPDATE child SET state = 'active' WHERE name = ?", (event.child,))
            return "retry-ready"
        case Action.SHED:
            return "shed-optional" if event.optional else "required-work"
        case Action.ESCALATE:
            return "await-parent-policy"
        case Action.FAIL:
            return "handler-failed"


def apply_open(db, event):
    request = link(event)
    prior = db.execute("SELECT request,result FROM receipts WHERE nonce=?", (event.nonce,)).fetchone()
    if prior:
        return prior[1] if prior[0] == request else "event-scope-mismatch"
    parent_hard, tick = db.execute("SELECT hard,tick FROM parent").fetchone()
    if event.tick < tick:
        return "clock-went-backward"
    child_hard, state, reopen = db.execute(
        "SELECT hard,state,reopen FROM child WHERE name=?", (event.child,)
    ).fetchone()
    result = decide(db, event, child_hard, state, reopen, parent_hard)
    assert result is not None
    db.execute("UPDATE parent SET tick=?", (event.tick,))
    db.execute("INSERT INTO receipts VALUES (?,?,?)", (event.nonce, request, result))
    assert usage(db) <= parent_hard and usage(db, event.child) <= child_hard
    return result


def apply(path, event, *, interrupt=False):
    with closing(database(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        result = apply_open(db, event)
        if interrupt:
            assert result == "reserved"
            os._exit(55)
        db.commit()
        return result


def settle(path, nonce, actual):
    with closing(database(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        maximum, previous = db.execute("SELECT reserved,settled FROM claims WHERE nonce=?", (nonce,)).fetchone()
        if not 0 <= actual <= maximum:
            return "settlement-out-of-scope"
        if previous is not None:
            return "already-settled" if previous == actual else "settlement-conflict"
        db.execute("UPDATE claims SET settled=? WHERE nonce=?", (actual, nonce))
        db.commit()
    return "settled"


def inspect(path):
    with closing(database(path)) as db:
        sizes = [usage(db), usage(db, "A"), usage(db, "B")]
        claims = db.execute("SELECT count(*) FROM claims").fetchone()[0]
        receipts = db.execute("SELECT count(*) FROM receipts").fetchone()[0]
        return {"charged_and_held": sizes, "claims": claims, "receipts": receipts}


def invocation(path, event, work, mode, marker=None):
    request = work / "event.json"
    request.write_bytes(encode(asdict(event)))
    return [sys.executable, __file__, "--child", str(path), str(request), mode,
            "" if marker is None else str(marker)]


def study(work):
    path = work / "quota.db"
    initialize(path)
    rows = []
    root_event = Event("A-first", "A", 0, 6, Action.CONTINUE)

    def check(name, expected, callback):
        outcome = callback()
        assert outcome == expected, (name, outcome)
        rows.append({"case": name, "decision": outcome, **inspect(path)})

    before = inspect(path)
    aborted = subprocess.run(invocation(path, root_event, work, "abort"),
                             capture_output=True, check=False)
    assert aborted.returncode == 55 and not aborted.stdout and not aborted.stderr
    assert inspect(path) == before
    rows.append({"case": "exit before durable decision", "decision": "neither-committed", **before})

    competitor = Event("B-first", "B", 0, 6, Action.CONTINUE)
    marker = work / "waiting"
    with closing(database(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        child = subprocess.Popen(invocation(path, competitor, work, "race", marker),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists():
                assert time.monotonic() < deadline and child.poll() is None
                time.sleep(0.01)
            assert apply_open(db, root_event) == "reserved"
            db.commit()
            stdout, stderr = child.communicate(timeout=10)
            assert child.returncode == 0 and stdout == b"parent-hard-limit\n" and not stderr
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
    rows.append({"case": "two individually admissible writers", "decision": "parent-hard-limit", **inspect(path)})
    assert inspect(path)["charged_and_held"] == [6, 6, 0]
    check("exact replay holds once", "reserved", lambda: apply(path, root_event))
    check("event reused with changed request", "event-scope-mismatch",
          lambda: apply(path, replace(root_event, requested=5)))
    check("settlement cannot exceed hold", "settlement-out-of-scope",
          lambda: settle(path, root_event.nonce, 7))
    with (work / "native-output").open("wb", buffering=0) as sink:
        count = sink.write(b"data")
        assert count == 4
    check("native four-byte settlement", "settled", lambda: settle(path, root_event.nonce, count))
    check("repeated settlement", "already-settled", lambda: settle(path, root_event.nonce, count))
    check("changed settlement", "settlement-conflict", lambda: settle(path, root_event.nonce, 3))

    def event(label, child, tick, requested, action, expected, **options):
        selected = Event(label, child, tick, requested, action, **options)
        check(label, expected, lambda: apply(path, selected))

    event("throttle", "B", 1, 0, Action.THROTTLE, "throttled", alternative=3)
    event("throttled before boundary", "B", 2, 1, Action.CONTINUE, "rate-limit-active")
    event("retry at boundary", "B", 3, 0, Action.RETRY, "retry-ready")
    event("pause", "B", 3, 0, Action.PAUSE, "paused")
    event("pause blocks new budget", "B", 3, 1, Action.CONTINUE, "scope-closed-or-paused")
    event("explicit resume", "B", 4, 0, Action.RETRY, "retry-ready")
    event("cannot exceed delegated child cap", "B", 4, 7, Action.CONTINUE, "child-hard-limit")
    event("degrade", "B", 4, 9, Action.DEGRADE, "reserved", alternative=3)
    assert inspect(path)["charged_and_held"] == [7, 4, 3]
    event("cancel", "B", 5, 1, Action.CANCEL, "cancelled")
    assert inspect(path)["charged_and_held"] == [7, 4, 3]
    event("cancel prevents new admission", "B", 5, 1, Action.CONTINUE, "scope-closed-or-paused")
    check("terminal partial work retained", "settled", lambda: settle(path, "degrade", 2))
    assert inspect(path)["charged_and_held"] == [6, 4, 2]
    event("optional shed", "A", 5, 1, Action.SHED, "shed-optional", optional=True)
    event("required work cannot be shed", "A", 5, 1, Action.SHED, "required-work")
    event("escalate", "A", 6, 9, Action.ESCALATE, "await-parent-policy")
    event("handler fails", "A", 6, 1, Action.FAIL, "handler-failed")
    event("terminate", "A", 6, 0, Action.TERMINATE, "terminated")
    event("terminate cannot resume", "A", 6, 1, Action.RETRY, "scope-closed")
    event("clock regression", "B", 1, 0, Action.ESCALATE, "clock-went-backward")
    assert inspect(path)["charged_and_held"] == [6, 4, 2]
    return {"format": "durable-limit-handlers-01", "sqlite": sqlite3.sqlite_version,
            "rows": rows, "native_output_bytes": count}


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "--child":
        path, raw = map(Path, sys.argv[2:4])
        value = json.loads(raw.read_bytes())
        event = Event(**(value | {"kind": Action(value["kind"])}))
        mode = sys.argv[4]
        if mode == "race":
            with closing(database(path, timeout=0)) as db:
                try:
                    db.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as error:
                    assert error.sqlite_errorcode == sqlite3.SQLITE_BUSY
                else:
                    raise AssertionError("expected existing writer lock")
            Path(sys.argv[5]).touch()
        print(apply(path, event, interrupt=(mode == "abort")))
        sys.exit()
    with TemporaryDirectory(prefix="llmlang-limit-handler-") as directory:
        evidence = study(Path(directory))
    content = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
