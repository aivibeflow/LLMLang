"""Validate per-call-site impact decisions against an exact candidate Snapshot.

This checks materialized object/reference consistency for the explicit declaration
subset. It does not prove behavioral compatibility or whole-program completeness.
"""
from __future__ import annotations

from dataclasses import dataclass

from .impact_planning import CallSiteDisposition, ImpactPlan
from .semantic_dependency_index import SemanticObjectError, validate_declaration
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
    """Check every planned call-site decision against materialized candidate objects.

    The check is fail-closed and accumulates diagnostics. A valid result means:
    - the plan is bound to the supplied baseline and candidate roots;
    - each decision refers to an exact call edge in the baseline Snapshot;
    - selected callee and resulting caller objects exist and are selected in candidate;
    - the candidate caller's stored declaration contains the exact selected target;
    - PRESERVE retains both the original callee and original caller version;
    - stored caller/callee content hashes recompute correctly.

    It does not establish that ADAPT/FORK/MIGRATE are behaviorally compatible,
    nor does it cover runtime reflection, external dispatch, or omitted call sites.
    """
    errors: list[str] = []
    baseline_hashes = _selected_hashes(baseline)
    candidate_hashes = _selected_hashes(candidate)

    if plan.baseline_root != baseline.root_hash:
        errors.append("plan baseline root does not match supplied baseline Snapshot")
    if plan.candidate_root != candidate.root_hash:
        errors.append("plan candidate root does not match supplied candidate Snapshot")

    decisions = tuple(plan.call_site_decisions)
    decision_keys = [
        (item.caller_hash, item.call_site_id, item.target_id) for item in decisions
    ]
    if len(set(decision_keys)) != len(decision_keys):
        errors.append("plan contains duplicate call-site decisions")

    resulting_callers: dict[str, str] = {}
    checked = 0
    for decision in decisions:
        checked += 1
        key = (decision.caller_hash, decision.call_site_id, decision.target_id)
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

        # Bind the decision to the actual source edge, not just to two selected hashes.
        try:
            base_caller_value = store.get(decision.caller_hash)
            _verify_stored_hash(store, decision.caller_hash)
            base_declaration = validate_declaration(base_caller_value.payload)
            base_sites = {
                site["call_site_id"]: site for site in base_declaration["call_sites"]
            }
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
        except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"{prefix}: baseline caller validation failed: {exc}")
            continue

        if (decision.disposition is CallSiteDisposition.MIGRATE
                and decision.selected_callee_hash == decision.base_callee_hash):
            errors.append(f"{prefix}: MIGRATE retained the exact base callee hash")
        if decision.selected_callee_hash not in candidate_hashes:
            errors.append(f"{prefix}: selected callee is not selected by candidate Snapshot")
            continue
        if decision.resulting_caller_hash not in candidate_hashes:
            errors.append(f"{prefix}: resulting caller is not selected by candidate Snapshot")
            continue
        if not decision.decision_evidence_id or not decision.rationale:
            errors.append(f"{prefix}: resolved decision lacks rationale or evidence identity")

        previous = resulting_callers.setdefault(
            decision.caller_hash, decision.resulting_caller_hash
        )
        if previous != decision.resulting_caller_hash:
            errors.append(
                f"{prefix}: decisions for one base caller disagree on resulting caller version"
            )

        if (decision.disposition is CallSiteDisposition.PRESERVE
                and decision.selected_callee_hash != decision.base_callee_hash):
            errors.append(f"{prefix}: PRESERVE changed the exact callee hash")
        if (decision.disposition in {
                CallSiteDisposition.MIGRATE, CallSiteDisposition.ADAPT,
                CallSiteDisposition.FORK,
            } and decision.resulting_caller_hash == decision.caller_hash):
            errors.append(f"{prefix}: changed disposition retained the old caller version")

        try:
            _verify_stored_hash(store, decision.selected_callee_hash)
            _verify_stored_hash(store, decision.resulting_caller_hash)
            caller_value = store.get(decision.resulting_caller_hash)
            declaration = validate_declaration(caller_value.payload)
            if declaration["kind"] != caller_value.kind:
                errors.append(f"{prefix}: caller declaration kind differs from stored kind")
                continue
            sites = {
                site["call_site_id"]: site for site in declaration["call_sites"]
            }
            site = sites.get(decision.call_site_id)
            if site is None:
                errors.append(f"{prefix}: candidate caller omits the planned call site")
                continue
            targets = {
                target["target_id"]: target for target in site["targets"]
            }
            target = targets.get(decision.target_id)
            if target is None:
                errors.append(f"{prefix}: candidate caller omits the planned call target")
                continue
            if target["target_hash"] != decision.selected_callee_hash:
                errors.append(
                    f"{prefix}: candidate call target points to {target['target_hash']}, "
                    f"not selected callee {decision.selected_callee_hash}"
                )
            callee_value = store.get(decision.selected_callee_hash)
            if callee_value.kind not in {"function", "operation"}:
                errors.append(f"{prefix}: selected call target is not a function or operation")
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
