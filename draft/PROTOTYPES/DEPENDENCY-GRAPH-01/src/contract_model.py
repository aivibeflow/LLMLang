"""Finite observable-trace refinement checker for research experiments.

This proves refinement only for explicitly complete finite models. It does not
prove that source code was translated into, or faithfully represented by, a model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .semantic_graph import digest


Trace = tuple[str, ...]


class ContractModelError(ValueError):
    pass


@dataclass(frozen=True)
class FiniteBehaviorModel:
    role: str
    inputs: tuple[str, ...]
    traces_by_input: tuple[tuple[str, tuple[Trace, ...]], ...]
    complete: bool
    model_hash: str

    @classmethod
    def create(cls, role: str, inputs: Iterable[str],
               traces_by_input: dict[str, Iterable[Iterable[str]]],
               complete: bool = True) -> "FiniteBehaviorModel":
        if role not in {"contract", "implementation"}:
            raise ContractModelError("role must be contract or implementation")
        ordered_inputs = tuple(sorted(set(inputs)))
        if not ordered_inputs:
            raise ContractModelError("finite input domain must not be empty")
        if set(traces_by_input) != set(ordered_inputs):
            raise ContractModelError("every declared input needs a trace set")
        rows = []
        for item in ordered_inputs:
            traces = tuple(sorted(set(tuple(trace) for trace in traces_by_input[item])))
            if not traces:
                raise ContractModelError(f"trace set must not be empty for input: {item}")
            if any(not all(isinstance(event, str) for event in trace) for trace in traces):
                raise ContractModelError("trace events must be strings")
            rows.append((item, traces))
        payload = {
            "domain": "llmlang.finite-behavior-model.v1",
            "role": role,
            "inputs": ordered_inputs,
            "traces_by_input": rows,
            "complete": bool(complete),
        }
        return cls(role, ordered_inputs, tuple(rows), bool(complete), digest(payload))

    @property
    def trace_map(self) -> dict[str, tuple[Trace, ...]]:
        return dict(self.traces_by_input)


@dataclass(frozen=True)
class RefinementCounterexample:
    input_value: str
    implementation_trace: Trace | None
    reason: str


@dataclass(frozen=True)
class FiniteRefinementResult:
    status: str
    contract_hash: str
    implementation_model_hash: str
    counterexamples: tuple[RefinementCounterexample, ...]
    scope: str = "complete-finite-observable-trace-model"


def check_finite_refinement(
    contract: FiniteBehaviorModel,
    implementation: FiniteBehaviorModel,
) -> FiniteRefinementResult:
    """Check whether every modeled implementation trace is contract-allowed.

    PROVEN is returned only when both models declare complete finite semantics.
    A concrete forbidden trace against a complete contract disproves refinement,
    even if the implementation model is otherwise incomplete.
    """
    if contract.role != "contract":
        raise ContractModelError("first model must have role=contract")
    if implementation.role != "implementation":
        raise ContractModelError("second model must have role=implementation")

    contract_traces = contract.trace_map
    implementation_traces = implementation.trace_map
    counterexamples = []
    unresolved = not contract.complete

    for input_value in contract.inputs:
        if input_value not in implementation_traces:
            if implementation.complete:
                counterexamples.append(RefinementCounterexample(
                    input_value, None, "implementation has no behavior for required input"))
            else:
                unresolved = True
            continue

        allowed = set(contract_traces[input_value])
        actual = implementation_traces[input_value]
        for trace in actual:
            if trace not in allowed and contract.complete:
                counterexamples.append(RefinementCounterexample(
                    input_value, trace, "implementation trace is not contract-allowed"))

    if counterexamples:
        status = "DISPROVEN"
    elif unresolved or not implementation.complete:
        status = "UNKNOWN"
    else:
        status = "PROVEN"

    return FiniteRefinementResult(
        status, contract.model_hash, implementation.model_hash,
        tuple(counterexamples),
    )
