"""Fail-closed semantic diff audit against an approved ImpactPlan.

The audit binds exact Snapshot roots, graph-audit digests, and CIP identity. Its
scope is the current explicit declaration subset; it does not prove behavior or
discover dynamic/runtime dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .candidate_graph_audit import audit_candidate_snapshot_graph
from .candidate_validation import validate_candidate_call_site_decisions
from .impact_planning import (
    ActionKind, CallSiteDisposition, ImpactPlan, OutputOperation,
    PlannedEdgeKind, PlannedEdgeOperation, compute_impact_plan_id,
)
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


@dataclass(frozen=True, order=True)
class SemanticEdgeChange:
    logical_key: str
    edge_kind: str
    edge_id: str
    relation: str
    baseline_target_hash: str | None
    candidate_target_hash: str | None
    baseline_condition: str | None
    candidate_condition: str | None

    def record(self) -> dict[str, str | None]:
        return {
            "logical_key": self.logical_key,
            "edge_kind": self.edge_kind,
            "edge_id": self.edge_id,
            "relation": self.relation,
            "baseline_target_hash": self.baseline_target_hash,
            "candidate_target_hash": self.candidate_target_hash,
            "baseline_condition": self.baseline_condition,
            "candidate_condition": self.candidate_condition,
        }


@dataclass(frozen=True, order=True)
class MaterializedOutputBinding:
    output_id: str
    logical_key: str
    candidate_hash: str


@dataclass(frozen=True)
class CandidateSemanticDiffResult:
    valid: bool
    baseline_root: str
    candidate_root: str
    plan_id: str
    changes: tuple[SelectionChange, ...]
    diff_digest: str
    errors: tuple[str, ...]
    baseline_graph_digest: str = ""
    candidate_graph_digest: str = ""
    baseline_edge_set_digest: str = ""
    candidate_edge_set_digest: str = ""
    edge_changes: tuple[SemanticEdgeChange, ...] = ()
    materialized_outputs: tuple[MaterializedOutputBinding, ...] = ()


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


def _declaration_edges(store: ContentStore, value_hash: str):
    value = store.get(value_hash)
    declaration = validate_declaration(value.payload)
    if declaration["kind"] != value.kind:
        raise SemanticObjectError("stored kind differs from declaration kind")
    edges = {}
    for row in declaration["references"]:
        edges[("reference", row["reference_id"])] = (
            row["relation"], row["target_hash"], row["condition"]
        )
    for site in declaration["call_sites"]:
        for target in site["targets"]:
            edges[("call", site["call_site_id"] + "/" + target["target_id"])] = (
                "calls", target["target_hash"], target["condition"]
            )
    return edges


def _plan_identity_matches(plan: ImpactPlan) -> bool:
    return plan.plan_id == compute_impact_plan_id(plan)


def _content_digest(declaration: dict) -> str:
    return sha256(canonical_bytes(declaration["content"])).hexdigest()


def _observed_edge_operation(old_row, new_row):
    if old_row is None:
        return PlannedEdgeOperation.ADD
    if new_row is None:
        return PlannedEdgeOperation.REMOVE
    if old_row[2] != new_row[2] and old_row[1] == new_row[1] and old_row[0] == new_row[0]:
        return PlannedEdgeOperation.CONDITION
    return PlannedEdgeOperation.REWRITE


def _edge_record_matches(record, output_id, edge_kind, edge_id, old_row, new_row) -> bool:
    operation = _observed_edge_operation(old_row, new_row)
    old_relation, old_target, old_condition = old_row if old_row else (None, None, None)
    new_relation, new_target, new_condition = new_row if new_row else (None, None, None)
    return (
        record.output_id == output_id
        and record.edge_kind is edge_kind
        and record.edge_id == edge_id
        and record.operation is operation
        and record.relation == (new_relation or old_relation)
        and record.baseline_target_hash == old_target
        and record.candidate_target_hash == new_target
        and record.baseline_condition == old_condition
        and record.candidate_condition == new_condition
    )


def audit_candidate_semantic_diff(
    store: ContentStore,
    baseline: Snapshot,
    candidate: Snapshot,
    plan: ImpactPlan,
) -> CandidateSemanticDiffResult:
    """Require exact action coverage, graph integrity, and call-site decisions.

    The plan identity is recomputed. Both Snapshot graph audits must pass and are
    bound into the returned diff digest. All changed typed-reference edges are
    rejected until the CIP schema has exact records for them. Call-site target
    changes require both a matching decision and a REWRITE_CALL_SITE action.
    """
    errors: list[str] = []
    before = _snapshot_selections(baseline, "baseline", errors)
    after = _snapshot_selections(candidate, "candidate", errors)

    if plan.baseline_root != baseline.root_hash:
        errors.append("ImpactPlan baseline root does not match supplied baseline Snapshot")
    if plan.candidate_root != candidate.root_hash:
        errors.append("ImpactPlan candidate root does not match supplied candidate Snapshot")
    if not _plan_identity_matches(plan):
        errors.append("ImpactPlan plan_id does not match its canonical contents")

    baseline_graph = audit_candidate_snapshot_graph(store, baseline)
    candidate_graph = audit_candidate_snapshot_graph(store, candidate)
    if not baseline_graph.valid:
        errors.extend("baseline graph audit: " + item for item in baseline_graph.errors)
    if not candidate_graph.valid:
        errors.extend("candidate graph audit: " + item for item in candidate_graph.errors)
    if baseline_graph.snapshot_root != baseline.root_hash:
        errors.append("baseline graph audit is bound to a different Snapshot")
    if candidate_graph.snapshot_root != candidate.root_hash:
        errors.append("candidate graph audit is bound to a different Snapshot")

    changes: list[SelectionChange] = []
    for key in sorted(set(before) | set(after)):
        old_hash, new_hash = before.get(key), after.get(key)
        if old_hash == new_hash:
            continue
        kind = "added" if old_hash is None else "removed" if new_hash is None else "changed"
        changes.append(SelectionChange(key, kind, old_hash, new_hash))

    action_hashes = {action.artifact_hash for action in plan.actions}
    output_by_key = {item.logical_key: item for item in plan.planned_outputs}
    if len(output_by_key) != len(plan.planned_outputs):
        errors.append("ImpactPlan contains duplicate planned output logical keys")
    change_by_key = {item.logical_key: item for item in changes}
    materialized_outputs: list[MaterializedOutputBinding] = []
    for change in changes:
        output = output_by_key.get(change.logical_key)
        if output is None:
            errors.append(f"{change.logical_key}: selection change has no exact CIP planned output record")
            continue
        expected_operation = {
            "added": OutputOperation.ADD,
            "removed": OutputOperation.REMOVE,
            "changed": OutputOperation.REPLACE,
        }[change.change_kind]
        if output.operation is not expected_operation:
            errors.append(f"{change.logical_key}: CIP output operation differs from observed selection change")
        if output.base_hash != change.baseline_hash:
            errors.append(f"{change.logical_key}: CIP output base hash differs from baseline selection")
        if output.operation is not OutputOperation.REMOVE and change.candidate_hash is not None:
            try:
                value = store.get(change.candidate_hash)
                declaration = validate_declaration(value.payload)
                if value.kind != output.expected_kind or declaration["kind"] != output.expected_kind:
                    errors.append(f"{change.logical_key}: materialized output kind differs from CIP")
                if _content_digest(declaration) != output.expected_content_digest:
                    errors.append(f"{change.logical_key}: materialized declaration content differs from CIP digest")
                materialized_outputs.append(MaterializedOutputBinding(
                    output.output_id, output.logical_key, change.candidate_hash
                ))
            except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
                errors.append(f"{change.logical_key}: cannot bind materialized CIP output: {exc}")
        if output.operation is not OutputOperation.ADD and output.base_hash is not None:
            if output.base_hash not in before.values():
                errors.append(f"{change.logical_key}: CIP base hash is not selected in baseline")
        exact_hashes = {value for value in (change.baseline_hash, change.candidate_hash) if value is not None}
        if not exact_hashes & action_hashes:
            errors.append(
                f"{change.logical_key}: semantic {change.change_kind} selection "
                "is not covered by any CIP action on its exact old or new hash"
            )
    for key in sorted(set(output_by_key) - set(change_by_key)):
        errors.append(f"{key}: CIP planned output was not materialized as a selection change")

    decision_rows = tuple(plan.call_site_decisions)
    decision_map = {
        (item.caller_hash, item.call_site_id, item.target_id): item
        for item in decision_rows
    }
    if len(decision_map) != len(decision_rows):
        errors.append("ImpactPlan contains duplicate call-site decisions")

    changed_old_hashes = {
        change.baseline_hash for change in changes if change.baseline_hash is not None
    }
    # Re-scan baseline-selected declarations rather than trusting the reverse index
    # used by the planner. This is a differential check within the same trust domain.
    for caller_hash in sorted(set(before.values())):
        try:
            old_edges = _declaration_edges(store, caller_hash)
        except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"{caller_hash}: cannot enumerate baseline declaration edges: {exc}")
            continue
        for (edge_kind, edge_id), (relation, target_hash, _condition) in sorted(old_edges.items()):
            if edge_kind != "call" or target_hash not in changed_old_hashes:
                continue
            site_id, target_id = edge_id.split("/", 1)
            if (caller_hash, site_id, target_id) not in decision_map:
                errors.append(
                    f"{caller_hash}:{site_id}/{target_id}: changed baseline callee "
                    f"{target_hash} has no CIP decision from the independently scanned Snapshot"
                )

    edge_changes: list[SemanticEdgeChange] = []
    observed_edge_keys = set()
    planned_edge_rows = tuple(plan.planned_edge_changes)
    for change in changes:
        if change.baseline_hash is None or change.candidate_hash is None:
            continue
        try:
            old_edges = _declaration_edges(store, change.baseline_hash)
            new_edges = _declaration_edges(store, change.candidate_hash)
        except (KeyError, SemanticObjectError, TypeError, ValueError) as exc:
            errors.append(f"{change.logical_key}: cannot derive semantic edge diff: {exc}")
            continue
        for edge_key in sorted(set(old_edges) | set(new_edges)):
            old_row, new_row = old_edges.get(edge_key), new_edges.get(edge_key)
            if old_row == new_row:
                continue
            edge_kind, edge_id = edge_key
            old_relation, old_target, old_condition = old_row if old_row else (None, None, None)
            new_relation, new_target, new_condition = new_row if new_row else (None, None, None)
            relation = old_relation or new_relation or ""
            edge_changes.append(SemanticEdgeChange(
                change.logical_key, edge_kind, edge_id, relation,
                old_target, new_target, old_condition, new_condition,
            ))
            output = output_by_key.get(change.logical_key)
            expected_kind = PlannedEdgeKind.TYPED_REFERENCE if edge_kind == "reference" else PlannedEdgeKind.CALL_TARGET
            matches = [
                row for row in planned_edge_rows
                if _edge_record_matches(row, output.output_id if output else "", expected_kind,
                                        edge_id, old_row, new_row)
            ]
            if len(matches) != 1:
                errors.append(
                    f"{change.logical_key}:{edge_id}: observed {edge_kind} delta "
                    "must match exactly one typed CIP edge-change record"
                )
            else:
                observed_edge_keys.add(matches[0])
            if edge_kind == "call" and old_row is not None and new_row is not None and old_target != new_target:
                site_id, target_id = edge_id.split("/", 1)
                decision = decision_map.get((change.baseline_hash, site_id, target_id))
                if decision is None:
                    errors.append(f"{change.logical_key}:{edge_id}: changed call target has no exact CIP decision")
                    continue
                if decision.base_callee_hash != old_target:
                    errors.append(f"{change.logical_key}:{edge_id}: CIP base callee differs from baseline target")
                if decision.selected_callee_hash != new_target:
                    errors.append(f"{change.logical_key}:{edge_id}: CIP selected callee differs from candidate target")
                if decision.resulting_caller_hash != change.candidate_hash:
                    errors.append(f"{change.logical_key}:{edge_id}: CIP resulting caller differs from candidate caller")
                if decision.disposition is CallSiteDisposition.PRESERVE:
                    errors.append(f"{change.logical_key}:{edge_id}: PRESERVE cannot authorize a changed target")
                if not any(
                    action.kind is ActionKind.REWRITE_CALL_SITE
                    and action.artifact_hash == change.baseline_hash
                    for action in plan.actions
                ):
                    errors.append(
                        f"{change.logical_key}:{edge_id}: changed call target lacks a "
                        "REWRITE_CALL_SITE action for the exact baseline caller"
                    )

    for row in planned_edge_rows:
        if row not in observed_edge_keys:
            errors.append(
                f"{row.output_id}:{row.edge_id}: planned CIP edge change was not observed "
                "exactly in the candidate"
            )

    # Candidate materialization also checks unchanged PRESERVE edges and exact
    # selected caller/callee membership.
    try:
        materialized = validate_candidate_call_site_decisions(
            store, baseline, candidate, plan
        )
        errors.extend(materialized.errors)
    except Exception as exc:
        errors.append(f"candidate call-site materialization check failed: {exc}")

    change_records = [item.record() for item in sorted(changes)]
    edge_records = [item.record() for item in sorted(edge_changes)]
    digest_payload = {
        "domain": "llmlang.candidate-semantic-diff.v2",
        "baseline_root": baseline.root_hash,
        "candidate_root": candidate.root_hash,
        "plan_id": plan.plan_id,
        "baseline_graph_digest": baseline_graph.graph_digest,
        "candidate_graph_digest": candidate_graph.graph_digest,
        "baseline_edge_set_digest": baseline_graph.edge_set_digest,
        "candidate_edge_set_digest": candidate_graph.edge_set_digest,
        "schema_version": baseline_graph.dependency_index.schema_version,
        "changes": change_records,
        "edge_changes": edge_records,
        "materialized_outputs": [
            (item.output_id, item.logical_key, item.candidate_hash)
            for item in sorted(materialized_outputs)
        ],
    }
    diff_digest = sha256(canonical_bytes(digest_payload)).hexdigest()
    return CandidateSemanticDiffResult(
        valid=not errors,
        baseline_root=baseline.root_hash,
        candidate_root=candidate.root_hash,
        plan_id=plan.plan_id,
        changes=tuple(sorted(changes)),
        diff_digest=diff_digest,
        errors=tuple(sorted(set(errors))),
        baseline_graph_digest=baseline_graph.graph_digest,
        candidate_graph_digest=candidate_graph.graph_digest,
        baseline_edge_set_digest=baseline_graph.edge_set_digest,
        candidate_edge_set_digest=candidate_graph.edge_set_digest,
        edge_changes=tuple(sorted(edge_changes)),
        materialized_outputs=tuple(sorted(materialized_outputs)),
    )
