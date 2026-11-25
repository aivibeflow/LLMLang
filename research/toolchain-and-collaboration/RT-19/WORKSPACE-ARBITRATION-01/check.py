"""Compare workspace-local CAS with branch-bound idempotent acceptance."""

from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import sqlite3
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class Proposal:
    principal: str
    workspace: str
    branch: str
    revision: int
    base: str
    candidate: str
    request_id: str


LEFT = Proposal("alice", "one", "left", 1, "base", "candidate-a", "request")
RIGHT = Proposal("bob", "two", "left", 1, "base", "candidate-b", "request")


def fingerprint(proposal):
    return sha256(json.dumps(asdict(proposal), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def open_db(path):
    return sqlite3.connect(path, isolation_level=None, timeout=5)


def initialize(path, peer_branch):
    with closing(open_db(path)) as db:
        db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE workspace (name TEXT PRIMARY KEY, principal TEXT, branch TEXT, revision INTEGER);
            CREATE TABLE refs (name TEXT PRIMARY KEY, root TEXT);
            CREATE TABLE receipts (principal TEXT, id TEXT, fingerprint TEXT, result TEXT,
                                   PRIMARY KEY(principal, id));
            INSERT INTO refs VALUES ('left', 'base'), ('right', 'base');
            INSERT INTO workspace VALUES ('one', 'alice', 'left', 1);
        """)
        db.execute("INSERT INTO workspace VALUES ('two','bob',?,1)", (peer_branch,))


def accept(path, proposal, *, current_grants):
    with closing(open_db(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        workspace = db.execute("SELECT principal, branch, revision FROM workspace WHERE name=?",
                               (proposal.workspace,)).fetchone()
        if (proposal.principal, proposal.workspace) not in current_grants or workspace is None or (
                workspace[:2] != (proposal.principal, proposal.branch)):
            db.rollback()
            return ("scope-unavailable", None)
        claim = fingerprint(proposal)
        prior = db.execute("SELECT fingerprint, result FROM receipts WHERE principal=? AND id=?",
                           (proposal.principal, proposal.request_id)).fetchone()
        if prior is not None:
            db.rollback()
            return ("replay", prior[1]) if prior[0] == claim else ("request-conflict", None)
        if workspace[2] != proposal.revision:
            db.rollback()
            return ("stale-workspace", None)
        updated = db.execute("UPDATE refs SET root=? WHERE name=? AND root=?",
                             (proposal.candidate, proposal.branch, proposal.base)).rowcount
        if not updated:
            db.rollback()
            return ("stale-branch", None)
        db.execute("UPDATE workspace SET revision=revision+1 WHERE name=?", (proposal.workspace,))
        db.execute("INSERT INTO receipts VALUES (?,?,?,?)",
                   (proposal.principal, proposal.request_id, claim, proposal.candidate))
        db.commit()
        return ("accepted", proposal.candidate)


def query(path):
    with closing(open_db(path)) as db:
        return (dict(db.execute("SELECT name, root FROM refs")),
                dict(db.execute("SELECT name, revision FROM workspace")),
                db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0])


def run(work):
    rows = []
    totals = Counter()
    for shared, reversed_order, stale_local, replay_changed in product((False, True), repeat=4):
        path = work / f"fixture-{len(rows)}.sqlite"
        other_branch = LEFT.branch if shared else "right"
        initialize(path, other_branch)
        grants = {("alice", "one"), ("bob", "two")}
        peer = replace(RIGHT, branch=other_branch)
        first, second = (peer, LEFT) if reversed_order else (LEFT, peer)
        assert accept(path, first, current_grants=grants) == ("accepted", first.candidate)
        if stale_local:
            with closing(open_db(path)) as db:
                db.execute("UPDATE workspace SET revision=2 WHERE name=?", (second.workspace,))
        result = accept(path, second, current_grants=grants)[0]
        assert result == ("stale-workspace" if stale_local else "stale-branch" if shared else "accepted")
        retry = replace(first, candidate="different") if replay_changed else first
        retry_result = accept(path, retry, current_grants=grants)
        assert retry_result == (("request-conflict", None) if replay_changed else ("replay", first.candidate))
        assert accept(path, first, current_grants=grants - {(first.principal, first.workspace)}) == (
            "scope-unavailable", None)
        actual_refs, revisions, stored = query(path)
        expected_refs = {"left": "base", "right": "base"}
        expected_refs[first.branch] = first.candidate
        if result == "accepted":
            expected_refs[second.branch] = second.candidate
        assert actual_refs == expected_refs
        assert revisions[first.workspace] == 2
        assert stored == (2 if result == "accepted" else 1)
        totals[result] += 1
        rows.append({"same_branch": shared, "reverse_order": reversed_order, "stale_workspace": stale_local,
                     "changed_retry": replay_changed, "second": result, "retry": retry_result[0],
                     "branch_roots": actual_refs, "durable_receipts": stored})
    return {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "outcomes": totals, "rows": rows, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="rt19-workspace-arbitration-") as temp:
        print(json.dumps(run(Path(temp)), sort_keys=True, indent=2))
