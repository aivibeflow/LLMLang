"""Validate per-call-site impact decisions against an exact candidate Snapshot.

This checks materialized object/reference consistency for the explicit declaration
subset. It does not prove behavioral compatibility or whole-program completeness.
"""
from __future__ import annotations

from dataclasses import dataclass

from .impact_planning import CallSiteDisposition, ImpactPlan
from .semantic_dependency_index import SemanticObjectError, _provided_contract_hash, validate_declaration
from .semantic_graph import ContentStore, Snapshot, digest


@dataclass(frozen=True)
class CandidateValidationResult:
    valid: bool
    baseline_root: str
    candidate_root: str
    plan_id: str
    checked_decisions: int
    errors: tuple[str, ...]


def _selected_hashes(snapshot: Snapshot) -> set[str]:
    return set(snapshot.mapping.values())


def _verify_stored_hash(store: ContentStore, value_hash: str) -> None:
    value = store.get(value_hash)
    canonical = {
        "domain": "llmlang.semantic-value.v1",
        "kind": value.kind,
        "payload": value.payload,
        "dependencies": [dependency.record() for dependency in value.dependencies],
    }
    if value.value_hash != value_hash or digest(canonical) != value_hash:
        raise ValueError(f"stored semantic value does not match its content hash: {value_hash}")


def validate_candidate_call_site_decisions(
    store: ContentStore,
    baseline: Snapshot,
    candidate: Snapshot,
    plan: ImpactPlan,
) -> CandidateValidationResult:
    """Validate call-site decisions and their path-specific materialized outputs.

    This checks exact source/candidate edge and Contract bindings. It does not
    authenticate compatibility evidence or prove behavioral refinement.
    """
    errors: list[str] = []
    baseline_hashes = _selected_hashes(baseline)
    candidate_hashes = _selected_hashes(candidate)
    candidate_selection = dict(candidate.selections)

    if plan.baseline_root != baseline.root_hash:
        errors.append("plan baseline root does not match supplied baseline Snapshot")
    if plan.candidate_root != candidate.root_hash:
        errors.append("plan candidate root does not match supplied candidate Snapshot")

    decisions = tuple(plan.call_site_decisions)
    decision_keys = [
        (item.caller_hash, item.call_site_id, item.target_id, item.consumer_path_id)
        for item in decisions
    ]
    if len(set(decision_keys)) != len(decision_keys):
        errors.append("plan contains duplicate call-site decisions for one consumer path")

    resulting_callers: dict[tuple[str, str], str] = {}
    planned_outputs = {item.output_id: item for item in plan.planned_outputs}
    checked = 0
    for decision in decisions:
        checked += 1
        prefix = f"{decision.caller_hash}:{decision.call_site_id}/{decision.target_id}"

        if decision.disposition is CallSiteDisposition.UNRESOLVED:
            errors.append(f"{prefix}: unresolved decision cannot validate a candidate")
            continue
        if decision.caller_hash not in baseline_hashes:
            errors.append(f"{prefix}: base caller is not selected by baseline Snapshot")
            continue
        if decision.base_callee_hash not in baseline_hashes:
            errors.append(f"{prefix}: base callee is not selected by baseline Snapshot")
            continue

        try:
            base_caller_value = store.get(decision.caller_hash)
            _verify_stored_hash(store, decision.caller_hash)
            base_declaration = validate_declaration(base_caller_value.payload)
            base_sites = {site["call_site_id"]: site for site in base_declaration["call_sites"]}
            base_site = base_sites.get(decision.call_site_id)
            base_targets = ({
                target["target_id"]: target for target in base_site["targets"]
            } if base_site is not None else {})
            base_target = base_targets.get(decision.target_id)
            if base_target is None:
                errors.append(f"{prefix}: exact base call site/target is absent from baseline caller")
                continue
            if base_target["target_hash"] != decision.base_callee_hash:
                errors.append(f"{prefix}: base caller does not reference the decision's exact base callee")
                continue
            if base_target["required_contract_hash"] != decision.required_contract_hash:
                errors.append(f"{prefix}: base call site does not preserve the decision's exact required contract")
                continue
            if _provided_contract_hash(store, decision.base_callee_hash) != decision.base_callee_contract_hash:
                errors.append(f"{prefix}: decision does not bind the base callee's exact provided contract")
                continue
        except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"{prefix}: baseline caller validation failed: {exc}")
            continue

        selected_callee_hash = decision.selected_callee_hash
        if decision.selected_output_id is not None:
            selected_output = planned_outputs.get(decision.selected_output_id)
            if selected_output is None or selected_output.operation.value == "remove":
                errors.append(f"{prefix}: selected output ID is absent or removed in the CIP")
            else:
                if (selected_output.base_hash or selected_output.source_hash) != decision.base_callee_hash:
                    errors.append(f"{prefix}: selected output is not derived from the exact base callee")
                bound_hash = candidate_selection.get(selected_output.logical_key)
                if selected_callee_hash is not None and selected_callee_hash != bound_hash:
                    errors.append(f"{prefix}: selected callee hash differs from its output binding")
                selected_callee_hash = bound_hash

        resulting_caller_hash = decision.resulting_caller_hash
        if decision.resulting_output_id is not None:
            output = planned_outputs.get(decision.resulting_output_id)
            if output is None or output.operation.value == "remove":
                errors.append(f"{prefix}: resulting output ID is absent or removed in the CIP")
            else:
                if (output.base_hash or output.source_hash) != decision.caller_hash:
                    errors.append(f"{prefix}: resulting output is not derived from this exact base caller")
                if output.consumer_path_id != decision.consumer_path_id:
                    errors.append(f"{prefix}: resulting output consumer path differs from the decision")
                bound_hash = candidate_selection.get(output.logical_key)
                if resulting_caller_hash is not None and resulting_caller_hash != bound_hash:
                    errors.append(f"{prefix}: resulting caller hash differs from its output binding")
                resulting_caller_hash = bound_hash

        if (decision.disposition is CallSiteDisposition.MIGRATE
                and selected_callee_hash == decision.base_callee_hash):
            errors.append(f"{prefix}: MIGRATE retained the exact base callee hash")
        if selected_callee_hash not in candidate_hashes:
            errors.append(f"{prefix}: selected callee is not selected by candidate Snapshot")
            continue
        if resulting_caller_hash not in candidate_hashes:
            errors.append(f"{prefix}: resulting caller is not selected by candidate Snapshot")
            continue
        if (not decision.decision_evidence_id or not decision.rationale
                or decision.compatibility_status != "PROVEN"
                or not decision.selected_callee_contract_hash):
            errors.append(f"{prefix}: resolved decision lacks PROVEN compatibility, contract binding, rationale, or evidence identity")

        path_key = (decision.caller_hash, decision.consumer_path_id)
        previous = resulting_callers.setdefault(path_key, resulting_caller_hash)
        if previous != resulting_caller_hash:
            errors.append(f"{prefix}: decisions for one base caller/consumer path disagree on resulting caller version")
        if decision.consumer_path_id and not decision.resulting_output_id:
            errors.append(f"{prefix}: consumer-specific caller version lacks a resulting output ID")

        if decision.disposition is CallSiteDisposition.PRESERVE:
            if selected_callee_hash != decision.base_callee_hash:
                errors.append(f"{prefix}: PRESERVE changed the exact callee hash")
            if decision.selected_callee_contract_hash != decision.base_callee_contract_hash:
                errors.append(f"{prefix}: PRESERVE changed the exact callee-provided contract hash")
        if (decision.disposition in {
                CallSiteDisposition.MIGRATE, CallSiteDisposition.ADAPT,
                CallSiteDisposition.FORK,
            } and resulting_caller_hash == decision.caller_hash):
            errors.append(f"{prefix}: changed disposition retained the old caller version")

        try:
            _verify_stored_hash(store, selected_callee_hash)
            _verify_stored_hash(store, resulting_caller_hash)
            caller_value = store.get(resulting_caller_hash)
            declaration = validate_declaration(caller_value.payload)
            if declaration["kind"] != caller_value.kind:
                errors.append(f"{prefix}: caller declaration kind differs from stored kind")
                continue
            sites = {site["call_site_id"]: site for site in declaration["call_sites"]}
            site = sites.get(decision.call_site_id)
            if site is None:
                errors.append(f"{prefix}: candidate caller omits the planned call site")
                continue
            targets = {target["target_id"]: target for target in site["targets"]}
            target = targets.get(decision.target_id)
            if target is None:
                errors.append(f"{prefix}: candidate caller omits the planned call target")
                continue
            if target["target_hash"] != selected_callee_hash:
                errors.append(f"{prefix}: candidate call target points to {target['target_hash']}, not selected callee {selected_callee_hash}")
            if target["required_contract_hash"] != (
                decision.candidate_required_contract_hash or decision.required_contract_hash
            ):
                errors.append(f"{prefix}: candidate call site differs from the CIP-bound required contract")
            callee_value = store.get(selected_callee_hash)
            if callee_value.kind not in {"function", "operation"}:
                errors.append(f"{prefix}: selected call target is not a function or operation")
            elif _provided_contract_hash(store, selected_callee_hash) != decision.selected_callee_contract_hash:
                errors.append(f"{prefix}: selected callee does not provide the contract bound by the decision")
        except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"{prefix}: candidate object validation failed: {exc}")

    return CandidateValidationResult(
        valid=not errors,
        baseline_root=baseline.root_hash,
        candidate_root=candidate.root_hash,
        plan_id=plan.plan_id,
        checked_decisions=checked,
        errors=tuple(sorted(set(errors))),
    )
