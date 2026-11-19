"""Scenario 19 prototype: dependency completeness auditing and impact action planning.

This module validates evidence bindings and conservative planning policy. It does not
perform static analysis, trace execution, sandbox programs, or verify proof artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable


class PlanningError(ValueError):
    pass


CIP_SCHEMA_VERSION = 5


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
    required_contract_hash: str | None = None


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
    REWRITE …8747 tokens truncated…          subject_kind="call_site",
                    ))
            normalized_decisions.append(decision)

    if unresolved_edges:
        unsafe.extend("call-site:" + item for item in unresolved_edges)
        actions.add(PlannedAction(
            ActionKind.HUMAN_REVIEW, candidate_root,
            "every discovered call-site edge needs an evidence-backed disposition: "
            + ", ".join(sorted(unresolved_edges)),
            subject_kind="candidate",
        ))
        actions.add(PlannedAction(
            ActionKind.FULL_REVALIDATION, candidate_root,
            "call-site compatibility decisions are incomplete or unresolved",
            subject_kind="candidate",
        ))

    if unsafe:
        reason = "dependency completeness or call-site decisions are not supported for: " + ", ".join(sorted(unsafe))
        actions.add(PlannedAction(ActionKind.HUMAN_REVIEW, candidate_root, reason, subject_kind="candidate"))
        actions.add(PlannedAction(
            ActionKind.FULL_REVALIDATION, candidate_root,
            "optimized impact plan is unsafe while dependency completeness is unresolved",
            subject_kind="candidate",
        ))

    validate_action_kind_policy(actions)
    ordered = tuple(sorted(assign_planned_action_ids(actions), key=lambda a: (
        a.kind.value, a.artifact_hash, a.reason, a.prerequisite_hashes,
        a.action_id, a.prerequisite_action_ids,
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
