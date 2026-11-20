"""Conservative handling of solver outcomes for bounded path feasibility.

This module does not solve predicates. It checks the result-handling contract:
only a replayable witness establishes feasibility, and an infeasibility result
prunes a path only when its evidence basis is explicitly accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Verdict(Enum):
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNKNOWN = "unknown"


_ACCEPTED_UNSAT_BASES = {
    "trusted_backend",
    "checked_certificate",
    "exact_finite_oracle",
}


@dataclass(frozen=True)
class SolverAnswer:
    status: str
    model: Mapping[str, bool] | None = None
    reason: str | None = None
    unsat_basis: str | None = None


def evaluate_predicate(predicate: object, assignment: Mapping[str, bool]) -> bool:
    """Evaluate the Scenario 100 immutable Boolean predicate fragment."""
    if not isinstance(predicate, dict) or len(predicate) != 1:
        raise ValueError("predicate must be a single-operation mapping")
    op, arg = next(iter(predicate.items()))
    if op == "literal" and type(arg) is bool:
        return arg
    if op == "bool_var" and isinstance(arg, str) and arg:
        if arg not in assignment or type(assignment[arg]) is not bool:
            raise ValueError(f"missing or non-Boolean assignment for {arg!r}")
        return assignment[arg]
    if op == "bool_not":
        return not evaluate_predicate(arg, assignment)
    if op in {"bool_and", "bool_or"} and isinstance(arg, list) and len(arg) == 2:
        left = evaluate_predicate(arg[0], assignment)
        right = evaluate_predicate(arg[1], assignment)
        return left and right if op == "bool_and" else left or right
    raise ValueError(f"unsupported Boolean predicate: {op!r}")


def classify_solver_answer(
    answer: SolverAnswer,
    constraints: tuple[object, ...],
    variables: frozenset[str],
) -> Verdict:
    """Classify a route without turning uncertainty into an unreachable claim.

    A model is used as positive evidence only after complete assignment and
    local replay. An UNSAT status is accepted only with an explicit evidence
    basis; the caller remains responsible for authenticating that basis.
    """
    model = answer.model
    if answer.status in {"sat", "unknown"} and model is not None and set(model) == set(variables):
        if all(type(value) is bool for value in model.values()):
            try:
                if all(evaluate_predicate(item, model) for item in constraints):
                    return Verdict.FEASIBLE
            except (TypeError, ValueError):
                pass

    if answer.status == "unsat" and answer.unsat_basis in _ACCEPTED_UNSAT_BASES:
        return Verdict.INFEASIBLE
    return Verdict.UNKNOWN


def retain_as_possible(verdict: Verdict) -> bool:
    """Return whether a route belongs in the conservative may-feasible set."""
    return verdict is not Verdict.INFEASIBLE
