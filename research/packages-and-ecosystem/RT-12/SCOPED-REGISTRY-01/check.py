"""Check exact shared artifacts and scoped discovery in a local SQLite registry."""

from collections import Counter
from contextlib import closing
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import sqlite3
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
SOURCES = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-INDEX-01"
sys.path.insert(0, str(SOURCES))
from content_store import SQLiteContentStore, content_hash


def typed(kind, payload):
    return b"llmlang.fixture-artifact.v1\0" + kind.encode("ascii") + b"\0" + payload


def operation(meaning, profile):
    return content_hash(typed("operation", ("reserve/" + meaning + "/" + profile).encode()))


def publish(registry, store, expected_head, rows):
    with store.open_snapshot() as snapshot:
        for tenant, exact_operation, artifact, kind in rows:
            try:
                data = snapshot.get_object(artifact)
            except KeyError:
                return "missing-artifact"
            if data["kind"] != kind:
                return "wrong-artifact-kind"
    registry.execute("BEGIN IMMEDIATE")
    try:
        head, = registry.execute("SELECT generation FROM head").fetchone()
        if head != expected_head:
            registry.rollback()
            return "stale-head"
        registry.executemany("INSERT INTO bindings VALUES (?,?,?,?,?)",
                             [(head + 1, *row) for row in rows])
        registry.execute("UPDATE head SET generation = ?", (head + 1,))
        registry.commit()
    except sqlite3.IntegrityError:
        registry.rollback()
        return "conflicting-binding"
    return "published"


def discovery(registry, snapshot, scope, authorized):
    if scope not in authorized:
        return ()
    return tuple(registry.execute(
        "SELECT operation, artifact, kind FROM bindings WHERE generation=? AND tenant=? ORDER BY operation",
        (snapshot, scope),
    ))


def exact(registry, store, snapshot, scope, authorized, op, expected_artifact):
    if scope not in authorized:
        return None
    row = registry.execute(
        "SELECT artifact, kind FROM bindings WHERE generation=? AND tenant=? AND operation=?",
        (snapshot, scope, op),
    ).fetchone()
    if row is None or row[0] != expected_artifact:
        return None
    with store.open_snapshot() as view:
        try:
            expected = view.get_object(row[0])
            with view.open_object(row[0]) as stream:
                data = stream.read()
        except KeyError:
            return None
    if expected["kind"] != row[1] or expected["size"] != len(data) or content_hash(data) != row[0]:
        return None
    return data


def run(scratch):
    store = SQLiteContentStore(scratch / "content.sqlite")
    body = typed("implementation", b"shared immutable body")
    proof = typed("proof", b"shared immutable body")
    next_body = typed("implementation", b"new body")
    old = store.put_object(body, "implementation", [])
    with store.open_snapshot() as view:
        before = view.snapshot_id
    assert old == store.put_object(body, "implementation", [])
    with store.open_snapshot() as view:
        assert before == view.snapshot_id
    audited = store.put_object(proof, "proof", [])
    new = store.put_object(next_body, "implementation", [])
    assert len({old, audited, new}) == 3
    linux = operation("exact", "linux")
    other = operation("exact", "windows")
    privileged = operation("audit", "linux")
    old_rows = [("A", linux, old, "implementation"), ("B", linux, old, "implementation"),
                ("A", privileged, audited, "proof")]
    new_rows = [("A", linux, new, "implementation"), ("B", linux, old, "implementation"),
                ("B", other, new, "implementation")]

    with closing(sqlite3.connect(scratch / "registry.sqlite", isolation_level=None)) as db:
        db.executescript("""
            CREATE TABLE head (generation INTEGER NOT NULL);
            INSERT INTO head VALUES (0);
            CREATE TABLE bindings (
                generation INTEGER NOT NULL,
                tenant TEXT NOT NULL,
                operation TEXT NOT NULL,
                artifact TEXT NOT NULL,
                kind TEXT NOT NULL,
                PRIMARY KEY (generation, tenant, operation)
            );
        """)
        assert publish(db, store, 0, old_rows) == "published"
        assert publish(db, store, 1, new_rows) == "published"
        controls = {
            "conflicting_rows": publish(db, store, 2, [*new_rows, new_rows[0]]),
            "stale_head": publish(db, store, 1, old_rows),
            "absent_artifact": publish(db, store, 2, [("A", linux,
                content_hash(b"absent"), "implementation")]),
            "incorrect_kind": publish(db, store, 2, [("A", linux, old, "proof")]),
        }
        assert db.execute("SELECT generation FROM head").fetchone() == (2,)
        assert db.execute("SELECT COUNT(*) FROM bindings WHERE generation=3").fetchone() == (0,)
        assert controls == {"conflicting_rows": "conflicting-binding", "stale_head": "stale-head",
                            "absent_artifact": "missing-artifact", "incorrect_kind": "wrong-artifact-kind"}

        expected = {
            (1, "A"): {linux: (old, "implementation"), privileged: (audited, "proof")},
            (1, "B"): {linux: (old, "implementation")},
            (2, "A"): {linux: (new, "implementation")},
            (2, "B"): {linux: (old, "implementation"), other: (new, "implementation")},
        }
        payload = {old: body, audited: proof, new: next_body}
        outcomes = Counter()
        discoveries = 0
        for generation, scope, grants in product((1, 2, 3), ("A", "B"),
                                                 ((), ("A",), ("B",), ("A", "B"))):
            names = expected.get((generation, scope), {}) if scope in grants else {}
            assert discovery(db, generation, scope, grants) == tuple(
                (op, *record) for op, record in sorted(names.items())
            )
            discoveries += 1
            for op, artifact in product((linux, privileged, other), (old, new, audited)):
                result = exact(db, store, generation, scope, grants, op, artifact)
                known = names.get(op)
                want = payload[artifact] if known is not None and known[0] == artifact else None
                assert result == want
                outcomes["available" if result is not None else "unavailable"] += 1

    return {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "discoveries": discoveries, "exact_reads": dict(outcomes), "controls": controls,
            "immutable_idempotent_insert": True, "shared_body_canonical_hash": old,
            "separate_proof_hash_for_same_body_suffix": audited,
            "operation_ids": [linux, other, privileged],
            "sources": {"check.py": sha256(Path(__file__).read_bytes()).hexdigest(),
                        "content_store.py": sha256((SOURCES / "content_store.py").read_bytes()).hexdigest()}}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="rt12-scoped-registry-") as work:
        print(json.dumps(run(Path(work)), sort_keys=True, indent=2))
