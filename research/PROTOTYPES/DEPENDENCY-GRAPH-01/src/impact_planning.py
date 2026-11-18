"""Scenario 19 prototype: dependency completeness auditing and impact action planning.

This module validates evidence bindings and conservative planning policy. It does not
perform static analysis, trace execution, sandbox programs, or verify proof artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class PlanningError(ValueError):
    pass


class CompletenessStatus(str, Enum):
    GAP_FOUND = "GAP_FOUND"
    SUPPORTED_WITHIN_SCOPE = "SUPPORTED_WITHIN_SCOPE"
    UNKNOWN = "UNKNOWN"
    NOT_CHECKED = "NOT_CHECKED"


class ActionKind(str, Enum):
    RE_DERIVE = "RE_DERIVE"
    REGENERATE_TESTS = "REGENERATE_TESTS"
    RUN_TESTS = "RUN_TESTS"
    REBUILD = "REBUILD"
    REPROVE = "REPROVE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    FULL_REVALIDATION = "FULL_REVALIDATION"
    NO_ACTION = "NO_ACTION"
    REWRITE_CALL_SITE = "REWRITE_CALL_SITE"


@dataclass(frozen=True)
class CompletenessEvidence:
    artifact_hash: str
    declared_dependency_digest: str
    scope: str
    method: str
    tool_id: str
    observed_dependencies: frozenset[str]
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    current: bool = True


@dataclass(frozen=True, order=True)
class IncomingCallSite:
    caller_hash: str
    call_site_id: str
    target_id: str
    target_hash: str
    condition: str | None = None


class CallSiteDisposition(str, Enum):
    MIGRATE = "migrate"
    PRESERVE = "preserve"
    ADAPT = "adapt"
    FORK = "fork"
    UNRESOLVED = "unresolved"


class OutputOperation(str, Enum):
    ADD = "add"
    REPLACE = "replace"
    REMOVE = "remove"


class PlannedEdgeKind(str, Enum):
    TYPED_REFERENCE = "typed_reference"
    CALL_TARGET = "call_target"


class PlannedEdgeOperation(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    REWRITE = "rewrite"
    CONDITION = "condition"


@dataclass(frozen=True, order=True)
class PlannedOutput:
    """One exact logical output slot in the approved candidate graph.

    expected_content_digest is SHA-256 over canonical declaration.content.
    If expected_output_hash is not known before materialization, the successful
    diff receipt binds the actual exact hash to output_id and candidate_root.
    """
    output_id: str
    logical_key: str
    operation: OutputOperation
    base_hash: str | None
    expected_kind: str | None
    expected_content_digest: str | None
    rationale: str
    evidence_id: str


@dataclass(frozen=True, order=True)
class PlannedEdgeChange:
    """An exact payload edge delta attached to a planned logical output."""
    output_id: str
    edge_kind: PlannedEdgeKind
    edge_id: str
    operation: PlannedEdgeOperation
    baseline_relation: str | None
    candidate_relation: str | None
    baseline_target_hash: str | None
    candidate_target_hash: str | None
    baseline_condition: str | None
    candidate_condition: str | None
    rationale: str
    evidence_id: str


@dataclass(frozen=True, order=True)
class CallSiteDecision:
    caller_hash: str
    call_site_id: str
    target_id: str
    base_callee_hash: str
    disposition: CallSiteDisposition
    selected_callee_hash: str | None
    resulting_caller_hash: str | None
    rationale: str
    decision_evidence_id: str | None = None


@dataclass(frozen=True)
class CompletenessAudit:
    status: CompletenessStatus
    missing_dependencies: tuple[str, ...]
    artifact_hash: str
    scope: str
    evidence_method: str | None
    reason: str
    snapshot_root: str | None = None
    target_hash: str | None = None
    evidence_id: str | None = None
    edge_set_digest: str | None = None
    index_schema_version: int | None = None
    extractor_id: str | None = None
    incoming_call_sites: tuple[IncomingCallSite, ...] = ()


@dataclass(frozen=True)
class ImpactedArtifact:
    artifact_hash: str
    kind: str
    reason: str


@dataclass(frozen=True)
class NonInterferenceCertificate:
    artifact_hash: str
    changed_input_hash: str
    boundary: str
    checker_id: str
    status: str
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class PlannedAction:
    kind: ActionKind
    artifact_hash: str
    reason: str
    prerequisite_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImpactPlan:
    plan_id: str
    baseline_root: str
    candidate_root: str
    policy_id: str
    actions: tuple[PlannedAction, ...]
    audit_statuses: tuple[tuple[str, str], ...]
    audit_bindings: tuple[tuple[str, str, str, str, int, str, str, str], ...] = ()
    call_site_decisions: tuple[CallSiteDecision, ...] = ()
    planned_outputs: tuple[PlannedOutput, ...] = ()
    planned_edge_changes: tuple[PlannedEdgeChange, ...] = ()


def impact_plan_payload(plan: ImpactPlan) -> dict:
    return {
        "baseline": plan.baseline_root,
        "candidate": plan.candidate_root,
        "policy": plan.policy_id,
        "actions": [
            (a.kind.value, a.artifact_hash, a.reason, a.prerequisite_hashes)
            for a in plan.actions
        ],
        "audits": sorted(plan.audit_statuses),
        "audit_bindings": sorted(plan.audit_bindings),
        "call_site_decisions": [
            (d.caller_hash, d.call_site_id, d.target_id, d.base_callee_hash,
             d.disposition.value, d.selected_callee_hash, d.resulting_caller_hash,
             d.rationale, d.decision_evidence_id)
            for d in sorted(plan.call_site_decisions)
        ],
        "planned_outputs": [
            (o.output_id, o.logical_key, o.operation.value, o.base_hash,
             o.expected_kind, o.expected_content_digest, o.rationale, o.evidence_id)
            for o in sorted(plan.planned_outputs)
        ],
        "planned_edge_changes": [
            (e.output_id, e.edge_kind.value, e.edge_id, e.operation.value,
             e.baseline_relation, e.candidate_relation, e.baseline_target_hash,
             e.candidate_target_hash, e.baseline_condition, e.candidate_condition,
             e.rationale, e.evidence_id)
            for e in sorted(plan.planned_edge_changes)
        ],
    }


def compute_impact_plan_id(plan: ImpactPlan) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(
        impact_plan_payload(plan), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def dependency_digest(dependencies: Iterable[str]) -> str:
    """Deterministic digest for a set of dependency identities."""
    import hashlib
    import json

    payload = json.dumps(sorted(set(dependencies)), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def audit_dependency_completeness(
    artifact_hash: str,
    declared_dependencies: Iterable[str],
    scope: str,
    evidence: CompletenessEvidence | None,
) -> CompletenessAudit:
    declared = frozenset(declared_dependencies)
    if evidence is None:
        return CompletenessAudit(
            CompletenessStatus.NOT_CHECKED, (), artifact_hash, scope, None,
            "no independent completeness evidence was supplied",
        )
    if not evidence.current:
        return CompletenessAudit(
            CompletenessStatus.UNKNOWN, (), artifact_hash, scope, evidence.method,
            "completeness evidence is stale",
        )
    expected_digest = dependency_digest(declared)
    if (evidence.artifact_hash != artifact_hash
            or evidence.declared_dependency_digest != expected_digest
            or evidence.scope != scope
            or not evidence.method
            or not evidence.tool_id):
        return CompletenessAudit(
            CompletenessStatus.UNKNOWN, (), artifact_hash, scope, evidence.method,
            "evidence does not match exact artifact, dependency set, scope, or tool identity",
        )
    missing = tuple(sorted(evidence.observed_dependencies - declared))
    if missing:
        return CompletenessAudit(
            CompletenessStatus.GAP_FOUND, missing, artifact_hash, scope, evidence.method,
            "independently observed dependencies are absent from the declared dependency set",
        )
    return CompletenessAudit(
        CompletenessStatus.SUPPORTED_WITHIN_SCOPE, (), artifact_hash, scope,
        evidence.method,
        "no discrepancy observed within the evidence's stated scope; this is not a global completeness proof",
    )


def audit_snapshot_incoming(result: object) -> CompletenessAudit:
    """Adapt a SnapshotIncomingResult without discarding its exact query bindings.

    This adapter validates the shape and status mapping only. It does not
    authenticate external evidence or prove the observation model sound.
    """
    required = (
        "snapshot_root", "target_hash", "scope", "edge_set_digest",
        "index_schema_version", "extractor_id", "completeness_status",
        "reason", "evidence_id", "discrepancies",
    )
    if any(not hasattr(result, name) for name in required):
        raise PlanningError("snapshot incoming result is missing required bindings")
    try:
        status = CompletenessStatus(result.completeness_status.value)
    except (AttributeError, ValueError) as exc:
        raise PlanningError("snapshot incoming result has an invalid completeness status") from exc
    if not all(isinstance(getattr(result, name), str) and getattr(result, name)
               for name in ("snapshot_root", "target_hash", "scope", "edge_set_digest", "extractor_id")):
        raise PlanningError("snapshot incoming result identities, extractor, and edge digest are required")
    if not isinstance(result.index_schema_version, int) or result.index_schema_version < 1:
        raise PlanningError("snapshot incoming result index schema version must be positive")
    discrepancies = tuple(result.discrepancies)
    if status is CompletenessStatus.GAP_FOUND and not discrepancies:
        raise PlanningError("GAP_FOUND snapshot result must identify discrepancies")
    incoming_call_sites = []
    for edge in result.edges:
        if edge.relation != "calls":
            continue
        if not isinstance(edge.edge_id, str) or edge.edge_id.count("/") != 1:
            raise PlanningError("call edge must have an exact call_site_id/target_id identity")
        call_site_id, target_id = edge.edge_id.split("/", 1)
        if not call_site_id or not target_id:
            raise PlanningError("call edge has an empty call-site or target identity")
        incoming_call_sites.append(IncomingCallSite(
            caller_hash=edge.source_hash, call_site_id=call_site_id,
            target_id=target_id, target_hash=edge.target_hash, condition=edge.condition,
        ))
    return CompletenessAudit(
        status=status,
        missing_dependencies=discrepancies,
        artifact_hash=result.target_hash,
        scope=result.scope,
        evidence_method="snapshot-reverse-lookup",
        reason=result.reason,
        snapshot_root=result.snapshot_root,
        target_hash=result.target_hash,
        evidence_id=result.evidence_id,
        edge_set_digest=result.edge_set_digest,
        index_schema_version=result.index_schema_version,
        extractor_id=result.extractor_id,
        incoming_call_sites=tuple(incoming_call_sites),
    )


def _actions_for(artifact: ImpactedArtifact) -> tuple[PlannedAction, ...]:
    h, reason = artifact.artifact_hash, artifact.reason
    if artifact.kind in {"formal_clause", "caller_contract", "requirement_derived_model"}:
        return (PlannedAction(ActionKind.RE_DERIVE, h, reason),)
    if artifact.kind == "test_suite":
        return (
            PlannedAction(ActionKind.REGENERATE_TESTS, h, reason),
            PlannedAction(ActionKind.RUN_TESTS, h, "execute regenerated/selected tests"),
        )
    if artifact.kind in {"implementation", "build_artifact", "generated_artifact"}:
        return (
            PlannedAction(ActionKind.REBUILD, h, reason),
            PlannedAction(ActionKind.RUN_TESTS, h, "execute tests against rebuilt candidate"),
        )
    if artifact.kind in {"verification_record", "proof"}:
        return (PlannedAction(ActionKind.REPROVE, h, reason),)
    if artifact.kind in {"requirement", "business_rule", "intent"}:
        return (PlannedAction(ActionKind.HUMAN_REVIEW, h,
                              "confirm meaning, applicability, authority, and unresolved assumptions"),)
    return (
        PlannedAction(ActionKind.HUMAN_REVIEW, h, f"unknown artifact kind: {artifact.kind}"),
        PlannedAction(ActionKind.FULL_REVALIDATION, h,
                      "artifact policy is not defined; use conservative validation"),
    )


def no_action_is_justified(
    artifact_hash: str,
    changed_input_hash: str,
    boundary: str,
    certificate: NonInterferenceCertificate | None,
) -> bool:
    """Check certificate binding only; this function does not verify its proof."""
    return bool(
        certificate
        and certificate.artifact_hash == artifact_hash
        and certificate.changed_input_hash == changed_input_hash
        and certificate.boundary == boundary
        and certificate.checker_id
        and certificate.status == "PROVEN"
    )


def plan_impact(
    baseline_root: str,
    candidate_root: str,
    policy_id: str,
    impacted_artifacts: Iterable[ImpactedArtifact],
    audits: Iterable[CompletenessAudit],
    require_snapshot_evidence: bool = True,
    call_site_decisions: Iterable[CallSiteDecision] = (),
    planned_outputs: Iterable[PlannedOutput] = (),
    planned_edge_changes: Iterable[PlannedEdgeChange] = (),
) -> ImpactPlan:
    if not baseline_root or not candidate_root or not policy_id:
        raise PlanningError("baseline, candidate, and policy identities are required")
    artifacts = tuple(impacted_artifacts)
    audit_rows = tuple(audits)
    audit_map = {a.artifact_hash: a for a in audit_rows}
    if len(audit_map) != len(audit_rows):
        raise PlanningError("duplicate completeness audit for an artifact")

    decisions = tuple(call_site_decisions)
    output_rows = tuple(sorted(planned_outputs))
    edge_change_rows = tuple(sorted(planned_edge_changes))
    output_map = {row.output_id: row for row in output_rows}
    if len(output_map) != len(output_rows):
        raise PlanningError("duplicate planned output_id")
    if len({row.logical_key for row in output_rows}) != len(output_rows):
        raise PlanningError("multiple planned outputs target the same logical selection key")
    for row in output_rows:
        if not all((row.output_id, row.logical_key, row.rationale, row.evidence_id)):
            raise PlanningError("planned output identity, rationale, and evidence are required")
        if not isinstance(row.operation, OutputOperation):
            raise PlanningError("planned output has an invalid operation")
        if row.operation is OutputOperation.ADD:
            if row.base_hash is not None:
                raise PlanningError("ADD output cannot name a baseline hash")
        elif not row.base_hash:
            raise PlanningError("REPLACE/REMOVE output requires an exact baseline hash")
        if row.operation is OutputOperation.REMOVE:
            if row.expected_kind is not None or row.expected_content_digest is not None:
                raise PlanningError("REMOVE output cannot declare candidate content")
        elif not all((row.expected_kind, row.expected_content_digest)):
            raise PlanningError("ADD/REPLACE output requires exact kind and canonical content digest")
    if len(set(edge_change_rows)) != len(edge_change_rows):
        raise PlanningError("duplicate planned edge change")
    for row in edge_change_rows:
        if row.output_id not in output_map:
            raise PlanningError("planned edge change references an unknown output_id")
        if not all((row.edge_id, row.rationale, row.evidence_id)) or not (row.baseline_relation or row.candidate_relation):
            raise PlanningError("planned edge change identity, relation, rationale, and evidence are required")
        if not isinstance(row.edge_kind, PlannedEdgeKind) or not isinstance(row.operation, PlannedEdgeOperation):
            raise PlanningError("planned edge change has an invalid kind or operation")
        if row.operation is PlannedEdgeOperation.ADD and (row.baseline_target_hash is not None or not row.candidate_target_hash):
            raise PlanningError("edge ADD requires only a candidate target hash")
        if row.operation is PlannedEdgeOperation.REMOVE and (not row.baseline_target_hash or row.candidate_target_hash is not None):
            raise PlanningError("edge REMOVE requires only a baseline target hash")
        if row.operation in {PlannedEdgeOperation.REWRITE, PlannedEdgeOperation.CONDITION} and not (row.baseline_target_hash and row.candidate_target_hash):
            raise PlanningError("edge REWRITE/CONDITION requires exact old and new target hashes")
    decision_map = {(d.caller_hash, d.call_site_id, d.target_id): d for d in decisions}
    if len(decision_map) != len(decisions):
        raise PlanningError("duplicate call-site decision")
    call_edges: dict[tuple[str, str, str], IncomingCallSite] = {}
    for audit in audit_rows:
        for edge in audit.incoming_call_sites:
            key = (edge.caller_hash, edge.call_site_id, edge.target_id)
            if key in call_edges:
                raise PlanningError("duplicate incoming call-site edge across completeness audits")
            call_edges[key] = edge
    extra_decisions = set(decision_map) - set(call_edges)
    if extra_decisions:
        raise PlanningError("call-site decision does not match an exact discovered Snapshot edge")

    actions: set[PlannedAction] = set()
    statuses: list[tuple[str, str]] = []
    unsafe: list[str] = []
    audit_bindings: list[tuple[str, str, str, str, int, str, str, str]] = []
    for artifact in artifacts:
        audit = audit_map.get(artifact.artifact_hash)
        status = audit.status if audit else CompletenessStatus.NOT_CHECKED
        if audit is not None:
            if audit.snapshot_root is None:
                if require_snapshot_evidence:
                    status = CompletenessStatus.NOT_CHECKED
            elif (audit.snapshot_root != baseline_root
                  or audit.target_hash != artifact.artifact_hash
                  or not audit.scope or not audit.edge_set_digest
                  or not audit.index_schema_version or audit.index_schema_version < 1
                  or not audit.extractor_id
                  or (status is not CompletenessStatus.NOT_CHECKED and not audit.evidence_id)):
                status = CompletenessStatus.UNKNOWN
            else:
                audit_bindings.append((
                    artifact.artifact_hash, audit.snapshot_root, audit.target_hash,
                    audit.scope, audit.index_schema_version, audit.extractor_id,
                    audit.evidence_id or "", audit.edge_set_digest,
                ))
        statuses.append((artifact.artifact_hash, status.value))
        actions.update(_actions_for(artifact))
        if status is not CompletenessStatus.SUPPORTED_WITHIN_SCOPE:
            unsafe.append(f"{artifact.artifact_hash}:{status.value}")

    normalized_decisions: list[CallSiteDecision] = []
    unresolved_edges: list[str] = []
    for key, edge in sorted(call_edges.items()):
        decision = decision_map.get(key)
        if decision is None:
            unresolved_edges.append(f"{edge.caller_hash}:{edge.call_site_id}/{edge.target_id}")
            continue
        if not isinstance(decision.disposition, CallSiteDisposition):
            raise PlanningError("call-site decision has an invalid disposition")
        if not all((decision.caller_hash, decision.call_site_id, decision.target_id,
                    decision.base_callee_hash, decision.rationale)):
            raise PlanningError("call-site decision identities and rationale are required")
        if decision.base_callee_hash != edge.target_hash:
            raise PlanningError("call-site decision is bound to a different base callee hash")
        if not decision.rationale:
            raise PlanningError("call-site decision requires a rationale")
        if decision.disposition is CallSiteDisposition.UNRESOLVED:
            if any((decision.selected_callee_hash, decision.resulting_caller_hash,
                    decision.decision_evidence_id)):
                raise PlanningError("unresolved call-site decision cannot select output hashes or claim evidence")
            unresolved_edges.append(f"{edge.caller_hash}:{edge.call_site_id}/{edge.target_id}")
        else:
            if not all((decision.selected_callee_hash, decision.resulting_caller_hash,
                        decision.decision_evidence_id)):
                raise PlanningError("resolved call-site decisions require selected callee, resulting caller, and evidence")
            if decision.disposition is CallSiteDisposition.PRESERVE and decision.selected_callee_hash != edge.target_hash:
                raise PlanningError("PRESERVE must retain the exact existing callee hash")
            if decision.disposition is CallSiteDisposition.MIGRATE and decision.selected_callee_hash == edge.target_hash:
                raise PlanningError("MIGRATE must select a different exact callee hash")
            if decision.disposition in {CallSiteDisposition.MIGRATE, CallSiteDisposition.ADAPT,
                                        CallSiteDisposition.FORK} and decision.resulting_caller_hash == edge.caller_hash:
                raise PlanningError("caller content identity must change for migrate/adapt/fork")
            if decision.disposition is not CallSiteDisposition.PRESERVE:
                actions.add(PlannedAction(
                    ActionKind.REWRITE_CALL_SITE, edge.caller_hash,
                    f"{decision.disposition.value} {edge.call_site_id}/{edge.target_id} "
                    f"to {decision.selected_callee_hash}; resulting caller {decision.resulting_caller_hash}",
                ))
        normalized_decisions.append(decision)
    if unresolved_edges:
        unsafe.extend("call-site:" + item for item in unresolved_edges)
        actions.add(PlannedAction(
            ActionKind.HUMAN_REVIEW, candidate_root,
            "every discovered call-site edge needs an evidence-backed disposition: "
            + ", ".join(sorted(unresolved_edges)),
        ))
        actions.add(PlannedAction(
            ActionKind.FULL_REVALIDATION, candidate_root,
            "call-site compatibility decisions are incomplete or unresolved",
        ))

    if unsafe:
        reason = "dependency completeness or call-site decisions are not supported for: " + ", ".join(sorted(unsafe))
        actions.add(PlannedAction(ActionKind.HUMAN_REVIEW, candidate_root, reason))
        actions.add(PlannedAction(
            ActionKind.FULL_REVALIDATION, candidate_root,
            "optimized impact plan is unsafe while dependency completeness is unresolved",
        ))

    ordered = tuple(sorted(actions, key=lambda a: (
        a.kind.value, a.artifact_hash, a.reason, a.prerequisite_hashes
    )))
    provisional = ImpactPlan(
        "", baseline_root, candidate_root, policy_id, ordered,
        tuple(sorted(statuses)), tuple(sorted(audit_bindings)),
        tuple(sorted(normalized_decisions)), output_rows, edge_change_rows,
    )
    plan_id = compute_impact_plan_id(provisional)
    return ImpactPlan(
        plan_id, baseline_root, candidate_root, policy_id,
        ordered, tuple(sorted(statuses)), tuple(sorted(audit_bindings)),
        tuple(sorted(normalized_decisions)), output_rows, edge_change_rows,
    )
