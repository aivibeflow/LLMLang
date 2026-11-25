#!/usr/bin/env python3
"""Check exact graph-replica admission with SQLite metadata and a filesystem CAS."""

from contextlib import closing
from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASE = runpy.run_path(str(HERE.parent / "CLOSED-GRAPH-BACKUP-01/run.py"))
encode = BASE["encode"]
digest = BASE["digest"]
closure = BASE["closure"]
RestoreError = BASE["RestoreError"]


@dataclass(frozen=True)
class Revision:
    serial: int
    parent: str | None
    root: str
    inventory: str

    def identity(self):
        return digest(encode(asdict(self)))


class Refusal(ValueError):
    pass


def database(path):
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS selected (name TEXT PRIMARY KEY, revision BLOB NOT NULL)")
    return connection


def selected(connection):
    row = connection.execute("SELECT revision FROM selected WHERE name = 'current'").fetchone()
    return None if row is None else Revision(**json.loads(row[0]))


def select(connection, revision):
    connection.execute(
        "INSERT INTO selected VALUES ('current', ?) ON CONFLICT(name) DO UPDATE SET revision = excluded.revision",
        (encode(asdict(revision)),),
    )


def stage(directory, raw):
    address = digest(raw)
    target = directory / address
    if target.exists() and target.read_bytes() == raw:
        return
    with NamedTemporaryFile(dir=directory, delete=False) as temporary:
        temporary.write(raw)
        temporary.flush()
        os.fsync(temporary.fileno())
    pending = Path(temporary.name)
    try:
        os.replace(pending, target)
        fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        pending.unlink(missing_ok=True)


def checked_contents(revision, load):
    payloads = closure(revision.root, load)
    if digest(encode(sorted(payloads))) != revision.inventory:
        raise Refusal("inventory-mismatch")
    return payloads


def publish(root, revision, expected_identity, delta, *, interrupted=False):
    if revision.identity() != expected_identity:
        raise Refusal("revision-scope-mismatch")
    if any(digest(raw) != key for key, raw in delta.items()):
        raise Refusal("delta-digest-mismatch")
    cas = root / "cas"
    with closing(database(root / "selected.sqlite")) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            current = selected(connection)
            if current == revision:
                outcome = "already-selected"
            else:
                if current is None:
                    successor = revision.serial == 1 and revision.parent is None
                else:
                    successor = revision.serial == current.serial + 1 and revision.parent == current.identity()
                if not successor:
                    raise Refusal("non-successor")
                outcome = "published"
            payloads = checked_contents(
                revision, lambda addr: delta[addr] if addr in delta else (cas / addr).read_bytes()
            )
            if not set(delta) <= set(payloads):
                raise Refusal("delta-outside-closure")
            for raw in delta.values():
                stage(cas, raw)
            local = checked_contents(revision, lambda addr: (cas / addr).read_bytes())
            assert local == payloads
            select(connection, revision)
            if interrupted:
                os._exit(24)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return outcome


def inspect(root, latest, *, promote=False, fence=None):
    with closing(database(root / "selected.sqlite")) as connection:
        revision = selected(connection)
    if revision is None:
        return "empty"
    try:
        checked_contents(revision, lambda addr: (root / "cas" / addr).read_bytes())
    except (Refusal, RestoreError):
        return "unreadable"
    if revision.identity() != latest:
        return "historical-only"
    if promote:
        if fence != (revision.identity(), "separate-writer-authority"):
            return "read-only"
        return "eligible-with-external-fence"
    return "exact-current-read"


def experiment(directory):
    inventory = {}

    def object_file(kind, value, refs=()):
        raw = encode({"kind": kind, "value": value, "references": refs})
        address = digest(raw)
        inventory[address] = raw
        return address

    def revision(serial, parent, root):
        reachable = closure(root, inventory.__getitem__)
        return Revision(serial, None if parent is None else parent.identity(),
                        root, digest(encode(sorted(reachable)))), reachable

    core = object_file("contract", {"type": "nat"})
    shared = object_file("implementation", {"unit": "shared"}, (core,))
    one = object_file("snapshot", {"seq": 1}, (shared,))
    start, first = revision(1, None, one)
    extra = object_file("implementation", {"unit": "extra"}, (core,))
    two = object_file("snapshot", {"seq": 2}, (shared, extra))
    second, second_files = revision(2, start, two)
    three = object_file("snapshot", {"seq": 3}, (extra,))
    third, third_files = revision(3, second, three)
    third_mutation = object_file("snapshot", {"seq": 3, "side": "alternative"}, (extra,))
    fork, fork_files = revision(3, second, third_mutation)
    delta_two = {addr: raw for addr, raw in second_files.items() if addr not in first}
    delta_three = {addr: raw for addr, raw in third_files.items() if addr not in second_files}
    rows = []

    follower = directory / "follower"
    (follower / "cas").mkdir(parents=True)
    cas = follower / "cas"

    def expect(name, value, call):
        try:
            answer = call()
        except (RestoreError, Refusal) as error:
            answer = str(error)
        assert answer == value, (name, answer, value)
        rows.append({"case": name, "decision": answer})

    expect("empty replica", "empty", lambda: inspect(follower, start.identity()))
    expect("bootstrap from a complete verified view", "published",
           lambda: publish(follower, start, start.identity(), first))
    expect("lagging replica reads its historical root", "historical-only",
           lambda: inspect(follower, second.identity()))
    expect("offer valid next manifest with missing blob", "missing object",
           lambda: publish(follower, second, second.identity(), {two: delta_two[two]}))
    expect("offer bad bytes at known address", "delta-digest-mismatch",
           lambda: publish(follower, second, second.identity(), delta_two | {extra: b"not exact"}))
    expect("offer a structurally valid unrequested support blob", "delta-outside-closure",
           lambda: publish(follower, second, second.identity(),
                           delta_two | {third_mutation: inventory[third_mutation]}))
    expect("changed inventory even if supplied as trusted", "inventory-mismatch",
           lambda: publish(follower, replace(second, inventory=start.inventory),
                           replace(second, inventory=start.inventory).identity(), delta_two))

    transaction_file = directory / "interrupted.json"
    transaction_file.write_bytes(encode({"target": asdict(second),
                                         "delta": {addr: raw.decode() for addr, raw in delta_two.items()}}))
    child = subprocess.run([sys.executable, __file__, "--interrupt", str(follower), str(transaction_file)],
                           capture_output=True, check=False)
    assert child.returncode == 24 and not child.stdout and not child.stderr
    with closing(database(follower / "selected.sqlite")) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert selected(connection) == start
    assert {addr for addr in delta_two if (cas / addr).exists()} == set(delta_two)
    expect("process exit after CAS staging and before commit", "historical-only",
           lambda: inspect(follower, second.identity()))
    expect("retry recognizes exact staged bytes", "published",
           lambda: publish(follower, second, second.identity(), delta_two))
    expect("identical retransmission is idempotent", "already-selected",
           lambda: publish(follower, second, second.identity(), delta_two))
    expect("current selected graph has no writer fence", "read-only",
           lambda: inspect(follower, second.identity(), promote=True))
    expect("writer fence for previous revision is inapplicable", "read-only",
           lambda: inspect(follower, second.identity(), promote=True,
                           fence=(start.identity(), "separate-writer-authority")))
    expect("current verified graph with an external fence", "eligible-with-external-fence",
           lambda: inspect(follower, second.identity(), promote=True,
                           fence=(second.identity(), "separate-writer-authority")))

    (cas / shared).write_bytes(b"corrupt synthetic bytes")
    expect("detect corrupt retained dependency", "unreadable",
           lambda: inspect(follower, second.identity()))
    expect("exact same-revision repair restores resident closure", "already-selected",
           lambda: publish(follower, second, second.identity(), {shared: second_files[shared]}))
    expect("verify repaired root", "exact-current-read", lambda: inspect(follower, second.identity()))

    expect("reject unrequested fork at the next serial", "revision-scope-mismatch",
           lambda: publish(follower, fork, third.identity(), fork_files))
    expect("apply exact next serial increment", "published",
           lambda: publish(follower, third, third.identity(), delta_three))
    expect("reject replayed predecessor", "non-successor",
           lambda: publish(follower, second, second.identity(), delta_two))
    expect("verify exact final closure", "exact-current-read", lambda: inspect(follower, third.identity()))
    return {
        "format": "graph-replica-recovery-01", "sqlite": sqlite3.sqlite_version,
        "revision_identities": [row.identity() for row in (start, second, third)],
        "closure_sizes": list(map(len, (first, second_files, third_files))),
        "incremental_objects": list(map(len, (delta_two, delta_three))),
        "interrupted_child_exit": child.returncode, "rows": rows,
    }


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--interrupt":
        handoff = json.loads(Path(sys.argv[3]).read_bytes())
        target = Revision(**handoff["target"])
        delta = {addr: value.encode() for addr, value in handoff["delta"].items()}
        publish(Path(sys.argv[2]), target, target.identity(), delta, interrupted=True)
        sys.exit(1)
    with TemporaryDirectory(prefix="llmlang-replica-recovery-") as temp:
        ledger = experiment(Path(temp))
    text = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
