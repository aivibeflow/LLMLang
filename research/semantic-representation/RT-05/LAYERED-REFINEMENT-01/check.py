"""Compare exact SPG dependency edges with version-bound refinement evidence."""

from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, Dependency, RelationStore, make_snapshot


INPUTS = tuple(range(16))
PROFILES = ("hash-all", "checked-relations", "trace-only")
CHECKER = "approval-threshold-v1/all-16-inputs"


@dataclass(frozen=True)
class Case:
    requirement: int
    contract: int
    implementation: int
    note: str = "policy-source-1"
    derived: bool = False


def should_review(threshold, amount):
    return amount >= threshold


def refinement(requirement, contract):
    return next((x for x in INPUTS if should_review(requirement, x)
                 and not should_review(contract, x)), None)


def conformance(contract, implementation):
    return next((x for x in INPUTS if should_review(contract, x) != should_review(implementation, x)), None)


def make_graph(store, relations, case, policy):
    if not all(type(value) is int and value in INPUTS for value in (case.requirement, case.contract, case.implementation)):
        raise ValueError("Threshold is outside the complete fixture domain")
    if case.derived and case.contract != case.requirement:
        raise ValueError("An exactly derived contract must preserve its threshold input")
    requirement = store.put("requirement", {"manual_required_at": case.requirement})
    exact_requirement = [Dependency("derived_from", requirement)] if case.derived or policy == "hash-all" else []
    contract = store.put("contract", {"manual_iff_at": case.contract}, exact_requirement)
    body = store.put("implementation", {"returns_manual_at": case.implementation},
                     [Dependency("provides", contract)])
    selection = {"specification": requirement, "design": contract, "implementation": body}
    snapshot = make_snapshot(selection)
    relations.add(snapshot.root_hash, contract, "refines", requirement)
    relations.add(snapshot.root_hash, requirement, "provenance", case.note)
    return snapshot


def keys(snapshot, checker=CHECKER):
    selection = snapshot.mapping
    spec, design, implementation = (selection[name] for name in ("specification", "design", "implementation"))
    return {"refines": ("refines", design, spec, checker),
            "provides": ("provides", implementation, design, checker)}


def check(store, key):
    relation, subject, target, checker = key
    if checker != CHECKER:
        raise ValueError("Incomplete or unknown checker profile")
    source_value, target_value = store.get(subject), store.get(target)
    if relation == "refines" and (source_value.kind, target_value.kind) == ("contract", "requirement"):
        return refinement(target_value.payload["manual_required_at"], source_value.payload["manual_iff_at"])
    if relation == "provides" and (source_value.kind, target_value.kind) == ("implementation", "contract"):
        return conformance(target_value.payload["manual_iff_at"], source_value.payload["returns_manual_at"])
    raise ValueError("Bad endpoint types")


def admit(policy, snapshot, relations, verified, checker=CHECKER):
    exact = keys(snapshot, checker)
    trace_relations = relations.for_scope(snapshot.root_hash)
    if (snapshot.root_hash, exact["refines"][1], "refines", exact["refines"][2]) not in trace_relations:
        return "missing-refines-link"
    if policy == "trace-only":
        return "admitted"
    for label, key in exact.items():
        if key not in verified:
            return f"unchecked-{label}"
        if verified[key] is not None:
            return f"refuted-{label}"
    return "admitted"


def verify_analytic_oracle():
    for first, second in product(INPUTS, repeat=2):
        if (refinement(first, second) is None) != (second <= first):
            raise AssertionError("Refinement enumeration differs from threshold implication")
        if (conformance(first, second) is None) != (first == second):
            raise AssertionError("Conformance enumeration differs from exact threshold equality")


def expected_judgment(case):
    if case.contract > case.requirement:
        return "refuted-refines"
    if case.implementation != case.contract:
        return "refuted-provides"
    return "admitted"


def compare():
    baseline = Case(8, 8, 8)
    variants = {
        "provenance_only": Case(8, 8, 8, "policy-source-2"),
        "weaken_requirement": Case(10, 8, 8),
        "tighten_requirement": Case(6, 8, 8),
        "adapt_design_only": Case(6, 6, 8),
        "adapt_design_and_implementation": Case(6, 6, 6),
        "drift_implementation": Case(8, 8, 9),
    }
    samples = {}
    for policy in PROFILES:
        store = ContentStore()
        relations = RelationStore()
        old = make_graph(store, relations, baseline, policy)
        initial = {key: check(store, key) for key in keys(old).values()}
        for name, case in variants.items():
            candidate = make_graph(store, relations, case, policy)
            target_keys = keys(candidate)
            changed = sorted(key for key, value in candidate.mapping.items() if old.mapping[key] != value)
            missing = sorted(label for label, key in target_keys.items() if key not in initial)
            before = admit(policy, candidate, relations, initial)
            candidate_evidence = {**initial, **{target_keys[label]: check(store, target_keys[label])
                                               for label in missing}}
            result = admit(policy, candidate, relations, candidate_evidence)
            expected = expected_judgment(case)
            if policy != "trace-only" and result != expected:
                raise AssertionError(f"Policy disagrees with the analytic oracle: {policy}, {name}")
            if policy == "trace-only" and result != "admitted":
                raise AssertionError("Trace-only control ought to admit a linked candidate")
            samples.setdefault(name, {})[policy] = {
                "changed_values": changed, "invalidated_checked_judgments": missing,
                "before_new_evidence": before, "after_new_evidence": result,
                "independent_oracle": expected,
                "witnesses": {label: candidate_evidence[key] for label, key in target_keys.items()},
            }

    store = ContentStore()
    relations = RelationStore()
    pure = make_graph(store, relations, baseline, "checked-relations")
    evidence = {key: check(store, key) for key in keys(pure).values()}
    no_link = admit("checked-relations", pure, RelationStore(), evidence)
    wrong_profile = admit("checked-relations", pure, relations, evidence, "wrong-checker/domain-0-7")
    if (no_link, wrong_profile) != ("missing-refines-link", "unchecked-refines"):
        raise AssertionError("Release accepted incomplete binding")
    derived_old = make_graph(store, relations, Case(8, 8, 8, derived=True), "checked-relations")
    derived_new = make_graph(store, relations, Case(10, 10, 10, derived=True), "checked-relations")
    derived_changes = sorted(key for key, value in derived_new.mapping.items() if derived_old.mapping[key] != value)
    derived_edge, = store.get(derived_new.mapping["design"]).dependencies
    if derived_edge.target_hash != derived_new.mapping["specification"] or len(derived_changes) != 3:
        raise AssertionError("Derived contract lost its exact requirement input")
    return {"scenarios": samples, "derived_contract_changes": derived_changes,
            "missing_link": no_link, "unrecognized_checker_scope": wrong_profile}


if __name__ == "__main__":
    verify_analytic_oracle()
    print(json.dumps({"analytically_crosschecked_threshold_pairs_per_relation": len(INPUTS) ** 2,
                      **compare()}, sort_keys=True, indent=2))
