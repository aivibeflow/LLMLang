"""Exercise defensive local publication for a typed address migration in SQLite WAL."""

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
BASE = "3856c0165e2c7f6122291e2adb6e97bd16ba6792"
PRIOR = HERE.parent / "DIGEST-MIGRATION-01"
sys.path.insert(0, str(PRIOR))
from run import Store, StoreError, fixture, envelope, rewrite, structure
from migration import address


class SqliteStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")

    def initialize(self):
        assert self.db.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        self.db.executescript("""
            CREATE TABLE value (locator TEXT PRIMARY KEY, bytes BLOB NOT NULL);
            CREATE TABLE selected (slot INTEGER PRIMARY KEY, locator TEXT NOT NULL);
            CREATE TABLE quarantine (locator TEXT PRIMARY KEY);
        """)

    def read(self, name, suites):
        suite, _, _ = name.partition(":")
        if suite not in suites:
            raise StoreError("unsupported suite")
        if self.db.execute("SELECT 1 FROM quarantine WHERE locator = ?", (name,)).fetchone():
            raise StoreError("quarantined")
        row = self.db.execute("SELECT bytes FROM value WHERE locator = ?", (name,)).fetchone()
        if row is None:
            raise StoreError("missing address")
        blob, = row
        if address(blob, suite) != name:
            raise StoreError("digest mismatch")
        return blob

    def selected(self):
        return self.db.execute("SELECT locator FROM selected WHERE slot = 0").fetchone()[0]

    def put(self, blob, suite):
        name = address(blob, suite)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.db.execute("SELECT 1 FROM quarantine WHERE locator = ?", (name,)).fetchone():
                return "quarantined"
            row = self.db.execute("SELECT bytes FROM value WHERE locator = ?", (name,)).fetchone()
            if row is not None:
                if row == (blob,):
                    return "already-present"
                self.db.execute("INSERT INTO quarantine VALUES (?)", (name,))
                return "collision"
            self.db.execute("INSERT INTO value VALUES (?, ?)", (name, blob))
        return "added"


def child(path, expected, target, mode):
    store = SqliteStore(path)
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        if store.selected() != expected:
            return 4
        try:
            staged_shape, _ = structure(store, target, {"sha512"})
        except StoreError as error:
            assert str(error) == "missing address"
            return 5
        if staged_shape != structure(store, expected, {"sha256"})[0]:
            return 6
        store.db.execute("UPDATE selected SET locator = ? WHERE slot = 0", (target,))
        if mode == "before-commit":
            os._exit(71)
    if mode == "after-commit":
        os._exit(72)
    return 0


def check_publication(directory):
    memory = Store()
    old, subjects = fixture(memory)
    new, rewritten = rewrite(memory, old)
    old_shape, old_names = structure(memory, old, {"sha256"})
    new_shape, new_names = structure(memory, new, {"sha512"})
    assert old_shape == new_shape and old_names.isdisjoint(new_names)
    assert all(name != rewritten[name] for name in subjects.values())
    wrong = memory.put(envelope("snapshot", {"different": True}), "sha512")
    scenarios = {
        "wrong-structure": (6, False),
        "normal": (0, True),
        "before-commit": (71, False),
        "after-commit": (72, True),
        "missing-staged-object": (5, False),
        "stale-selection": (4, False),
    }
    results = {}
    for mode, (status, current) in scenarios.items():
        path = directory / f"{mode}.db"
        store = SqliteStore(path)
        store.initialize()
        staged = new_names - ({rewritten[subjects["operation"]]} if mode == "missing-staged-object" else set())
        if mode == "wrong-structure":
            staged.add(wrong)
        for name in sorted(old_names | staged):
            assert store.put(memory.blobs[name], name.partition(":")[0]) == "added"
        with store.db:
            store.db.execute("INSERT INTO selected VALUES (0, ?)", (old,))
        store.db.close()
        expected_parent = new if mode == "stale-selection" else old
        target = wrong if mode == "wrong-structure" else new
        result = subprocess.run([sys.executable, "-B", __file__, "child", path, expected_parent, target, mode],
                                check=False, timeout=10)
        assert result.returncode == status
        reader = SqliteStore(path)
        selected = reader.selected()
        assert selected == (new if current else old)
        suite = {"sha512"} if current else {"sha256"}
        assert structure(reader, selected, suite)[0] == old_shape
        assert structure(reader, old, {"sha256"})[0] == old_shape
        assert reader.db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        reader.db.close()
        results[mode] = {"writer_status": status, "selected": "new" if current else "old",
                         "retained_old_closure": True}
    return {"old_nodes": len(old_names), "new_nodes": len(new_names), "cases": results}


def check_quarantine(directory):
    path = directory / "quarantine.db"
    store = SqliteStore(path)
    store.initialize()
    trial_suite = "fixture-collision"
    a = envelope("contract", {"profile": "one"})
    b = envelope("contract", {"profile": "two"})
    assert a != b
    locator = address(a, trial_suite)
    assert locator == address(b, trial_suite)
    assert store.put(a, trial_suite) == "added"
    assert store.put(a, trial_suite) == "already-present"
    assert store.put(b, trial_suite) == "collision"
    store.db.close()

    restarted = SqliteStore(path)
    try:
        restarted.read(locator, {trial_suite})
    except StoreError as error:
        assert str(error) == "quarantined"
    else:
        raise AssertionError("A quarantined locator was readable after reopen")
    assert restarted.put(a, trial_suite) == restarted.put(b, trial_suite) == "quarantined"
    assert restarted.db.execute("SELECT bytes FROM value WHERE locator = ?", (locator,)).fetchone() == (a,)
    restarted.db.close()
    return {"after_reopen": "quarantined", "both_retries": "quarantined", "original_bytes_preserved": True}


def run():
    with TemporaryDirectory() as temp:
        directory = Path(temp)
        return {
            "revision": BASE, "sqlite": sqlite3.sqlite_version, "python": sys.version.split()[0],
            "sources": {p.name: sha256(p.read_bytes()).hexdigest()
                        for p in (Path(__file__), PRIOR / "migration.py", PRIOR / "run.py")},
            "publication": check_publication(directory), "quarantine": check_quarantine(directory),
        }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(child(*sys.argv[2:]))
    print(json.dumps(run(), indent=2, sort_keys=True))
