#!/usr/bin/env python3
"""Check versioned proof cache keys, atomic publication, and recovery."""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCHEMA = """
CREATE TABLE object (
    digest TEXT PRIMARY KEY,
    payload BLOB NOT NULL
);
CREATE TABLE receipt (
    kind TEXT NOT NULL CHECK (kind IN ('modular', 'provider', 'premise', 'closed')),
    request TEXT NOT NULL,
    digest TEXT NOT NULL REFERENCES object(digest),
    PRIMARY KEY (kind, request)
);
CREATE TABLE publication (
    slot INTEGER PRIMARY KEY CHECK (slot = 0),
    kind TEXT NOT NULL CHECK (kind = 'closed'),
    request TEXT NOT NULL,
    FOREIGN KEY (kind, request) REFERENCES receipt(kind, request)
);
"""


class CacheError(ValueError):
    pass


def wire(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(content):
    return sha256(content).hexdigest()


def request_digest(value):
    return digest(wire(value))


def connect(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 2000")
    return db


@dataclass(frozen=True)
class Modular:
    spg: str
    caller_contract: str
    callee_contract: str
    assumptions: tuple[str, ...]
    profile: str
    decoder: str
    generator: str
    compiler: str
    toolchain: str

    def request(self):
        return request_digest(["modular-proof/1", asdict(self)])


@dataclass(frozen=True)
class Proof:
    kind: str
    request: str
    body: str

    def payload(self):
        return wire(asdict(self) | {"format": "fixture-proof-receipt/1"})

    def address(self):
        return digest(self.payload())


def save(db, proof):
    own_transaction = not db.in_transaction
    if own_transaction:
        db.execute("BEGIN IMMEDIATE")
    try:
        present = lookup(db, proof.kind, proof.request)
        if present is not None and present != proof.address():
            raise CacheError("conflicting receipt")
        db.execute("INSERT OR IGNORE INTO object VALUES (?, ?)", (proof.address(), proof.payload()))
        db.execute("INSERT OR IGNORE INTO receipt VALUES (?, ?, ?)",
                   (proof.kind, proof.request, proof.address()))
    except BaseException:
        if own_transaction:
            db.rollback()
        raise
    if own_transaction:
        db.commit()


def lookup(db, kind, request):
    row = db.execute("""
        SELECT receipt.digest, object.payload
        FROM receipt JOIN object USING (digest)
        WHERE receipt.kind = ? AND receipt.request = ?
        """, (kind, request)).fetchone()
    if row is None:
        return None
    address, payload = row
    if digest(payload) != address:
        raise CacheError("payload digest mismatch")
    subject = json.loads(payload)
    if (subject.get("kind"), subject.get("request")) != (kind, request):
        raise CacheError("receipt subject mismatch")
    if subject.get("format") != "fixture-proof-receipt/1":
        raise CacheError("unsupported receipt format")
    if kind == "closed":
        verify_inventory(db, request, subject["body"])
    return address


def closed(snapshot, dependencies, trust="fixture-allowlist-v1"):
    inventory = sorted((item.kind, item.request, item.address()) for item in dependencies)
    key = request_digest(["closed-proof/1", snapshot, trust, inventory])
    return Proof("closed", key, wire({"snapshot": snapshot, "trust": trust,
                                      "dependencies": inventory}).decode("utf-8"))


def verify_inventory(db, request, encoded):
    body = json.loads(encoded)
    required = body["dependencies"]
    if sorted(item[0] for item in required) != ["modular", "premise", "provider"]:
        raise CacheError("incomplete proof inventory")
    if request_digest(["closed-proof/1", body["snapshot"], body["trust"], required]) != request:
        raise CacheError("closure request mismatch")
    for kind, proof_request, address in required:
        if lookup(db, kind, proof_request) != address:
            raise CacheError("missing exact admitted dependency")


def publish(db, receipt):
    if receipt.kind != "closed":
        raise CacheError("invalid publication kind")
    db.execute("BEGIN IMMEDIATE")
    try:
        verify_inventory(db, receipt.request, receipt.body)
        save(db, receipt)
        db.execute("""
            INSERT INTO publication VALUES (0, 'closed', ?)
            ON CONFLICT (slot) DO UPDATE SET request = excluded.request
            """, (receipt.request,))
    except BaseException:
        db.rollback()
        raise
    db.commit()


def active(db):
    row = db.execute("SELECT kind, request FROM publication WHERE slot = 0").fetchone()
    return lookup(db, *row) if row else None


def must_fail(action, reason):
    try:
        action()
    except CacheError as failure:
        if str(failure) == reason:
            return reason
        raise
    raise AssertionError(f"Expected refusal: {reason}")


def versioned_inputs():
    return Modular("canonical-caller-spg", "ordered-caller/1", "ordered-callee/1",
                   ("provider-trace", "trusted-import"), "integer/ordered-v1", "spg-decoder/1",
                   "generator/1", "compile/1", "lean/4.36.0")


def base_inputs():
    module = Proof("modular", versioned_inputs().request(), "generic-checked-caller")
    old_provider = Proof("provider", request_digest(["provider/1", "v1"]), "provider-proof-v1")
    old_leaf = Proof("premise", request_digest(["premise/1", "v1"]), "transitive-proof-v1")
    return module, old_provider, old_leaf


def crash_before_commit(path):
    db = connect(path)
    module, provider, leaf = base_inputs()
    interrupted = closed("interrupted", (module, provider, leaf))
    db.execute("BEGIN IMMEDIATE")
    save(db, interrupted)
    db.execute("UPDATE publication SET request = ? WHERE slot = 0", (interrupted.request,))
    os._exit(17)


def compare(path):
    module, provider, leaf = base_inputs()
    old = closed("snapshot-a", (module, provider, leaf))
    db = connect(path)
    journal = db.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    assert journal == "wal"
    db.executescript(SCHEMA)
    for proof in (module, provider, leaf):
        save(db, proof)
    publish(db, old)
    db.close()

    db = connect(path)
    assert active(db) == old.address()
    truncated = closed("incomplete", (module, provider))
    incomplete = must_fail(lambda: publish(db, truncated), "incomplete proof inventory")
    wrong_request = must_fail(lambda: publish(db, replace(old, request="arbitrary")),
                              "closure request mismatch")
    assert active(db) == old.address()
    save(db, module)
    variants = {
        field: ("changed" if field != "assumptions" else ("weaker-trace",))
        for field in asdict(versioned_inputs())
    }
    misses = {}
    for field, new in variants.items():
        changed = replace(versioned_inputs(), **{field: new})
        found = lookup(db, "modular", changed.request())
        if found is not None:
            raise AssertionError(field)
        misses[field] = "miss"

    different_proof = replace(module, body="new-theorem-bytes-for-same-input-key")
    conflict = must_fail(lambda: save(db, different_proof), "conflicting receipt")
    assert lookup(db, "modular", module.request) == module.address()

    same_statement_new_artifact = replace(leaf, body="independently-checked-new-proof")
    refreshed_artifact = closed("snapshot-a", (module, provider, same_statement_new_artifact))
    assert refreshed_artifact.request != old.request
    assert lookup(db, "closed", refreshed_artifact.request) is None
    trust_changed = closed("snapshot-a", (module, provider, leaf), trust="changed-allowlist-v2")
    assert trust_changed.request != old.request and lookup(db, "closed", trust_changed.request) is None

    reader = connect(path)
    reader.execute("BEGIN")
    assert active(reader) == old.address()
    new_provider = Proof("provider", request_digest(["provider/1", "v2"]), "provider-proof-v2")
    new_leaf = Proof("premise", request_digest(["premise/1", "v2"]), "transitive-proof-v2")
    rebound = closed("snapshot-b", (module, new_provider, new_leaf))
    save(db, new_provider)
    missing = must_fail(lambda: publish(db, rebound), "missing exact admitted dependency")
    assert active(db) == old.address()
    save(db, new_leaf)
    publish(db, rebound)
    assert active(reader) == old.address() and active(db) == rebound.address()
    reader.rollback()
    assert active(reader) == rebound.address()
    reader.close()

    failure = subprocess.run([sys.executable, "-B", str(Path(__file__)), "--crash", str(path)],
                             check=False)
    assert failure.returncode == 17
    db.close()
    db = connect(path)
    assert active(db) == rebound.address()
    interrupted = closed("interrupted", (module, provider, leaf))
    assert lookup(db, "closed", interrupted.request) is None
    publish(db, interrupted)
    assert active(db) == interrupted.address()

    db.execute("UPDATE object SET payload = ? WHERE digest = ?", (b"corrupt", module.address()))
    corrupt = must_fail(lambda: lookup(db, "modular", module.request), "payload digest mismatch")
    corrupt_closure = must_fail(lambda: active(db), "payload digest mismatch")
    db.close()
    return {
        "journal_mode": journal, "modular_input_mutations": misses,
        "baseline_reopened": old.address(), "modular_reused_after_rebind": module.address(),
        "old_closed": old.request, "rebound_closed": rebound.request,
        "changed_artifact_closed": refreshed_artifact.request, "changed_trust_closed": trust_changed.request,
        "cold_rebind_refusal": missing, "different_payload_same_key_refusal": conflict,
        "incomplete_inventory_refusal": incomplete, "wrong_request_refusal": wrong_request,
        "pinned_reader_then_new_view": True, "interrupted_publish_recovered": True,
        "interrupted_publish_same_request_retried": True, "corrupted_payload_refusal": corrupt,
        "corrupted_dependency_blocks_closed_reuse": corrupt_closure,
    }


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--crash":
        crash_before_commit(Path(sys.argv[2]))
    with tempfile.TemporaryDirectory() as root:
        results = compare(Path(root) / "proofs.db")
    print(json.dumps({
        "schema": "llmlang-proof-cache-store/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "runner_sha256": digest(Path(__file__).read_bytes()),
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
