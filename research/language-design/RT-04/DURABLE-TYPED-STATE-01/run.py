#!/usr/bin/env python3
"""Check scope-qualified typed state transitions, atomic receipts and retries."""

from contextlib import closing
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

CATALOG = """
CREATE TABLE live (
    name TEXT PRIMARY KEY, owner TEXT NOT NULL, incarnation INTEGER NOT NULL,
    generation INTEGER NOT NULL, phase TEXT NOT NULL, result INTEGER
);
CREATE TABLE receipts (
    nonce TEXT PRIMARY KEY, request TEXT NOT NULL, after BLOB NOT NULL
);
"""
STORE = "fixture-state-store/1"
SLOT = "job"


@dataclass(frozen=True)
class Permit:
    store: str
    slot: str
    owner: str
    incarnation: int
    generation: int
    phase: str


@dataclass(frozen=True)
class Request:
    nonce: str
    permit: Permit
    amount: int


def encode(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def identity(record):
    return sha256(encode(record)).hexdigest()


def open_db(path, timeout=10):
    return sqlite3.connect(path, isolation_level=None, timeout=timeout)


def initialize(path):
    with closing(open_db(path)) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.executescript(CATALOG)
        connection.execute("INSERT INTO live VALUES (?, 'owner-A', 1, 0, 'open', NULL)", (SLOT,))


def current(connection):
    return connection.execute(
        "SELECT owner, incarnation, generation, phase, result FROM live WHERE name = ?", (SLOT,)
    ).fetchone()


def transition(connection, request):
    permit = request.permit
    if permit.store != STORE or permit.slot != SLOT:
        return "invalid-store-or-slot"
    subject = identity(asdict(request))
    row = connection.execute("SELECT request, after FROM receipts WHERE nonce = ?", (request.nonce,)).fetchone()
    live = current(connection)
    if row is not None:
        saved, snapshot = row
        if saved != subject:
            return "nonce-scope-mismatch"
        return "retry-current" if tuple(json.loads(snapshot)) == live else "retry-historical"
    if type(request.amount) is not int or not 0 <= request.amount <= 255:
        return "value-out-of-range"
    if permit.owner != live[0]:
        return "wrong-owner"
    if permit.incarnation != live[1]:
        return "stale-incarnation"
    if permit.generation != live[2]:
        return "stale-generation"
    if permit.phase != "open" or live[3] != "open":
        return "invalid-phase"
    if permit.generation == 2**63 - 1:
        return "generation-exhausted"
    new_state = (permit.owner, permit.incarnation, permit.generation + 1,
                 "sealed", request.amount)
    connection.execute(
        "UPDATE live SET owner=?, incarnation=?, generation=?, phase=?, result=? WHERE name=?",
        (*new_state, permit.slot),
    )
    connection.execute("INSERT INTO receipts VALUES (?, ?, ?)",
                       (request.nonce, subject, encode(new_state)))
    return "published"


def apply(path, request, *, outcome=None):
    with closing(open_db(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        result = transition(connection, request)
        if outcome == "before":
            assert result == "published"
            os._exit(41)
        connection.commit()
        if outcome == "after":
            assert result == "published"
            os._exit(42)
        return result


def user_view(path):
    with closing(open_db(path)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        receipts = connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
        return current(connection), receipts


def schedule(work):
    path = work / "state.sqlite"
    initialize(path)
    initial = Permit(STORE, SLOT, "owner-A", 1, 0, "open")
    first = Request("first", initial, 13)
    rows = []

    def checked(label, expected, action):
        result = action()
        assert result == expected, (label, result, expected)
        state, count = user_view(path)
        rows.append({"case": label, "decision": result, "state": state, "receipts": count})

    def invocation(request, mode, marker=None):
        file = work / "request.json"
        file.write_bytes(encode(asdict(request)))
        return [sys.executable, __file__, "--child", str(path), str(file), mode,
                "" if marker is None else str(marker)]

    checked("wrong store scope", "invalid-store-or-slot",
            lambda: apply(path, replace(first, permit=replace(initial, store="other"))))
    checked("wrong owner at same generation", "wrong-owner",
            lambda: apply(path, replace(first, permit=replace(initial, owner="owner-B"))))
    checked("wrong typestate", "invalid-phase",
            lambda: apply(path, replace(first, permit=replace(initial, phase="sealed"))))
    checked("out of constrained value domain", "value-out-of-range",
            lambda: apply(path, replace(first, amount=256)))

    for when, code, expected in (("before", 41, "not-committed"), ("after", 42, "committed")):
        halted = subprocess.run(invocation(first, when), check=False, capture_output=True)
        assert halted.returncode == code and not halted.stderr and not halted.stdout
        state, count = user_view(path)
        assert (count, state[-1]) == ((0, None) if when == "before" else (1, 13))
        rows.append({"case": "exit-" + when, "decision": expected, "exit": code,
                     "state": state, "receipts": count})

    checked("same request retry after commit", "retry-current", lambda: apply(path, first))
    checked("nonce with altered payload", "nonce-scope-mismatch",
            lambda: apply(path, replace(first, amount=17)))
    checked("new nonce with stale phase generation", "stale-generation",
            lambda: apply(path, replace(first, nonce="different")))

    # Model an administrative refill as an explicit fresh identity in the
    # same named slot. The old receipt remains historical.
    with closing(open_db(path)) as connection:
        connection.execute("UPDATE live SET incarnation=2, generation=0, phase='open', result=NULL")
    checked("old exact request retrieves historical receipt only", "retry-historical",
            lambda: apply(path, first))
    checked("ABA control with same slot and generation", "stale-incarnation",
            lambda: apply(path, replace(first, nonce="old-incarnation")))

    live = replace(initial, incarnation=2)
    winner = Request("winning-transition", live, 21)
    competitor = Request("competing-transition", live, 34)
    marker = work / "busy-observed"
    with closing(open_db(path)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        contender = subprocess.Popen(invocation(competitor, "race", marker),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists():
                assert contender.poll() is None and time.monotonic() < deadline
                time.sleep(0.01)
            assert transition(writer, winner) == "published"
            writer.commit()
            stdout, stderr = contender.communicate(timeout=10)
            assert contender.returncode == 0 and stdout == b"stale-generation\n" and not stderr
            state, count = user_view(path)
            assert state == ("owner-A", 2, 1, "sealed", 21) and count == 2
        finally:
            if contender.poll() is None:
                contender.kill()
                contender.communicate()
    rows.append({"case": "actual competing writer", "decision": "only-first-published",
                 "state": state, "receipts": count})
    checked("winner retry confirms same durable receipt", "retry-current", lambda: apply(path, winner))
    checked("other owner cannot retrieve receipt under same nonce", "nonce-scope-mismatch",
            lambda: apply(path, replace(winner, permit=replace(live, owner="owner-B"))))

    with closing(open_db(path)) as connection:
        connection.execute("UPDATE live SET incarnation=3, generation=?, phase='open', result=NULL", (2**63 - 1,))
    exhausted = Request("exhausted", replace(initial, incarnation=3, generation=2**63 - 1), 0)
    checked("representable generation exhausted", "generation-exhausted", lambda: apply(path, exhausted))
    return {"format": "durable-typed-state-01", "sqlite": sqlite3.sqlite_version, "rows": rows}


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "--child":
        path, exchange = map(Path, sys.argv[2:4])
        item = json.loads(exchange.read_bytes())
        request = Request(item["nonce"], Permit(**item["permit"]), item["amount"])
        mode = sys.argv[4]
        if mode == "race":
            with closing(open_db(path, timeout=0)) as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as error:
                    assert error.sqlite_errorcode == sqlite3.SQLITE_BUSY
                else:
                    raise AssertionError("expected competing transaction lock")
            Path(sys.argv[5]).touch()
        print(apply(path, request, outcome=mode))
        sys.exit()
    with TemporaryDirectory(prefix="llmlang-typed-state-") as work:
        evidence = schedule(Path(work))
    content = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
