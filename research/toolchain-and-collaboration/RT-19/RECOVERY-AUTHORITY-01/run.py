#!/usr/bin/env python3
"""Compare present-effect reconciliation and fresh append authority in a local fixture."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "MUTABLE-LOG-RECOVERY-01"
POLICIES = ("prepared_authority", "blanket_fresh", "split_fresh", "split_fenced")
SCENARIOS = {
    "ordinary_complete": ("append", None, None),
    "ordinary_fresh": ("before", None, None),
    "ordinary_prefix": ("prefix", None, None),
    "complete_write_revoked": ("append", "write", None),
    "missing_write_revoked": ("before", "write", None),
    "prefix_write_revoked": ("prefix", "write", None),
    "complete_read_revoked": ("append", "read", None),
    "missing_read_revoked": ("before", "read", None),
    "complete_both_revoked": ("receipt", "both", None),
    "write_revokes_after_check": ("before", None, "write"),
    "read_revokes_after_check": ("append", None, "read"),
    "prefix_revokes_after_check": ("prefix", None, "write"),
}


def checksum(value):
    return sha256(value).hexdigest()


def load_prior(directory):
    spec = importlib.util.spec_from_file_location("rt19_mutable_log_fixture", directory / "run.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    return prior


def initialize(prior, root):
    prior.initialize(root, "before_effect")
    with prior.database(root) as db:
        db.execute("CREATE TABLE authority (current_epoch INTEGER, may_observe INTEGER, may_append INTEGER)")
        db.execute("CREATE TABLE original_authority AS SELECT * FROM authority")
        db.execute("INSERT INTO authority VALUES (1,1,1)")
        db.execute("INSERT INTO original_authority SELECT * FROM authority")


def authorization(db, initial=False):
    table = "original_authority" if initial else "authority"
    epoch, observe, append = db.execute(f"SELECT * FROM {table}").fetchone()
    return {"epoch": epoch, "observe": bool(observe), "append": bool(append)}


def revoke(root, rights):
    with sqlite3.connect(root / "journal.sqlite", isolation_level=None, timeout=0) as db:
        try:
            db.execute("UPDATE authority SET current_epoch=current_epoch+1, "
                       "may_observe=may_observe AND ?, may_append=may_append AND ?",
                       (rights not in {"read", "both"}, rights not in {"write", "both"}))
        except sqlite3.OperationalError as error:
            assert error.sqlite_errorname == "SQLITE_BUSY"
            return "busy"
        return "revoked"


def peer(root, rights):
    command = [sys.executable, "-B", __file__, "--revoke", str(root), rights]
    response = subprocess.check_output(command, text=True, timeout=10).strip()
    assert response in {"revoked", "busy"}
    return response


def perform(prior, root, policy, advance):
    with prior.log_handle(root) as fd, prior.database(root) as db:
        fenced = policy == "split_fenced"
        if fenced:
            db.execute("BEGIN IMMEDIATE")
        selected = authorization(db, initial=policy == "prepared_authority")
        display = False
        appended = False
        inspected = False
        changed = None
        before_advance = authorization(db)
        current = before_advance
        if not selected["observe"] or (policy == "blanket_fresh" and not selected["append"]):
            status = "denied_read" if not selected["observe"] else "denied_blanket"
        else:
            desired, target, offset, cached = prior.prepare_read(db)
            previous = prior.read_log(fd)
            records, tail, complete = prior.split(previous)
            assert complete
            inspected = True
            expected = json.loads(desired)
            needs_write = expected not in records
            assert not tail or needs_write
            if needs_write and not selected["append"]:
                status = "denied_append"
            else:
                if advance:
                    changed = peer(root, advance)
                    assert changed == ("busy" if fenced else "revoked")
                current = authorization(db)
                status = prior.check_exact(fd, desired, target, offset, cached)
                display = status in prior.SUCCESS
                appended = prior.read_log(fd) != previous
                assert status in {"present", "cached", "appended", "completed_prefix"}
                if display and not cached:
                    prior.receipt(db, desired)
        if fenced:
            db.execute("COMMIT")
        if changed == "busy":
            assert peer(root, advance) == "revoked"
        final = authorization(db)
    return {
        "status": status, "proof_returned": display, "external_log_inspected": inspected, "external_bytes_appended": appended,
        "selected_authorization": selected, "before_advance": before_advance, "authority_at_result": current,
        "authority_after_result": final, "peer_before_result": changed,
        "unauthorized_effect": appended and not current["append"],
        "unauthorized_disclosure": display and not current["observe"],
    }


def exercise(prior, root, policy, name):
    cut, early, late = SCENARIOS[name]
    initialize(prior, root)
    stopped = subprocess.run([sys.executable, "-B", str(prior.__file__), "--crash", str(root), cut],
                             capture_output=True, timeout=10)
    assert stopped.returncode == 71 and not stopped.stdout and not stopped.stderr
    if early:
        assert peer(root, early) == "revoked"
    old = (root / "effects.log").read_bytes()
    result = perform(prior, root, policy, late)
    new = (root / "effects.log").read_bytes()
    records, tail, complete = prior.split(new)
    assert complete and len(records) <= 1
    assert result["external_bytes_appended"] == (old != new)
    assert not result["proof_returned"] or (records == [{"id": prior.TASK, "payload": prior.PAYLOAD}] and not tail)
    if not result["external_log_inspected"]:
        assert not result["proof_returned"] and not result["external_bytes_appended"]
    result["valid_historical_result_denied"] = name == "complete_write_revoked" and not result["proof_returned"]
    return {"case": name, "policy": policy, "stopped_after": cut, "before_hex": old.hex(),
            "after_hex": new.hex(), **result}


def run(directory, prior_path):
    prior = load_prior(prior_path)
    rows = [exercise(prior, directory / f"{name}-{policy}", policy, name)
            for name, policy in product(SCENARIOS, POLICIES)]
    fields = ("proof_returned", "unauthorized_effect", "unauthorized_disclosure", "valid_historical_result_denied")
    totals = {}
    for policy in POLICIES:
        counters = Counter()
        for row in rows:
            if row["policy"] == policy:
                for name in fields:
                    counters[name] += row[name]
        totals[policy] = dict(counters)
    safe = totals["split_fenced"]
    assert safe["unauthorized_effect"] == safe["unauthorized_disclosure"] == safe["valid_historical_result_denied"] == 0
    assert totals["split_fresh"]["unauthorized_effect"] and totals["split_fresh"]["unauthorized_disclosure"]
    events = {(row["case"], row["policy"]): row for row in rows}
    assert events["complete_write_revoked", "split_fenced"]["status"] == "present"
    assert events["missing_write_revoked", "split_fenced"]["status"] == "denied_append"
    assert events["prefix_write_revoked", "split_fenced"]["status"] == "denied_append"
    assert not events["complete_read_revoked", "split_fenced"]["external_log_inspected"]
    assert events["write_revokes_after_check", "split_fenced"]["peer_before_result"] == "busy"
    return {
        "schema": "llmlang-rt19-recovery-authority/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "linux": platform.release(),
        "runner_sha256": checksum(Path(__file__).read_bytes()), "prior_sha256": checksum(Path(prior.__file__).read_bytes()),
        "scenarios": len(rows), "metrics": totals, "observations": rows,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--revoke":
        print(revoke(Path(sys.argv[2]), sys.argv[3]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--log-fixture", type=Path, default=PRIOR)
        args = parser.parse_args()
        with TemporaryDirectory(prefix="llmlang-rt19-recovery-auth-") as scratch:
            result = run(Path(scratch), args.log_fixture.resolve())
        observations = result.pop("observations")
        print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
        print(",\n".join("    " + json.dumps(row) for row in observations))
        print("  ]\n}")
