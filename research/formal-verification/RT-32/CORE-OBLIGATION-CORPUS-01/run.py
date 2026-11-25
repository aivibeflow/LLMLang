#!/usr/bin/env python3
"""Replay exact SPG-to-Lean profiles and reconcile failure categories."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
ARCHIVE = "95339a98c50b914d9ba7ce12fed37ba113d09cc9"
BASE = "research/formal-verification/RT-32"
PROFILES = {
    "CONDITIONAL-EMBEDDINGS-01": ("run.py", False, "823b76416779d8e6cef0e9e1119c693b1efc38e47a853cca1da34987b5df8c30"),
    "LOOP-OBLIGATIONS-01": ("replay.py", False, "8ec8efaf006bb4b916cfe732aef38a649489e3e8ba668ed43e1083c354088cd9"),
    "MUTUAL-TERMINATION-01": ("run.py", True, "362592bff9594767977620d8ee9ff63c0a569e8e05bb4ea3e272003e3dae9250"),
    "MUTUAL-EFFECTS-01": ("run.py", True, "d43a799446851e39d37fa24023793d4d4b2aab1534e118f2c40ea3c747d3b9da"),
    "GENERATED-CALL-01": ("run.py", True, "496fd92cdcf0260856f95284d4faff5e286ba8cb0ff8c30f84572bef5c519b7d"),
    "COMPILED-ADMISSION-01": ("run.py", True, "138db7bca6d9392b9d9ea1627771b23b022167a0afe006c7ae3f02ea493f594b"),
}


def replay(root, profile):
    script, writes_output, expected = PROFILES[profile]
    directory = root / BASE / profile
    checked = (directory / "evidence.json").read_bytes()
    if sha256(checked).hexdigest() != expected:
        raise AssertionError(f"Archived ledger mismatch for {profile}")
    arguments = [sys.executable, "-B", str(directory / script)]
    output = root / f"{profile}.json"
    if writes_output:
        arguments.extend(("--output", str(output)))
    proc = subprocess.run(arguments, capture_output=True)
    if proc.returncode:
        raise AssertionError((profile, proc.stderr.decode(), proc.stdout.decode()))
    observed = output.read_bytes() if writes_output else proc.stdout
    if observed != checked:
        # Individual properties remain visible if a later toolchain changes an artifact.
        raise AssertionError(f"Replayed result did not match the archive: {profile}")
    return json.loads(checked)


def unsupported_effect(root):
    core = root / BASE / "CONDITIONAL-EMBEDDINGS-01" / "Embedding.lean"
    directory = core.parent
    subprocess.run(["lean", "-DwarningAsError=true", "-o", "Embedding.olean", core.name],
                   cwd=directory, capture_output=True, check=True)
    source = '''import Embedding
open Lean ScopedConditional
def effectfulWire : Json :=
  .arr #[.str "foreign-effect", .str "provider", .arr #[.str "argument", .num ⟨0, 0⟩]]
example : decode 24 effectfulWire = none := by rfl
'''
    (directory / "Unsupported.lean").write_text(source)
    proc = subprocess.run(["lean", "-DwarningAsError=true", "Unsupported.lean"],
                          cwd=directory, env={**os.environ, "LEAN_PATH": str(directory)},
                          text=True, capture_output=True)
    if proc.returncode or proc.stderr:
        raise AssertionError((proc.stdout, proc.stderr))
    return {"profile": "structured call-free ordered effects", "status": "rejected-before-lowering",
            "source_sha256": sha256(source.encode()).hexdigest()}


def summarize(results, effect):
    branches = results["CONDITIONAL-EMBEDDINGS-01"]
    loop = results["LOOP-OBLIGATIONS-01"]
    termination = results["MUTUAL-TERMINATION-01"]
    recursive = results["MUTUAL-EFFECTS-01"]
    calls = results["GENERATED-CALL-01"]["cases"]
    admission = results["COMPILED-ADMISSION-01"]["cases"]
    if loop["controls"]["MissingInvariant"] != "rejected-before-generation":
        raise AssertionError("A required invariant was omitted")
    assert termination["controls"]["no_measure_decrease"]["lean_rejected"]
    assert calls["bad_rebound/late"]["expected"] == "bad_provider"
    assert calls["broader_provider/late"]["expected"] == "contract_mismatch"
    assert calls["rebound/late"]["negative_replay"] == "stale_provider_rejected"
    assert admission["old-proof-for-rebound"]["full_admission"] == "receipt-subject"

    return {
        "positives": {
            "conditional_proofs": branches["kernel"]["closed_json_decodes"],
            "conditional_ground_observations": branches["kernel"]["checked_ground_observations"],
            "loop_proofs": len(loop["programs"]),
            "recursive_termination_encodings": len(termination["variants"]),
            "recursive_effect_encodings": len(recursive["encodings"]),
            "generated_closed_caller_claims": sum("closed" in row["axioms"] for row in calls.values()),
            "compiled_receipts_admitted": sum(row["full_admission"] == "closed"
                                              for row in admission.values()),
        },
        "adversarial_evidence": {
            "wrong_implementation": {
                "provider": calls["bad_rebound/late"]["expected"],
                "recursive_base": termination["controls"]["changed_base_result"]["lean_rejected"],
            },
            "weakened_imported_contract": calls["broader_provider/late"]["expected"],
            "missing_invariant": loop["controls"]["MissingInvariant"],
            "invalid_decrease": loop["controls"]["ZeroDecrease"]["failed_obligations"],
            "mismatched_translation": branches["kernel"]["false_observations_refused"],
            "stale_callee_proof": {
                "generated": calls["rebound/late"]["negative_replay"],
                "compiled": admission["old-proof-for-rebound"]["full_admission"],
            },
            "unsupported_effect": effect,
            "compiled_admission_cases": {name: row["full_admission"] for name, row in admission.items()},
        },
    }


def main():
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        archive = subprocess.check_output([
            "git", "archive", ARCHIVE, *(f"{BASE}/{name}" for name in PROFILES),
            "research/PROTOTYPES/DEPENDENCY-GRAPH-01",
            "research/toolchain-and-collaboration/RT-24/AUDIT-AUTHORITY-01",
        ])
        with open_tar(fileobj=BytesIO(archive), mode="r:") as exact:
            exact.extractall(root, filter="data")
        with ThreadPoolExecutor(max_workers=3) as pool:
            future = {profile: pool.submit(replay, root, profile) for profile in PROFILES}
            results = {name: process.result() for name, process in future.items()}
        evidence = summarize(results, unsupported_effect(root))
    print(json.dumps({
        "schema": "llmlang-spg-core-obligation-corpus/1", "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archived_revision": ARCHIVE,
        "exact_replay_sha256": {profile: row[2] for profile, row in PROFILES.items()},
        **evidence,
    }, indent=2))


if __name__ == "__main__":
    main()
