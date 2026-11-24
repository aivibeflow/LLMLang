"""Project comparable and non-comparable boundaries from pinned research ledgers."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


RESEARCH = Path(__file__).resolve().parents[2]
COMPILER = "compiler-and-translation/RT-13"
GIT = "toolchain-and-collaboration/RT-23"
PATHS = {
    "rust_llvm": f"{COMPILER}/GENERATED-RUST-INTEGERS-01/evidence.json",
    "go": f"{COMPILER}/GENERATED-GO-INTEGERS-01/evidence.json",
    "validators": f"{COMPILER}/LLVM-VALIDATORS-01/stock-eh-evidence.json",
    "jit": f"{COMPILER}/JIT-MATERIALIZATION-01/evidence/builds-paused/summary.json",
    "caller": "formal-verification/RT-32/GENERATED-CALL-01/evidence.json",
    "prepared": f"{GIT}/GIT-PREPARED-CRASH-01/evidence.json",
    "commit_visibility": f"{GIT}/REF-VISIBILITY-01/evidence.json",
    "mcp": "toolchain-and-collaboration/RT-19/MCP-STDIO-01/evidence.json",
    "cancel": "runtime-and-systems/RT-26/LINUX-IO-CANCEL-01/evidence.json",
}


def load():
    raw = {name: (RESEARCH / path).read_bytes() for name, path in PATHS.items()}
    return {name: json.loads(data) for name, data in raw.items()}, {
        name: {"path": PATHS[name], "sha256": sha256(data).hexdigest()} for name, data in raw.items()
    }


def integer_comparison(rust, go):
    source_names = ("integer_fixture.py", "llvm_integer_probe.py")
    for source in source_names:
        if rust["input_sources_sha256"][source] != go["input_sha256"][source]:
            raise ValueError(f"Incomparable integer fixture source: {source}")
    if (rust["programs"], rust["vectors"]) != (go["programs"], go["vectors"]):
        raise ValueError("Integer workload dimensions differ")
    expected = rust["programs"] * rust["vectors"]
    profiles = {**rust["profiles"], **{f"go_{name}": row for name, row in go["profiles"].items()}}
    all_statuses = profiles["llvm_O0"]["statuses"]
    for name, row in profiles.items():
        if (row["statuses"] != all_statuses or sum(row["statuses"].values()) != expected
                or row["observations"] != expected):
            raise ValueError(f"Different observed source classifications in {name}")
    if go["profiles"]["c_shared"]["checked_c_exports"] != rust["programs"]:
        raise ValueError("Expected all workload entries at the C boundary")
    return {"programs": rust["programs"], "inputs_per_program": rust["vectors"], "per_profile": expected,
            "profiles": sorted(profiles), "classified": all_statuses,
            "shared_source_sha256": {source: go["input_sha256"][source] for source in source_names},
            "object_bytes": {name: row["object_bytes"] for name, row in rust["profiles"].items()},
            "packaged_bytes": {name: row["bytes"] for name, row in go["profiles"].items()},
            "rust_debug_runtime_imports": rust["rust_O0_debug_assertions_imports"],
            "rust_debug_undefined_link_rejected": rust["rust_O0_debug_link_without_runtime_rejected"]}


def check():
    data, sources = load()
    integers = integer_comparison(data["rust_llvm"], data["go"])
    validator_cases = data["validators"]["cases"]
    verdicts = {name: row["alive2"] for name, row in validator_cases.items()}
    if verdicts != {"identity": "valid", "alias": "refuted", "wrap": "refuted",
                    "atomic": "unsupported", "fence": "unsupported"}:
        raise ValueError("Validator coverage boundary changed")
    jit = data["jit"]["combined"]
    jit_selected = {name: jit[name] for name in ("llvm-O0", "cranelift-none")}
    for timing in ("first", "subsequent"):
        if (jit_selected["llvm-O0"][timing]["n"] != jit_selected["cranelift-none"][timing]["n"]
                or jit_selected["llvm-O0"][timing]["p50_us"] <= jit_selected["cranelift-none"][timing]["p50_us"]):
            raise ValueError("The JIT comparison needs re-adjudication")
    proof = data["caller"]["cases"]
    old = proof["base/late"]
    new = proof["rebound/late"]
    if (old["source_ids"]["Caller"] != new["source_ids"]["Caller"]
            or old["source_ids"]["Provider"] == new["source_ids"]["Provider"]
            or old["subject"]["binding"] == new["subject"]["binding"]
            or new["negative_replay"] != "stale_provider_rejected"):
        raise ValueError("Expected reusable conditional caller and changed closure inputs")
    prepared = data["prepared"]["cases"]
    visibility = data["commit_visibility"]["cases"]
    chosen = {
        "files_kill_at_prepare": prepared["files/kill"]["ordinary_retry"],
        "files_unrelated_ref": prepared["files/kill"]["unrelated_write_after_crash"],
        "reftable_kill_at_prepare": prepared["reftable/kill"]["ordinary_retry"],
        "reftable_unrelated_ref": prepared["reftable/kill"]["unrelated_write_after_crash"],
        "files_partial_visibility": visibility["files/branch_rename/kill"]["after"]["inspection"],
        "reftable_table_not_yet_visible": visibility["reftable/new_table_rename/resume"]["at_cut"]["inspection"],
        "reftable_list_change_visible": visibility["reftable/table_list_rename/resume"]["at_cut"]["inspection"],
    }
    expected_publication = {
        "files_kill_at_prepare": "blocked_by_lock", "files_unrelated_ref": "written",
        "reftable_kill_at_prepare": "blocked_by_lock", "reftable_unrelated_ref": "blocked_by_lock",
        "files_partial_visibility": "stale", "reftable_table_not_yet_visible": "retryable",
        "reftable_list_change_visible": "published",
    }
    if chosen != expected_publication:
        raise ValueError("Publication boundary changed")
    stdio = data["mcp"]["passed"]
    wait = data["cancel"]["cases"]
    if stdio != len(data["mcp"]["observations"]) or stdio != 42:
        raise ValueError("MCP fixture changed")
    if (wait["close_reuse_reader"]["still_blocked_after_close_and_reuse"], wait["cancel_only"]["outcome"],
            wait["both_ready_cancel_first"]["spent"], wait["both_ready_data_first"]["spent"]) != (
                True, "cancelled", 0, 4,
    ):
        raise ValueError("Execution and settlement control changed")
    return {"format": "llmlang-bounded-toolchain-option-evidence/1", "python": sys.version.split()[0],
            "inputs": sources, "results": {
                "integer_profiles": integers,
                "validator_coverage": verdicts,
                "ready_to_call_jit": jit_selected,
                "generated_calls": {"closed": sum(row["expected"] == "closed" for row in proof.values()),
                                    "cases": len(proof), "modular_caller_preserved": True,
                                    "closed_provider_changes": True, "stale_provider_rejected": True},
                "publication": chosen, "mcp_checks": stdio,
                "read_byte_settlement": {"cancel_priority": 0, "data_priority": 4},
            }}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
