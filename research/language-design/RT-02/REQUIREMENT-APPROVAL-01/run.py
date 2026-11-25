"""Check exact approval applicability against scenario controls."""

from collections import Counter
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
BASELINE = "2d557b45d54aa9b2ac892ca1c3d116a937083a4f"
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.business_intent import (BusinessRule, ClarificationDecision, IntentSource, accept_candidate,
                                 candidate_from_rule)
from src.semantic_graph import digest
from review import Decision, FormalStatus, Grant, ReviewAction, ReviewPackage, ReviewSubject, assess


def fixture():
    intent = IntentSource.create("Apply 12 percent from January 1 for preferred orders.")
    clarified = ClarificationDecision.create(intent, "Which effective date basis?",
                                             ("order", "invoice"), "order", "Policy owner")
    rule = BusinessRule.create("preferred_order", 1200, "2027-01-01", "order_date", intent, clarified)
    candidate = candidate_from_rule(rule)
    package = ReviewPackage(
        semantic=digest({"caller": rule.caller, "rate": rule.rate_basis_points,
                         "effective_from": rule.effective_from, "date_basis": rule.date_basis}),
        formal_model=digest([clause.predicate for clause in candidate.clauses]),
        intent_sources=digest([intent.source_hash, clarified.decision_hash]),
        provenance=digest([list(clause.source_refs) for clause in candidate.clauses]),
        reconstruction=digest("reconstruction v1"), scenarios=digest("scenario set v1"),
        analysis=digest("required checks run v1"), assumptions=digest("declared assumptions"),
        formal_status=FormalStatus.PASSED_REQUIRED_CHECKS)
    subject = ReviewSubject("project", "preferred-order-rate", "round-1", "policy-v1", package)
    grant = Grant("policy-owner", subject.project, subject.slot, subject.policy, digest("grant revision"))
    action = ReviewAction(subject.identity, grant.actor, grant.revision, Decision.ACCEPT, "Reviewed every clause.")
    return subject, grant, action, candidate


def run():
    subject, grant, action, legacy_candidate = fixture()
    package = subject.package
    active_grants = {grant.revision: grant}
    denied = "blocked"
    records = []

    def check(name, expected, *, current=subject, submitted=action, actor=grant.actor, grants=active_grants):
        outcome = assess(current, submitted, authenticated_actor=actor, active_grants=grants)
        assert outcome == expected, (name, outcome, expected)
        records.append({"case": name, "current_subject": current.identity, "submitted_action": submitted.identity,
                        "intent_review": outcome[0], "contract_gate": outcome[1]})

    def new_package(**fields):
        return replace(subject, package=replace(package, **fields))

    check("fresh", ("intent-accepted", "eligible-for-contract-admission"))
    check("same immutable acceptance reapplied", ("intent-accepted", "eligible-for-contract-admission"))
    for field in ("semantic", "formal_model", "intent_sources", "provenance", "reconstruction",
                  "scenarios", "analysis", "assumptions"):
        changed = new_package(**{field: digest(f"updated {field}")})
        assert (changed.package.semantic == package.semantic) == (field != "semantic")
        check(f"stale after {field} changes", ("different-review-subject", denied), current=changed)
    for field in ("project", "slot", "round", "policy"):
        check(f"same package in another {field}", ("different-review-subject", denied),
              current=replace(subject, **{field: "different"}))
    check("wrong authenticated actor", ("unauthenticated-reviewer", denied), actor="another-actor")
    check("removed grant", ("out-of-scope-authority", denied), grants={})
    check("grant for another slot", ("out-of-scope-authority", denied),
          grants={grant.revision: replace(grant, slot="other-slot")})
    check("missing rationale", ("invalid-review-action", denied), submitted=replace(action, rationale=" "))
    for decision, expected in ((Decision.REVISE, "revision-requested"),
                               (Decision.CLARIFY, "clarification-requested"),
                               (Decision.REJECT, "candidate-rejected")):
        check(decision.value, (expected, denied), submitted=replace(action, decision=decision))
    for field in ("unresolved_business_questions", "missing_provenance", "unsupported_clauses"):
        changed = new_package(**{field: ("clause-1",)})
        check(field, ("incomplete-review-package", denied), current=changed,
              submitted=replace(action, subject=changed.identity))
    for formal, disposition in ((FormalStatus.REFUTED, "formal-refuted"),
                                (FormalStatus.UNKNOWN, "formal-unknown"),
                                (FormalStatus.UNSUPPORTED, "formal-unsupported")):
        changed = new_package(formal_status=formal)
        check(f"separate formal result {formal}", ("intent-accepted", disposition), current=changed,
              submitted=replace(action, subject=changed.identity))

    changed_review = new_package(reconstruction=digest("reconstruction v2"))
    # The legacy experiment does not take a separately rendered review package.
    first = accept_candidate(legacy_candidate, "policy-owner", authorized=True)
    second = accept_candidate(legacy_candidate, "policy-owner", authorized=True)
    assert first.approval_hash == second.approval_hash
    assert changed_review.package.identity != package.identity
    check("legacy candidate unchanged while review text changes", ("different-review-subject", denied),
          current=changed_review)

    paths = [HERE / name for name in ("run.py", "review.py")]
    paths.extend(PROTOTYPE / "src" / name for name in ("business_intent.py", "semantic_graph.py"))
    return {
        "schema": "rt02-exact-review-approval-1", "baseline": BASELINE,
        "python": platform.python_version(),
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
        "case_count": len(records),
        "contract_gate_counts": dict(Counter(row["contract_gate"] for row in records)),
        "legacy_comparison": {
            "legacy_approval_identity_reused": True, "old_package": package.identity,
            "changed_package": changed_review.package.identity,
            "same_semantic_identity": package.semantic == changed_review.package.semantic,
        },
        "cases": records,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
