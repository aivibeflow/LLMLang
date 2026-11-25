#!/usr/bin/env python3
"""Check leased graph reachability across external-CAS collection and process exit."""

from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
FILES = runpy.run_path(str(HERE.parent / "GRAPH-REPLICA-RECOVERY-01/run.py"))
closure = FILES["closure"]
encode = FILES["encode"]
digest = FILES["digest"]
stage = FILES["stage"]
RestoreError = FILES["RestoreError"]
blob_address = FILES["BASE"]["blob_address"]


@dataclass(frozen=True)
class Plan:
    epoch: int
    removable: tuple[str, ...]


class Refusal(ValueError):
    pass


class Store:
    def __init__(self, directory):
        self.directory = directory
        self.active = directory / "active"
        self.quarantine = directory / "quarantine"
        self.active.mkdir(exist_ok=True)
        self.quarantine.mkdir(exist_ok=True)

        self.catalog = directory / "catalog.sqlite"
        with closing(sqlite3.connect(self.catalog, isolation_level=None)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS revision (epoch INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS heads (name TEXT PRIMARY KEY, root TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS leases (token TEXT PRIMARY KEY, root TEXT NOT NULL);
                INSERT INTO revision (epoch) SELECT 0 WHERE NOT EXISTS(SELECT 1 FROM revision);
                COMMIT;
            """)

    @contextmanager
    def transaction(self, *, writes=True):
        with closing(sqlite3.connect(self.catalog, isolation_level=None)) as connection:
            connection.execute("BEGIN IMMEDIATE" if writes else "BEGIN")
            yield connection
            connection.commit()

    def read(self, address):
        return (self.active / address).read_bytes()

    def candidate_bytes(self, address):
        try:
            return self.read(address)
        except FileNotFoundError:
            return (self.quarantine / address).read_bytes()

    def protected(self, connection, load):
        addresses = set()
        roots = connection.execute("SELECT root FROM heads UNION SELECT root FROM leases")
        for root, in roots:
            addresses.update(closure(root, load))
        return addresses

    def publish(self, name, root):
        with self.transaction() as connection:
            closure(root, self.read)
            connection.execute(
                "INSERT INTO heads VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET root = excluded.root",
                (name, root),
            )
            connection.execute("UPDATE revision SET epoch = epoch + 1")

    def pin(self, token, root):
        with self.transaction() as connection:
            closure(root, self.read)
            connection.execute("INSERT INTO leases VALUES (?, ?)", (token, root))
            connection.execute("UPDATE revision SET epoch = epoch + 1")

    def release(self, token):
        with self.transaction() as connection:
            result = connection.execute("DELETE FROM leases WHERE token = ?", (token,))
            assert result.rowcount == 1
            connection.execute("UPDATE revision SET epoch = epoch + 1")

    def plan(self):
        with self.transaction(writes=False) as connection:
            epoch, = connection.execute("SELECT epoch FROM revision").fetchone()
            protected = self.protected(connection, self.read)
            inventory = {path.name for path in self.active.iterdir() if len(path.name) == 64}
        return Plan(epoch, tuple(sorted(inventory - protected)))

    def sweep(self, plan, *, interrupt=False):
        with self.transaction() as connection:
            current, = connection.execute("SELECT epoch FROM revision").fetchone()
            if current != plan.epoch:
                raise Refusal("stale-plan")
            live = self.protected(connection, self.read)
            if set(plan.removable) & live:
                raise Refusal("plan-touches-live-object")
            moved = 0
            for address in plan.removable:
                blob_address(address)
                source = self.active / address
                if source.exists():
                    os.replace(source, self.quarantine / address)
                    moved += 1
                    if interrupt:
                        os._exit(28)
        return moved

    def recover(self):
        with self.transaction() as connection:
            live = self.protected(connection, self.candidate_bytes)
            salvaged = 0
            removed = 0
            for item in sorted(self.quarantine.iterdir()):
                address = item.name
                if address in live and not (self.active / address).exists():
                    raw = item.read_bytes()
                    assert digest(raw) == address
                    stage(self.active, raw)
                    salvaged += 1
            assert self.protected(connection, self.read) == live
            for item in self.quarantine.iterdir():
                item.unlink()
                removed += 1
        return {"salvaged": salvaged, "removed": removed}


def experiment(root):
    store = Store(root)

    def insert(kind, value, *refs):
        raw = encode({"kind": kind, "value": value, "references": list(refs)})
        stage(store.active, raw)
        return digest(raw)

    shared = insert("contract", "common")
    old_leaf = insert("implementation", "old", shared)
    old = insert("snapshot", 1, old_leaf)
    new_leaf = insert("implementation", "new", shared)
    new = insert("snapshot", 2, new_leaf)
    orphan_one = insert("blob", "orphan-one")
    orphan_two = insert("blob", "orphan-two")
    rows = []

    def refusal(label, expected, callback):
        try:
            callback()
        except (Refusal, RestoreError) as error:
            assert str(error) == expected, (label, str(error))
            rows.append({"case": label, "decision": expected})
        else:
            raise AssertionError(label)

    store.publish("branch", old)
    before_pin = store.plan()
    store.pin("reader-1", old)
    store.pin("reader-2", old)
    refusal("new leases invalidate a stale plan", "stale-plan", lambda: store.sweep(before_pin))
    before_new_head = store.plan()
    store.publish("branch", new)
    refusal("new root invalidates a plan that could collect its closure",
            "stale-plan", lambda: store.sweep(before_new_head))
    current = store.plan()
    assert set(current.removable) == {orphan_one, orphan_two}
    refusal("a dishonest plan cannot quarantine a protected object", "plan-touches-live-object",
            lambda: store.sweep(Plan(current.epoch, (shared,))))
    rows.append({"case": "latest root and both leases pin complete graphs", "decision": "two-orphans-only"})

    plan_path = root / "pending.json"
    plan_path.write_bytes(encode(asdict(current)))
    child = subprocess.run([sys.executable, __file__, "--interrupt", str(root), str(plan_path)],
                           capture_output=True, check=False)
    assert child.returncode == 28 and not child.stdout and not child.stderr
    assert len(list(store.quarantine.iterdir())) == 1
    assert set(closure(old, store.read)) == {old, old_leaf, shared}
    assert set(closure(new, store.read)) == {new, new_leaf, shared}
    rows.append({"case": "child exit after first quarantine move", "decision": "both-real-graphs-readable"})
    assert store.recover() == {"salvaged": 0, "removed": 1}
    next_plan = store.plan()
    assert len(next_plan.removable) == 1
    assert store.sweep(next_plan) == 1
    assert store.recover() == {"salvaged": 0, "removed": 1}
    rows.append({"case": "resume collection from fresh catalog view", "decision": "only-orphans-collected"})

    store.release("reader-1")
    assert store.plan().removable == ()
    store.release("reader-2")
    final = store.plan()
    assert set(final.removable) == {old, old_leaf}
    assert store.sweep(final) == 2
    assert store.recover() == {"salvaged": 0, "removed": 2}
    refusal("old snapshot after both leases were released", "missing object",
            lambda: closure(old, store.read))
    assert set(closure(new, store.read)) == {new, new_leaf, shared}
    rows.append({"case": "shared dependency survives historical collection", "decision": "current-verified"})

    os.replace(store.active / new_leaf, store.quarantine / new_leaf)
    refusal("ordinary marks halt on missing live graph", "missing object", store.plan)
    assert store.recover() == {"salvaged": 1, "removed": 1}
    assert set(closure(new, store.read)) == {new, new_leaf, shared}
    rows.append({"case": "recovery salvages checked protected bytes", "decision": "current-restored"})

    os.replace(store.active / new_leaf, store.quarantine / new_leaf)
    (store.quarantine / new_leaf).write_bytes(b"corrupt experiment bytes")
    refusal("recovery cannot publish a corrupted replacement", "object digest mismatch", store.recover)
    assert not (store.active / new_leaf).exists()
    assert (store.quarantine / new_leaf).exists()
    refusal("unreadable root cannot acquire a new lease", "missing object", lambda: store.pin("unreadable", new))
    return {"format": "external-cas-collection-01", "sqlite": sqlite3.sqlite_version,
            "interrupted_exit": child.returncode, "rows": rows}


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--interrupt":
        item = json.loads(Path(sys.argv[3]).read_bytes())
        Store(Path(sys.argv[2])).sweep(Plan(item["epoch"], tuple(item["removable"])), interrupt=True)
        sys.exit(1)
    with TemporaryDirectory(prefix="llmlang-external-cas-") as directory:
        evidence = experiment(Path(directory))
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
