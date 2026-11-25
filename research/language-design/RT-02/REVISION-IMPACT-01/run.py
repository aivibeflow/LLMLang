"""Compare revision impact with exact package and property-scoped evidence inputs."""

import hashlib
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))
from src.requirement_evolution import (
    analyze_impact,
    create_derived_artifact,
    create_requirement_state,
    make_verification_key,
)
from src.semantic_graph import ContentStore, make_snapshot

REQUIRED_FACTS = {
    "deadline": ("clock", "limit", "action"),
    "exception": ("action", "exception"),
    "notification": ("notification",),
}
BASE_FACTS = {
    "clock": "payment-registration",
    "limit": 5,
    "action": "automatic-confirmation",
    "exception": "reservation-failed",
    "notification": "email-only-after-confirmation",
    "audit-note": "history-v1",
}


def build(store, facts, *, provenance="span-v1", wording="v1", declared=REQUIRED_FACTS):
    fact_refs = {name: create_requirement_state(store, name, {"field": name, "value": value})
                 for name, value in facts.items()}
    provenance_ref = store.put("review_provenance", {"selector": provenance})
    formal, rendered, obligations, keys = {}, {}, {}, {}
    for prop, roles in declared.items():
        formal[prop] = create_derived_artifact(
            store, "formal_clause", {"property": prop}, [(role, fact_refs[role]) for role in roles]
        )
        rendered[prop] = create_derived_artifact(
            store, "explanation_clause", {"property": prop, "wording": wording if prop == "deadline" else "v1"},
            [("formal", formal[prop])]
        )
        obligations[prop] = create_derived_artifact(
            store, "implementation_obligation", {"property": prop}, [("formal", formal[prop])]
        )
        keys[prop] = make_verification_key(store, obligations[prop], "fixture-checker", {"profile": "v1"})

    review_package = create_derived_artifact(
        store, "review_package", {}, [("provenance", provenance_ref), *rendered.items()]
    )
    selected = {"review": review_package, "review_provenance": provenance_ref}
    for prefix, mapping in (("fact", fact_refs), ("formal", formal),
                            ("rendered", rendered), ("obligation", obligations)):
        selected.update({f"{prefix}:{role}": value for role, value in mapping.items()})
    return {
        "facts": fact_refs, "formal": formal, "rendered": rendered, "keys": keys,
        "package": review_package, "snapshot": make_snapshot(selected),
        "declared": declared,
    }


def observations(store, base, candidate):
    affected = set()
    for role, previous in base["facts"].items():
        current = candidate["facts"][role]
        if previous != current:
            impact = analyze_impact(store, previous, current, base["snapshot"], candidate["snapshot"])
            affected.update(impact.active_baseline_dependents)
    coverage_gaps = {
        prop: sorted(set(expected) - set(candidate["declared"][prop]))
        for prop, expected in REQUIRED_FACTS.items() if set(expected) - set(candidate["declared"][prop])
    }
    changed_formal = sorted(prop for prop, ref in base["formal"].items() if ref != candidate["formal"][prop])
    changed_text = sorted(prop for prop, ref in base["rendered"].items() if ref != candidate["rendered"][prop])
    unchanged_key = sorted(prop for prop, key in base["keys"].items() if key == candidate["keys"][prop])
    active_impact = sorted(slot for slot, ref in base["snapshot"].mapping.items() if ref in affected)
    return {
        "changed_facts": sorted(role for role, ref in base["facts"].items() if ref != candidate["facts"][role]),
        "changed_formal": changed_formal,
        "changed_explanations": changed_text,
        "graph_active_impact": active_impact,
        "unchanged_evidence_keys": unchanged_key,
        "eligible_evidence_reuse": [prop for prop in unchanged_key if prop not in coverage_gaps],
        "coverage_gaps": coverage_gaps,
        "review_package_changed": base["package"] != candidate["package"],
        "base_package": base["package"], "candidate_package": candidate["package"],
    }


def main():
    store = ContentStore()
    base = build(store, BASE_FACTS)
    cases = {
        "unchanged": (base, [], [], False),
        "deadline_only": (build(store, BASE_FACTS | {"limit": 6}), ["deadline"], ["deadline"], True),
        "exception_only": (build(store, BASE_FACTS | {"exception": "reservation-refused"}),
                           ["exception"], ["exception"], True),
        "shared_action": (build(store, BASE_FACTS | {"action": "explicit-review-confirmation"}),
                          ["deadline", "exception"], ["deadline", "exception"], True),
        "provenance_only": (build(store, BASE_FACTS, provenance="span-v2"), [], [], True),
        "wording_only": (build(store, BASE_FACTS, wording="v2"), [], ["deadline"], True),
        "unrelated_fact": (build(store, BASE_FACTS | {"audit-note": "history-v2"}), [], [], False),
    }
    results = {}
    for label, (candidate, formal, text, changed_package) in cases.items():
        result = observations(store, base, candidate)
        assert result["changed_formal"] == formal
        assert result["changed_explanations"] == text
        assert result["review_package_changed"] == changed_package
        assert result["eligible_evidence_reuse"] == sorted(set(REQUIRED_FACTS) - set(formal))
        results[label] = result

    missing = REQUIRED_FACTS | {"exception": ("exception",)}
    bad_base = build(store, BASE_FACTS, declared=missing)
    bad_edit = build(store, BASE_FACTS | {"action": "explicit-review-confirmation"}, declared=missing)
    hazard = observations(store, bad_base, bad_edit)
    assert hazard["coverage_gaps"] == {"exception": ["action"]}
    assert "exception" in hazard["unchanged_evidence_keys"]
    assert "exception" not in hazard["eligible_evidence_reuse"]
    assert "formal:exception" not in hazard["graph_active_impact"]
    assert "formal:exception" in results["shared_action"]["graph_active_impact"]

    paths = (Path(__file__), PROTOTYPE / "src/requirement_evolution.py",
             PROTOTYPE / "src/semantic_graph.py")
    return {
        "schema": "llmlang-rt02-revision-impact/1", "python": platform.python_version(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "baseline_required_facts": REQUIRED_FACTS, "revision_controls": results, "missing_edge_control": hazard,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
