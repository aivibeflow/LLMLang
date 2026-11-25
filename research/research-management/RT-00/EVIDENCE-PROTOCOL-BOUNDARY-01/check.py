"""Check archived evidence classifications and authority on an immutable research tree."""

import hashlib
import json
import re
import subprocess

BASE = "1ec32a8c356a1a44c3531a59e25d73a60120313b"
RUNTIME = "research/runtime-and-systems"
COMPILER = "research/compiler-and-translation"
MANAGEMENT = "research/research-management"

digests = {}


def read(path):
    data = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
    digests[path] = hashlib.sha256(data).hexdigest()
    return data.decode()


def main():
    template = read("research/templates/REPORT-TEMPLATE.md")
    headings = re.findall(r"(?m)^#{2,3} (.+)$", template)
    assert headings == [
        "Problem and hypotheses",
        "Prior art and alternatives",
        "Formal model and assumptions",
        "Experiments and method",
        "Results and evidence classification",
        "Negative results, rejected options and UNKNOWN",
        "Limitations and threats to validity",
        "Decision boundary and recommendation",
        "Draft impact and traceability",
        "Reproduction and quality-gate review",
    ]
    for marker in ("**Fixture:**", "**Tool versions:**", "**Expected output:**",
                   chr(96) * 3 + "sh", "Q1–Q5", "Exploratory only", "Hypothesis",
                   "Assumption", "Observation", "Experimental result", "Proof",
                   "Accepted decision"):
        assert marker in template, marker

    protocol = read(f"{MANAGEMENT}/QUALITY-REVIEW-PROTOCOL.md")
    decision = read("draft/ARCHITECTURE-DECISIONS.md")
    assert "**Status:** Proposed Stage 0.2 research-documentation process" in protocol
    assert "## 5. Quality gates and authority" in protocol
    assert "**Status:** Accepted project architecture decision" in decision
    assert "## Reconsideration trigger" in decision

    authority = json.loads(read(f"{MANAGEMENT}/RT-00/"
                                "RT-00-C-ACCEPTED-FEATURE-AUTHORITY-2026-11-25.json"))
    accepted = sorted(row["feature_id"] for row in authority["accepted_mappings"])
    assert authority["feature_rows"] == 143
    assert len(authority["decision_docs"]) == 5
    assert accepted == ["F-PORT-002", "F-TOOL-003"]

    proof = json.loads(read(f"{RUNTIME}/RT-38/SEL4-TRANSFER-CONTROLS-01/stock-evidence.json"))
    assert all(proof["proof_options"][flag] is False
               for flag in ("skip_proofs", "quick_and_dirty"))
    assert len(proof["proofs"]) == 4
    assert len(proof["expected_quickcheck_counterexamples"]) == 3
    assert len(proof["expected_genuine_nitpick_counterexamples"]) == 1
    assert proof["clean_session_outcomes"] == ["pass", "pass"]

    ffi = json.loads(read(f"{COMPILER}/RT-13/FFI-BIDIRECTIONAL-HOSTED-01/evidence.json"))
    assert len(ffi["profiles"]) == 16
    assert ffi["native_total"] == 96
    assert all(profile["wrong_symbol_refused"] is True for profile in ffi["profiles"].values())

    alloc = json.loads(read(f"{RUNTIME}/RT-25/CONCURRENT-ALLOCATOR-PRESSURE-01/samples.json"))
    samples = alloc["samples"]
    startup_errors = sum("startup_error" in row for row in samples)
    assert (len(samples), startup_errors) == (280, 28)

    quota = json.loads(read(f"{RUNTIME}/RT-26/NATIVE-READ-ADMISSION-01/samples.json"))
    samples = quota["samples"]
    decisions = sum(len(row["admit_ns"]) + len(row["refuse_ns"]) for row in samples)
    assert (len(samples), decisions) == (72, 92160)

    migration = json.loads(read(f"{COMPILER}/RT-28/CONTRIBUTION-AND-CUTOVER-01/evidence.json"))
    outcomes = migration["outcomes"]
    assert sum(outcomes.values()) == 48
    assert sum(count for outcome, count in outcomes.items()
               if outcome.endswith("/cutover-and-rollback")) == 2

    print(json.dumps({
        "base": BASE,
        "template_headings": headings,
        "accepted_features": accepted,
        "proofs": proof["proofs"],
        "quickcheck_counterexamples": 3,
        "genuine_nitpick_counterexamples": 1,
        "ffi_wrong_symbols_refused": 16,
        "ffi_native_observations": ffi["native_total"],
        "allocator_runs": len(alloc["samples"]),
        "allocator_startup_errors": startup_errors,
        "quota_runs": len(samples),
        "quota_decisions": decisions,
        "migration_outcomes": outcomes,
        "input_sha256": digests,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
