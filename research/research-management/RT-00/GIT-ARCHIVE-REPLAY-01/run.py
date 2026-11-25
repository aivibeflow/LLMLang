#!/usr/bin/env python3
"""Replay Git publication and bootstrap from the exact tracked fixture bytes."""
import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


BASE = "839fe94a6a915f5045b70859e89a8f55bcb852b0"
RT19 = "research/toolchain-and-collaboration/RT-19"
RT21 = "research/toolchain-and-collaboration/RT-21"
SUITES = {
    "coherent": f"{RT19}/COHERENT-MULTIREF-01",
    "faults": f"{RT19}/GIT-REF-FAULTS-01",
    "delivery": f"{RT19}/TWO-REMOTE-PUBLICATION-01",
    "contract": f"{RT19}/PUBLICATION-CONTRACT-01",
    "bootstrap": f"{RT21}/DEPENDENCY-BOOTSTRAP-01",
}


def invoke(argv, root, env, timeout=180):
    process = subprocess.run(argv, cwd=root, env=env, capture_output=True, timeout=timeout)
    if process.returncode:
        raise RuntimeError(f"{argv}\n{process.stdout.decode(errors='replace')}\n"
                           f"{process.stderr.decode(errors='replace')}")
    return process.stdout


def hashed(content):
    return sha256(content).hexdigest()


def replay(root, fixture, flags, env):
    path = root / fixture
    generated = root / "observations.json"
    invoke([sys.executable, "-B", path / "run.py", *flags, "--out", generated], root, env)
    actual = generated.read_bytes()
    expected = (path / "observations.json").read_bytes()
    assert actual == expected, (fixture, hashed(actual), hashed(expected))
    generated.unlink()
    return json.loads(actual), {name.name: hashed(name.read_bytes()) for name in sorted(path.iterdir())
                                if name.is_file()}


def compare(data):
    schedules = data["coherent"]["profiles"]
    rows = [row for profile in schedules for row in profile["summary"].values()]
    pinned = [row for profile in schedules for name, row in profile["summary"].items() if name.endswith("/pinned")]
    total, reads, superseded = (sum(row["runs"] for row in rows), sum(row["runs"] for row in pinned),
                               sum(row["pinned_stale_at_recheck"] for row in pinned))
    assert (len(schedules), total, reads, superseded) == (4, 308, 96, 44)
    assert data["coherent"]["profile_summaries_match"] and all(row["mixed"] == 0 for row in pinned)
    faults = Counter(tuple(row["visible_after_exit"]) for rows in data["faults"]["profiles"].values()
                     for row in rows if row["exit"] == 128)
    assert faults == {("old", "old"): 9, ("new", "old"): 1, ("new", "new"): 3}
    delivery = data["delivery"]["ref_storage_outcomes"]
    pairs = [result for profile in delivery.values() for result in profile.values()]
    exits = sum("after_process_exit" in result for result in pairs)
    assert len(pairs) == 24 and exits == 8
    model = data["contract"]["outcomes"]
    assert (model["candidate"]["distinct_states"], model["candidate"]["generated_states"],
            model["candidate"]["search_depth"], len(model) - 1) == (4032, 77401, 13, 7)
    assert all(len(result["validated_steps"]) == result["violation_depth"]
               for name, result in model.items() if name != "candidate")
    bootstrap = data["bootstrap"]
    assert (bootstrap["case_count"], bootstrap["register_cases"], len(bootstrap["refused_controls"])) == (16468, 12, 8)
    assert all(route["matched"] == bootstrap["case_count"] for route in bootstrap["native_routes"].values())
    return {"schedules": total, "exact_pinned_reads": reads, "superseded_pinned_reads": superseded,
            "faults_by_visible_vector": {"/".join(pair): count for pair, count in sorted(faults.items())},
            "two_repository_schedules": len(pairs), "delivery_process_exits": exits,
            "candidate_states": model["candidate"]["distinct_states"], "independently_checked_traces": 7,
            "bootstrap_cases_per_route": bootstrap["case_count"], "bootstrap_register_cases": bootstrap["register_cases"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tlc", required=True, type=lambda value: Path(value).resolve())
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "LD_"))}
    env.update({"LC_ALL": "C", "TZ": "UTC"})
    repo = Path.cwd()
    git_dir = invoke(["git", "rev-parse", "--absolute-git-dir"], repo, env).decode().strip()
    archive = invoke(["git", "archive", BASE, *SUITES.values()], repo, env)
    data, hashes = {}, {}
    with tempfile.TemporaryDirectory(prefix="rt00-git-archive-") as scratch:
        root = Path(scratch)
        with tarfile.open(fileobj=BytesIO(archive), mode="r:") as stream:
            stream.extractall(root, filter="data")
        for name, fixture in SUITES.items():
            flags = ["--tlc", args.tlc] if name == "contract" else []
            # The bootstrap reads one explicitly pinned register from history.
            # Its fixture inputs and generated builds stay inside the archive.
            fixture_env = {**env, "GIT_DIR": git_dir} if name == "bootstrap" else env
            data[name], hashes[name] = replay(root, fixture, flags, fixture_env)
    report = {"baseline": BASE, "matched_fixture_sha256": hashes, "claims": compare(data)}
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
