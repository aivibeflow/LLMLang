"""Persist exact occurrence-derived closure, including a checked recursive group."""
import argparse
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
import os
from pathlib import Path
import runpy
import sqlite3
from subprocess import check_output, run
import sys
import tarfile
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OCCURRENCES = HERE.parent / "SPG-PDG-OCCURRENCES-01/run.py"
PERSISTENCE = HERE.parent / "PROOF-CACHE-STORE-01/run.py"
PIN = "6a7443f7c687d08fffb98bd880f75f995622a058"
OCC = runpy.run_path(str(OCCURRENCES))
STORE = runpy.run_path(str(PERSISTENCE))
SCHEMA = """
CREATE TABLE payloads (address TEXT PRIMARY KEY, payload BLOB NOT NULL);
CREATE TABLE receipts (request TEXT PRIMARY KEY, address TEXT NOT NULL REFERENCES payloads);
CREATE TABLE publications (
    token TEXT PRIMARY KEY, subject TEXT NOT NULL, inventory TEXT NOT NULL, closure TEXT NOT NULL
);
CREATE TABLE active (
    slot INTEGER PRIMARY KEY CHECK (slot = 0), token TEXT NOT NULL REFERENCES publications
);
"""


class Refused(ValueError):
    pass


@dataclass(frozen=True)
class Demand:
    root: object
    inventory: dict
    subject: str


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return sha256(wire(value)).hexdigest()


def claim_request(claim, requires):
    return digest(["proof-occurrence/1", asdict(claim), [asdict(row) for row in sorted(requires)],
                   OCC["PRODUCER"], OCC["TOOLCHAIN"]])


def persist(db, receipt):
    request = claim_request(receipt.claim, receipt.requires)
    payload = wire(asdict(receipt))
    address = sha256(payload).hexdigest()
    existing = db.execute("SELECT address FROM receipts WHERE request = ?", (request,)).fetchone()
    if existing is not None and existing != (address,):
        raise Refused("conflicting-receipt")
    db.execute("INSERT OR IGNORE INTO payloads VALUES (?, ?)", (address, payload))
    db.execute("INSERT OR IGNORE INTO receipts VALUES (?, ?)", (request, address))


def collect(db, proof, demand):
    results = {}
    for claim, dependencies in demand.inventory.items():
        request = claim_request(claim, dependencies)
        stored = db.execute("""
            SELECT address, payload FROM receipts JOIN payloads USING(address) WHERE request = ?
        """, (request,)).fetchone()
        if stored is None:
            continue
        address, payload = stored
        if sha256(payload).hexdigest() != address:
            raise Refused("damaged-receipt")
        content = json.loads(payload)
        content["claim"] = proof.Claim(**content["claim"])
        content["requires"] = tuple(proof.Claim(**entry) for entry in content["requires"])
        results[claim] = proof.Receipt(**content)
    return results


def closure(db, proof, demand):
    receipts = collect(db, proof, demand)
    result = OCC["closure"](proof, demand.root, demand.inventory, receipts)
    if result.evidence_digest is None:
        raise Refused(",".join(sorted({reason for _, reason in result.blockers})))
    return result.evidence_digest


def inventory_digest(demand):
    return digest([(asdict(claim), [asdict(item) for item in sorted(edge)])
                   for claim, edge in sorted(demand.inventory.items())])


def current(db):
    row = db.execute("SELECT token FROM active WHERE slot = 0").fetchone()
    return row[0] if row else None


def publish(db, proof, demand, expected, incoming=(), *, terminate=False):
    db.execute("BEGIN IMMEDIATE")
    try:
        if current(db) != expected:
            raise Refused("stale-head")
        for receipt in incoming:
            persist(db, receipt)
        closed = closure(db, proof, demand)
        inventory = inventory_digest(demand)
        token = digest(["proof-publication/1", demand.subject, inventory, closed])
        db.execute("INSERT OR IGNORE INTO publications VALUES (?, ?, ?, ?)",
                   (token, demand.subject, inventory, closed))
        db.execute("INSERT INTO active VALUES (0, ?) ON CONFLICT(slot) DO UPDATE SET token = excluded.token",
                   (token,))
        if terminate:
            os._exit(73)
    except BaseException:
        db.rollback()
        raise
    db.commit()
    return token


def read_publication(db, proof, demand):
    own_transaction = not db.in_transaction
    if own_transaction:
        db.execute("BEGIN")
    try:
        row = db.execute("""
            SELECT publications.subject, publications.inventory, publications.closure, active.token
            FROM active JOIN publications USING(token) WHERE active.slot = 0
        """).fetchone()
        if row is None or row[:2] != (demand.subject, inventory_digest(demand)):
            raise Refused("wrong-active-subject")
        if row[2] != closure(db, proof, demand):
            raise Refused("wrong-closure")
        return row[3]
    finally:
        if own_transaction:
            db.rollback()


def reject(callback, reason):
    try:
        callback()
    except Refused as refused:
        assert str(refused) == reason, (reason, refused)
        return str(refused)
    raise AssertionError(f"expected {reason}")


def import_pinned(directory):
    git_archive = check_output(["git", "archive", OCC["REVISION"], OCC["PROTOTYPE"],
                               OCC["CALLS"], OCC["CLOSURE"]], cwd=ROOT)
    with tarfile.open(fileobj=BytesIO(git_archive)) as archive:
        archive.extractall(directory, filter="data")
    sys.path.insert(0, str(directory / OCC["CLOSURE"]))
    import closure as proof
    spec = spec_from_file_location("pinned_spg_calls", directory / OCC["CALLS"] / "run.py")
    calls = module_from_spec(spec)
    spec.loader.exec_module(calls)
    return calls, proof


def fixtures(calls, proof):
    original = calls.dispatch_program()
    paired = (*original.contracts["forward"], ("first", "last", "first", "last"))
    original = replace(original, contracts={**original.contracts, "forward": paired},
                       bindings={**original.bindings, "other": "other"})
    repeated = calls.replace_body(original, "late", 'op("provider", n) + op("provider", n)')
    mixed = calls.replace_body(original, "late", 'op("provider", n) + pin("primary", n)')
    rebound = replace(mixed, bindings={**mixed.bindings, "provider": "alternate"})
    deep = calls.replace_body(repeated, "primary", 'emit("first", emit("last", op("other", n)))')
    edit = calls.replace_body(deep, "other", "n - 8")
    result = {}
    for label, program in zip(("repeated", "mixed", "rebound", "deep", "transitive-edit"),
                              (repeated, mixed, rebound, deep, edit)):
        graph = calls.compile_program(program)
        entry = graph.snapshot.mapping["implementation:late"]
        root, inventory, calls_by_location = OCC["build"](graph, entry, calls, proof)
        result[label] = (Demand(root, inventory, graph.snapshot.root_hash), calls_by_location, entry)
    return result


def receipt_set(proof, demand):
    return OCC["tickets"](proof, demand.inventory)


def worker(database, checkout, expected, subject):
    calls, proof = import_pinned(checkout)
    demand = fixtures(calls, proof)[subject][0]
    with closing(STORE["connect"](database)) as db:
        publish(db, proof, demand, expected, receipt_set(proof, demand).values(), terminate=True)


def group_proof(tool):
    source = HERE / "RecursiveGroup.lean"
    observation = check_output([tool, "-DwarningAsError=true", source], cwd=ROOT, text=True).strip()
    assert observation == "'ReceiptGroup.simultaneous' does not depend on any axioms"
    version = check_output([tool, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    subject = digest(["recursive-group/1", ["ReceiptGroup.left", "ReceiptGroup.right"],
                      "ReceiptGroup.simultaneous", "structural-predecessor",
                      sha256(source.read_bytes()).hexdigest(), version, observation])
    return subject, version, observation


def recursion(db, proof, tool, previous):
    recursive, version, axiom_report = group_proof(tool)
    left = proof.Claim("recursive-local", "ReceiptGroup.left", "left-id", "nat/v1")
    right = proof.Claim("recursive-local", "ReceiptGroup.right", "right-id", "nat/v1")
    cyclic = Demand(left, {left: (right,), right: (left,)}, recursive)
    refusal = reject(lambda: publish(db, proof, cyclic, previous,
                                     receipt_set(proof, cyclic).values()), "cyclic-discharge")

    group = proof.Claim("joint-kernel-proof", recursive, "ReceiptGroup.simultaneous", "nat/v1")
    premise = proof.Claim("assumption", recursive, "admit-structural-induction", "nat/v1")
    packaged = Demand(group, {group: (premise,), premise: ()}, recursive)
    rows = receipt_set(proof, packaged)
    rows[group] = replace(rows[group], artifact=recursive)
    waiting = reject(lambda: publish(db, proof, packaged, previous, (rows[group],)), "unresolved-assumption")
    actual = publish(db, proof, packaged, previous, rows.values())
    assert read_publication(db, proof, packaged) == actual and actual != previous
    return {"raw_cycle": refusal, "missing_group_admission": waiting, "joint": actual,
            "theorem": recursive, "kernel": version, "axioms": axiom_report}


def exercise(directory, tool):
    with TemporaryDirectory() as checkout_name:
        calls, proof = import_pinned(Path(checkout_name))
        scopes = fixtures(calls, proof)
    database = directory / "closure.sqlite"
    repeated, sites, entry = scopes["repeated"]
    assert len(sites) == 2 and len({value["provider"] for value in sites.values()}) == 1
    all_repeated = receipt_set(proof, repeated)
    missing = min(sites)
    controls = {}
    tokens = {}
    with closing(STORE["connect"](database)) as writer, closing(STORE["connect"](database)) as observer:
        assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        writer.executescript(SCHEMA)
        controls["one-occurrence-absent"] = reject(
            lambda: publish(writer, proof, repeated, None, (row for claim, row in all_repeated.items() if claim != missing)),
            "pending-receipt")
        shortened = {**all_repeated, repeated.root: replace(all_repeated[repeated.root],
                     requires=tuple(claim for claim in repeated.inventory[repeated.root] if claim != missing))}
        controls["forged-shorter-root"] = reject(
            lambda: publish(writer, proof, repeated, None, shortened.values()), "pending-receipt")
        assert current(observer) is None and observer.execute("SELECT COUNT(*) FROM receipts").fetchone() == (0,)
        tokens["repeated"] = publish(writer, proof, repeated, None, all_repeated.values())
        assert read_publication(observer, proof, repeated) == tokens["repeated"]
        assert publish(writer, proof, repeated, tokens["repeated"], all_repeated.values()) == tokens["repeated"]

        mixed, _, mixed_entry = scopes["mixed"]
        rebound, rebound_sites, rebound_entry = scopes["rebound"]
        assert mixed_entry == rebound_entry and len({row["provider"] for row in rebound_sites.values()}) == 2
        mixed_rows = receipt_set(proof, mixed)
        rebound_rows = receipt_set(proof, rebound)
        modular = next(claim for claim in mixed.inventory if claim.role == "modular-theorem" and claim.subject == mixed_entry)
        assert mixed_rows[modular] == rebound_rows[modular]
        tokens["mixed"] = publish(writer, proof, mixed, tokens["repeated"], mixed_rows.values())
        controls["old-receipts-for-rebind"] = reject(
            lambda: publish(writer, proof, rebound, tokens["mixed"]), "pending-receipt")
        observer.execute("BEGIN")
        assert read_publication(observer, proof, mixed) == tokens["mixed"]
        tokens["rebound"] = publish(writer, proof, rebound, tokens["mixed"], rebound_rows.values())
        assert read_publication(observer, proof, mixed) == tokens["mixed"]
        observer.commit()
        assert read_publication(observer, proof, rebound) == tokens["rebound"]
        controls["stale-publication-head"] = reject(
            lambda: publish(observer, proof, mixed, tokens["mixed"]), "stale-head")

        deep, _, deep_entry = scopes["deep"]
        conditional_claim = proof.Claim("assumption", deep.subject, "observation-premise")
        body = next(claim for claim in deep.inventory if claim.role == "body-proof")
        conditional = Demand(deep.root, {
            **deep.inventory, body: tuple(sorted((*deep.inventory[body], conditional_claim))),
            conditional_claim: (),
        }, deep.subject)
        conditional_receipts = receipt_set(proof, conditional)
        controls["pending-external-premise"] = reject(
            lambda: publish(writer, proof, conditional, tokens["rebound"],
                            (row for claim, row in conditional_receipts.items() if claim != conditional_claim)),
            "unresolved-assumption")
        tokens["conditional-closed"] = publish(writer, proof, conditional, tokens["rebound"],
                                                conditional_receipts.values())
        assert read_publication(observer, proof, conditional) == tokens["conditional-closed"]

        edit, _, edited_entry = scopes["transitive-edit"]
        assert deep_entry == edited_entry and deep.subject != edit.subject
        before_counts = writer.execute("SELECT count(*) FROM receipts").fetchone()[0]
        with TemporaryDirectory() as child_checkout:
            process = run([sys.executable, "-B", __file__, "--crash", database, child_checkout,
                           tokens["conditional-closed"], "transitive-edit"], cwd=ROOT, timeout=20,
                          capture_output=True)
        assert process.returncode == 73, (process.returncode, process.stdout, process.stderr)
        assert read_publication(observer, proof, conditional) == tokens["conditional-closed"]
        assert observer.execute("SELECT count(*) FROM receipts").fetchone()[0] == before_counts
        tokens["transitive-edit"] = publish(writer, proof, edit, tokens["conditional-closed"],
                                             receipt_set(proof, edit).values())
        assert read_publication(observer, proof, edit) == tokens["transitive-edit"]
        controls["interrupted-publish"] = {"exit": process.returncode, "old-visible": True, "retry": "checked"}
        recursion_checks = recursion(writer, proof, tool, tokens["transitive-edit"])
    return {"closures": tokens, "controls": controls, "recursion": recursion_checks,
            "source_subjects": {name: item[0].subject for name, item in scopes.items()},
            "graph_sizes": {name: len(item[0].inventory) for name, item in scopes.items()},
            "same_modular_receipt_during_rebind": True,
            "wal_reader_retained_previous_closure": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--crash", nargs=4)
    args = parser.parse_args()
    if args.crash:
        database, directory, expected, subject = args.crash
        return worker(Path(database), Path(directory), expected, subject)
    pins = {}
    for path in (OCCURRENCES, PERSISTENCE):
        archived = check_output(["git", "show", f"{PIN}:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT)
        assert path.read_bytes() == archived
        pins[path.relative_to(ROOT).as_posix()] = sha256(archived).hexdigest()
    with TemporaryDirectory() as directory:
        result = exercise(Path(directory), args.lean.resolve(strict=True))
    args.output.write_text(json.dumps({"basis": PIN, "sources": pins, "sqlite": sqlite3.sqlite_version,
                                      **result}, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
