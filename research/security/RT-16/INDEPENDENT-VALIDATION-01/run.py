"""Attach independently evaluated fixture results to the RT-16 evidence gate."""

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
POLICY = HERE.parents[1] / "PROTOTYPES" / "RT-16-AUTHORIZATION-01" / "policy.py"
sys.path.insert(0, str(POLICY.parent))

from policy import EvidenceContext, VerificationEvidence, verify_required_evidence

BASELINE = "755977e024086acacedae74f4b48635251f031c0"
CHECKS = ("arithmetic", "ordered_trace")
VERIFIER = "bounded-independent-verifier/v1"
DOMAIN = tuple(range(256))
CANDIDATES = {
    "wrap": {"increment": "wrap", "logging": "original-then-result"},
    "saturate": {"increment": "saturate", "logging": "original-then-result"},
    "reordered": {"increment": "wrap", "logging": "result-then-original"},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def context(candidate, domain):
    return EvidenceContext(candidate=digest(candidate), toolchain=VERIFIER, target="uint8-model",
                           assumptions=digest({"domain": domain, "required_checks": CHECKS}))


def execute(candidate, raw):
    if candidate["increment"] == "wrap":
        result = (raw + 1) % 256
    elif candidate["increment"] == "saturate":
        result = min(raw + 1, 255)
    else:
        raise ValueError("outside the fixture operation set")
    if candidate["logging"] == "original-then-result":
        trace = (raw, result)
    elif candidate["logging"] == "result-then-original":
        trace = (result, raw)
    else:
        raise ValueError("outside the fixture effect set")
    return result, trace


def independently_check(candidate, domain, budget):
    evidence_context = context(candidate, domain)
    checked = domain[:budget]
    observed = [(raw, execute(candidate, raw)) for raw in checked]
    counterexamples = {key: [] for key in CHECKS}
    for raw, (value, trace) in observed:
        wanted = 0 if raw == 255 else raw + 1
        if value != wanted:
            counterexamples["arithmetic"].append(raw)
        if trace != (raw, wanted):
            counterexamples["ordered_trace"].append(raw)
    evidence = []
    for check in CHECKS:
        if counterexamples[check]:
            status = "failed"
        elif len(checked) == len(domain):
            status = "passed"
        else:
            status = "unknown"
        evidence.append(VerificationEvidence(check, evidence_context, VERIFIER, status))
    return evidence, {"counterexamples": counterexamples, "evaluated_rows": observed}


def consume(candidate, domain, received):
    return verify_required_evidence(CHECKS, context(candidate, domain), received, {VERIFIER})


def study():
    cases = {}
    fake_claims = (
        {"claimed_outcome": "pass", "proposed_check_ids": ["arithmetic"], "input_limit": 255},
        {"claimed_outcome": "fail", "proposed_check_ids": [], "input_limit": 0},
    )
    expected = {
        "wrap": {256: ("passed", "passed", True), 255: ("unknown", "unknown", False)},
        "saturate": {256: ("failed", "failed", False), 255: ("unknown", "unknown", False)},
        "reordered": {256: ("passed", "failed", False), 255: ("unknown", "failed", False)},
    }
    generated = {}
    for name, candidate in CANDIDATES.items():
        for budget in (256, 255):
            receipts, details = independently_check(candidate, DOMAIN, budget)
            decision = consume(candidate, DOMAIN, receipts)
            wanted = expected[name][budget]
            assert tuple(row.result for row in receipts) == wanted[:2]
            assert decision.allowed == wanted[2]
            key = f"{name}-{budget}"
            generated[key] = receipts
            cases[key] = {"candidate": candidate, "authorized_budget": budget, **details,
                          "engagements": []}
            for claim in fake_claims:
                # Claims are a presentation field. The preapproved request is passed separately.
                replay, replay_details = independently_check(candidate, DOMAIN, budget)
                assert replay == receipts and replay_details == details
                assert consume(candidate, DOMAIN, replay) == decision
                cases[key]["engagements"].append({
                    "agent_claim": claim, "decision": asdict(decision),
                    "evidence": [{"record": asdict(row), "digest": row.digest()} for row in replay],
                })

    good = generated["wrap-256"]
    narrow = DOMAIN[:-1]
    narrower_receipts, _ = independently_check(CANDIDATES["saturate"], narrow, len(narrow))
    assert consume(CANDIDATES["saturate"], narrow, narrower_receipts).allowed
    controls = {
        "self-reported-pass": (
            "wrap", [replace(row, verifier="model-proposal") for row in good], "untrusted-verifier",
        ),
        "same-program-incomplete-check-inventory": ("wrap", good[:1], "required-evidence-missing"),
        "duplicate-check-results": ("wrap", good + good[:1], "duplicate-check-evidence"),
        "changed-program": ("reordered", good, "stale-evidence"),
        "changed-obligation-domain": ("saturate", narrower_receipts, "stale-evidence"),
    }
    comparisons = {}
    for name, (candidate, received, reason) in controls.items():
        decision = consume(CANDIDATES[candidate], DOMAIN, received)
        assert not decision.allowed and decision.reason == reason
        comparisons[name] = {"candidate": candidate, "decision": asdict(decision),
                             "evidence": [asdict(row) for row in received]}
    assert cases["saturate-256"]["counterexamples"]["arithmetic"] == [255]
    assert len(cases["reordered-256"]["counterexamples"]["ordered_trace"]) == 256
    relative = str(POLICY.relative_to(ROOT))
    archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
    assert archived == POLICY.read_bytes()
    return {
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy_sha256": hashlib.sha256(archived).hexdigest(),
        "authorized_request": {"domain": [min(DOMAIN), max(DOMAIN)], "checks": CHECKS},
        "validation_cases": cases, "evidence_controls": comparisons,
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2))
