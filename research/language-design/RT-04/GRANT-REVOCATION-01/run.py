#!/usr/bin/env python3
"""Compare scoped grant revocation and effect commit across real SQLite processes."""

import argparse
from contextlib import closing
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import select
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
POLICIES = ("cached", "child_only", "ancestors", "global_epoch", "wal_upgrade")
SCENARIOS = ("unchanged", "ancestor_before", "ancestor_during", "child_during",
             "unrelated_during", "reissued_during", "ancestor_after", "wrong_issuer", "outside_scope")

SCHEMA = """
CREATE TABLE epoch (id INTEGER PRIMARY KEY CHECK(id = 1), revision INTEGER NOT NULL);
INSERT INTO epoch VALUES (1, 0);
CREATE TABLE grant_state (
    name TEXT PRIMARY KEY,
    parent TEXT,
    issuer TEXT NOT NULL,
    holder TEXT NOT NULL,
    prefix TEXT NOT NULL,
    live INTEGER NOT NULL CHECK(live IN (0, 1)),
    revision INTEGER NOT NULL
);
CREATE TABLE effects (
    operation TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    ancestor_revision INTEGER NOT NULL,
    child_revision INTEGER NOT NULL
);
"""


def connection(path):
    return sqlite3.connect(path, timeout=3, isolation_level=None)


def setup(db, scenario):
    assert db.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    db.executescript(SCHEMA)
    issuer = "unexpected-authority" if scenario == "wrong_issuer" else "authority-A"
    db.executemany(
        "INSERT INTO grant_state VALUES (?, ?, ?, ?, ?, 1, 1)",
        (
            ("root", None, issuer, "workspace-owner", "org/demo"),
            ("child", "root", "workspace-owner", "worker", "org/demo/src"),
            ("other", None, "authority-A", "other-owner", "org/else"),
        ),
    )


def covers(prefix, target):
    return target == prefix or target.startswith(prefix + "/")


def snapshot(db, target):
    epoch, = db.execute("SELECT revision FROM epoch").fetchone()
    records = {row[0]: row[1:] for row in db.execute(
        "SELECT name,parent,issuer,holder,prefix,live,revision FROM grant_state"
        " WHERE name IN ('root','child')"
    )}
    root_parent, root_issuer, owner, root_scope, root_live, root_version = records["root"]
    child_parent, child_issuer, child_holder, child_scope, child_live, child_version = records["child"]

    allowed = (root_parent is None and root_issuer == "authority-A" and bool(root_live)
               and child_parent == "root" and child_issuer == owner and child_holder == "worker"
               and bool(child_live) and covers(root_scope, child_scope) and covers(child_scope, target))
    return {"allowed": allowed, "versions": [root_version, child_version], "epoch": epoch,
            "child_live": bool(child_live)}


def update(db, grant, live):
    db.execute("BEGIN IMMEDIATE")
    try:
        cursor = db.execute("UPDATE grant_state SET live=?, revision=revision+1 WHERE name=?",
                            (live, grant))
        assert cursor.rowcount == 1
        db.execute("UPDATE epoch SET revision=revision+1 WHERE id=1")
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def install(db, target, initial):
    db.execute("INSERT INTO effects VALUES ('op-1', ?, ?, ?)", (target, *initial["versions"]))


def latest_publish(db, target, initial, policy):
    db.execute("BEGIN IMMEDIATE")
    current = snapshot(db, target)
    exact = current["allowed"] and current["versions"] == initial["versions"]
    if policy == "cached":
        allowed = True
    elif policy == "child_only":
        allowed = current["child_live"] and current["versions"][1] == initial["versions"][1]
    elif policy == "global_epoch":
        allowed = exact and initial["epoch"] == current["epoch"]
    else:
        allowed = exact

    if allowed:
        install(db, target, initial)
        db.execute("COMMIT")
    else:
        db.execute("ROLLBACK")
    return allowed


def worker(path, policy, target):
    with closing(connection(path)) as db:
        db.execute("BEGIN")
        initial = snapshot(db, target)
        if policy != "wal_upgrade":
            db.execute("COMMIT")
        print(json.dumps(initial), flush=True)
        if sys.stdin.readline() != "publish\n":
            raise ValueError("Expected publication barrier")

        busy_snapshot = False
        if not initial["allowed"]:
            if db.in_transaction:
                db.execute("ROLLBACK")
            committed = False
        elif policy == "wal_upgrade":
            try:
                install(db, target, initial)
            except sqlite3.OperationalError as error:
                if error.sqlite_errorname != "SQLITE_BUSY_SNAPSHOT":
                    raise
                busy_snapshot = True
                db.execute("ROLLBACK")
                committed = latest_publish(db, target, initial, "ancestors")
            else:
                db.execute("COMMIT")
                committed = True
        else:
            committed = latest_publish(db, target, initial, policy)
        print(json.dumps({"committed": committed, "busy_snapshot": busy_snapshot}), flush=True)


def reply(process):
    ready, _, _ = select.select([process.stdout], [], [], 5)
    if not ready:
        raise TimeoutError("No response from worker")
    line = process.stdout.readline()
    if not line:
        raise RuntimeError(process.stderr.read())
    return json.loads(line)


def change(db, scenario):
    match scenario:
        case "ancestor_before" | "ancestor_during" | "ancestor_after":
            update(db, "root", 0)
        case "child_during":
            update(db, "child", 0)
        case "unrelated_during":
            update(db, "other", 0)
        case "reissued_during":
            update(db, "root", 0)
            update(db, "root", 1)
        case _:
            raise ValueError(f"Unexpected change {scenario}")


BETWEEN = {"ancestor_during", "child_during", "unrelated_during", "reissued_during"}
INVALID_AT_READ = {"ancestor_before", "wrong_issuer", "outside_scope"}
STALE_FOR_EFFECT = {"ancestor_during", "child_during", "reissued_during"}


def oracle(scenario, policy):
    """Expected end state under each protocol, independent of database operations."""
    ready = scenario not in INVALID_AT_READ
    stale = scenario in STALE_FOR_EFFECT
    if policy == "cached":
        committed = ready
    elif policy == "child_only":
        committed = ready and scenario != "child_during"
    else:
        committed = ready and not stale and (scenario != "unrelated_during" or policy != "global_epoch")
    return ready, committed, policy == "wal_upgrade" and scenario in BETWEEN


def scenario_run(scenario, policy):
    with TemporaryDirectory(prefix="llmlang-grant-revoke-") as temporary:
        path = Path(temporary) / "authority.db"
        with closing(connection(path)) as db:
            setup(db, scenario)
            if scenario == "ancestor_before":
                change(db, scenario)
            target = "org/demo/src-other/file" if scenario == "outside_scope" else "org/demo/src/file"

            with subprocess.Popen(
                [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(path), policy, target],
                text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ) as child:
                try:
                    initial = reply(child)
                    if scenario in BETWEEN:
                        change(db, scenario)
                    before_publication = snapshot(db, target)
                    child.stdin.write("publish\n")
                    child.stdin.flush()
                    published = reply(child)
                    result = child.wait(timeout=5)
                    assert result == 0 and not child.stderr.read()
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=5)

            if scenario == "ancestor_after":
                change(db, scenario)
        with closing(connection(path)) as fresh:
            effects = [list(row) for row in fresh.execute(
                "SELECT operation,target,ancestor_revision,child_revision FROM effects"
            )]
            final = snapshot(fresh, target)

    ready, committed, busy = oracle(scenario, policy)
    assert (initial["allowed"], published["committed"], published["busy_snapshot"]) == (ready, committed, busy)
    if committed:
        assert effects == [["op-1", target, *initial["versions"]]]
    else:
        assert not effects
    authorized = ready and scenario not in STALE_FOR_EFFECT
    assert authorized == (
        before_publication["allowed"] and initial["versions"] == before_publication["versions"]
    )
    return {
        "scenario": scenario, "policy": policy, "target": target, "initial": initial,
        "before_publication": before_publication, "final": final, **published, "effects": effects,
        "false_admission": committed and not authorized, "false_refusal": authorized and not committed,
    }


def main():
    if sqlite3.sqlite_version != "3.53.1":
        raise ValueError("Expected pinned SQLite 3.53.1")
    rows = [scenario_run(scenario, policy) for policy, scenario in product(POLICIES, SCENARIOS)]
    counts = {}
    for policy in POLICIES:
        matched = [row for row in rows if row["policy"] == policy]
        counts[policy] = {field: sum(row[field] for row in matched)
                          for field in ("committed", "false_admission", "false_refusal", "busy_snapshot")}
    print(json.dumps({
        "schema": "llmlang-concurrent-grant-revocation/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "process_pairs": len(rows), "counts": counts, "runs": rows,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=3, metavar=("DB", "POLICY", "TARGET"))
    options = parser.parse_args()
    if options.worker is None:
        main()
    else:
        worker(*options.worker)
