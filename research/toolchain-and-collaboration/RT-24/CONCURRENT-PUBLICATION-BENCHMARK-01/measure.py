"""Measure optimistic graph publication with live SQLite writer contention."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
import os
from pathlib import Path
import platform
from random import Random
import sqlite3
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
from time import perf_counter_ns


HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE.parent / "CONCURRENT-GRAPH-01" / "run.py"
SPEC = spec_from_file_location("graph_edit_fixture", MODEL_PATH)
model = module_from_spec(SPEC)
sys.modules[SPEC.name] = model
SPEC.loader.exec_module(model)

WRITERS = (2, 4, 8)
POLICIES = ("whole-head", "exact-projection")
SHAPES = ("independent", "duplicate")
BACKBONE = 192


def snapshot(db, proposal):
    db.execute("BEGIN")
    head = db.execute("SELECT version FROM head").fetchone()[0]
    observed = model.project(db, proposal)
    db.execute("COMMIT")
    return head, observed


def worker(path, proposal, policy, launch, writers):
    db = sqlite3.connect(path, isolation_level=None, timeout=8)
    try:
        db.execute("PRAGMA synchronous=FULL")
        base, initial = snapshot(db, proposal)
        if base != 0 or not model.valid_projection(proposal, initial):
            raise ValueError("initial writer view changed")
        launch.wait(timeout=15)
        waits = []
        holds = []
        retries = 0
        for _ in range(writers):
            before = perf_counter_ns()
            db.execute("BEGIN IMMEDIATE")
            locked = perf_counter_ns()
            waits.append(locked - before)
            head = db.execute("SELECT version FROM head").fetchone()[0]
            matches = head == base if policy == "whole-head" else model.project(db, proposal) == initial
            if matches:
                db.execute("INSERT INTO edge VALUES (?, ?)", (proposal.source, proposal.target))
                db.execute("UPDATE head SET version = version + 1")
                db.execute("COMMIT")
                holds.append(perf_counter_ns() - locked)
                return True, retries, waits, holds
            db.execute("ROLLBACK")
            holds.append(perf_counter_ns() - locked)
            if policy == "exact-projection":
                return False, retries, waits, holds
            retries += 1
            base, initial = snapshot(db, proposal)
            if not model.valid_projection(proposal, initial):
                return False, retries, waits, holds
        raise ValueError("writer exceeded the bounded retry budget")
    finally:
        db.close()


def probe(path, writers, shape, policy):
    initial = {(i, i + 1) for i in range(BACKBONE)}
    active = set(range(BACKBONE + writers + 1))
    proposals = [model.Edit("add", BACKBONE + (i + 1 if shape == "independent" else 1), 0)
                 for i in range(writers)]
    added = {(proposal.source, proposal.target) for proposal in proposals}
    db = sqlite3.connect(path)
    try:
        if db.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
            raise ValueError("expected WAL")
        db.executescript("""
        CREATE TABLE head (version INTEGER NOT NULL);
        INSERT INTO head VALUES (0);
        CREATE TABLE node (id INTEGER PRIMARY KEY, active INTEGER NOT NULL);
        CREATE TABLE edge (src INTEGER, dst INTEGER, PRIMARY KEY (src, dst));
        """)
        with db:
            db.executemany("INSERT INTO node VALUES (?, 1)", ((node,) for node in sorted(active)))
            db.executemany("INSERT INTO edge VALUES (?, ?)", sorted(initial))
        start = []
        start_barrier = Barrier(writers + 1, action=lambda: start.append(perf_counter_ns()))
        with ThreadPoolExecutor(max_workers=writers) as pool:
            futures = [pool.submit(worker, path, proposal, policy, start_barrier, writers)
                       for proposal in proposals]
            start_barrier.wait(timeout=15)
            results = [future.result(timeout=20) for future in futures]
            elapsed = perf_counter_ns() - start[0]
        commits = sum(committed for committed, _, _, _ in results)
        observed = set(db.execute("SELECT src, dst FROM edge"))
        if (commits != len(added) or observed != initial | added or not model.check_graph(active, observed)
                or db.execute("SELECT version FROM head").fetchone() != (commits,)):
            raise ValueError((shape, policy, commits, added))
        waits = [duration for _, _, wait, _ in results for duration in wait]
        holds = [duration for _, _, _, hold in results for duration in hold]
        retries = sum(retry for _, retry, _, _ in results)
        if policy == "exact-projection" and (retries != 0 or len(waits) != writers):
            raise ValueError("exact validation did not finish in one write attempt per worker")
        if policy == "whole-head" and retries < writers - 1:
            raise ValueError("initial simultaneous snapshots failed to generate stale-head retries")
        return {
            "writers": writers, "shape": shape, "policy": policy, "commits": commits,
            "refusals": writers - commits, "write_attempts": len(waits), "retries": retries,
            "batch_ns": elapsed, "total_wait_ns": sum(waits), "max_wait_ns": max(waits),
            "total_hold_ns": sum(holds),
            "final_edges_sha256": sha256(json.dumps(sorted(observed)).encode()).hexdigest(),
        }
    finally:
        db.close()


def counters():
    return {key: int(value) for key, value in
            map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())}


def collect(args):
    if args.trials < 2 or args.cpu not in os.sched_getaffinity(0):
        raise ValueError("invalid CPU or trials")
    os.sched_setaffinity(0, {args.cpu})
    before = counters()
    random = Random(args.seed)
    rows = []
    with TemporaryDirectory(prefix="rt24-concurrent-publication-") as temp:
        root = Path(temp)
        for block in range(args.trials):
            profiles = list(product(WRITERS, SHAPES, POLICIES))
            random.shuffle(profiles)
            for position, (workers, shape, policy) in enumerate(profiles):
                database = root / f"trial-{block}-{position}.db"
                rows.append({"block": block, "position": position, **probe(database, workers, shape, policy)})
    after = counters()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    config = {
        "cpu": args.cpu, "trials": args.trials, "seed": args.seed, "kernel": platform.release(),
        "backbone_edges": BACKBONE, "cpu_model": next(line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "counter_delta": {key: after[key] - before[key] for key in before},
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "model_sha256": sha256(MODEL_PATH.read_bytes()).hexdigest(),
    }
    (args.output / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("cpu", "seed", "trials"):
        parser.add_argument(f"--{field}", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    collect(parser.parse_args())
