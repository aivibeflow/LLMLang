"""Pair kernel admission obligations with native certificate and SQLite race controls."""
import argparse
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import runpy
import sqlite3
from subprocess import check_output
from tempfile import TemporaryDirectory
from threading import Event, Thread

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PIN = "4ec1a3fafc4aff01fa58067c46fd0f9bf452a3f1"
CHECKER = HERE.parent / "SMT-ARTIFACT-REPLAY-01/run.py"
CERT = runpy.run_path(str(CHECKER))
DEPENDENCIES = {"observed-source": b"recorded integer return", "expectation": b"exact required return"}
ROLES = tuple(sorted(DEPENDENCIES))


@dataclass(frozen=True)
class Task:
    observed: int = 3
    required: int = 3
    bound: int = 4
    revision: str = "source-revision-a"
    semantics: str = "integers-within-bound"
    premise: str = "current-observation"


@dataclass(frozen=True)
class Policy:
    epoch: int = 5
    premise: str | None = "current-observation"


@dataclass(frozen=True)
class Receipt:
    query: str
    revision: str
    semantics: str
    dependencies: tuple[tuple[str, str], ...]
    epoch: int
    artifact: str


def digest(value):
    return sha256(value).hexdigest()


def query(task):
    coverage = "true" if task.observed <= task.bound else "false"
    return (
        f"(set-logic QF_LIA)\n(declare-const x Int)\n(assert (= x {task.observed}))\n"
        f"(assert (not (= x {task.required})))\n(assert {coverage})\n(check-sat)\n(exit)\n"
    ).encode()


def exact_query_id(task):
    # The source bound is still part of the typed request when the folded SMT bytes are unchanged.
    return digest(json.dumps({"bound": task.bound, "wire": digest(query(task))},
                             sort_keys=True, separators=(",", ":")).encode())


def inventory():
    return tuple((role, digest(DEPENDENCIES[role])) for role in ROLES)


def issue(task, policy, proof):
    return Receipt(exact_query_id(task), task.revision, task.semantics, inventory(), policy.epoch, digest(proof))


def preflight(task, receipt, policy, dependencies, payload):
    if receipt.revision != task.revision or receipt.semantics != task.semantics:
        return "semantic-scope-refused"
    if receipt.query != exact_query_id(task):
        return "typed-query-refused"
    if receipt.dependencies != inventory() or set(dependencies) != set(ROLES):
        return "inventory-refused"
    if any(digest(dependencies[role]) != address for role, address in receipt.dependencies):
        return "dependency-bytes-refused"
    if task.observed > task.bound:
        return "source-outside-bound"
    if policy.epoch != receipt.epoch or policy.premise != task.premise:
        return "live-policy-refused"
    if digest(payload) != receipt.artifact:
        return "artifact-bytes-refused"
    return "candidate"


def check_native(tools, scope, blob, directory):
    return CERT["assess"](tools, "alethe", query(scope), blob, directory, None)


def admission(tools, scope, receipt, policy, dependencies, blob, directory):
    status = preflight(scope, receipt, policy, dependencies, blob)
    if status != "candidate":
        return status
    return "admitted" if check_native(tools, scope, blob, directory) == "checked" else "certificate-refused"


def native_matrix(tools, directory):
    task = Task()
    current = Policy()
    outside = replace(task, observed=7)
    changed_bound = replace(task, bound=5)
    assert query(task) == query(changed_bound) and exact_query_id(task) != exact_query_id(changed_bound)
    cases = {"original": task, "outside-bound": outside, "altered-result": replace(task, observed=4)}
    native = {}
    for label, value in cases.items():
        status, artifact = CERT["generate"](tools.cvc5, "alethe", query(value), directory, None)
        assert status == ("sat" if label == "altered-result" else "unsat")
        raw = check_native(tools, value, artifact, directory)
        assert raw == ("missing-alethe-certificate" if label == "altered-result" else "checked")
        decision = admission(tools, value, issue(value, current, artifact), current, DEPENDENCIES, artifact, directory)
        assert decision == {"original": "admitted", "outside-bound": "source-outside-bound",
                            "altered-result": "certificate-refused"}[label]
        native[label] = {"solver": status, "certificate": raw, "proof_or_verdict": artifact.decode(),
                         "source_admission": decision, "query": query(value).decode()}
    proof = native["original"]["proof_or_verdict"].encode()
    receipt = issue(task, current, proof)
    hole = proof.replace(b":rule resolution :premises (a0 a1) :args (@p_1 true)", b":rule hole", 1)
    assert hole != proof and check_native(tools, task, hole, directory) == "holey"
    controls = (
        ("different-revision", replace(task, revision="source-revision-b"), receipt,
         current, DEPENDENCIES, proof, "semantic-scope-refused"),
        ("different-semantics", replace(task, semantics="different-profile"), receipt,
         current, DEPENDENCIES, proof, "semantic-scope-refused"),
        ("different-bound-same-wire", changed_bound, receipt, current, DEPENDENCIES, proof, "typed-query-refused"),
        ("unsupported-rule", task, replace(receipt, artifact=digest(hole)), current, DEPENDENCIES, hole,
         "certificate-refused"),
        ("missing-source-role", task, receipt, current, {"expectation": DEPENDENCIES["expectation"]}, proof,
         "inventory-refused"),
        ("forged-declared-inventory", task, replace(receipt, dependencies=receipt.dependencies[:-1]),
         current, DEPENDENCIES, proof, "inventory-refused"),
        ("corrupt-dependency", task, receipt, current, {**DEPENDENCIES, "expectation": b"corrupt"}, proof,
         "dependency-bytes-refused"),
        ("revoked-premise", task, receipt, replace(current, premise=None), DEPENDENCIES, proof,
         "live-policy-refused"),
        ("previous-epoch", task, receipt, replace(current, epoch=6), DEPENDENCIES, proof, "live-policy-refused"),
        ("corrupt-proof-bytes", task, receipt, current, DEPENDENCIES, proof + b"changed", "artifact-bytes-refused"),
    )
    outcome = {}
    for label, scope, candidate, policy, roles, payload, expected in controls:
        observed = admission(tools, scope, candidate, policy, roles, payload, directory)
        assert observed == expected, (label, observed)
        outcome[label] = observed
    return task, receipt, native, outcome


def finite_projection(task, receipt, payload):
    failures = 0
    passed = 0
    for gates in product((False, True), repeat=6):
        wrong_revision, wrong_query, wrong_inventory, wrong_dependency, revoked, wrong_artifact = gates
        proposed = replace(receipt,
            revision="old" if wrong_revision else receipt.revision,
            query="other" if wrong_query else receipt.query,
            dependencies=() if wrong_inventory else receipt.dependencies,
            artifact="invalid" if wrong_artifact else receipt.artifact,
        )
        policy = Policy(premise=None) if revoked else Policy()
        values = {**DEPENDENCIES, "expectation": b"other"} if wrong_dependency else DEPENDENCIES
        # Real artifact check is in native_matrix. Here the recorded content address represents a checked witness.
        result = preflight(task, proposed, policy, values, payload)
        assert (result == "candidate") == (not any(gates))
        passed += result == "candidate"
        failures += result != "candidate"
    return {"eligible_preflights": passed, "refused_preflights": failures}


def connection(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA busy_timeout=2500")
    return db


def publication(path, task, receipt, independently_checked):
    with closing(connection(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        epoch, premise = db.execute("SELECT epoch, premise FROM authority").fetchone()
        if (independently_checked != receipt or epoch != receipt.epoch or premise != task.premise
                or (receipt.query, receipt.revision, receipt.semantics)
                != (exact_query_id(task), task.revision, task.semantics)):
            db.rollback()
            return "refused-at-publication"
        identity = digest(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")).encode())
        db.execute("INSERT OR IGNORE INTO history VALUES (?, ?, ?, ?)",
                   (identity, receipt.query, epoch, premise))
        db.commit()
    return "published"


def revocation(path):
    with closing(connection(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE authority SET epoch = epoch + 1, premise = NULL")
        db.commit()


def races(directory, task, candidate, checked_receipt):
    results = {}
    for order in ("revoke-before-publication", "revoke-after-publication"):
        path = directory / f"{order}.sqlite"
        with closing(connection(path)) as db:
            db.executescript("""
                PRAGMA journal_mode = WAL;
                CREATE TABLE authority (epoch INTEGER NOT NULL, premise TEXT);
                INSERT INTO authority VALUES (5, 'current-observation');
                CREATE TABLE history (identity TEXT PRIMARY KEY, query TEXT NOT NULL,
                                      epoch INTEGER NOT NULL, premise TEXT NOT NULL);
            """)
        permission, complete = Event(), Event()
        outcome = []
        worker_errors = []
        def writer():
            try:
                assert permission.wait(3)
                outcome.append(publication(path, task, candidate, checked_receipt))
            except BaseException as error:
                worker_errors.append(error)
            finally:
                complete.set()
        agent = Thread(target=writer)
        agent.start()
        if order == "revoke-before-publication":
            revocation(path)
            permission.set()
            assert complete.wait(3)
        else:
            results["unrelated-checked-identity"] = publication(
                path, task, candidate, replace(candidate, artifact="different"),
            )
            assert results["unrelated-checked-identity"] == "refused-at-publication"
            permission.set()
            assert complete.wait(3)
            assert publication(path, task, candidate, checked_receipt) == "published"
            revocation(path)
        agent.join(timeout=1)
        assert not worker_errors, worker_errors
        with closing(connection(path)) as db:
            history = db.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            valid = db.execute("""SELECT COUNT(*) FROM history JOIN authority
                                  ON history.epoch = authority.epoch AND history.premise = authority.premise""").fetchone()[0]
        expected_history = int(order == "revoke-after-publication")
        assert valid == 0 and history == expected_history
        assert outcome == (["published"] if expected_history else ["refused-at-publication"])
        results[order] = {"writer": outcome[0], "historical_receipts": history, "active_receipts": valid}
    return results


def check(tools, directory):
    task, receipt, native, controls = native_matrix(tools, directory)
    assert native["original"]["source_admission"] == "admitted"
    payload = native["original"]["proof_or_verdict"].encode()
    kernel = check_output([tools.lean, "-DwarningAsError=true", HERE / "Admission.lean"], text=True).splitlines()
    assert len(kernel) == 8 and all("does not depend on any axioms" in line for line in kernel)
    return {
        "kernel": kernel, "native": native, "controls": controls,
        "publication": races(directory, task, receipt, receipt),
        "finite_projection": finite_projection(task, receipt, payload), "checked_request": asdict(receipt),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("lean", "cvc5", "carcara", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    tools = parser.parse_args()
    reference = CHECKER.relative_to(ROOT).as_posix()
    archive = check_output(["git", "show", f"{PIN}:{reference}"], cwd=ROOT)
    assert CHECKER.read_bytes() == archive
    versions = {}
    for name in ("lean", "cvc5", "carcara"):
        binary = getattr(tools, name).resolve(strict=True)
        setattr(tools, name, binary)
        versions[name] = {"version": check_output([binary, "--version"], text=True).splitlines()[0],
                          "sha256": digest(binary.read_bytes())}
    with TemporaryDirectory() as scratch:
        evidence = check(tools, Path(scratch))
    tools.output.write_text(json.dumps({"basis": PIN, "checker_source_sha256": digest(archive),
                                       "tools": versions, "sqlite": sqlite3.sqlite_version, **evidence},
                                      sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
