"""Finite RT-02 candidate lifecycle and evidence-binding experiment."""

import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[4]
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))
from src.requirement_evolution import create_requirement_state
from src.semantic_graph import ContentStore, Dependency

PARENTS = {
    "intent": {},
    "question": {"intent": "intent"},
    "clarification": {"question": "question"},
    "provenance": {"intent": "intent", "clarification": "clarification", "requirement": "requirement_state"},
    "formal": {"requirement": "requirement_state"},
    "analysis": {"formal": "formal"},
    "explanation": {"formal": "formal"},
    "package": {"formal": "formal", "analysis": "analysis", "explanation": "explanation",
                "provenance": "provenance"},
    "approval": {"package": "package"},
    "accepted": {"approval": "approval", "package": "package"},
    "component": {"formal": "formal"},
    "tests": {"component": "component"},
    "implementation": {"component": "component"},
    "verification": {"component": "component", "tests": "tests", "implementation": "implementation"},
}


def parents(store, artifact):
    return {edge.role: edge.target_hash for edge in store.get(artifact).dependencies}


def put(store, kind, payload, **refs):
    signature = PARENTS[kind]
    if refs.keys() != signature.keys():
        raise ValueError(f"wrong roles for {kind}")
    if any(ref not in store or store.get(ref).kind != signature[role] for role, ref in refs.items()):
        raise ValueError(f"missing or ill-typed parent for {kind}")
    if kind == "provenance":
        question = parents(store, refs["clarification"])["question"]
        if parents(store, question)["intent"] != refs["intent"]:
            raise ValueError("clarification belongs to another intent")
    if kind == "package":
        formal = refs["formal"]
        if any(parents(store, refs[role])["formal"] != formal for role in ("analysis", "explanation")):
            raise ValueError("package mixes formal versions")
        if parents(store, refs["provenance"])["requirement"] != parents(store, formal)["requirement"]:
            raise ValueError("package mixes requirement versions")
    if kind == "accepted" and not approval_matches(store, refs["package"], refs["approval"], exact=True):
        raise ValueError("accepted record requires exact authorized approval")
    if kind == "verification":
        if any(parents(store, refs[role])["component"] != refs["component"]
               for role in ("tests", "implementation")):
            raise ValueError("verification mixes component versions")
    return store.put(kind, payload, [Dependency("requires", target, role) for role, target in refs.items()])


def bundle(store, *, deadline=5, source_fragment="lines 1-2", wording="v1", analysis="CONSISTENT",
           revision="v1", test_revision="v1", complete=True):
    intent = put(store, "intent", {"text": "Confirm the order soon after a successful payment."})
    question = put(store, "question", {"text": "Which deadline and outcome apply?"}, intent=intent)
    clarification = put(store, "clarification", {"deadline": deadline, "authority": "fixture-owner"},
                        question=question)
    requirement = create_requirement_state(store, "order-confirmation", {
        "trigger": "payment-registered", "effect": "order-confirmed", "deadline": deadline
    })
    provenance = put(store, "provenance", {"source_fragment": source_fragment, "complete": complete},
                     intent=intent, clarification=clarification, requirement=requirement)
    formal = put(store, "formal", {"clock": "integer-seconds", "profile": "bounded-v1"},
                 requirement=requirement)
    analyzed = put(store, "analysis", {"outcome": analysis, "scope": "bounded-fixture"}, formal=formal)
    formal_requirement = store.get(parents(store, formal)["requirement"]).payload["semantic"]
    explanation = put(store, "explanation", {"deadline": formal_requirement["deadline"], "wording": wording},
                      formal=formal)
    package = put(store, "package", {}, formal=formal, analysis=analyzed,
                  explanation=explanation, provenance=provenance)
    component = put(store, "component", {"implementation_scope": "order-service"}, formal=formal)
    tests = put(store, "tests", {"revision": test_revision}, component=component)
    implementation = put(store, "implementation", {"revision": revision}, component=component)
    return package, {"component": component, "tests": tests, "implementation": implementation}


def approval_matches(store, package, approval, *, exact):
    metadata = store.get(approval).payload
    current = parents(store, package)
    if metadata["actor"] != "fixture-owner" or metadata["outcome"] != "ACCEPT":
        return False
    if store.get(current["analysis"]).payload["outcome"] != "CONSISTENT":
        return False
    if not store.get(current["provenance"]).payload["complete"]:
        return False
    reviewed = parents(store, approval)["package"]
    return reviewed == package if exact else parents(store, reviewed)["formal"] == current["formal"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    store = ContentStore()
    base, expected_execution = bundle(store)
    approved = put(store, "approval", {"actor": "fixture-owner", "outcome": "ACCEPT"}, package=base)
    retained = put(store, "verification", {"outcome": "BOUNDED_CHECK", "tool": "fixture-v1"},
                   **expected_execution)
    cases = {
        "unchanged": (base, expected_execution, approved),
        "presentation_only": (*bundle(store, wording="v2"), approved),
        "provenance_only": (*bundle(store, source_fragment="lines 2-3"), approved),
        "new_deadline": (*bundle(store, deadline=6), approved),
        "implementation_only": (*bundle(store, revision="v2"), approved),
        "tests_only": (*bundle(store, test_revision="v2"), approved),
    }
    new_package, inputs = bundle(store, analysis="UNKNOWN")
    unknown_approval = put(store, "approval", {"actor": "fixture-owner", "outcome": "ACCEPT"},
                           package=new_package)
    cases["analysis_unknown_with_exact_approval"] = new_package, inputs, unknown_approval
    new_package, inputs = bundle(store, complete=False)
    incomplete_approval = put(store, "approval", {"actor": "fixture-owner", "outcome": "ACCEPT"},
                              package=new_package)
    cases["incomplete_provenance_with_exact_approval"] = new_package, inputs, incomplete_approval
    for outcome in ("REVISE", "CLARIFY", "REJECT"):
        decision = put(store, "approval", {"actor": "fixture-owner", "outcome": outcome}, package=base)
        cases[outcome.lower()] = base, expected_execution, decision
    untrusted = put(store, "approval", {"actor": "proposal-agent", "outcome": "ACCEPT"}, package=base)
    cases["proposal_agent_accept"] = base, expected_execution, untrusted
    records = {}
    for name, (package, execution, approval) in cases.items():
        exact = approval_matches(store, package, approval, exact=True)
        semantic_only = approval_matches(store, package, approval, exact=False)
        reusable = parents(store, retained) == execution
        accepted = put(store, "accepted", {}, package=package, approval=approval) if exact else None
        records[name] = {"semantic_only_approval": semantic_only, "exact_approval": exact,
                         "exact_package_reuse": package == base and reusable,
                         "execution_receipt_applicable": reusable,
                         "both_bindings_match": exact and reusable, "accepted_record": accepted}
    assert {k for k, r in records.items() if r["exact_approval"]} == {
        "unchanged", "implementation_only", "tests_only"
    }
    assert {k for k, r in records.items() if r["semantic_only_approval"] and not r["exact_approval"]} == {
        "presentation_only", "provenance_only"
    }
    assert {k for k, r in records.items() if not r["execution_receipt_applicable"]} == {
        "new_deadline", "implementation_only", "tests_only"
    }
    assert {k for k, r in records.items() if r["both_bindings_match"]} == {"unchanged"}
    base_refs = parents(store, base)
    revised, revised_execution, _ = cases["new_deadline"]
    revised_refs = parents(store, revised)
    attempts = {
        "dangling_formal": ("explanation", {"formal": "missing"}),
        "wrong_artifact_kind": ("approval", {"package": base_refs["formal"]}),
        "mixed_formal_versions": ("package", base_refs | {"analysis": revised_refs["analysis"]}),
        "mixed_requirement_versions": ("package", base_refs | {"provenance": revised_refs["provenance"]}),
        "stale_review": ("accepted", {"package": revised, "approval": approved}),
        "mixed_component_versions": ("verification", expected_execution | {"tests": revised_execution["tests"]}),
    }
    rejections = {}
    for name, (kind, refs) in attempts.items():
        try:
            put(store, kind, {}, **refs)
        except ValueError as error:
            rejections[name] = str(error)
        else:
            raise AssertionError(f"invalid chain was accepted: {name}")
    files = (__file__, PROTOTYPE / "src/requirement_evolution.py", PROTOTYPE / "src/semantic_graph.py")
    return {"schema": "llmlang-rt02-artifact-lifecycle/1", "python": platform.python_version(),
            "source_sha256": {str(Path(file).resolve().relative_to(ROOT)): digest(Path(file)) for file in files},
            "base_review_package": base, "base_verification": retained, "cases": records,
            "rejected_chain_controls": rejections}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
