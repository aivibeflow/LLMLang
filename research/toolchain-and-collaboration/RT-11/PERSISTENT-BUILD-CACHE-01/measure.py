"""Measure fresh processes consuming a verified persistent action cache."""

import argparse
import csv
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import platform
from random import Random
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns


HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "MULTI-ACTION-HITS-01" / "run.py"
SPEC = spec_from_file_location("native_build_fixture", FIXTURE)
fixture = module_from_spec(SPEC)
sys.modules[SPEC.name] = fixture
SPEC.loader.exec_module(fixture)


class SQLiteCache:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS action_cache ("
                        "action TEXT PRIMARY KEY, digest TEXT NOT NULL, value BLOB NOT NULL)")

    def __contains__(self, key):
        return self.db.execute("SELECT 1 FROM action_cache WHERE action = ?", (key,)).fetchone() is not None

    def __getitem__(self, key):
        return self.db.execute("SELECT digest, value FROM action_cache WHERE action = ?", (key,)).fetchone()

    def __setitem__(self, key, value):
        digest, data = value
        self.db.execute("INSERT INTO action_cache VALUES (?, ?, ?)", (key, digest, data))


def child(mode, directory, database, revision, tool_context):
    start = perf_counter_ns()
    sqlite_cache = SQLiteCache(database) if mode == "persistent" else None
    runner = fixture.Runner(directory, "exact_payload" if sqlite_cache else "forced", tool_context)
    if sqlite_cache:
        runner.cache = sqlite_cache
    try:
        report = runner.build(revision)
        if sqlite_cache:
            sqlite_cache.db.commit()
        status = "complete"
    except AssertionError as error:
        if str(error) != "Cache payload failed verification":
            raise
        report, status = None, "refused-corruption"
        if any((directory / "out").iterdir()):
            raise ValueError("corrupt first action was materialized")
    finally:
        if sqlite_cache:
            sqlite_cache.db.close()
    return {"status": status, "build_ns": perf_counter_ns() - start, "native": report}


def group_counters():
    return {key: int(value) for key, value in
            map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())}


def invoke(mode, trial, phase, database, revision, tool_context):
    target = trial / phase
    start = perf_counter_ns()
    done = subprocess.run([sys.executable, __file__, "--child", mode, target, database,
                           str(revision), tool_context], check=True, text=True, capture_output=True, timeout=45)
    elapsed = perf_counter_ns() - start
    if done.stderr:
        raise ValueError(done.stderr)
    return {**json.loads(done.stdout), "process_ns": elapsed}


def verify_output(report, expected_a, expected_b, satisfied_a):
    if report["status"] != "complete":
        raise ValueError(report)
    observations = report["native"]["observations"]
    expected = {
        "a": {"observed": expected_a, "minimum": 0 if satisfied_a else 1000, "satisfied": satisfied_a},
        "b": {"observed": expected_b, "minimum": 0, "satisfied": True},
    }
    if observations != expected:
        raise ValueError((observations, expected))


def measure_trial(stage, tool_key, force_first):
    database = stage / "cache.db"
    if force_first:
        forced = invoke("forced", stage, "forced", database, 3, tool_key)
    cold = invoke("persistent", stage, "cold", database, 3, tool_key)
    warm = invoke("persistent", stage, "warm", database, 3, tool_key)
    policy = invoke("persistent", stage, "policy", database, 4, tool_key)
    if not force_first:
        forced = invoke("forced", stage, "forced", database, 3, tool_key)
    forced_policy = invoke("forced", stage, "forced-policy", database, 4, tool_key)
    profiles = {"cold": (cold, 0, 0, forced), "restored": (warm, 10, 10, forced),
                "policy-changed": (policy, 9, 9, forced_policy), "forced": (forced, 0, 0, cold)}
    rows = {}
    for phase, (report, hits, restored, comparison) in profiles.items():
        verify_output(report, 9, 12, phase != "policy-changed")
        expected = comparison["native"]["artifacts"]
        measured = report["native"]
        if (measured["artifacts"] != expected or sum(measured["hits"].values()) != hits
                or measured["restored"] != restored):
            raise ValueError((phase, measured, expected))
        if phase == "policy-changed" and measured["hits"] != {"compile": 4, "archive": 2, "link": 2, "verify": 1}:
            raise ValueError("policy change affected an unrelated action")
        rows[phase] = {
            "build_ns": report["build_ns"], "process_ns": report["process_ns"], "hits": hits,
            "restored": restored, "artifacts_sha256": fixture.digest(fixture.encode(expected)),
        }

    corrupt = stage / "corrupt.db"
    shutil.copyfile(database, corrupt)
    action = cold["native"]["rows"][0]["key"]
    with sqlite3.connect(corrupt) as connection:
        changed = connection.execute("UPDATE action_cache SET value = ? WHERE action = ?",
                                     (b"intentionally corrupt fixture artifact", action))
        if changed.rowcount != 1:
            raise ValueError("corruption control missed its exact action")
    blocked = invoke("persistent", stage, "corrupt-replay", corrupt, 3, tool_key)
    if blocked["status"] != "refused-corruption":
        raise ValueError("the restored cache did not refuse corrupt bits")
    return rows, database.stat().st_size


def collect(args):
    if args.trials < 2 or args.cpu not in os.sched_getaffinity(0):
        raise ValueError("invalid trial count or CPU")
    os.sched_setaffinity(0, {args.cpu})
    random = Random(args.seed)
    records = []
    before = group_counters()
    with TemporaryDirectory(prefix="rt11-durable-compilation-") as temporary:
        root = Path(temporary)
        tools = fixture.tools(root)
        tool_key = fixture.digest(fixture.encode(tools))
        for trial in range(args.trials):
            stage = root / f"trial-{trial}"
            stage.mkdir()
            force_first = bool(random.getrandbits(1))
            rows, cache_bytes = measure_trial(stage, tool_key, force_first)
            records.extend({"trial": trial, "phase": phase, "force_first": force_first, "cache_bytes": cache_bytes,
                            **row} for phase, row in rows.items())
    after = group_counters()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    metadata = {
        "trials": args.trials, "seed": args.seed, "cpu": args.cpu, "kernel": platform.release(),
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "tools": tools,
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "corruption_controls": args.trials, "counter_delta": {key: after[key] - before[key] for key in before},
        "source_sha256": {"measure.py": sha256(Path(__file__).read_bytes()).hexdigest(),
                          "native_build_fixture": sha256(FIXTURE.read_bytes()).hexdigest()},
    }
    (args.output / "config.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 7 and sys.argv[1] == "--child":
        _, _, mode, directory, database, revision, context = sys.argv
        print(json.dumps(child(mode, Path(directory), Path(database), int(revision), context)))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        for field in ("cpu", "trials", "seed"):
            parser.add_argument(f"--{field}", required=True, type=int)
        parser.add_argument("--output", required=True, type=Path)
        collect(parser.parse_args())
