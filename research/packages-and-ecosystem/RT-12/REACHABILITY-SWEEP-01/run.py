"""Check local reachability collection across pinned roots and WAL writers."""

from hashlib import sha256
import json
from pathlib import Path
import platform
import sqlite3
from tempfile import TemporaryDirectory

BASE = "7464b5277edd6c0c987b85e02377fd963791219d"
OBJECTS = ("alpha", "beta", "shared", "old-leaf", "new-leaf", "garbage", "cycle-a", "cycle-b")
EDGES = (("alpha", "shared"), ("alpha", "old-leaf"), ("beta", "shared"),
         ("beta", "new-leaf"), ("cycle-a", "cycle-b"), ("cycle-b", "cycle-a"))
REACHABLE = """
WITH RECURSIVE live(id) AS (
    SELECT root FROM pin
    UNION
    SELECT edge.child FROM edge JOIN live ON edge.parent = live.id
)
SELECT id FROM live ORDER BY id
"""


def initialize(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=0)
    assert db.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
    db.executescript("""
      PRAGMA foreign_keys = ON;
      CREATE TABLE object(id TEXT PRIMARY KEY, present INTEGER NOT NULL, complete INTEGER NOT NULL);
      CREATE TABLE edge(parent TEXT REFERENCES object(id), child TEXT REFERENCES object(id), PRIMARY KEY(parent, child));
      CREATE TABLE pin(name TEXT PRIMARY KEY, root TEXT NOT NULL REFERENCES object(id));
      CREATE TABLE epoch(value INTEGER NOT NULL);
      INSERT INTO epoch VALUES (0);
    """)
    db.executemany("INSERT INTO object VALUES (?,1,1)", ((name,) for name in OBJECTS))
    db.executemany("INSERT INTO edge VALUES (?,?)", EDGES)
    db.execute("INSERT INTO pin VALUES ('current','alpha')")
    return db


def certain(db, roots):
    state = {name: (present, complete) for name, present, complete in db.execute("SELECT * FROM object")}
    return all(state.get(root) == (1, 1) for root in roots)


def descendants(db, root):
    return tuple(row[0] for row in db.execute("""
        WITH RECURSIVE closure(id) AS (
            VALUES (?) UNION SELECT edge.child FROM edge JOIN closure ON edge.parent=closure.id
        ) SELECT id FROM closure ORDER BY id
    """, (root,)))


def mutate_pin(db, name, root):
    db.execute("BEGIN IMMEDIATE")
    if root is not None and not certain(db, descendants(db, root)):
        db.rollback()
        return "root-incomplete"
    if root is None:
        db.execute("DELETE FROM pin WHERE name=?", (name,))
    else:
        db.execute("INSERT INTO pin VALUES (?,?) ON CONFLICT(name) DO UPDATE SET root=excluded.root", (name, root))
    db.execute("UPDATE epoch SET value=value+1")
    db.commit()
    return "updated"


def mark(db):
    epoch, = db.execute("SELECT value FROM epoch").fetchone()
    live = tuple(row[0] for row in db.execute(REACHABLE))
    if not certain(db, live):
        return None
    dead = tuple(row[0] for row in db.execute("SELECT id FROM object WHERE present=1 ORDER BY id") if row[0] not in live)
    return epoch, dead


def apply(db, plan, *, compare_generation):
    if plan is None:
        return "unknown-closure"
    epoch, dead = plan
    if compare_generation and db.execute("SELECT value FROM epoch").fetchone() != (epoch,):
        return "stale-generation"
    db.executemany("UPDATE object SET present=0 WHERE id=?", ((name,) for name in dead))
    db.execute("UPDATE epoch SET value=value+1")
    return "swept"


def sweep(db, plan=None, *, compare_generation=True):
    db.execute("BEGIN IMMEDIATE")
    outcome = apply(db, mark(db) if plan is None else plan, compare_generation=compare_generation)
    db.commit()
    return outcome


def present(db):
    return [row[0] for row in db.execute("SELECT id FROM object WHERE present=1 ORDER BY id")]


def run():
    observations = []
    with TemporaryDirectory(prefix="llmlang-sweep-") as root:
        def fixture(name):
            path = Path(root) / (name + ".db")
            collector = initialize(path)
            writer = sqlite3.connect(path, isolation_level=None, timeout=0)
            writer.execute("PRAGMA foreign_keys = ON")
            return collector, writer

        for policy in ("unchecked", "generation", "locked"):
            collector, writer = fixture(policy)
            collector.execute("BEGIN IMMEDIATE" if policy == "locked" else "BEGIN")
            plan = mark(collector)
            assert plan is not None
            if policy != "locked":
                collector.commit()
            try:
                publication = mutate_pin(writer, "current", "beta")
            except sqlite3.OperationalError as error:
                assert error.sqlite_errorname == "SQLITE_BUSY"
                publication = "writer-busy"
            if policy == "locked":
                result = apply(collector, plan, compare_generation=True)
                collector.commit()
                retry = mutate_pin(writer, "current", "beta")
                assert (publication, result, retry) == ("writer-busy", "swept", "root-incomplete")
            else:
                result = sweep(collector, plan, compare_generation=policy == "generation")
                retry = sweep(collector) if result == "stale-generation" else None
            current, = writer.execute("SELECT root FROM pin WHERE name='current'").fetchone()
            closed = certain(writer, descendants(writer, current))
            assert closed == (policy != "unchecked")
            if policy == "generation":
                assert (publication, result, retry, current) == ("updated", "stale-generation", "swept", "beta")
            observations.append({"case": policy, "attempted_publication": publication,
                                 "first_sweep": result, "retry": retry,
                                 "current_root": current, "current_closure_present": closed, "present": present(writer)})
            collector.close()
            writer.close()

        collector, writer = fixture("leases")
        assert mutate_pin(writer, "reader-one", "alpha") == "updated"
        assert mutate_pin(writer, "reader-two", "alpha") == "updated"
        assert mutate_pin(writer, "current", "beta") == "updated"
        statuses = []
        for lease in (None, "reader-one", "reader-two"):
            if lease is not None:
                assert mutate_pin(writer, lease, None) == "updated"
            assert sweep(collector) == "swept"
            statuses.append(certain(writer, descendants(writer, "alpha")))
        assert statuses == [True, True, False]
        assert "shared" in present(writer)
        observations.append({"case": "reader-leases", "historical_root_present": statuses,
                             "present": present(writer)})
        collector.close()
        writer.close()

        collector, writer = fixture("cycle")
        assert mutate_pin(writer, "cycle-root", "cycle-a") == "updated"
        assert sweep(collector) == "swept"
        assert {"cycle-a", "cycle-b"} <= set(present(writer))
        mutate_pin(writer, "cycle-root", None)
        assert sweep(collector) == "swept"
        assert {"cycle-a", "cycle-b"}.isdisjoint(present(writer))
        observations.append({"case": "cycle", "retained_while_rooted": True, "reclaimed_after_unpin": True})
        collector.close()
        writer.close()

        collector, writer = fixture("incomplete")
        writer.execute("UPDATE object SET complete=0 WHERE id='shared'")
        assert sweep(collector) == "unknown-closure"
        assert set(present(writer)) == set(OBJECTS)
        observations.append({"case": "incomplete-dependencies", "sweep": "unknown-closure", "present": present(writer)})
        collector.close()
        writer.close()

    through = sqlite3.connect(":memory:")
    source_id = through.execute("SELECT sqlite_source_id()").fetchone()[0]
    through.close()
    return {
        "schema": "rt12-reachability-sweep-comparison-v1", "baseline": BASE,
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "sqlite_source_id": source_id,
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "observations": observations,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
