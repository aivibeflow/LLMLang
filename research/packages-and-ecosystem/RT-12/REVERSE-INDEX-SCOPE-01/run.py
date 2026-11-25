"""Check exact reverse-index completeness, scope, and reader snapshots."""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
from tempfile import TemporaryDirectory

BASE = (
    ("caller", "provider", "invoke", "site-0"),
    ("caller", "provider", "contract", "site-1"),
    ("checker", "provider", "invoke", "site-0"),
    ("tests", "fixture", "input", "site-0"),
)
CURRENT = (
    *BASE[:2], ("caller", "provider", "invoke", "site-2"),
    ("checker", "replacement", "invoke", "site-0"), BASE[3],
)
QUERY_SET = (
    ("provider", None), ("provider", "invoke"), ("provider", "contract"),
    ("replacement", None), ("fixture", None), ("absent", None),
)


def identity(rows):
    return hashlib.sha256(json.dumps(sorted(rows), separators=(",", ":")).encode()).hexdigest()


def store(db, root, rows):
    db.executemany("INSERT INTO reverse_edges VALUES (?,?,?,?,?)", [(root, *row) for row in rows])


def create_db(directory):
    db = sqlite3.connect(directory / "index.sqlite")
    mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    assert mode == "wal"
    db.executescript(
        "CREATE TABLE reverse_edges("
        "root TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL,"
        "role TEXT NOT NULL, occurrence TEXT NOT NULL,"
        "PRIMARY KEY(root, source, role, occurrence));"
        "CREATE INDEX reverse_lookup ON reverse_edges(root, target, role);"
    )
    db.commit()
    return db


def query(db, root, target, role):
    sql = "SELECT source,target,role,occurrence FROM reverse_edges WHERE root=? AND target=?"
    args = (root, target)
    if role is not None:
        sql += " AND role=?"
        args += (role,)
    return sorted(db.execute(sql, args).fetchall())


def canonical(rows, target, role):
    return sorted(r for r in rows if r[1] == target and (role is None or r[2] == role))


def anchor_matches(db, root, expected_digest):
    rows = db.execute(
        "SELECT source,target,role,occurrence FROM reverse_edges WHERE root=?", (root,)
    ).fetchall()
    return identity(rows) == expected_digest


def run_cases(directory):
    expected_digest = identity(CURRENT)
    root = "required-current-root"
    replacements = {
        "exact": CURRENT,
        "reordered_rows": tuple(reversed(CURRENT)),
        "stale_rows_under_current_label": BASE,
        "missing_occurrence": CURRENT[:1] + CURRENT[2:],
        "inactive_edge": (*CURRENT, ("inactive-caller", "provider", "invoke", "site-3")),
        "role_drift": (("caller", "provider", "read", "site-0"), *CURRENT[1:]),
        "collapsed_pair": (CURRENT[0], CURRENT[3], CURRENT[4]),
        "absent_index": (),
    }
    observations = {}
    with closing(create_db(directory)) as db:
        for name, rows in replacements.items():
            db.execute("DELETE FROM reverse_edges")
            store(db, root, rows)
            # Query an immutable earlier generation in the same database to test root scoping.
            store(db, "earlier-root", BASE)
            db.commit()
            checked = anchor_matches(db, root, expected_digest)
            raw_wrong = []
            for target, role in QUERY_SET:
                expected = canonical(CURRENT, target, role)
                raw = query(db, root, target, role)
                if raw != expected:
                    raw_wrong.append({"target": target, "role": role, "raw": raw, "canonical": expected})
                selected = raw if checked else canonical(CURRENT, target, role)
                assert selected == expected
            observations[name] = {"validated": checked, "raw_wrong_queries": raw_wrong,
                                  "strict": "INDEX" if checked else "UNKNOWN",
                                  "with_authoritative_fallback": "INDEX" if checked else "FORWARD_SCAN"}
    assert {name for name, item in observations.items() if item["validated"]} == {"exact", "reordered_rows"}
    assert all(observations[name]["raw_wrong_queries"] for name in replacements if not observations[name]["validated"])
    return observations


def interleave(directory):
    root = "current"
    expected = canonical(CURRENT, "provider", None)
    with closing(create_db(directory)) as reader:
        store(reader, root, CURRENT)
        reader.commit()
        with closing(sqlite3.connect(directory / "index.sqlite")) as writer:
            reader.execute("BEGIN")
            verified = anchor_matches(reader, root, identity(CURRENT))
            assert verified
            writer.execute("DELETE FROM reverse_edges WHERE root=? AND source=? AND occurrence=?",
                           (root, "caller", "site-2"))
            writer.commit()
            bound_read = query(reader, root, "provider", None)
            reader.commit()
            stale_read = query(reader, root, "provider", None)
            assert bound_read == expected and stale_read != expected
            assert not anchor_matches(reader, root, identity(CURRENT))
    return {"validation_passed_before_write": verified, "same_read_transaction": bound_read,
            "later_unbound_lookup": stale_read, "canonical": expected}


def main():
    with TemporaryDirectory(prefix="llmlang-reverse-index-") as temp:
        root = Path(temp)
        (root / "cases").mkdir()
        (root / "race").mkdir()
        cases = run_cases(root / "cases")
        race = interleave(root / "race")
    return {"schema": "llmlang-rt12-reverse-index-scope/1", "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "journal_mode": "wal", "authoritative_current_edge_digest": identity(CURRENT),
            "authoritative_current_edges": CURRENT, "queries": QUERY_SET,
            "cases": cases, "validation_lookup_interleaving": race}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
