"""Fail-closed selection-level semantic diff audit against an approved ImpactPlan.

This prototype compares immutable Snapshot selections and explicit call-site targets.
It does not prove behavioral compatibility or discover dynamic/runtime dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .candidate_validation import validate_candidate_call_site_decisions
from .impact_planning import ImpactPlan
from .semantic_dependency_index import SemanticObjectError, validate_declaration
from .semantic_graph import ContentStore, Snapshot, canonical_bytes, make_snapshot


@dataclass(frozen=True, order=True)
class SelectionChange:
    logical_key: str
    change_kind: str
    baseline_hash: str | None
    candidate_hash: str | None

    def record(self) -> dict[str, str | None]:
        return {
            "logical_key": self.logical_key,
            "change_kind": self.change_kind,
            "baseline_hash": self.baseline_hash,
            "candidate_hash": self.candidate_hash,
        }


@dataclass(frozen=True)
class CandidateSemanticDiffResult:
    valid: bool
    baseline_root: str
    candidate_root: str
    plan_id: str
    changes: tuple[SelectionChange, ...]
    diff_digest: str
    errors: tuple[str, ...]


def _snapshot_selections(snapshot: Snapshot, label: str, errors: list[str]) -> dict[str, str]:
    try:
        rows = tuple(snapshot.selections)
    except TypeError:
        errors.append(f"{label} Snapshot selections are not iterable")
        return {}
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, tuple) or len(row) != 2:
            errors.append(f"{label} Snapshot contains a malformed selection row")
            continue
        key, value_hash = row
        if not isinstance(key, str) or not key or key in result:
            errors.append(f"{label} Snapshot contains an empty, non-string, or duplicate logical key")
            continue
        if not isinstance(value_hash, str) or not value_hash:
            errors.append(f"{label} Snapshot selection {key!r} has an invalid exact hash")
            continue
        result[key] = value_hash
    try:
        parents = tuple(snapshot.parent_roots)
        if any(not isinstance(item, str) or not item for item in parents):
            raise ValueError("invalid parent root")
        if make_snapshot(result, parents).root_hash != snapshot.root_hash:
            errors.append(f"{label} Snapshot root does not match its selections and parents")
    except (TypeError, ValueError):
        errors.append(f"{label} Snapshot parent roots or structure are invalid")
    return result


def _call_targets(store: ContentStore, value_hash: str) -> dict[tuple[str, str], str]:
    value = store.get(value_hash)
    declaration = validate_declaration(value.payload)
    return {
        (site["call_site_id"], target["target_id"]): target["target_hash"]
        for site in declaration["call_sites"]
        for target in site["targets"]
    }


def audit_candidate_semantic_diff(
    store: ContentStore,
    baseline: Snapshot,
    candidate: Snapshot,
    plan: ImpactPlan,
) -> CandidateSemanticDiffResult:
    """Require exact CIP action coverage and call-site decisions for observed changes.

    Every changed logical selection must be named by at least one plan action using
    its old or new exact hash. Every changed explicit call target must have exactly
    one matching decision whose resulting caller and selected callee are materialized.
    Added/removed call-site identities fail closed because the current CIP decision
    model cannot express their disposition.
    """
    errors: list[str] = []
    before = _snapshot_selections(baseline, "baseline", errors)
    after = _snapshot_selections(candidate, "candidate", errors)

    if plan.baseline_root != baseline.root_hash:
        errors.append("ImpactPlan baseline root does not match supplied baseline Snapshot")
    if plan.candidate_root != candidate.root_hash:
        errors.append("ImpactPlan candidate root does not match supplied candidate Snapshot")

    changes: list[SelectionChange] = []
    for key in sorted(set(before) | set(after)):
        old_hash, new_hash = before.get(key), after.get(key)
        if old_hash == new_hash:
            continue
        kind = "added" if old_hash is None else "removed" if new_hash is None else "changed"
        changes.append(SelectionChange(key, kind, old_hash, new_hash))

    action_hashes = {action.artifact_hash for action in plan.actions}
    for change in changes:
        if not ({change.baseline_hash, change.candidate_hash} - {None}) & action_hashes:
            errors.append(
                f"{change.logical_key}: semantic {change.change_kind} selection "
                "is not covered by any CIP action on its exact old or new hash"
            )

    decision_rows = tuple(plan.call_site_decisions)
    decision_map = {
        (item.caller_hash, item.call_site_id, item.target_id): item
        for item in decision_rows
    }
    if len(decision_map) != len(decision_rows):
        errors.append("ImpactPlan contains duplicate call-site decisions")

    # Independently enumerate baseline-selected callers for every changed old
    # selection hash. This prevents a manually assembled ImpactPlan from omitting
    # an incoming call-site decision merely because its reverse-query evidence
    # was incomplete. It remains scoped to explicit declarations in this Snapshot.
    changed_old_hashes = {
        change.baseline_hash for change in changes if change.baseline_hash is not None
    }
    for caller_hash in sorted(set(before.values())):
        try:
            incoming_targets = _call_targets(store, caller_hash)
        except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"{caller_hash}: cannot independently enumerate baseline call sites: {exc}")
            continue
        for (call_site_id, target_id), target_hash in sorted(incoming_targets.items()):
            if target_hash not in changed_old_hashes:
                continue
            decision_key = (caller_hash, call_site_id, target_id)
            if decision_key not in decision_map:
                errors.append(
                    f"{caller_hash}:{call_site_id}/{target_id}: changed baseline callee "
                    f"{target_hash} has no CIP decision from the independently scanned Snapshot"
                )

    for change in changes:
        if change.baseline_hash is None or change.candidate_hash is None:
            # The current call-site decision model only represents migration of an
            # existing caller edge; it cannot authorize whole-caller addition/removal.
            try:
                h = change.baseline_hash or change.candidate_hash
                if h is not None and _call_targets(store, h):
                    errors.append(
                        f"{change.logical_key}: added/removed caller with call sites "
                        "is not representable by the current CIP decision model"
                    )
            except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
                errors.append(f"{change.logical_key}: cannot inspect call sites: {exc}")
            continue
        try:
            old_targets = _call_targets(store, change.baseline_hash)
            new_targets = _call_targets(store, change.candidate_hash)
        except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"{change.logical_key}: cannot derive explicit call-site diff: {exc}")
            continue

        for edge_key in sorted(set(old_targets) | set(new_targets)):
            old_target, new_target = old_targets.get(edge_key), new_targets.get(edge_key)
            if old_target == new_target:
                continue
            call_site_id, target_id = edge_key
            if old_target is None or new_target is None:
                errors.append(
                    f"{change.logical_key}:{call_site_id}/{target_id}: added or removed "
                    "call-site target is not representable by the current CIP decision model"
                )
                continue
            decision_key = (change.baseline_hash, call_site_id, target_id)
            decision = decision_map.get(decision_key)
            if decision is None:
                errors.append(
                    f"{change.logical_key}:{call_site_id}/{target_id}: changed call target "
                    "has no exact CIP decision"
                )
                continue
            if decision.base_callee_hash != old_target:
                errors.append(
                    f"{change.logical_key}:{call_site_id}/{target_id}: CIP base callee "
                    "does not match the observed baseline target"
                )
            if decision.selected_callee_hash != new_target:
                errors.append(
                    f"{change.logical_key}:{call_site_id}/{target_id}: CIP selected callee "
                    "does not match the observed candidate target"
                )
            if decision.resulting_caller_hash != change.candidate_hash:
                errors.append(
                    f"{change.logical_key}:{call_site_id}/{target_id}: CIP resulting caller "
                    "does not match the changed logical selection"
                )

    # Reuse the call-site materialization gate: it independently checks exact
    # baseline/candidate membership, stored hashes, and candidate payload targets.
    materialized = validate_candidate_call_site_decisions(
        store, baseline, candidate, plan
    )
    errors.extend(materialized.errors)

    records = [item.record() for item in sorted(changes)]
    diff_digest = sha256(canonical_bytes({
        "domain": "llmlang.candidate-semantic-diff.v1",
        "baseline_root": baseline.root_hash,
        "candidate_root": candidate.root_hash,
        "plan_id": plan.plan_id,
        "changes": records,
    })).hexdigest()
    return CandidateSemanticDiffResult(
        valid=not errors,
        baseline_root=baseline.root_hash,
        candidate_root=candidate.root_hash,
        plan_id=plan.plan_id,
        changes=tuple(sorted(changes)),
        diff_digest=diff_digest,
        errors=tuple(sorted(set(errors))),
    )
