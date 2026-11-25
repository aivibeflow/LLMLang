"""Measure checked theorem launches and separate finite-oracle runs."""

import argparse
import csv
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import platform
from random import Random
import resource
import subprocess
import sys
from time import perf_counter_ns


HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
PROFILES = {
    "discovery": ("compiler-and-translation/RT-13/DISCOVERY-BINDING-01",
                  "lean_check", "matrix", ("comparisons", "examples"), "comparisons"),
    "multiversion": ("compiler-and-translation/RT-13/MULTIVERSION-GUARDS-01",
                     "lean_check", "matrix", ("counts", "controls"), "decisions"),
    "mapping-ipc": ("runtime-and-systems/RT-38/COMPOSED-MAPPING-IPC-01",
                    "check_proof", "check_states", ("counts", "witnesses"), "transitions"),
}


def load(path):
    specification = spec_from_file_location("timed_fixture", path)
    module = module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def child(profile, mode, lean):
    directory, proof_entry, test_entry, keys, count_key = PROFILES[profile]
    root = RESEARCH / directory
    pinned_path = root / "evidence.json"
    archived = json.loads(pinned_path.read_text())
    module = load(root / "run.py")
    if mode == "proof":
        execute = lambda: getattr(module, proof_entry)(lean)
        expected = archived["lean"]
        rss_target = resource.RUSAGE_CHILDREN
        work = len(expected["axioms"])
    elif mode == "test":
        execute = lambda: getattr(module, test_entry)()
        expected = [archived[key] for key in keys]
        rss_target = resource.RUSAGE_SELF
        work = expected[0][count_key]
    else:
        raise ValueError(mode)

    started = perf_counter_ns()
    observed = execute()
    elapsed = perf_counter_ns() - started
    peak = resource.getrusage(rss_target).ru_maxrss
    observed_json = json.dumps(observed, sort_keys=True)
    if json.loads(observed_json) != expected:
        raise ValueError(f"{profile}: evidence deviated from its exact archived receipt")
    return {"inner_ns": elapsed, "peak_kib": peak, "work": work,
            "receipt_sha256": sha256(observed_json.encode()).hexdigest(),
            "archive_sha256": sha256(pinned_path.read_bytes()).hexdigest(),
            "harness_sha256": sha256((root / "run.py").read_bytes()).hexdigest()}


def counters():
    return {line.split()[0]: int(line.split()[1]) for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines()}


def collect(args):
    if args.trials < 2 or args.cpu not in os.sched_getaffinity(0):
        raise ValueError("invalid trial count or CPU")
    os.sched_setaffinity(0, {args.cpu})
    random = Random(args.seed)
    rows = []
    baseline = counters()
    for batch in range(args.trials):
        combinations = [(profile, mode) for profile in PROFILES for mode in ("proof", "test")]
        random.shuffle(combinations)
        for position, (profile, mode) in enumerate(combinations):
            start = perf_counter_ns()
            proc = subprocess.run([sys.executable, __file__, "--child", profile, mode, args.lean],
                                  check=True, text=True, capture_output=True, timeout=40)
            elapsed = perf_counter_ns() - start
            if proc.stderr:
                raise ValueError(proc.stderr)
            rows.append({"batch": batch, "position": position, "profile": profile, "mode": mode,
                         "process_ns": elapsed, **json.loads(proc.stdout)})
    after = counters()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    config = {
        "cpu": args.cpu, "trials": args.trials, "seed": args.seed, "kernel": platform.release(),
        "python": platform.python_version(), "cpu_model": next(
            line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")),
        "lean": subprocess.check_output([args.lean, "--version"], text=True, timeout=30).strip(),
        "counter_delta": {key: after[key] - baseline[key] for key in baseline},
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (args.output / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--child":
        print(json.dumps(child(sys.argv[2], sys.argv[3], sys.argv[4])))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        for field in ("cpu", "trials", "seed"):
            parser.add_argument(f"--{field}", required=True, type=int)
        parser.add_argument("--lean", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)
        collect(parser.parse_args())
