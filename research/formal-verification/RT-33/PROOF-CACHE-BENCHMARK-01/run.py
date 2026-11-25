"""Measure paired cold/warm proof caching with pinned cvc5 and Carcara."""
import argparse
from contextlib import closing
import csv
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import random
import select
import signal
import sqlite3
from subprocess import Popen, check_output
from tempfile import TemporaryDirectory, TemporaryFile
from time import perf_counter_ns

BLOCKS = 11
ROSTER = tuple(f"unit-{index:02}" for index in range(12))
EDITED = frozenset(ROSTER[:3])
SEED = 1731
SCHEMA = """
CREATE TABLE cas (hash TEXT PRIMARY KEY, data BLOB NOT NULL);
CREATE TABLE receipt (key TEXT PRIMARY KEY, query TEXT NOT NULL, scope TEXT NOT NULL,
                      artifact TEXT NOT NULL REFERENCES cas, checked INTEGER NOT NULL CHECK (checked=1));
"""


class Refused(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    name: str
    value: int
    memo: str = "original"


def sha(data):
    return sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def query(task):
    return (f"(set-logic QF_LIA)\n(declare-const x Int)\n(assert (= x {task.value}))\n"
            f"(assert (not (= x {task.value})))\n(check-sat)\n(exit)\n").encode()


def scope(task, tools, policy):
    return {"subject": task.name, "profile": "int-equality-and-negation/v1",
            "producer": tools["cvc5"]["sha256"], "checker": tools["carcara"]["sha256"],
            "environment": "c-locale-single-cpu-corpus/v1", "policy": policy}


def key(task, tools, policy):
    wire = query(task)
    domain = sha(encode(scope(task, tools, policy)))
    return sha(encode(["proof-execution/1", sha(wire), domain])), wire, domain


def child(helper, argv, directory):
    """Measure the selected child, independently of previous child RSS peaks."""
    with TemporaryFile() as output, TemporaryFile() as errors:
        metric = directory / "child.measured"
        metric.unlink(missing_ok=True)
        proc = Popen([helper, metric, *argv], cwd=directory, stdout=output, stderr=errors,
                     env={**os.environ, "LC_ALL": "C"}, start_new_session=True)
        descriptor = os.pidfd_open(proc.pid)
        try:
            if not select.select([descriptor], [], [], 10)[0]:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                raise TimeoutError(argv[0])
        finally:
            os.close(descriptor)
        status = proc.wait()
        elapsed, peak = map(int, metric.read_text().split())
        output.seek(0)
        errors.seek(0)
        return status, output.read(), errors.read(), elapsed, peak


def solve(tools, directory, wire):
    problem = directory / "query.smt2"
    problem.write_bytes(wire)
    status, stdout, stderr, ns, rss = child(tools["measure"]["path"],
        [tools["cvc5"]["path"], "--produce-proofs", "--proof-format-mode=alethe",
         "--proof-alethe-res-pivots", "--dump-proofs", problem], directory)
    assert status == 0 and not stderr
    lines = stdout.splitlines()
    assert lines[:2] == [b"unsat", b"("] and lines[-1] == b")", stdout
    return b"\n".join(lines[2:-1]) + b"\n", ns, rss


def verify(tools, directory, wire, payload):
    problem, proof = directory / "query.smt2", directory / "check.alethe"
    problem.write_bytes(wire)
    proof.write_bytes(payload)
    status, output, _, ns, rss = child(tools["measure"]["path"],
                                      [tools["carcara"]["path"], "check", proof, problem], directory)
    return status == 0 and output.strip() == b"valid", ns, rss, output.strip().decode()


def lookup(db, identity, wire, domain):
    row = db.execute("""SELECT query, scope, artifact, data FROM receipt
                        LEFT JOIN cas ON receipt.artifact = cas.hash WHERE key = ?""", (identity,)).fetchone()
    if row is None:
        return None
    request, bound, artifact, data = row
    if (request, bound) != (sha(wire), domain):
        raise Refused("wrong-scope")
    if data is None or sha(data) != artifact:
        raise Refused("damaged-cache")
    return data


def publish(db, identity, wire, domain, payload):
    address = sha(payload)
    with db:
        db.execute("INSERT OR IGNORE INTO cas VALUES (?, ?)", (address, payload))
        db.execute("INSERT INTO receipt VALUES (?, ?, ?, ?, 1)", (identity, sha(wire), domain, address))


def measure(task, tools, case, trial, db, database, directory):
    start = perf_counter_ns()
    identity, wire, domain = key(task, tools, 1)
    projected = perf_counter_ns()
    data = None if case == "oracle" else lookup(db, identity, wire, domain)
    searched = perf_counter_ns()
    solve_ns = check_ns = publish_ns = solve_rss = check_rss = 0
    hit = data is not None
    if not hit:
        data, solve_ns, solve_rss = solve(tools, directory, wire)
        valid, check_ns, check_rss, outcome = verify(tools, directory, wire, data)
        assert valid and outcome == "valid"
        if case != "oracle":
            first = perf_counter_ns()
            publish(db, identity, wire, domain, data)
            publish_ns = perf_counter_ns() - first
    end = perf_counter_ns()
    return {
        "block": trial, "mode": case, "subject": task.name, "value": task.value,
        "hit": int(hit), "query_sha256": sha(wire), "proof_sha256": sha(data),
        "project_ns": projected - start, "lookup_ns": searched - projected,
        "solve_ns": solve_ns, "check_ns": check_ns, "publish_ns": publish_ns,
        "total_ns": end - start, "cvc5_peak_rss_kib": solve_rss, "carcara_peak_rss_kib": check_rss,
        "artifact_bytes": len(data), "sqlite_file_bytes": database.stat().st_size,
        "llm_requests": 0, "llm_tokens": 0,
    }


def error(callback, expected):
    try:
        callback()
    except Refused as failure:
        assert str(failure) == expected
        return
    raise AssertionError(expected)


def negative(tools, directory):
    base, drift = Task("base", 3), Task("base", 4)
    old_key, original, domain = key(base, tools, 1)
    current_key, new, current = key(drift, tools, 1)
    payload, _, _ = solve(tools, directory, original)
    assert verify(tools, directory, original, payload)[0]
    with closing(sqlite3.connect(":memory:")) as db:
        db.executescript(SCHEMA)
        publish(db, old_key, original, domain, payload)
        assert lookup(db, current_key, new, current) is None
        new_policy = key(base, tools, 2)
        assert lookup(db, *new_policy) is None
        noop_edit = key(replace(base, memo="presentation-only"), tools, 1)
        assert lookup(db, *noop_edit) == payload
        with db:
            db.execute("INSERT INTO receipt SELECT ?, query, scope, artifact, checked FROM receipt WHERE key = ?",
                       (current_key, old_key))
        error(lambda: lookup(db, current_key, new, current), "wrong-scope")
        with db:
            db.execute("UPDATE cas SET data = ? WHERE hash = ?", (b"corrupt", sha(payload)))
        error(lambda: lookup(db, old_key, original, domain), "damaged-cache")
    incomplete = payload.replace(b":rule resolution :premises (a0 a1) :args (@p_1 true)", b":rule hole")
    assert incomplete != payload
    passed, _, _, verdict = verify(tools, directory, original, incomplete)
    assert not passed and verdict == "holey"
    return {
        "changed-query": "miss", "changed-policy": "miss", "metadata-only": "exact-hit",
        "copied-stale-receipt": "refused", "corrupt-payload": "refused", "unsupported-proof-hole": "refused",
    }


def experiment(tools, directory):
    rows = []
    baseline = tuple(Task(name, index + 3) for index, name in enumerate(ROSTER))
    changed = tuple(replace(item, value=item.value + 100, memo="amended") if item.name in EDITED
                    else replace(item, memo="presentation") for item in baseline)
    rng = random.Random(SEED)

    def mode(_db, storage, case, block, subjects):
        order = list(subjects)
        rng.shuffle(order)
        return [measure(task, tools, case, block, _db, storage, directory) for task in order]

    for block in range(BLOCKS):
        database = directory / f"block-{block}.sqlite"
        with closing(sqlite3.connect(database)) as store:
            store.execute("PRAGMA foreign_keys = ON")
            store.executescript(SCHEMA)
            assert store.execute("PRAGMA synchronous").fetchone() == (2,)
            def oracle():
                # Price both original and edited subjects independently in the paired block.
                return mode(store, database, "oracle", block, (*baseline, *changed[:3]))
            if block % 2 == 0:
                rows.extend(oracle())
            rows.extend(mode(store, database, "cold", block, baseline))
            rows.extend(mode(store, database, "warm", block, baseline))
            rows.extend(mode(store, database, "edit", block, changed))
            rows.extend(mode(store, database, "revert", block, baseline))
            if block % 2:
                rows.extend(oracle())
    return rows


def summarize_exact(rows, controls):
    expected = {"cold": (BLOCKS * 12, 0), "warm": (BLOCKS * 12, BLOCKS * 12),
                "edit": (BLOCKS * 12, BLOCKS * 9), "revert": (BLOCKS * 12, BLOCKS * 12),
                "oracle": (BLOCKS * 15, 0)}
    outcomes = {}
    for mode, measure in expected.items():
        selected = [item for item in rows if item["mode"] == mode]
        assert (len(selected), sum(item["hit"] for item in selected)) == measure
        outcomes[mode] = {"executions": len(selected), "cache_hits": measure[1]}
    oracle = {(item["block"], item["subject"], item["value"]): item for item in rows if item["mode"] == "oracle"}
    assert all((item["query_sha256"], item["proof_sha256"]) == (
        oracle[(item["block"], item["subject"], item["value"])]["query_sha256"],
        oracle[(item["block"], item["subject"], item["value"])]["proof_sha256"],
    ) for item in rows)
    assert all(item["llm_requests"] == item["llm_tokens"] == 0 for item in rows)
    return {"paired_blocks": BLOCKS, "random_seed": SEED, "exact_modes": outcomes, "controls": controls,
            "queries_and_certificates_match_independent_generation": True,
            "llm_requests": 0, "llm_tokens": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("cvc5", "carcara", "csv", "protocol"):
        parser.add_argument("--" + parameter, required=True, type=Path)
    args = parser.parse_args()
    tools = {}
    for tool in ("cvc5", "carcara"):
        executable = getattr(args, tool).resolve(strict=True)
        tools[tool] = {"path": str(executable), "sha256": sha(executable.read_bytes()),
                       "version": check_output([executable, "--version"], text=True).splitlines()[0]}
    assert "1.4.2" in tools["cvc5"]["version"] and "1.1.0" in tools["carcara"]["version"]
    assert len(os.sched_getaffinity(0)) == 1
    with TemporaryDirectory() as scratch:
        directory = Path(scratch)
        source = Path(__file__).with_name("measure.c")
        helper = directory / "measure-child"
        check_output(["gcc", "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", source, "-o", helper])
        tools["measure"] = {"path": str(helper), "sha256": sha(helper.read_bytes()),
                            "source_sha256": sha(source.read_bytes()),
                            "compiler": check_output(["gcc", "--version"], text=True).splitlines()[0]}
        rows = experiment(tools, directory)
        exact = summarize_exact(rows, negative(tools, directory))
    with args.csv.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    machine = {"python": platform.python_version(), "kernel": platform.release(),
               "sqlite": sqlite3.sqlite_version, "affinity": sorted(os.sched_getaffinity(0)),
               "cpu": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name"))}
    versioned_tools = {name: {key: value for key, value in details.items() if key != "path"}
                       for name, details in tools.items()}
    args.protocol.write_text(json.dumps({"tools": versioned_tools, "host": machine, **exact},
                                        sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
