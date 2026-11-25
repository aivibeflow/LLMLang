"""Verify benchmark corpus pins and exercise the comparable-pair admission rules."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RT13 = HERE.parent
BACKENDS = {"llvm", "cranelift", "dedicated-wat", "direct-native"}
MATCHED_FIELDS = (
    "workload", "input_sha256", "oracle_sha256", "target", "host_profile", "optimization_intent",
    "boundary", "cache_state", "edit_sha256", "measured_unit",
)


def verified_inventory(data):
    inventory = {}
    for case in data["workloads"]:
        identifier = case["id"]
        if identifier in inventory or not case["profiles"] or not case["artifacts"]:
            raise ValueError(f"invalid or duplicate workload {identifier}")
        if set(case["profiles"]) - BACKENDS:
            raise ValueError(f"unknown backend for {identifier}")
        if any(status not in {"observed", "scoped-control", "missing"} for status in case["profiles"].values()):
            raise ValueError(f"invalid backend status for {identifier}")
        for relative, pinned in case["artifacts"].items():
            path = (RT13 / relative).resolve()
            if not path.is_relative_to(RT13) or not path.is_file():
                raise ValueError(f"missing or outside corpus: {relative}")
            if sha256(path.read_bytes()).hexdigest() != pinned:
                raise ValueError(f"artifact bytes changed: {relative}")
        inventory[identifier] = case
    return inventory


def comparison_gate(inventory, left, right):
    if any(left[field] != right[field] for field in MATCHED_FIELDS):
        return "different-comparison-profile"
    if left["backend"] == right["backend"]:
        return "same-backend"
    case = inventory[left["workload"]]
    if left["target"] != case["target"]:
        return "workload-target-mismatch"
    if any(case["profiles"].get(side["backend"]) != "observed" for side in (left, right)):
        return "unavailable-comparison-route"
    if any(side["conformance"] != "checked" or not side["negative_controls_detected"]
           or side["timed_artifact_sha256"] != side["checked_artifact_sha256"] for side in (left, right)):
        return "unverified-artifact"
    return "comparable-at-recorded-scope"


def gate_controls(inventory):
    # Synthetic comparison receipts test only record admission, with no timings.
    left = {"workload": "checked-add-jit", "input_sha256": "1" * 64, "oracle_sha256": "2" * 64,
            "target": "x86_64-linux-gnu-sysv", "host_profile": "synthetic-pinned-host",
            "optimization_intent": "debug-latency", "boundary": "jit-ready-to-call",
            "cache_state": "fresh-process", "edit_sha256": None, "measured_unit": "ns",
            "backend": "llvm", "conformance": "checked", "negative_controls_detected": True,
            "checked_artifact_sha256": "3" * 64, "timed_artifact_sha256": "3" * 64}
    right = dict(left, backend="cranelift", checked_artifact_sha256="4" * 64, timed_artifact_sha256="4" * 64)
    alternatives = {
        "matched": ({}, "comparable-at-recorded-scope"),
        "different-input": ({"input_sha256": "5" * 64}, "different-comparison-profile"),
        "different-oracle": ({"oracle_sha256": "5" * 64}, "different-comparison-profile"),
        "cycle-vs-time": ({"measured_unit": "cycles"}, "different-comparison-profile"),
        "different-host": ({"host_profile": "other-host"}, "different-comparison-profile"),
        "warm-vs-cold": ({"cache_state": "repeated-in-process"}, "different-comparison-profile"),
        "different-change": ({"edit_sha256": "5" * 64}, "different-comparison-profile"),
        "different-boundary": ({"boundary": "full-process"}, "different-comparison-profile"),
        "different-target": ({"target": "aarch64-linux-gnu"}, "different-comparison-profile"),
        "different-optimization": ({"optimization_intent": "throughput"}, "different-comparison-profile"),
        "candidate-missing": ({"backend": "direct-native"}, "unavailable-comparison-route"),
        "duplicate-backend": ({"backend": "llvm"}, "same-backend"),
        "weaker-conformance": ({"conformance": "unknown"}, "unverified-artifact"),
        "mutant-escaped": ({"negative_controls_detected": False}, "unverified-artifact"),
        "artifact-changed": ({"timed_artifact_sha256": "5" * 64}, "unverified-artifact"),
    }
    output = {}
    for name, (change, expected) in alternatives.items():
        outcome = comparison_gate(inventory, left, right | change)
        if outcome != expected:
            raise ValueError((name, outcome))
        output[name] = outcome
    wrong_target = {"target": "aarch64-linux-gnu"}
    outcome = comparison_gate(inventory, left | wrong_target, right | wrong_target)
    if outcome != "workload-target-mismatch":
        raise ValueError(("both-targets-mismatch-workload", outcome))
    output["both-targets-mismatch-workload"] = outcome
    return output


def collect():
    data = json.loads((HERE / "corpus.json").read_text())
    inventory = verified_inventory(data)
    corrupt = deepcopy(data)
    first = corrupt["workloads"][0]["artifacts"]
    first[next(iter(first))] = "0" * 64
    try:
        verified_inventory(corrupt)
    except ValueError as error:
        if "artifact bytes changed" not in str(error):
            raise
    else:
        raise ValueError("stale artifact accepted")
    return {
        "corpus_sha256": sha256((HERE / "corpus.json").read_bytes()).hexdigest(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "verified_pins": sum(len(case["artifacts"]) for case in inventory.values()),
        "workloads": {name: case["profiles"] for name, case in inventory.items()},
        "stale_artifact": "rejected",
        "comparison_controls": gate_controls(inventory),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(), indent=2, sort_keys=True) + "\n")
