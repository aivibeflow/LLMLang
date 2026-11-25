"""Reproduce an exact archive of proof and matching source observations."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest
import json
from math import factorial
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

REVISION = "55d54059aa8ba1c18e047f491843e1e7d278d25d"
PROOFS = "research/formal-verification/RT-32"
PINNED = {
    "SOURCE-CLEANUP-KERNEL-01": ("language-design/RT-03/SOURCE-CLEANUP-CFG-01", "native_evidence_sha256"),
    "WORKER-CANCEL-01": ("language-design/RT-01/RESOURCE-WORKER-01", "native_archive_sha256"),
    "RECORD-OWNERSHIP-01": ("semantic-representation/RT-05/PARTIAL-RECORD-01", "native_ledger_sha256"),
    "BOUND-METHOD-OBSERVATIONS-01": ("semantic-representation/RT-05/STATEFUL-BOUND-METHOD-01",
                                    "native_archive_sha256"),
    "MUTABLE-RENAMING-01": ("semantic-representation/RT-05/MUTABLE-REFERENCE-TOPOLOGY-01",
                            "native_archive_sha256"),
}
LIFECYCLE = ("PROOF-CACHE-STORE-01", "LEAN-ARTIFACT-REPLAY-01", "CALLER-EVIDENCE-STATES-01")


def sha(path):
    with path.open("rb") as file:
        return file_digest(file, "sha256").hexdigest()


def structural_checks(ledgers):
    cleanup = ledgers["SOURCE-CLEANUP-KERNEL-01"]
    assert cleanup["source_agreement"] + cleanup["resource_completion"] + cleanup["mutation_inequalities"] == len(
        cleanup["theorems"]
    )
    worker = ledgers["WORKER-CANCEL-01"]
    assert worker["guarded_schedules"] == len(worker["archive_equalities"])
    assert worker["guarded_terminal_outcomes"] == 2 * worker["guarded_schedules"]
    assert worker["incorrect_late_cancellation_proof"] == "rejected"
    record = ledgers["RECORD-OWNERSHIP-01"]
    assert record["source_cases"] == record["archive_equalities"]
    assert record["native_measurements_represented"] == 2 * record["oracle_vectors"]
    method = ledgers["BOUND-METHOD-OBSERVATIONS-01"]
    assert method["native_distinct_full_probe_signatures"] - method["native_distinct_short_probe_signatures"] == 9
    assert len(method["archive_equalities"]) == len(method["native_probe_equalities"])
    assert ledgers["MUTABLE-RENAMING-01"]["incorrect_split_preservation_proof"] == "rejected"

    artifact = ledgers["LEAN-ARTIFACT-REPLAY-01"]["experiment"]["cases"]
    assert artifact["comment"]["dependency_module"] == artifact["base"]["dependency_module"]
    assert artifact["comment"]["dependency_source"] != artifact["base"]["dependency_source"]
    assert artifact["comment"]["exact_artifact_reuse"] == "refused-before-import"
    assert artifact["changed-meaning"]["import_with_t0"] == "checked"
    assert artifact["changed-meaning"]["stored_term"] == "refused"
    cache = ledgers["PROOF-CACHE-STORE-01"]["results"]
    assert len({cache["old_closed"], cache["rebound_closed"], cache["changed_artifact_closed"],
                cache["changed_trust_closed"]}) == 4
    assert cache["interrupted_publish_recovered"] and cache["interrupted_publish_same_request_retried"]
    caller = ledgers["CALLER-EVIDENCE-STATES-01"]
    schedules = caller["schedule_counts"]
    assert schedules["schedules"] == factorial(7)
    assert schedules["prefixes"] == 7 * schedules["schedules"]
    assert all(caller["trust_controls"][name] == "conditional" for name in (
        "subject", "version", "contract", "theorem", "imports", "toolchain", "unapproved_provenance"
    ))
    return {"cleanup_theorems": len(cleanup["theorems"]), "worker_archive_steps": worker["guarded_steps"],
            "record_archive_vectors": record["oracle_vectors"], "bound_method_probe_vectors": method["native_probe_vectors"],
            "exact_closed_proof_keys_after_edits": 4,
            "caller_evidence_schedule_prefixes": schedules["prefixes"],
            "wrong_scope_planning_false_closures": schedules["scope_free_false_closures"]}


def audit(lean, work):
    root = work / "tree"
    root.mkdir()
    archive = work / "source.tar"
    with archive.open("wb") as stream:
        subprocess.run(["git", "archive", REVISION, "research"], stdout=stream, check=True, timeout=45)
    with tarfile.open(archive) as stream:
        stream.extractall(root, filter="data")
    env = dict(os.environ, LC_ALL="C", PYTHONHASHSEED="3", PYTHONDONTWRITEBYTECODE="1")

    def replay(relative, *, args=(), output=False):
        directory = root / relative
        runner = directory / "run.py"
        command = [sys.executable, str(runner), *args]
        out = work / f"{directory.name}.json"
        if output:
            command += ["--output", str(out)]
        execution = subprocess.run(command, env=env, capture_output=True, check=True, timeout=180)
        actual = out.read_bytes() if output else execution.stdout
        ledger = directory / "evidence.json"
        if ledger.read_bytes() != actual:
            raise ValueError(f"Replay mismatch: {relative}")
        local_files = {path.name: sha(path) for path in sorted(directory.iterdir())
                       if path.is_file() and path != ledger}
        return json.loads(actual), {"path": str(ledger.relative_to(root)), "sha256": sha(ledger),
                                    "local_files_sha256": local_files}

    def proof(name):
        arguments = ["--lean", str(lean)] if name in (*PINNED, "LEAN-ARTIFACT-REPLAY-01") else []
        return name, replay(f"{PROOFS}/{name}", args=arguments, output=name == "LEAN-ARTIFACT-REPLAY-01")

    def source(name):
        relative, _ = PINNED[name]
        return name, replay(f"research/{relative}")[1]

    with ThreadPoolExecutor(max_workers=3) as pool:
        executions = dict(pool.map(proof, (*PINNED, *LIFECYCLE)))
        sources = dict(pool.map(source, PINNED))
    ledgers = {name: result[0] for name, result in executions.items()}
    for name, record in sources.items():
        _, expected = PINNED[name]
        assert record["sha256"] == ledgers[name][expected]

    tools = {"lean": lean}
    for name in ("gcc", "git", "node", "rustc"):
        found = shutil.which(name)
        if found is None:
            raise ValueError(f"Missing executable: {name}")
        tools[name] = Path(found)
    recorded_tools = {}
    for name, binary in tools.items():
        banner = subprocess.check_output([binary, "--version"], env=env, text=True, timeout=20).splitlines()[0]
        if name == "rustc":
            sysroot = subprocess.check_output([binary, "--print", "sysroot"], text=True).strip()
            binary = Path(sysroot) / "bin/rustc"
        recorded_tools[name] = {"banner": banner, "sha256": sha(binary)}
    return {"commit": REVISION, "python": sys.version.split()[0], "python_sha256": sha(Path(sys.executable)),
            "host": {"machine": platform.machine(), "kernel": platform.release()}, "sqlite": sqlite3.sqlite_version,
            "tools": recorded_tools, "proof_replays": {name: parts[1] for name, parts in executions.items()},
            "source_replays": sources, "checks": structural_checks(ledgers)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-rt32-cohort-") as directory:
        evidence = audit(args.lean.resolve(strict=True), Path(directory))
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
