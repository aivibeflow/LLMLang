"""Check local contribution dispositions, shadow isolation and stateful cutover/rollback."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
DISPOSITIONS = ("accepted", "modified", "deferred", "rejected")
EVIDENCE = ("exact", "stale", "missing")


def git(repo, *args):
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@local.example",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@local.example",
           "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"}
    return subprocess.check_output(["git", *args], cwd=repo, env=env, text=True, timeout=20).strip()


def commit(repo, value):
    (repo / "provider.txt").write_text(value + "\n")
    git(repo, "add", "provider.txt")
    git(repo, "commit", "-qm", value)
    return git(repo, "rev-parse", "HEAD")


def history(repo, disposition):
    git(repo, "init", "-q", "-b", "upstream")
    original = commit(repo, "original behavior")
    git(repo, "switch", "-qc", "proposed")
    proposal = commit(repo, "proposed behavior")
    git(repo, "switch", "-q", "upstream")
    if disposition == "accepted":
        git(repo, "merge", "--ff-only", "proposed")
    elif disposition == "modified":
        commit(repo, "independently modified contribution")
    current = git(repo, "rev-parse", "HEAD")
    if disposition == "accepted":
        assert current == proposal
    elif disposition == "modified":
        assert current not in (original, proposal)
    else:
        assert current == original
    assert git(repo, "rev-parse", "refs/heads/proposed") == proposal
    return original, proposal, current


def initialize(db, original, proposal, disposition, in_flight):
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        conn.executescript(
            "CREATE TABLE routing (provider TEXT, schema_key TEXT, generation INTEGER);"
            "CREATE TABLE contribution (proposal TEXT, disposition TEXT);"
            "CREATE TABLE pending (request TEXT PRIMARY KEY);"
            "CREATE TABLE effects (request TEXT PRIMARY KEY, provider TEXT);"
        )
        conn.execute("INSERT INTO routing VALUES (?, 'v1', 0)", (original,))
        conn.execute("INSERT INTO contribution VALUES (?, ?)", (proposal, disposition))
        if in_flight:
            conn.execute("INSERT INTO pending VALUES ('active-request')")


def read_binding(conn):
    return conn.execute("SELECT provider, schema_key, generation FROM routing").fetchone()


def shadow(conn, candidate):
    conn.execute("SAVEPOINT shadow")
    conn.execute("INSERT INTO effects VALUES ('shadow', ?)", (candidate,))
    assert conn.execute("SELECT provider FROM effects WHERE request='shadow'").fetchone() == (candidate,)
    conn.execute("ROLLBACK TO shadow")
    conn.execute("RELEASE shadow")
    assert not conn.execute("SELECT * FROM effects").fetchall()


def cutover(conn, current, attested, schema):
    conn.execute("BEGIN IMMEDIATE")
    original, stored_schema, generation = read_binding(conn)
    _, disposition = conn.execute("SELECT proposal, disposition FROM contribution").fetchone()
    pending = conn.execute("SELECT 1 FROM pending LIMIT 1").fetchone()
    if (disposition not in {"accepted", "modified"} or attested != current or current == original
            or stored_schema != schema or pending or generation != 0):
        conn.rollback()
        return False
    conn.execute("UPDATE routing SET provider=?, generation=1", (current,))
    conn.commit()
    return True


def settle_and_rollback(conn, original, candidate):
    with conn:
        assert read_binding(conn) == (candidate, "v1", 1)
        conn.execute("INSERT INTO effects VALUES ('canary', ?)", (candidate,))
    with conn:
        assert conn.execute("SELECT provider FROM effects WHERE request='canary'").fetchone() == (candidate,)
        outcomes = []
        for _ in range(2):
            changed = conn.execute(
                "UPDATE routing SET provider=?, generation=2 WHERE provider=? AND generation=1 AND schema_key='v1'",
                (original, candidate),
            )
            outcomes.append(changed.rowcount)
        assert outcomes == [1, 0]


def one_case(work, disposition, evidence, schema, pending):
    repo = work / "synthetic-source"
    repo.mkdir()
    original, proposal, current = history(repo, disposition)
    db = work / "rollout.sqlite3"
    initialize(db, original, proposal, disposition, pending)
    older = proposal if disposition == "modified" else original
    evidence_ref = current if evidence == "exact" else older if evidence == "stale" else None
    with sqlite3.connect(db) as conn:
        shadow(conn, current)
        allowed = cutover(conn, current, evidence_ref, schema)
        expected = (disposition in {"accepted", "modified"} and evidence == "exact"
                    and schema == "v1" and not pending)
        assert allowed == expected
        if allowed:
            settle_and_rollback(conn, original, current)
    with sqlite3.connect(db) as fresh:
        expected_effects = [("canary", current)] if allowed else []
        assert fresh.execute("SELECT request, provider FROM effects").fetchall() == expected_effects
        assert read_binding(fresh) == (original, "v1", 2 if allowed else 0)
        assert fresh.execute("SELECT proposal, disposition FROM contribution").fetchone() == (proposal, disposition)
    return "cutover-and-rollback" if allowed else "held-original"


def main():
    counter = Counter()
    for disposition, evidence, schema, pending in product(DISPOSITIONS, EVIDENCE, ("v1", "v2"), (False, True)):
        with TemporaryDirectory() as directory:
            outcome = one_case(Path(directory), disposition, evidence, schema, pending)
            counter[f"{disposition}/{outcome}"] += 1
    assert sum(counter.values()) == 48 and counter["accepted/cutover-and-rollback"] == 1
    assert counter["modified/cutover-and-rollback"] == 1
    archives = {name: sha256((HERE.parent / name).read_bytes()).hexdigest() for name in
                ("ZLIB-RELEASE-MIRROR-01/evidence.json", "MIXED-SETTLEMENT-01/evidence.json",
                 "SOURCE-BINDING-01/evidence.json")}
    return {"outcomes": counter, "archive_sha256": archives, "git": git(HERE, "--version"),
            "sqlite": sqlite3.sqlite_version, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
