"""Bounded RT-05/RT-20 experiment for tracking exact call obligations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .contract_model import FiniteBehaviorModel, check_finite_refinement
from .semantic_dependency_index import IndexedEdge, build_snapshot_dependency_index, validate_declaration
from .semantic_graph import ContentStore, Snapshot, make_snapshot


class RefactorError(ValueError):
    """The evidence does not account for the supplied refactoring."""


@dataclass(frozen=True)
class CallRef:
    selection: str
    caller_hash: str
    edge_id: str


@dataclass(frozen=True)
class InlineRef:
    selection: str
    caller_hash: str
    region: str


@dataclass(frozen=True)
class Transfer:
    source: CallRef
    destinations: tuple[CallRef | InlineRef, ...]


@dataclass(frozen=True)
class RefactorPlan:
    baseline_root: str
    candidate_root: str
    transfers: tuple[Transfer, ...]
    new_calls: tuple[CallRef, ...] = ()


@dataclass(frozen=True)
class BoundaryCheck:
    source: CallRef
    destination: CallRef | InlineRef
    evidence: Literal["exact-call-binding", "finite-inline-equivalence"]
    checked_inputs: tuple[int, ...] = ()


@dataclass(frozen=True)
class RefactorAudit:
    boundary_checks: tuple[BoundaryCheck, ...]
    new_calls_requiring_review: tuple[CallRef, ...]


def _call_edges(store: ContentStore, snapshot: Snapshot) -> dict[CallRef, IndexedEdge]:
    if make_snapshot(snapshot.mapping, snapshot.parent_roots) != snapshot:
        raise RefactorError("Snapshot root or selections are inconsistent")
    edges = build_snapshot_dependency_index(store, snapshot)
    return {
        CallRef(key, value_hash, edge.edge_id): edge
        for key, value_hash in snapshot.selections
        for edge in edges.outgoing(value_hash)
        if edge.relation == "calls"
    }


def _finite_outputs(content: dict[str, Any]) -> dict[int, tuple[int, ...]]:
    cases = content.get("finite_outputs")
    if set(content) != {"finite_outputs"} or not isinstance(cases, list) or not cases:
        raise RefactorError("inline check requires an explicit finite Int contract")
    result = {}
    for row in cases:
        if not isinstance(row, dict) or set(row) != {"input", "outputs"}:
            raise RefactorError("invalid finite contract row")
        value, outputs = row["input"], row["outputs"]
        if (type(value) is not int or value in result or not isinstance(outputs, list)
                or not outputs or any(type(output) is not int for output in outputs)):
            raise RefactorError("finite contract requires unique Int inputs and nonempty Int outcomes")
        result[value] = tuple(outputs)
    return result


def _inline_inputs(
    store: ContentStore, source: CallRef, edge: IndexedEdge, destination: InlineRef,
) -> tuple[int, ...]:
    """Compare one whole-body, unconditional unary call with an inline body."""
    baseline = store.get(source.caller_hash).payload
    if (edge.condition is not None or baseline["content"] != {"forward_input_to": edge.edge_id}
            or sum(len(site["targets"]) for site in baseline["call_sites"]) != 1):
        raise RefactorError("inline check requires a whole-body unconditional forwarding call")
    callee = validate_declaration(store.get(edge.target_hash).payload)
    old_offset = callee["content"].get("add_offset")
    if set(callee["content"]) != {"add_offset"} or type(old_offset) is not int or callee["call_sites"]:
        raise RefactorError("inline source callee is outside the unary offset fragment")
    replacement = store.get(destination.caller_hash).payload
    body = replacement["content"].get("inline_input_offset")
    if (set(replacement["content"]) != {"inline_input_offset"} or replacement["call_sites"]
            or not isinstance(body, dict) or set(body) != {"region", "offset"}
            or body["region"] != destination.region or type(body["offset"]) is not int):
        raise RefactorError("candidate has no matching executable inline body")

    required = validate_declaration(store.get(edge.required_contract_hash).payload)
    outputs = _finite_outputs(required["content"])
    inputs = tuple(sorted(outputs))
    contract = FiniteBehaviorModel.create("contract", map(str, inputs), {
        str(value): [(f"return:{answer}",) for answer in outputs[value]] for value in inputs
    })
    for label, offset in (("baseline", old_offset), ("inline", body["offset"])):
        model = FiniteBehaviorModel.create("implementation", map(str, inputs), {
            str(value): [(f"return:{value + offset}",)] for value in inputs
        })
        checked = check_finite_refinement(contract, model)
        if checked.status != "PROVEN":
            example = checked.counterexamples[0].input_value
            raise RefactorError(f"{label} body violates the required contract at input {example}")
    for value in inputs:
        if value + old_offset != value + body["offset"]:
            raise RefactorError(f"inline result differs from baseline at input {value}")
    return inputs


def audit_refactor(
    store: ContentStore, baseline: Snapshot, candidate: Snapshot, plan: RefactorPlan,
) -> RefactorAudit:
    """Account for every changed call edge in this explicit declaration fixture."""
    if (plan.baseline_root, plan.candidate_root) != (baseline.root_hash, candidate.root_hash):
        raise RefactorError("refactor plan belongs to another Snapshot pair")
    old = _call_edges(store, baseline)
    new = _call_edges(store, candidate)
    candidate_selection = candidate.mapping
    removed = old.keys() - new.keys()
    added = new.keys() - old.keys()
    seen_sources: set[CallRef] = set()
    claimed_calls: set[CallRef] = set()
    claimed_regions: set[InlineRef] = set()
    checks = []
    for transfer in plan.transfers:
        source = transfer.source
        if source not in old or source in seen_sources or not transfer.destinations:
            raise RefactorError("transfer needs an exact source and unique nonempty destinations")
        seen_sources.add(source)
        before = old[source]
        for destination in transfer.destinations:
            if isinstance(destination, CallRef):
                if destination not in added or destination in claimed_calls:
                    raise RefactorError("destination is not a unique added call edge")
                claimed_calls.add(destination)
                after = new[destination]
                fields = ("target_hash", "target_kind", "condition", "required_contract_hash")
                if any(getattr(before, field) != getattr(after, field) for field in fields):
                    raise RefactorError("moved call changed target, guard, or required contract")
                checks.append(BoundaryCheck(source, destination, "exact-call-binding"))
            else:
                if (source not in removed or not isinstance(destination, InlineRef)
                        or destination.selection != source.selection
                        or destination in claimed_regions
                        or candidate_selection.get(destination.selection) != destination.caller_hash):
                    raise RefactorError("inline destination is not a unique selected replacement")
                claimed_regions.add(destination)
                inputs = _inline_inputs(store, source, before, destination)
                checks.append(BoundaryCheck(source, destination, "finite-inline-equivalence", inputs))

    if removed - seen_sources:
        raise RefactorError("removed call edge has no transfer or inline check")
    for entry in plan.new_calls:
        if entry not in added or entry in claimed_calls:
            raise RefactorError("declared new call is absent or already accounted for")
        claimed_calls.add(entry)
    if added - claimed_calls:
        raise RefactorError("added call edge has no classification")
    return RefactorAudit(tuple(checks), plan.new_calls)
