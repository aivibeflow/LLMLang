"""Check reuse against downstream observation roles using pinned RT-11 ledgers."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import subprocess

BASE = "0d845c854b290999f05aeccfe86c2ec3f388b907"
ROOT = "research/toolchain-and-collaboration/RT-11"
INPUTS = (
    "ELF-METADATA-REUSE-01", "CROSS-TOOLCHAIN-CACHE-01",
    "NATIVE-RUNTIME-CLOSURE-01", "TYPED-ACTION-RECEIPTS-01",
)
DEMANDS = {
    "exact_artifact": ("artifact",),
    "normal_result": ("load_segments", "normal"),
    "self_inspection": ("load_segments", "self_inspection"),
    "normal_result_and_exact_artifact": ("load_segments", "normal", "artifact"),
}


def load(study):
    path = f"{ROOT}/{study}/evidence.json"
    original = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
    return json.loads(original), sha256(original).hexdigest()


def equal_payloads(source, target, role):
    return all(source[field] == target[field] for field in DEMANDS[role])


def audit_elf(ledger):
    counts = Counter()
    for opt, detail in ledger["results"].items():
        profiles = detail["profiles"]
        assert len(profiles) == 6 and detail["normal_observations"] == 54
        assert detail["pairs_compared"] == 15
        for source, target in product(profiles, repeat=2):
            for role in DEMANDS:
                counts[role] += equal_payloads(source, target, role)
    assert set(ledger["results"]) == {"O0", "O2"}
    assert counts == {
        "exact_artifact": 12, "normal_result": 72, "self_inspection": 12,
        "normal_result_and_exact_artifact": 12,
    }
    return {"pairs_considered": 72, "equal_by_consumer_role": dict(counts)}


def audit_returns(ledger):
    profiles = ledger["profiles"]
    gcc = profiles["gcc"]["wrapping"]
    clang = profiles["clang"]["wrapping"]
    saturating = profiles["clang"]["saturating"]
    full, restricted = ledger["full_bridge"], ledger["restricted_bridge"]
    assert gcc["action_key"] != clang["action_key"]
    assert gcc["object_sha256"] != clang["object_sha256"]
    assert gcc["observations"] == clang["observations"]
    assert (full["origin"], full["destination"], full["scope"]) == (
        gcc["action_key"], clang["action_key"], list(range(256)))
    assert (restricted["origin"], restricted["destination"], restricted["scope"]) == (
        gcc["action_key"], saturating["action_key"], list(range(255)))
    changed = [i for i, (origin, target) in enumerate(
        zip(gcc["observations"], saturating["observations"], strict=True)) if origin != target]
    assert changed == [255]
    comparisons = ledger["comparisons"]
    assert comparisons["exact_observation_bridge_admitted"] is True
    assert comparisons["bridge_reversed"] is False
    assert comparisons["partial_bridge_reused_for_full_scope"] is False
    assert sum(len(case["observations"]) for compiler in profiles.values()
               for case in compiler.values()) == 1024
    return {"native_returns_compared": 1024, "different_return_inputs": changed,
            "directional_receipt_only": True, "exact_object_identity_retained": True}


def audit_runtime(ledger):
    rows = ledger["rows"]
    counts = Counter(row["decision"] for row in rows)
    assert counts == {"publish": 4, "hit": 4, "uncached": 2, "load-error": 2, "policy-denied": 2}
    uncached = [row for row in rows if row["decision"] == "uncached"]
    assert all(row["action_key"] is None and row["clean"]["stdout"].strip() == "29"
               for row in uncached)
    return {"decisions": dict(counts), "observations_with_no_cache_key": len(uncached)}


def audit_roles(ledger):
    equivalent = ledger["cases"]["equivalent_source"]
    baseline = ledger["cases"]["baseline"]
    assert baseline["compile"]["key"] != equivalent["compile"]["key"]
    assert baseline["compile"]["artifact"] == equivalent["compile"]["artifact"]
    assert baseline["link"] == equivalent["link"]
    assert ledger["refused"]["input_exact_bytes_wrong_kind"] == "input roles and types"
    assert ledger["refused"]["input_reversed"] == "input roles and types"
    assert len(ledger["cases"]) == 5
    return {"role_and_order_controls_rejected": 2, "changed_compile_key_same_link_receipt": True}


def main():
    findings, inputs = {}, {}
    for study, audit in zip(INPUTS, (audit_elf, audit_returns, audit_runtime, audit_roles), strict=True):
        raw, digest = load(study)
        findings[study] = audit(raw)
        inputs[study] = digest
    print(json.dumps({"base": BASE, "evidence_sha256_by_study": inputs, "findings": findings},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
