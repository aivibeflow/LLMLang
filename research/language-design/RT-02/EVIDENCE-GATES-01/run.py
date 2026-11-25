"""Check fail-closed composition without collapsing three evidence claims."""

from dataclasses import dataclass, replace
import hashlib
from itertools import product
import json
from pathlib import Path
import platform


@dataclass(frozen=True)
class Inputs:
    review_subject: str = "review-package-v1"
    reviewer_authorized: bool = True
    review: str = "ACCEPT"
    provenance_complete: bool = True
    source_coverage_complete: bool = True
    reconstruction_valid: bool = True
    formal_subject: str = "formal-model-v1"
    supported: bool = True
    assumptions_discharged: bool = True
    analysis: str = "CHECKED"
    implementation_subject: str = "execution-tuple-v1"
    implementation_evidence: str = "CHECKED_PROOF"


def assess(inputs):
    intent = [reason for missing, reason in (
        (inputs.review_subject != "review-package-v1", "review-package-mismatch"),
        (not inputs.reviewer_authorized, "unauthorized-review"),
        (inputs.review != "ACCEPT", "review-" + inputs.review.lower()),
        (not inputs.provenance_complete, "missing-provenance"),
        (not inputs.source_coverage_complete, "incomplete-source-coverage"),
        (not inputs.reconstruction_valid, "reconstruction-failure"),
    ) if missing]
    formal = [reason for missing, reason in (
        (inputs.formal_subject != "formal-model-v1", "formal-model-mismatch"),
        (not inputs.supported, "unsupported-construct"),
        (not inputs.assumptions_discharged, "unresolved-assumption"),
        (inputs.analysis != "CHECKED", "analyzer-" + inputs.analysis.lower()),
    ) if missing]
    implementation = [reason for missing, reason in (
        (inputs.implementation_subject != "execution-tuple-v1", "implementation-tuple-mismatch"),
        (inputs.implementation_evidence != "CHECKED_PROOF", "evidence-" + inputs.implementation_evidence.lower()),
    ) if missing]
    gates = {
        "intent": {"open_reasons": intent, "reported_outcome": inputs.review},
        "formal_contract": {"open_reasons": formal, "reported_outcome": inputs.analysis},
        "implementation": {"open_reasons": implementation, "reported_outcome": inputs.implementation_evidence},
    }
    for gate in gates.values():
        gate["satisfies_gate"] = not gate["open_reasons"]
    return {"gates": gates,
            "contract_admission": not (intent or formal),
            "closed_implementation_claim": not (intent or formal or implementation)}


def main():
    baseline = Inputs()
    blockers = (
        ("unsupported", {"supported": False}, "formal_contract", "unsupported-construct"),
        ("open_assumption", {"assumptions_discharged": False}, "formal_contract", "unresolved-assumption"),
        ("missing_provenance", {"provenance_complete": False}, "intent", "missing-provenance"),
        ("incomplete_source_coverage", {"source_coverage_complete": False}, "intent", "incomplete-source-coverage"),
        ("analyzer_unknown", {"analysis": "UNKNOWN"}, "formal_contract", "analyzer-unknown"),
        ("reconstruction_failure", {"reconstruction_valid": False}, "intent", "reconstruction-failure"),
    )
    factorial = {}
    for flags in product((False, True), repeat=len(blockers)):
        active = [item for flag, item in zip(flags, blockers) if flag]
        changes = {key: value for _, fields, _, _ in active for key, value in fields.items()}
        expected = {"intent": set(), "formal_contract": set(), "implementation": set()}
        for _, _, gate, reason in active:
            expected[gate].add(reason)
        result = assess(replace(baseline, **changes))
        assert {gate: set(row["open_reasons"]) for gate, row in result["gates"].items()} == expected
        assert result["contract_admission"] == result["closed_implementation_claim"] == (not active)
        factorial["+".join(row[0] for row in active) or "all_applicable"] = result

    additional = {
        "review_only_current": ({"formal_subject": "formal-old", "implementation_subject": "execution-old"},
                                (True, False, False)),
        "formal_only_current": ({"review_subject": "review-old", "implementation_subject": "execution-old"},
                                (False, True, False)),
        "exact_implementation_with_unresolved_intent": ({"review": "CLARIFY"}, (False, True, True)),
        "unauthorized_review": ({"reviewer_authorized": False}, (False, True, True)),
        "valid_contract_with_tests_only": ({"implementation_evidence": "BOUNDED_TEST"}, (True, True, False)),
        "valid_contract_with_conditional_proof": ({"implementation_evidence": "CONDITIONAL_PROOF"},
                                                  (True, True, False)),
        "formal_refutation_and_open_assumption": ({"analysis": "REFUTED", "assumptions_discharged": False},
                                                  (True, False, True)),
        "implementation_refutation": ({"implementation_evidence": "REFUTED"}, (True, True, False)),
    }
    examples = {}
    for label, (changes, expected) in additional.items():
        result = assess(replace(baseline, **changes))
        gates = result["gates"]
        assert tuple(row["satisfies_gate"] for row in gates.values()) == expected
        assert result["contract_admission"] == all(expected[:2])
        assert result["closed_implementation_claim"] == all(expected)
        examples[label] = result
    composite = examples["formal_refutation_and_open_assumption"]["gates"]["formal_contract"]
    assert composite["reported_outcome"] == "REFUTED"
    assert set(composite["open_reasons"]) == {"unresolved-assumption", "analyzer-refuted"}
    return {"schema": "llmlang-rt02-evidence-gates/1", "python": platform.python_version(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "factorial_controls": factorial, "typed_evidence_controls": examples}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
