"""Interrupt disposable SQLite-backed receipts before or after commit."""

from contextlib import contextmanager
from itertools import product
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import get_args

from rt04_backup_roles import BackupPair, permits
from rt04_cancel_receipts import Evidence, Invocation, Reservation, admits
from rt04_durable_receipts import Cut, Publication, RecoveryView, predict, recover
from sqlite_cleanup_probe import require


INTERRUPTED = 73


@contextmanager
def open_store(path):
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(path):
    with open_store(path) as db:
        db.executescript("""
            CREATE TABLE invocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                phase TEXT NOT NULL CHECK (phase IN ('pending', 'consumed')),
                CHECK (source <> destination)
            );
            CREATE TABLE effects (
                invocation INTEGER PRIMARY KEY REFERENCES invocations (id),
                live INTEGER NOT NULL CHECK (live IN (0, 1))
            );
        """)


def reserve(path, roles):
    with open_store(path) as db:
        db.execute("BEGIN IMMEDIATE")
        active = tuple(BackupPair(*row) for row in db.execute(
            "SELECT source, destination FROM invocations WHERE phase = 'pending' ORDER BY id"
        ))
        if not permits(active, roles):
            return None
        cursor = db.execute(
            "INSERT INTO invocations (source, destination, phase) VALUES (?, ?, 'pending')",
            (roles.source, roles.destination),
        )
        generation = cursor.lastrowid
        db.execute("INSERT INTO effects (invocation, live) VALUES (?, 1)", (generation,))
    return Invocation(roles, generation)


def lookup(path, subject):
    with open_store(path) as db:
        row = db.execute(
            "SELECT phase FROM invocations WHERE id = ? AND source = ? AND destination = ?",
            (subject.generation, subject.roles.source, subject.roles.destination),
        ).fetchone()
    return Evidence(subject, "consumed") if row == ("consumed",) else None


def finish(path, generation, publication, cut):
    with open_store(path) as db:
        if cut == "before_effect":
            os._exit(INTERRUPTED)
        update = db.execute("UPDATE effects SET live = 0 WHERE invocation = ?", (generation,))
        require("existing invocation to finish", update.rowcount, 1)
        if publication == "separate":
            db.commit()
        if cut == "after_effect":
            os._exit(INTERRUPTED)

        db.execute("UPDATE invocations SET phase = 'consumed' WHERE id = ?", (generation,))
        if cut == "after_record":
            os._exit(INTERRUPTED)
        db.commit()
        if cut == "after_commit":
            os._exit(INTERRUPTED)
    print("consumed")


def run_worker(*arguments):
    return subprocess.run(
        [sys.executable, "-B", __file__, *map(str, arguments)], capture_output=True, text=True, timeout=10,
    )


def reserve_in_process(path, roles):
    child = run_worker("reserve", path, roles.source, roles.destination)
    require("allocator worker exit", (child.returncode, child.stderr), (0, ""))
    result = child.stdout.strip()
    return None if result == "conflict" else Invocation(roles, int(result))


def probe(path, publication, cut):
    initialize(path)
    roles = BackupPair("a", "b")
    original = reserve_in_process(path, roles)
    if original is None:
        raise RuntimeError("fresh fixture refused the original reservation")
    child = run_worker("finish", path, original.generation, publication, cut)
    code = 0 if cut == "complete" else INTERRUPTED
    require("fixture worker exit", (child.returncode, child.stderr), (code, ""))
    require("delivered result", child.stdout.strip(), "consumed" if cut == "complete" else "")
    terminal = lookup(path, original)
    with open_store(path) as db:
        (live,) = db.execute("SELECT live FROM effects WHERE invocation = ?", (original.generation,)).fetchone()

    view = RecoveryView(bool(live), terminal is not None, child.stdout.strip() == "consumed")
    recovered = recover(Reservation(original), terminal)
    require("recovery permits the same roles", admits(recovered, roles), view.terminal_record)
    successor = reserve_in_process(path, roles)
    require("store admits a new invocation", successor is not None, view.terminal_record)
    if successor is not None:
        require("durable generation increases after release", successor.generation > original.generation, True)
        require("old evidence leaves the successor pending", recover(Reservation(successor), terminal), Reservation(successor))
        wrong_roles = BackupPair(roles.destination, roles.source)
        require("lookup binds roles as well as generation", lookup(path, Invocation(wrong_roles, original.generation)), None)
    return view


def main():
    print(f"Python sqlite3 library {sqlite3.sqlite_version}")
    with TemporaryDirectory(prefix="llmlang-receipts-") as directory:
        for publication, cut in product(get_args(Publication), get_args(Cut)):
            path = Path(directory) / f"{publication}-{cut}.sqlite"
            actual = probe(path, publication, cut)
            require((publication, cut), actual, predict(publication, cut))
            print(f"{publication}, {cut}: {actual}")


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "finish":
        _, _, filename, generation, policy, point = sys.argv
        finish(filename, int(generation), policy, point)
    elif len(sys.argv) == 5 and sys.argv[1] == "reserve":
        _, _, filename, source, destination = sys.argv
        invocation = reserve(filename, BackupPair(source, destination))
        print("conflict" if invocation is None else invocation.generation)
    else:
        main()
