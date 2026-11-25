"""Exercise path-specific call decisions against the existing materialization gate."""
import argparse
from dataclasses import replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(GRAPH))
from src.candidate_validation import validate_candidate_call_site_decisions
from src.impact_planning import (
    CallSiteDecision, CallSiteDisposition, ImpactPlan, OutputOperation, PlannedOutput,
    compute_call_site_decision_id, compute_impact_plan_id,
)
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, canonical_bytes, make_snapshot

PATHS = ("legacy", "summary", "detail")


def record(kind, name, content, **extra):
    return {"format": FORMAT, "schema_version": SCHEMA_VERSION, "kind": kind,
            "declaration_id": name, "content": content, **extra}


def fixtures():
    store = ContentStore()
    contract = publish_declaration(store, record("contract", "offset", {"input": "i32"}))
    provides = [{"reference_id": "provided", "relation": "provides_contract",
                 "target_hash": contract, "target_kind": "contract"}]

    def function(name, content, targets=()):
        return publish_declaration(store, record(
            "function", name, content, references=provides, call_sites=[
                {"call_site_id": f"site:{number}", "targets": [
                    {"target_id": "direct", "target_hash": target, "condition": None,
                     "required_contract_hash": contract},
                ]}
                for number, target in enumerate(targets)
            ],
        ))

    def output(slot, key, source, value, consumer=""):
        declaration = store.get(value).payload
        subject = {"declaration_id": declaration["declaration_id"], "content": declaration["content"]}
        return PlannedOutput(
            slot, key, OutputOperation.ADD, None, "function", sha256(canonical_bytes(subject)).hexdigest(),
            "selected call subtree", "output-evidence:" + slot, source, consumer,
        )

    leaves = [function("leaf", {"offset": ordinal}) for ordinal in range(3)]
    forks = [function("shared", {"body": "two ordered calls"}, (leaf, leaves[0])) for leaf in leaves]
    baseline = make_snapshot({"base-leaf": leaves[0], "base-shared": forks[0]})
    selections = {"base-leaf": leaves[0]}
    decs, outs = [], []
    for order, (path, leaf, fork) in enumerate(zip(PATHS, leaves, forks)):
        caller_slot = f"caller:{path}"
        outputs = [output(caller_slot, caller_slot, forks[0], fork, path)]
        selections[caller_slot] = fork
        if order > 0:
            leaf_slot = f"callee:{path}"
            selections[leaf_slot] = leaf
            outputs.append(output(leaf_slot, leaf_slot, leaves[0], leaf))
        else:
            leaf_slot = None
        path_decisions = []
        for site, changed in enumerate((order > 0, False)):
            path_decisions.append(CallSiteDecision(
                caller_hash=forks[0], call_site_id=f"site:{site}", target_id="direct",
                base_callee_hash=leaves[0],
                disposition=CallSiteDisposition.MIGRATE if changed else CallSiteDisposition.PRESERVE,
                selected_callee_hash=None if changed else leaves[0], resulting_caller_hash=None,
                rationale="exact fixture binding", decision_evidence_id=f"edge-evidence:{path}:{site}",
                required_contract_hash=contract, compatibility_status="PROVEN",
                consumer_path_id=path, resulting_output_id=caller_slot,
                selected_output_id=leaf_slot if changed else None,
            ))
        decs.append(tuple(path_decisions))
        outs.append(tuple(outputs))
    candidate = make_snapshot(selections)
    return store, baseline, candidate, tuple(decs), tuple(outs)


def flat(groups):
    return tuple(value for group in groups for value in group)


def assess():
    store, baseline, candidate, groups, slots = fixtures()
    all_decisions, all_outputs = flat(groups), flat(slots)
    prototype_plan = ImpactPlan(
        plan_id="", baseline_root=baseline.root_hash, candidate_root=candidate.root_hash,
        policy_id="fork-identity-v1", actions=(), audit_statuses=(),
        call_site_decisions=all_decisions, planned_outputs=all_outputs,
    )
    digest = compute_impact_plan_id(prototype_plan)
    assert len({compute_call_site_decision_id(decision) for decision in all_decisions}) == 6
    erased = {(row.caller_hash, row.call_site_id, row.target_id) for row in all_decisions}
    with_path = {(row.caller_hash, row.call_site_id, row.target_id, row.consumer_path_id)
                 for row in all_decisions}
    assert (len(erased), len(with_path)) == (2, 6)
    ordering_checks = 0
    for decision_order, output_order, reverse_sites in product(
        permutations(range(3)), permutations(range(3)), product((False, True), repeat=3),
    ):
        decisions = flat(groups[i][::-1] if reverse_sites[i] else groups[i] for i in decision_order)
        outputs = flat(slots[i] for i in output_order)
        plan = replace(prototype_plan, plan_id=digest, call_site_decisions=decisions, planned_outputs=outputs)
        result = validate_candidate_call_site_decisions(store, baseline, candidate, plan)
        assert compute_impact_plan_id(plan) == digest
        assert result.valid and result.checked_decisions == 6, result.errors
        ordering_checks += 1
    assert ordering_checks == 288

    summary = groups[1][0]
    summary_caller = slots[1][0]
    selected = dict(candidate.selections)
    explicit = replace(summary, selected_callee_hash=selected["callee:summary"],
                       resulting_caller_hash=selected["caller:summary"])
    mixed = replace(prototype_plan, call_site_decisions=tuple(
        explicit if row == summary else row for row in all_decisions
    ))
    mixed_id = compute_impact_plan_id(mixed)
    assert mixed_id != digest
    reversed_mixed = replace(mixed, call_site_decisions=mixed.call_site_decisions[::-1])
    assert compute_impact_plan_id(reversed_mixed) == mixed_id
    assert validate_candidate_call_site_decisions(store, baseline, candidate, mixed).valid
    controls = (
        ("wrong-path", replace(summary, consumer_path_id="detail"), None, None,
         "output consumer path differs"),
        ("swapped-caller-slot", replace(summary, resulting_output_id="caller:detail"), None, None,
         "output consumer path differs"),
        ("wrong-leaf-slot", replace(summary, selected_output_id="callee:detail"), None, None,
         "candidate call target points"),
        ("direct-hash-conflicts-with-caller-slot", replace(summary, resulting_caller_hash=summary.caller_hash),
         None, None, "caller hash differs from its output binding"),
        ("missing-path-specific-output", replace(summary, resulting_output_id=None,
                                                 resulting_caller_hash=dict(candidate.selections)["caller:summary"]),
         None, None, "consumer-specific caller version lacks"),
        ("wrong-resulting-origin", None, replace(summary_caller, source_hash=summary.base_callee_hash),
         None, "output is not derived from this exact base caller"),
        ("duplicate-decision", None, None, "duplicate", "duplicate call-site decisions"),
        ("stale-candidate-snapshot", None, None, "stale", "plan candidate root does not match"),
    )
    negatives = {}
    for name, decision, output, special, expected in controls:
        decisions = tuple(decision if row == summary and decision is not None else row
                          for row in all_decisions)
        outputs = tuple(output if row == summary_caller and output is not None else row
                        for row in all_outputs)
        if special == "duplicate":
            decisions += (summary,)
        supplied = baseline if special == "stale" else candidate
        attempt = replace(prototype_plan, call_site_decisions=decisions, planned_outputs=outputs)
        comparison = validate_candidate_call_site_decisions(store, baseline, supplied, attempt)
        assert not comparison.valid and any(expected in error for error in comparison.errors), comparison
        # A stale supplied snapshot is outside the unchanged plan's digest calculation.
        assert (compute_impact_plan_id(attempt) == digest) == (special == "stale")
        negatives[name] = expected

    incomplete = replace(prototype_plan, call_site_decisions=all_decisions[:-1])
    remaining_rows = validate_candidate_call_site_decisions(store, baseline, candidate, incomplete)
    assert remaining_rows.valid and remaining_rows.checked_decisions == 5
    assert compute_impact_plan_id(incomplete) != digest
    return {
        "ordered_replays": ordering_checks,
        "one_base_caller_paths": len(PATHS),
        "base_key_cardinality": len(erased),
        "path_key_cardinality": len(with_path),
        "candidate_root": candidate.root_hash,
        "plan_id": digest,
        "mixed_explicit_and_slot_only_plan_id": mixed_id,
        "exact_decision_ids": [{"consumer": row.consumer_path_id, "site": row.call_site_id,
                                "id": compute_call_site_decision_id(row)} for row in all_decisions],
        "rejected_controls": negatives,
        "omitted_decision_control": "supplied-row materializer validates five rows; independent completeness is required",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(assess(), indent=2) + "\n")


if __name__ == "__main__":
    main()
