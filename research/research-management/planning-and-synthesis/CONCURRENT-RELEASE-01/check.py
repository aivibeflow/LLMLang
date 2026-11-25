"""Probe the exact local release gate at two controlled cross-process cut points."""

import argparse
from hashlib import sha256
import importlib.util
from itertools import product
import json
import multiprocessing
from pathlib import Path
import shutil
import sqlite3
import sys
from tempfile import TemporaryDirectory
from typing import get_args

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "EXACT-PROVIDER-RELEASE-01"
FIXTURE = PREVIOUS / "run.py"
BASE = "c92e9e3c"


def load():
    spec = importlib.util.spec_from_file_location("native_exact_release", FIXTURE)
    fixture = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fixture
    spec.loader.exec_module(fixture)
    return fixture


native = load()
cache = native.cache


class AtSelection:
    """Pause after exact evidence and parent checks, just before selection."""

    def __init__(self, db, control, late_lock):
        self.db = db
        self.control = control
        self.late_lock = late_lock

    def execute(self, sql, args=()):
        if self.late_lock and sql == "BEGIN IMMEDIATE":
            return None
        if sql.startswith("UPDATE state SET current"):
            self.control.send("before-selection")
            if not self.control.poll(15) or self.control.recv() != "apply":
                raise RuntimeError("Selection barrier expired")
            if self.late_lock:
                self.db.execute("BEGIN IMMEDIATE")
        return self.db.execute(sql, args)

    def __getattr__(self, name):
        return getattr(self.db, name)


def start_catalog(path, current):
    with sqlite3.connect(path) as db:
        db.executescript(
            "CREATE TABLE state(generation INTEGER, allowed INTEGER, current TEXT); "
            "CREATE TABLE history(parent TEXT, artifact TEXT, generation INTEGER);"
        )
        db.execute("INSERT INTO state VALUES (1, 1, ?)", (current,))
        db.execute("INSERT INTO history VALUES (NULL, ?, 1)", (current,))


def submit(db, signers, profile, parent):
    receipt = profile["evidence"]
    return native.publish(
        db, signers, profile["request"], profile["signature"],
        {receipt["artifact"]: profile["primary"]}, profile["rebuild"], receipt, receipt, parent
    )


def writer(path, control, signers, profile, parent, late_lock):
    try:
        with sqlite3.connect(path, isolation_level=None, timeout=0) as db:
            result = submit(AtSelection(db, control, late_lock), signers, profile, parent)
        control.send(result)
    finally:
        control.close()


def concurrent_operation(db, cut, signers, rival, parent):
    try:
        if cut == "revocation":
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE state SET generation = 2, allowed = 0")
            db.commit()
            return "revoked"
        return submit(db, signers, rival, parent)
    except sqlite3.OperationalError as error:
        if error.sqlite_errorcode != sqlite3.SQLITE_BUSY:
            raise
        return "SQLITE_BUSY"


def await_message(conn):
    if not conn.poll(20):
        raise RuntimeError("Timed out waiting for release writer")
    return conn.recv()


def run_cut(root, profiles, signers, cut, late_lock):
    _, new = profiles
    old_address, new_address = (item["evidence"]["artifact"] for item in profiles)
    path = root / f"{cut}-{late_lock}.sqlite"
    start_catalog(path, old_address)
    ctx = multiprocessing.get_context("fork")
    conn, child = ctx.Pipe()
    process = ctx.Process(target=writer, args=(path, child, signers, new, old_address, late_lock))
    process.start()
    child.close()
    try:
        assert await_message(conn) == "before-selection"
        with sqlite3.connect(path, isolation_level=None, timeout=0) as db:
            rival_first = concurrent_operation(db, cut, signers, new, old_address)
            generation_at_cut = db.execute("SELECT generation FROM state").fetchone()[0]
            conn.send("apply")
            assert await_message(conn) == "published"
            rival_retry = None
            if rival_first == "SQLITE_BUSY":
                rival_retry = concurrent_operation(db, cut, signers, new, old_address)
            state = db.execute("SELECT generation, allowed, current FROM state").fetchone()
            history = db.execute("SELECT * FROM history ORDER BY rowid").fetchall()
    finally:
        conn.close()
        process.join(timeout=4)
        if process.is_alive():
            process.terminate()
            process.join()
    if process.exitcode != 0:
        raise RuntimeError(f"Release writer exited with {process.exitcode}")

    assert state == ((2, 0, new_address) if cut == "revocation" else (1, 1, new_address))
    rows = [(None, old_address, 1), (old_address, new_address, 1)]
    expected_first, expected_retry = "SQLITE_BUSY", "revoked" if cut == "revocation" else "parent-refused"
    if late_lock:
        expected_first, expected_retry = ("revoked" if cut == "revocation" else "published"), None
        if cut == "competing_parent":
            # Two publications use the same spent parent token for the same exact target.
            rows.append((old_address, new_address, 1))
    assert (rival_first, rival_retry, history) == (expected_first, expected_retry, rows)
    assert generation_at_cut == (2 if cut == "revocation" and late_lock else 1)
    return {"rival_at_cut": rival_first, "rival_after_selection": rival_retry,
            "generation_at_writer_resumption": generation_at_cut, "writer_verdict": "published",
            "history": history, "final_generation": state[0]}


def audit(work, rustc):
    previous = json.loads((PREVIOUS / "evidence.json").read_text())
    tools = {}
    for name, details in previous["tools"].items():
        binary = rustc if name == "rustc" else Path(shutil.which(name, path=cache.ENV["PATH"]))
        current = {"sha256": sha256(binary.read_bytes()).hexdigest(),
                   "version": native.output([str(binary), "--version"]).splitlines()[0]}
        assert current == details
        tools[name] = current
    abi = native.provider.abi
    roles = (*product("abc", repeat=4), ("a", "b", "c", "d"))
    dispositions = get_args(abi.Disposition)
    cases = [(abi.Inputs(ids, wants, local, handle), close)
             for ids, wants, local, handle, close in product(
                 roles, (False, True), dispositions, dispositions, dispositions)]
    inputs = "".join(abi.encode_input(*case, physical)
                     for case in cases for physical in (False, True)).encode()
    timing = "before_cleanup"
    caller = abi.compile_caller(native.provider.SOURCE, timing)
    roots = {name: native.configure(work / name, caller, timing) for name in ("primary", "rebuild")}
    sources = {}
    for name in ("run.py", "evidence.json"):
        path = PREVIOUS / name
        ref = str(path.relative_to(native.REPO))
        expected = native.output(["git", "-C", str(native.REPO), "rev-parse", f"{BASE}:{ref}"])
        assert expected == native.output(["git", "-C", str(native.REPO), "hash-object", ref])
        sources[ref] = expected
    sources.update(native.pin_sources())

    results = {}
    for route in native.ROUTES:
        route_root = work / route
        route_root.mkdir()
        signers = cache.Signers(route_root)
        profiles = []
        for label in native.provider.PROVIDERS:
            traces = native.provider.reference(caller, cases, label)
            expected = ("\n".join(traces) + "\n").encode()
            binaries = [native.build(work / name, label, route, artifacts, inputs, expected, rustc)[0]
                        for name, artifacts in roots.items()]
            evidence = previous["outcomes"][route]["profiles"][label]["evidence"]
            assert sha256(inputs).hexdigest() == evidence["inputs"]
            assert sha256(expected).hexdigest() == evidence["trace"]
            assert sha256(binaries[0]).hexdigest() == evidence["artifact"]
            assert binaries[0] == binaries[1]
            request = cache.Request(evidence["action"], evidence["closure"], "local-cor13-release",
                                    1, frozenset({"alice"}))
            profiles.append({"primary": binaries[0], "rebuild": binaries[1], "request": request,
                             "signature": native.statement(signers, request, binaries[0]),
                             "evidence": evidence})
        results[route] = {
            f"{cut}/{'late_lock' if late_lock else 'fenced'}":
                run_cut(route_root, profiles, signers, cut, late_lock)
            for cut, late_lock in product(("revocation", "competing_parent"), (False, True))
        }
    return {"base": native.output(["git", "-C", str(native.REPO), "rev-parse", BASE]),
            "sources": sources, "tools": tools, "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rustc = args.rustc or Path(native.output(["rustc", "--print", "sysroot"])) / "bin/rustc"
    with TemporaryDirectory(prefix="llmlang-release-race-") as directory:
        result = audit(Path(directory), rustc.resolve(strict=True))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
