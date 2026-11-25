#!/usr/bin/env python3
"""Check exact scope and observation requirements for testing claims."""

from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
BASELINE = "840258f39219be2a1cdb94f12e9afd18b47ed73d"
ARCHIVES = {
    "branch": (
        "research/formal-verification/RT-07/IDENTICAL-BRANCH-01/evidence.json",
        "6805fe6787d014b212b85d4cdd2599cddb7edaff932532626e0674bd1b6962ac",
    ),
    "state_result": (
        "research/compiler-and-translation/RT-13/STATE-RESULT-MUTATIONS-01/evidence.json",
        "eb05a5dd8f287d4b4a1195e88d470bc3640a73898e14b9d14cafcc2c921bf32e",
    ),
    "checked_add": (
        "research/compiler-and-translation/RT-13/LLVM-CHECKED-ADD-SYMBOLIC-01/evidence.json",
        "7cbab41fe9ab36ccc201d618e70edf8d065d465fc97a6eb0af72410adfdeadcb",
    ),
}
DOMAIN = tuple(product(range(32), range(2), range(2)))
VARIANTS = ("identity", "omitted_schedule_effect", "rare_result", "error_only",
            "reordered_effects")
PROFILES = {
    "result": lambda outcome: outcome[:2],
    "unordered_effects": lambda outcome: (*outcome[:2], *sorted(outcome[2])),
    "complete": lambda outcome: outcome,
}


def reference(case):
    address, fails, schedule = case
    tag = "error" if fails else "return"
    return tag, address, ("begin", f"step-{schedule}", "end")


def target(case, variant):
    address, fails, schedule = case
    tag, value, trace = reference(case)
    if variant == "omitted_schedule_effect" and schedule == 1:
        trace = ("begin", "end")
    elif variant == "rare_result" and address == 31 and not fails:
        value = 0
    elif variant == "error_only" and fails:
        tag = "return"
    elif variant == "reordered_effects":
        trace = trace[1], trace[0], trace[2]
    return tag, value, trace


def ranges():
    return {
        "whole_declared_domain": DOMAIN,
        "first_8_addresses": tuple(case for case in DOMAIN if case[0] < 8),
        "all_inputs_one_schedule": tuple(case for case in DOMAIN if case[2] == 0),
        "success_only": tuple(case for case in DOMAIN if case[1] == 0),
    }


def compare():
    records = {}
    for name, suite in ranges().items():
        complete_inputs = set(suite) == set(DOMAIN)
        profiles = {}
        for profile, project in PROFILES.items():
            matches = {}
            checked = set()
            for variant in VARIANTS:
                differences = [case for case in suite
                               if project(reference(case)) != project(target(case, variant))]
                matches[variant] = {"mismatches": len(differences), "first": next(iter(differences), None)}
                if not differences:
                    checked.add(variant)
            profiles[profile] = {
                "pass": sorted(checked),
                "closes_full_declared_claim": sorted(checked) if complete_inputs and profile == "complete" else [],
                "variants": matches,
            }
        records[name] = {"rows": len(suite), "input_pairs": len({case[:2] for case in suite}),
                         "profiles": profiles}
    exact = records["whole_declared_domain"]["profiles"]["complete"]
    assert exact["closes_full_declared_claim"] == ["identity"]
    assert {"identity", "omitted_schedule_effect"} == set(
        records["all_inputs_one_schedule"]["profiles"]["complete"]["pass"])
    assert "reordered_effects" in records["whole_declared_domain"]["profiles"]["unordered_effects"]["pass"]
    return records


def archived():
    records = {}
    evidence = {}
    for name, (path, expected) in ARCHIVES.items():
        data = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"])
        actual = sha256(data).hexdigest()
        if actual != expected:
            raise AssertionError(f"Archived record hash changed for {name}")
        records[name] = {"path": path, "sha256": actual}
        evidence[name] = json.loads(data)
    branch = evidence["branch"]
    state = evidence["state_result"]
    add = evidence["checked_add"]
    records["branch"]["summary"] = {
        "compared_guard_body_pairs": branch["counts"]["body_comparisons"],
        "trace_only_erasure_changes": branch["counts"]["erase_only_changes_trace"],
        "native_rows": {level: data["rows"] for level, data in branch["native"]["builds"].items()},
    }
    records["state_result"]["summary"] = {
        "corpus_keys": list(state["corpora"]),
        "exact_claim_limited_to_these_corpora": True,
    }
    records["checked_add"]["summary"] = {
        "checked_lean_claims": len(add["theorems"]),
        "incorrect_whole_domain_claims": len(add["incorrect_whole_domain_claims"]),
        "covers_ir_model_under_recorded_assumptions": True,
    }
    return records


if __name__ == "__main__":
    print(json.dumps({
        "schema": "llmlang-exhaustive-testing-claim-scope/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Coverage.lean", "axioms.txt")},
        "archived_commit": BASELINE, "archives_reconciled": archived(), "suites": compare(),
    }, indent=2))
