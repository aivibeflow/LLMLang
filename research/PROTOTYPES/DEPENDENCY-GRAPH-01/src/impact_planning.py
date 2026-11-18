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
) -> ImpactPlan:
    if not baseline_root or not candidate_root or not policy_id:
        raise PlanningError("baseline, candidate, and policy identities are required")
    artifacts = tuple(impacted_artifacts)
    audit_rows = tuple(audits)
    audit_map = {a.artifact_hash: a for a in audit_rows}
    if len(audit_map) != len(audit_rows):
        raise PlanningError("duplicate completeness audit for an artifact")

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

    if unsafe:
        reason = "dependency completeness is not supported for: " + ", ".join(sorted(unsafe))
        actions.add(PlannedAction(ActionKind.HUMAN_REVIEW, candidate_root, reason))
        actions.add(PlannedAction(
            ActionKind.FULL_REVALIDATION, candidate_root,
            "optimized impact plan is unsafe while dependency completeness is unresolved",
        ))

    ordered = tuple(sorted(actions, key=lambda a: (
        a.kind.value, a.artifact_hash, a.reason, a.prerequisite_hashes
    )))
    import hashlib
    import json
    plan_payload = {
        "baseline": baseline_root,
        "candidate": candidate_root,
        "policy": policy_id,
        "actions": [
            (a.kind.value, a.artifact_hash, a.reason, a.prerequisite_hashes)
            for a in ordered
        ],
        "audits": sorted(statuses),
        "audit_bindings": sorted(audit_bindings),
    }
    plan_id = hashlib.sha256(json.dumps(
        plan_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return ImpactPlan(plan_id, baseline_root, candidate_root, policy_id,
                      ordered, tuple(sorted(statuses)), tuple(sorted(audit_bindings)))
