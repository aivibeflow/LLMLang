"""SymPy DPLL path-feasibility experiment for the finite Boolean predicate IR."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sympy import And, Not, Or, Symbol, false, true
from sympy.logic.inference import satisfiable


@dataclass(frozen=True)
class SolverPath:
    branch_choices: tuple[tuple[str, bool], ...]
    witness: tuple[tuple[str, bool], ...]


def _to_sympy(predicate: Any):
    if not isinstance(predicate, dict) or len(predicate) != 1:
        raise ValueError("predicate must be a single-operation mapping")
    op, arg = next(iter(predicate.items()))
    if op == "literal" and type(arg) is bool:
        return true if arg else false
    if op == "bool_var" and isinstance(arg, str) and arg:
        return Symbol(arg)
    if op == "bool_not":
        return Not(_to_sympy(arg))
    if op in {"bool_and", "bool_or"} and isinstance(arg, list) and len(arg) == 2:
        left, right = (_to_sympy(item) for item in arg)
        return And(left, right) if op == "bool_and" else Or(left, right)
    raise ValueError(f"unsupported Boolean predicate: {op!r}")


def _predicate_variables(predicate: Any) -> set[str]:
    if not isinstance(predicate, dict) or len(predicate) != 1:
        raise ValueError("predicate must be a single-operation mapping")
    op, arg = next(iter(predicate.items()))
    if op == "literal" and type(arg) is bool:
        return set()
    if op == "bool_var" and isinstance(arg, str) and arg:
        return {arg}
    if op == "bool_not":
        return _predicate_variables(arg)
    if op in {"bool_and", "bool_or"} and isinstance(arg, list) and len(arg) == 2:
        return _predicate_variables(arg[0]) | _predicate_variables(arg[1])
    raise ValueError(f"unsupported Boolean predicate: {op!r}")


def _collect_paths(expression: Any, path: str = "$"):
    if not isinstance(expression, dict) or len(expression) != 1:
        raise ValueError("expression must be a single-operation mapping")
    op, arg = next(iter(expression.items()))
    if op == "if":
        if not isinstance(arg, dict) or set(arg) != {"condition", "then", "else"}:
            raise ValueError("if requires condition, then, and else")
        predicate = _to_sympy(arg["condition"])
        routes = []
        for choice, formula in ((True, predicate), (False, Not(predicate))):
            selected = arg["then"] if choice else arg["else"]
            branch_path = f"{path}.{'then' if choice else 'else'}"
            for child_choices, child_constraints in _collect_paths(selected, branch_path):
                routes.append((
                    ((path, choice),) + child_choices,
                    (formula,) + child_constraints,
                ))
        return routes
    if op == "sequence":
        if not isinstance(arg, list) or not arg:
            raise ValueError("sequence requires at least one expression")
        routes = [((), ())]
        for index, item in enumerate(arg):
            child_routes = _collect_paths(item, f"{path}.sequence[{index}]")
            routes = [
                (prior_choices + child_choices, prior_constraints + child_constraints)
                for prior_choices, prior_constraints in routes
                for child_choices, child_constraints in child_routes
            ]
        return routes
    if op == "with_resource" and isinstance(arg, dict) and "body" in arg:
        return _collect_paths(arg["body"], f"{path}.body")
    if op in {"literal", "perform"}:
        return [((), ())]
    raise ValueError(f"unsupported path expression: {op!r}")


def _collect_variables(expression: Any) -> set[str]:
    op, arg = next(iter(expression.items()))
    if op == "if":
        variables = _predicate_variables(arg["condition"])
        return variables | _collect_variables(arg["then"]) | _collect_variables(arg["else"])
    if op == "sequence":
        variables: set[str] = set()
        for item in arg:
            variables.update(_collect_variables(item))
        return variables
    if op == "with_resource":
        return _collect_variables(arg["body"])
    return set()


def enumerate_solver_paths(expression: Any) -> tuple[SolverPath, ...]:
    """Check each syntactic branch route with SymPy's explicit ``dpll2`` backend."""
    names = tuple(sorted(_collect_variables(expression)))
    routes = _collect_paths(expression)
    feasible = []
    for choices, constraints in routes:
        result = satisfiable(And(*constraints), algorithm="dpll2")
        if result is false or result is False:
            continue
        witness = tuple(
            (name, bool(result.get(Symbol(name), False))) for name in names
        )
        feasible.append(SolverPath(choices, witness))
    return tuple(sorted(feasible, key=lambda path: path.branch_choices))
