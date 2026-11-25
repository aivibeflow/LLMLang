#!/usr/bin/env python3
"""Replay exact generated proofs and check incremental evidence boundaries."""

from collections import Counter
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
BASE = "cd95185e445ed247cfc06bf454977d836ab38d44"
RT32 = "research/formal-verification/RT-32"
CALLS = f"{RT32}/GENERATED-CALL-01"
CLOSURE = f"{RT32}/TRANSITIVE-CLOSURE-01"
MODULAR = (
    "caller", "caller_contract", "callee_contract", "premise", "generator", "toolchain", "artifact",
)
CLOSED = ("snapshot", "provider", "provider_receipt", "leaf_receipt")
FIELDS = (*MODULAR, *CLOSED, "leaf_disposition")


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def replay(directory):
    archive = subprocess.check_output(["git", "archive", BASE, CALLS, CLOSURE,
                                       "research/PROTOTYPES/DEPENDENCY-GRAPH-01"])
    with open_tar(fileobj=BytesIO(archive), mode="r:") as extracted:
        extracted.extractall(directory, filter="data")
    expected = {
        CALLS: "496fd92cdcf0260856f95284d4faff5e286ba8cb0ff8c30f84572bef5c519b7d",
        CLOSURE: "a3a717d38ccee308df1c4ebc1524ab27e021bff4a1f87903af02a46bff830490",
    }
    generated = directory / "generated.json"
    subprocess.run([sys.executable, "-B", f"{CALLS}/run.py", "--output", str(generated)],
                   cwd=directory, check=True)
    observed = {
        CALLS: generated.read_bytes(),
        CLOSURE: subprocess.check_output([sys.executable, "-B", f"{CLOSURE}/check.py"],
                                         cwd=directory),
    }
    for study, content in observed.items():
        archived = (directory / study / "evidence.json").read_bytes()
        if sha256(archived).hexdigest() != expected[study] or content != archived:
            raise AssertionError(f"Archived replay did not match: {study}")
    return json.loads(observed[CALLS]), json.loads(observed[CLOSURE]), expected


def summarize_calls(ledger):
    cases = ledger["cases"]
    rows = {}
    for key, current in cases.items():
        _, mode = key.split("/")
        baseline = cases[f"base/{mode}"]
        source_ids = current["source_ids"]
        rows[key] = {
            "same_caller_source": baseline["source_ids"]["Caller"] == source_ids["Caller"],
            "same_provider_source": baseline["source_ids"]["Provider"] == source_ids["Provider"],
            "same_closure_source": baseline["source_ids"]["Closed"] == source_ids["Closed"],
            "conditional_checked": "conditional" in current["axioms"],
            "closed_checked": "closed" in current["axioms"],
            "negative_replay": current["negative_replay"],
        }
    assert rows["rebound/late"]["same_caller_source"] and not rows["rebound/late"]["same_closure_source"]
    assert not rows["primary_edit/direct"]["same_caller_source"]
    assert rows["bad_rebound/late"]["conditional_checked"] and not rows["bad_rebound/late"]["closed_checked"]
    assert not rows["broader_provider/late"]["conditional_checked"]
    return rows


def scope(request, fields):
    return digest({name: request[name] for name in fields})


def compare(ledger, closure_ledger):
    result = {}
    scenarios = closure_ledger["scenarios"]
    raw_leaf = scenarios["base_closure"]
    replacement_leaf = scenarios["replacement_artifact_closure"]
    assert raw_leaf != replacement_leaf
    for mode in ("late", "direct"):
        base = ledger["cases"][f"base/{mode}"]
        subject = base["subject"]
        baseline = {
            "caller": subject["caller"],
            "caller_contract": subject["caller_contract"],
            "callee_contract": subject["provider_contract"],
            "premise": digest(subject["provider_allowed"]),
            "generator": digest([BASE, CALLS, ledger["call_core_source_id"]]),
            "toolchain": digest(ledger["lean"]),
            "artifact": base["source_ids"]["Caller"],
            "snapshot": subject["root"],
            "provider": subject["provider"],
            "provider_receipt": base["source_ids"]["Provider"],
            "leaf_receipt": raw_leaf,
            "leaf_disposition": "checked",
        }
        alternatives = {key: digest([old, "controlled-change"]) for key, old in baseline.items()}
        alternatives["leaf_disposition"] = "pending"
        alternatives["leaf_receipt"] = replacement_leaf
        modular_fields = (*MODULAR, "provider") if mode == "direct" else MODULAR
        exact_receipt_fields = (*modular_fields, *[field for field in CLOSED if field not in modular_fields])
        closed_key = scope(baseline, exact_receipt_fields)
        module_key = scope(baseline, modular_fields)
        counts = Counter()
        witness = {}
        for mask in product((False, True), repeat=len(FIELDS)):
            changes = {key for key, changed in zip(FIELDS, mask, strict=True) if changed}
            request = {key: alternatives[key] if key in changes else baseline[key] for key in FIELDS}
            module_hit = scope(request, modular_fields) == module_key
            ready = request["leaf_disposition"] == "checked"
            closed_hit = ready and scope(request, exact_receipt_fields) == closed_key
            oracle_modular = all(request[field] == baseline[field] for field in modular_fields)
            oracle_closed = all(request[field] == old for field, old in baseline.items())
            if (module_hit, closed_hit) != (oracle_modular, oracle_closed):
                raise AssertionError((mode, changes))
            counts["change_profiles"] += 1
            counts["modular_hits"] += module_hit
            counts["closed_hits"] += closed_hit
            counts["conditional_only"] += module_hit and not closed_hit
            controls = {
                "reuse_modular_as_closed": module_hit,
                "omit_exact_proof_artifact": ready and not changes.difference({"artifact"}),
                "omit_toolchain": ready and not changes.difference({"toolchain"}),
                "omit_grandchild": ready and not changes.difference({"leaf_receipt"}),
                "omit_disposition": not changes.difference({"leaf_disposition"}),
            }
            for name, accepted in controls.items():
                if accepted and not oracle_closed:
                    counts[f"{name}_false_closures"] += 1
                    witness.setdefault(name, sorted(changes))
        assert counts["closed_hits"] == 1
        result[mode] = {"conditional_scope": module_key, "closed_scope": closed_key,
                        "counts": counts, "witnesses": witness}
    return result


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        calls, closures, archives = replay(Path(directory))
    print(json.dumps({
        "schema": "llmlang-incremental-proof-evidence/1", "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archive_revision": BASE, "replayed_archives": archives,
        "generated_case_results": summarize_calls(calls),
        "closure_archive_root_cases": closures["exhaustive"]["root_cases"],
        "synthetic_evidence_matrix": compare(calls, closures),
    }, indent=2))
