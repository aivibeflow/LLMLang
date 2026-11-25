#!/usr/bin/env python3
"""Check exact external-effect recovery after native process interruption."""

import argparse
from contextlib import ExitStack, closing, contextmanager
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

POLICIES = ("receipt_only", "name_only", "exact")
SCENARIOS = ("clean", "exit_before_link", "exit_after_link", "revoked_after_link",
             "collision_payload", "collision_operation", "collision_revision", "revoked_before_link")
COLLISIONS = {
    "collision_payload": {"payload": "substitute"},
    "collision_operation": {"operation": "other-operation"},
    "collision_revision": {"authority_revision": 2},
}
VALID_FILE = {"clean", "exit_after_link", "revoked_after_link"}
ENVELOPE = {"operation": "op-1", "authority_revision": 1, "payload": "expected bytes"}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(raw):
    return sha256(raw).hexdigest()


EXPECTED = digest(canonical(ENVELOPE))


def database(directory):
    return sqlite3.connect(directory / "authority.db", isolation_level=None, timeout=5)


def setup(directory, scenario):
    with closing(database(directory)) as db:
        mode = db.execute("PRAGMA journal_mode=WAL").fetchone()
        assert mode == ("wal",)
        db.executescript("""
          CREATE TABLE authority (name TEXT PRIMARY KEY, revision INTEGER, live INTEGER);
          INSERT INTO authority VALUES ('owner', 1, 1);
          CREATE TABLE intent (operation TEXT PRIMARY KEY, authority_revision INTEGER, artifact_sha TEXT);
          CREATE TABLE receipt (operation TEXT PRIMARY KEY, artifact_sha TEXT, disposition TEXT);
        """)
        db.execute("INSERT INTO intent VALUES ('op-1',1,?)", (EXPECTED,))
    if scenario in COLLISIONS:
        (directory / "op-1.object").write_bytes(canonical({**ENVELOPE, **COLLISIONS[scenario]}))


def revoke(directory):
    with closing(database(directory)) as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("UPDATE authority SET revision=revision+1,live=0 WHERE name='owner' AND live=1")
        assert cursor.rowcount == 1
        db.execute("COMMIT")


def send(value):
    print(value, flush=True)


def await_signal(action):
    if sys.stdin.readline() != action + "\n":
        raise RuntimeError(f"Expected barrier {action}")


def publish(directory):
    with closing(database(directory)) as db:
        db.execute("BEGIN IMMEDIATE")
        operation, required, expected = db.execute("SELECT * FROM intent").fetchone()
        revision, live = db.execute("SELECT revision,live FROM authority").fetchone()
        if not live or required != revision:
            db.execute("ROLLBACK")
            send("authority_refused")
            return
        assert operation == ENVELOPE["operation"] and digest(canonical(ENVELOPE)) == expected
        send("ready")
        await_signal("link")

        staged = directory / "staged.object"
        staged.write_bytes(canonical(ENVELOPE))
        try:
            os.link(staged, directory / "op-1.object")
        except FileExistsError:
            db.execute("ROLLBACK")
            send("name_conflict")
            return
        finally:
            staged.unlink()
        send("linked")
        await_signal("receipt")
        db.execute("INSERT INTO receipt VALUES (?,?,'published')", (operation, expected))
        db.execute("COMMIT")
        send("receipt")


def recover(directory, policy):
    send("ready")
    await_signal("recover")
    with closing(database(directory)) as db:
        db.execute("BEGIN IMMEDIATE")
        operation, _, expected = db.execute("SELECT * FROM intent").fetchone()
        if db.execute("SELECT artifact_sha FROM receipt WHERE operation=?", (operation,)).fetchone():
            db.execute("ROLLBACK")
            send("existing")
            return

        object_path = directory / f"{operation}.object"
        try:
            present = object_path.read_bytes()
        except FileNotFoundError:
            present = None
        if (policy == "receipt_only" or present is None
                or (policy == "exact" and digest(present) != expected)):
            db.execute("ROLLBACK")
            send("unresolved")
            return

        receipt_sha = digest(present)
        db.execute("INSERT INTO receipt VALUES (?,?,'observed')", (operation, receipt_sha))
        db.execute("COMMIT")
        send("observed")


@contextmanager
def process(directory, mode):
    with subprocess.Popen(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--child", str(directory), mode],
        text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ) as child:
        try:
            yield child
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


def read(child):
    ready, _, _ = select.select([child.stdout], [], [], 5)
    if not ready:
        raise TimeoutError("Process barrier did not arrive")
    result = child.stdout.readline()
    if not result:
        raise RuntimeError(child.stderr.read())
    return result.strip()


def trigger(child, action):
    child.stdin.write(action + "\n")
    child.stdin.flush()


def expect_exit(child, expected):
    result = child.wait(timeout=5)
    diagnostics = child.stderr.read()
    assert result == expected and not diagnostics, (result, diagnostics)


def publisher_run(directory, scenario):
    with process(directory, "publish") as child:
        initial = read(child)
        if initial == "authority_refused":
            assert scenario == "revoked_before_link"
            expect_exit(child, 0)
            return "authority_refused"
        if initial != "ready":
            raise ValueError(initial)
        if scenario == "exit_before_link":
            child.kill()
            expect_exit(child, -signal.SIGKILL)
            return "killed_before_link"

        trigger(child, "link")
        phase = read(child)
        if phase == "name_conflict":
            assert scenario in COLLISIONS
            expect_exit(child, 0)
            return "name_conflict"
        assert phase == "linked"
        if scenario in {"exit_after_link", "revoked_after_link", "concurrent_recovery"}:
            child.kill()
            expect_exit(child, -signal.SIGKILL)
            return "killed_after_link"

        trigger(child, "receipt")
        receipt = read(child)
        assert receipt == "receipt"
        expect_exit(child, 0)
        return "published"


def recovery_run(directory, policy, clients):
    with ExitStack() as stack:
        children = [stack.enter_context(process(directory, policy)) for _ in range(clients)]
        for child in children:
            ready = read(child)
            assert ready == "ready"
        for child in children:
            trigger(child, "recover")
        results = sorted(read(child) for child in children)
        for child in children:
            expect_exit(child, 0)
        return results


def trial(directory, scenario, policy, clients=1):
    setup(directory, scenario)
    if scenario == "revoked_before_link":
        revoke(directory)
    publication = publisher_run(directory, scenario)
    if scenario in {"revoked_after_link", "concurrent_recovery"}:
        revoke(directory)
    expected_file = scenario in VALID_FILE or scenario == "concurrent_recovery"
    artifact = directory / "op-1.object"
    original = artifact.read_bytes() if artifact.exists() else None
    content = digest(original) if original is not None else None
    assert (content == EXPECTED) == expected_file

    dispositions = recovery_run(directory, policy, clients)
    restored = artifact.read_bytes() if artifact.exists() else None
    assert restored == original

    with closing(database(directory)) as db:
        receipts = [list(row) for row in db.execute("SELECT * FROM receipt")]
        authority = list(db.execute("SELECT revision,live FROM authority").fetchone())
    if clients > 1:
        assert dispositions == ["existing", "observed"]
    elif scenario == "clean":
        assert dispositions == ["existing"]
    else:
        recovered = ((policy == "exact" and expected_file)
                     or (policy == "name_only" and (expected_file or scenario in COLLISIONS)))
        assert dispositions == (["observed"] if recovered else ["unresolved"])

    if "observed" in dispositions:
        assert receipts == [["op-1", content, "observed"]]
    elif dispositions == ["existing"]:
        assert receipts == [["op-1", EXPECTED, "published"]]
    else:
        assert not receipts
    return {
        "scenario": scenario, "policy": policy, "publisher": publication, "authority": authority,
        "object_sha256": content, "recovery": dispositions, "receipts": receipts,
        "false_receipt": bool(receipts) and not expected_file,
        "eligible_unresolved": not receipts and expected_file,
    }


def run():
    if sys.platform != "linux" or sqlite3.sqlite_version != "3.53.1":
        raise ValueError("Expected Linux and SQLite 3.53.1")
    rows = []
    for scenario, policy in product(SCENARIOS, POLICIES):
        with TemporaryDirectory(prefix="llmlang-external-effect-recovery-") as work:
            rows.append(trial(Path(work), scenario, policy))
    with TemporaryDirectory(prefix="llmlang-external-effect-recovery-") as work:
        concurrent = trial(Path(work), "concurrent_recovery", "exact", clients=2)
    counts = {}
    for policy in POLICIES:
        selected = [row for row in rows if row["policy"] == policy]
        counts[policy] = {
            "receipts": sum(bool(row["receipts"]) for row in selected),
            "false_receipts": sum(row["false_receipt"] for row in selected),
            "eligible_unresolved": sum(row["eligible_unresolved"] for row in selected),
        }
    return {
        "schema": "llmlang-external-receipt-recovery/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "kernel": platform.release(),
        "filesystem": subprocess.check_output(["stat", "-f", "-c", "%T", gettempdir()],
                                              text=True, timeout=5).strip(),
        "runner_sha256": digest(Path(__file__).read_bytes()), "exact_object_sha256": EXPECTED,
        "completed_schedules": len(rows), "counts": counts, "runs": rows, "concurrent": concurrent,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", nargs=2)
    args = parser.parse_args()
    if args.child is None:
        print(json.dumps(run(), indent=2))
    else:
        location, mode = args.child
        if mode == "publish":
            publish(Path(location))
        elif mode in POLICIES:
            recover(Path(location), mode)
        else:
            raise ValueError(f"Unknown recovery policy {mode}")
