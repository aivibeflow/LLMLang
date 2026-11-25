#!/usr/bin/env python3
"""Compare revocation placement and authority fences around an external file effect."""

import argparse
from contextlib import ExitStack, closing
import fcntl
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import select
import signal
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory, gettempdir

POLICIES = ("cached", "fresh", "leaf_lock", "ancestry_lock", "db_writer")
CASES = ("no_change", "already_revoked", "ancestor_before_check", "ancestor_after_check",
         "child_after_check", "unrelated_after_check", "uncoordinated_ancestor",
         "killed_before_replace", "killed_after_replace")
AFTER_CHECK = {"ancestor_after_check": "root", "child_after_check": "child",
               "unrelated_after_check": "other", "uncoordinated_ancestor": "root"}
EARLY = {"already_revoked", "ancestor_before_check"}
CRASH = {"killed_before_replace", "killed_after_replace"}
PROFILE = {
    "cached": (), "fresh": (), "leaf_lock": ("child",),
    "ancestry_lock": ("root", "child"), "db_writer": (),
}


def db_at(directory, timeout=3):
    return sqlite3.connect(directory / "authority.db", timeout=timeout, isolation_level=None)


def setup(directory):
    with closing(db_at(directory)) as connection:
        journal = connection.execute("PRAGMA journal_mode=WAL").fetchone()
        assert journal == ("wal",)
        connection.executescript("""
          CREATE TABLE grants (name TEXT PRIMARY KEY, present INTEGER, revision INTEGER);
          INSERT INTO grants VALUES ('root',1,1), ('child',1,1), ('other',1,1);
          CREATE TABLE receipts (operation TEXT PRIMARY KEY, root INTEGER, child INTEGER);
        """)
    for name in ("root", "child", "other"):
        (directory / f"{name}.lock").touch()


def state(connection):
    grants = {key: (bool(live), version) for key, live, version in connection.execute(
        "SELECT name,present,revision FROM grants WHERE name IN ('root','child')"
    )}
    root, child = grants["root"], grants["child"]
    return {"allowed": root[0] and child[0], "revisions": [root[1], child[1]]}


def take_lock(stack, directory, grant):
    lock = stack.enter_context((directory / f"{grant}.lock").open("rb"))
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def revoke(directory, grant, cooperative=True):
    with ExitStack() as stack:
        if cooperative:
            try:
                take_lock(stack, directory, grant)
            except BlockingIOError:
                return "advisory_blocked"
        connection = stack.enter_context(closing(db_at(directory, timeout=0)))
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            if error.sqlite_errorname != "SQLITE_BUSY":
                raise
            return "sqlite_writer_blocked"
        changed = connection.execute(
            "UPDATE grants SET present=0, revision=revision+1 WHERE name=? AND present=1", (grant,)
        )
        assert changed.rowcount == 1
        connection.execute("COMMIT")
        return "revoked"


def committed_revocation(directory, grant):
    result = revoke(directory, grant)
    assert result == "revoked"


def send(row):
    print(json.dumps(row), flush=True)


def await_step(expected):
    if sys.stdin.readline() != expected + "\n":
        raise RuntimeError(f"Expected barrier {expected}")


def write_effect(directory, initial):
    temporary = directory / "staged.tmp"
    temporary.write_text(json.dumps({"operation": "op-1", "revisions": initial["revisions"]}) + "\n",
                         encoding="utf-8")
    os.replace(temporary, directory / "effect.json")


def worker(directory, policy):
    with ExitStack() as stack:
        database = stack.enter_context(closing(db_at(directory)))
        initial = state(database)
        send(initial)
        await_step("check")
        for grant in PROFILE[policy]:
            take_lock(stack, directory, grant)
        if policy == "db_writer":
            database.execute("BEGIN IMMEDIATE")
        latest = state(database)
        admitted = initial["allowed"] and (policy == "cached" or initial == latest)
        send({"admitted": admitted, "checked": latest})
        if not admitted:
            if database.in_transaction:
                database.execute("ROLLBACK")
            return

        await_step("write")
        write_effect(directory, initial)
        send({"phase": "replaced"})
        await_step("finish")
        if not database.in_transaction:
            database.execute("BEGIN IMMEDIATE")
        database.execute("INSERT INTO receipts VALUES ('op-1', ?, ?)", initial["revisions"])
        database.execute("COMMIT")
        send({"phase": "receipt_committed"})


def receive(child):
    ready, _, _ = select.select([child.stdout], [], [], 5)
    if not ready:
        raise TimeoutError("Worker barrier timed out")
    reply = child.stdout.readline()
    if not reply:
        raise RuntimeError(child.stderr.read())
    return json.loads(reply)


def command(child, barrier):
    child.stdin.write(barrier + "\n")
    child.stdin.flush()
    return receive(child)


def schedule_oracle(scenario, policy):
    admitted = scenario != "already_revoked" and (scenario != "ancestor_before_check" or policy == "cached")
    writer = policy == "db_writer"
    gate = policy == "ancestry_lock"
    leaf = policy == "leaf_lock"
    blocking = {
        "ancestor_after_check": "sqlite_writer_blocked" if writer else "advisory_blocked" if gate else "revoked",
        "child_after_check": "sqlite_writer_blocked" if writer else "advisory_blocked" if gate or leaf else "revoked",
        "unrelated_after_check": "sqlite_writer_blocked" if writer else "revoked",
        "uncoordinated_ancestor": "sqlite_writer_blocked" if writer else "revoked",
    }.get(scenario)
    replaced = admitted and scenario != "killed_before_replace"
    receipt = replaced and scenario != "killed_after_replace"
    stale = replaced and (scenario == "ancestor_before_check"
                          or (scenario in AFTER_CHECK and scenario != "unrelated_after_check"
                              and blocking == "revoked"))
    return admitted, blocking, replaced, receipt, stale


def run_one(scenario, policy):
    with TemporaryDirectory(prefix="llmlang-external-revocation-") as temp:
        directory = Path(temp)
        setup(directory)
        if scenario == "already_revoked":
            committed_revocation(directory, "root")
        worker_cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(directory), policy]
        with subprocess.Popen(worker_cmd, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as child:
            try:
                initial = receive(child)
                if scenario == "ancestor_before_check":
                    committed_revocation(directory, "root")
                check = command(child, "check")
                blocking = None
                if scenario in AFTER_CHECK:
                    blocking = revoke(directory, AFTER_CHECK[scenario], scenario != "uncoordinated_ancestor")
                with closing(db_at(directory)) as observer:
                    authority_before_replace = state(observer)

                if check["admitted"] and scenario != "killed_before_replace":
                    replaced = command(child, "write")
                    assert replaced == {"phase": "replaced"}
                    if scenario != "killed_after_replace":
                        completed = command(child, "finish")
                        assert completed == {"phase": "receipt_committed"}
                if scenario in CRASH:
                    child.kill()
                    expected = -signal.SIGKILL
                else:
                    expected = 0
                status = child.wait(timeout=5)
                assert status == expected and not child.stderr.read()
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)

        if blocking in {"advisory_blocked", "sqlite_writer_blocked"}:
            committed_revocation(directory, AFTER_CHECK[scenario])
        if scenario in CRASH:
            committed_revocation(directory, "root")
        effect = directory / "effect.json"
        external = json.loads(effect.read_text(encoding="utf-8")) if effect.exists() else None
        with closing(db_at(directory)) as observer:
            receipts = [list(row) for row in observer.execute("SELECT operation,root,child FROM receipts")]
            final = state(observer)

    admitted, attempt, replaced, receipt, stale = schedule_oracle(scenario, policy)
    assert check["admitted"] == admitted and blocking == attempt
    expected_effect = {"operation": "op-1", "revisions": initial["revisions"]} if replaced else None
    assert external == expected_effect
    assert receipts == ([["op-1", *initial["revisions"]]] if receipt else [])
    assert stale == (replaced and (initial != authority_before_replace))
    return {
        "scenario": scenario, "policy": policy, "initial": initial, "last_check": check,
        "revocation_attempt": blocking, "authority_before_replace": authority_before_replace,
        "final": final, "external": external, "receipts": receipts, "stale_effect": stale,
    }


def replay():
    if sys.platform != "linux" or sqlite3.sqlite_version != "3.53.1":
        raise ValueError("Expected Linux flock and SQLite 3.53.1")
    runs = [run_one(scenario, policy) for policy, scenario in product(POLICIES, CASES)]
    counts = {}
    for policy in POLICIES:
        rows = [row for row in runs if row["policy"] == policy]
        counts[policy] = {
            "replaced": sum(row["external"] is not None for row in rows),
            "stale_effects": sum(row["stale_effect"] for row in rows),
            "unrelated_revocation_postponed": sum(
                row["scenario"] == "unrelated_after_check" and row["revocation_attempt"] != "revoked"
                for row in rows
            ),
            "effect_without_receipt": sum(row["external"] is not None and not row["receipts"] for row in rows),
        }
    return {
        "schema": "llmlang-external-grant-revocation/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "kernel": platform.release(),
        "filesystem": subprocess.check_output(["stat", "-f", "-c", "%T", gettempdir()],
                                              text=True, timeout=5).strip(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "process_pairs": len(runs), "counts": counts, "runs": runs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2)
    args = parser.parse_args()
    if args.worker is None:
        print(json.dumps(replay(), indent=2))
    else:
        worker(Path(args.worker[0]), args.worker[1])
