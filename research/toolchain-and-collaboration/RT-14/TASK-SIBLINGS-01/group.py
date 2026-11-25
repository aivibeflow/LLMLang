"""Bounded two-child Task Context lifecycle with SQLite arbitration."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import sqlite3

CHILDREN = ("left", "right")
GOAL = frozenset({"A", "B", "C", "D"})
CHECKS = frozenset({"mutation", "proof", "test"})
SCHEMA = """
CREATE TABLE task (epoch INTEGER, baseline TEXT, live_baseline TEXT, status TEXT);
INSERT INTO task VALUES (1,'base-a','base-a','active');
CREATE TABLE child (
    epoch INTEGER, child TEXT, actor TEXT, status TEXT,
    PRIMARY KEY(epoch,child)
);
CREATE TABLE ownership (
    epoch INTEGER, subject TEXT, child TEXT,
    PRIMARY KEY(epoch,subject)
);
CREATE TABLE outcome (
    operation TEXT PRIMARY KEY, digest TEXT, epoch INTEGER, child TEXT
);
"""


@dataclass(frozen=True)
class Work:
    epoch: int
    baseline: str
    child: str
    actor: str
    scope: tuple[str, ...]


@dataclass(frozen=True)
class Evidence:
    work: Work
    check: str
    outcome: str


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def settlement_digest(work, rows):
    ordered = sorted((asdict(row) for row in rows), key=canonical)
    return sha256(canonical({"work": asdict(work), "evidence": ordered}).encode()).hexdigest()


class Group:
    def __init__(self, path, initialize=False):
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        if initialize:
            status = self.db.execute("PRAGMA journal_mode=WAL").fetchone()
            assert status == ("wal",)
            self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def task(self):
        return self.db.execute("SELECT epoch,baseline,live_baseline,status FROM task").fetchone()

    def admissibility(self, epoch, baseline):
        live_epoch, bound, live_baseline, state = self.task()
        if epoch != live_epoch:
            return "stale-revision"
        if state != "active":
            return "inactive"
        if baseline != bound or live_baseline != bound:
            return "stale-baseline"
        return "ready"

    def delegate(self, work):
        with self.transaction():
            gate = self.admissibility(work.epoch, work.baseline)
            if gate != "ready":
                return gate
            if (work.child not in CHILDREN or not work.scope
                    or work.scope != tuple(sorted(set(work.scope))) or not set(work.scope) <= GOAL):
                return "scope-expansion"
            if self.db.execute("SELECT 1 FROM child WHERE epoch=? AND child=?",
                               (work.epoch, work.child)).fetchone():
                return "already-delegated"
            owned = {subject for (subject,) in self.db.execute(
                "SELECT subject FROM ownership WHERE epoch=?", (work.epoch,)
            )}
            if owned.intersection(work.scope):
                return "overlap"
            self.db.execute("INSERT INTO child VALUES (?,?,?,'delegated')",
                            (work.epoch, work.child, work.actor))
            self.db.executemany("INSERT INTO ownership VALUES (?,?,?)",
                                [(work.epoch, subject, work.child) for subject in work.scope])
            return "delegated"

    def settle(self, work, rows, operation):
        digest = settlement_digest(work, rows)
        with self.transaction():
            old = self.db.execute("SELECT digest FROM outcome WHERE operation=?", (operation,)).fetchone()
            if old is not None:
                return "replayed" if old[0] == digest else "operation-conflict"
            gate = self.admissibility(work.epoch, work.baseline)
            if gate != "ready":
                return gate
            selected = self.db.execute("SELECT actor,status FROM child WHERE epoch=? AND child=?",
                                       (work.epoch, work.child)).fetchone()
            scope = tuple(subject for (subject,) in self.db.execute("""
                SELECT subject FROM ownership WHERE epoch=? AND child=? ORDER BY subject
            """, (work.epoch, work.child)))
            if selected != (work.actor, "delegated") or scope != work.scope:
                return "ownership-mismatch"
            if (len(rows) != len(CHECKS) or {row.check for row in rows} != CHECKS
                    or any(row.work != work or row.outcome != "pass" for row in rows)):
                return "unsatisfied"
            self.db.execute("UPDATE child SET status='settled' WHERE epoch=? AND child=?",
                            (work.epoch, work.child))
            self.db.execute("INSERT INTO outcome VALUES (?,?,?,?)",
                            (operation, digest, work.epoch, work.child))
            return "settled"

    def complete(self, epoch, baseline):
        with self.transaction():
            gate = self.admissibility(epoch, baseline)
            if gate != "ready":
                return gate
            if set(self.db.execute("SELECT child,status FROM child WHERE epoch=?", (epoch,))) != {
                (child, "settled") for child in CHILDREN
            }:
                return "pending-children"
            actual_scope = {subject for (subject,) in self.db.execute(
                "SELECT subject FROM ownership WHERE epoch=?", (epoch,)
            )}
            if actual_scope != GOAL:
                return "pending-scope"
            self.db.execute("UPDATE task SET status='complete'")
            return "complete"

    def cancel(self, epoch):
        with self.transaction():
            live_epoch, _, _, state = self.task()
            if live_epoch != epoch:
                return "stale-revision"
            if state != "active":
                return "inactive"
            self.db.execute("UPDATE task SET status='cancelled'")
            return "cancelled"

    def move_baseline(self, root):
        with self.transaction():
            self.db.execute("UPDATE task SET live_baseline=?", (root,))

    def restart(self, epoch):
        with self.transaction():
            current, _, live, state = self.task()
            if current != epoch:
                return "stale-revision"
            if state != "cancelled":
                return "inactive"
            self.db.execute("UPDATE task SET epoch=?, baseline=?, status='active'",
                            (current + 1, live))
            return "restarted"
