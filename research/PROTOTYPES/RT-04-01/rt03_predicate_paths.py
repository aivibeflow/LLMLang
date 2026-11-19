"""Exhaustive finite-Boolean path feasibility for a small predicate IR.

This is a truth-table analyzer for immutable Boolean inputs, not an SMT solver
and not a source parser or complete RT-03 control-flow model.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any


@dataclass(frozen=True)
class FeasiblePath:
    branch_choices: tuple[tuple[str, bool], ...]
    witness: tuple[tuple[str, bool], ...]


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


def _evaluate_predicate(predicate: Any, assignment: dict[str, bool]) -> bool:
    op, arg = next(iter(predicate.items()))
    if op == "literal":
        if type(arg) is not bool:
            raise ValueError("predicate literal must be boolean")
        return arg
    if op == "bool_var":
        if not isinstance(arg, str) or not arg or arg not in assignment:
            raise ValueError(f"unbound Boolean input: {arg!r}")
        return assignment[arg]
    if op == "bool_not":
        return not _evaluate_predicate(arg, assignment)
    if op == "bool_and":
        if not isinstance(arg, list) or len(arg) != 2:
            raise ValueError("bool_and requires two predicates")
        return _evaluate_predicate(arg[0], assignment) and _evaluate_predicate(arg[1], assignment)
    if op == "bool_or":
        if not isinstance(arg, list) or len(arg) != 2:
            raise ValueError("bool_or requires two predicates")
        return _evaluate_predicate(arg[0], assignment) or _evaluate_predicate(arg[1], assignment)
    raise ValueError(f"unsupported Boolean predicate: {op!r}")


def _collect_variables(expression: Any, variables: set[str]) -> None:
    if not isinstance(expression, dict) or len(expression) != 1:
        raise ValueError("expression must be a single-operation mapping")
    op, arg = next(iter(expression.items()))
    if op == "if":
        if not isinstance(arg, dict) or set(arg) != {"condition", "then", "else"}:
            raise ValueError("if requires condition, then, and else")
        variables.update(_predicate_variables(arg["condition"]))
        _collect_variables(arg["then"], variables)
        _collect_variables(arg["else"], variables)
    elif op == "sequence":
        if not isinstance(arg, list) or not arg:
            raise ValueError("sequence requires at least one expression")
        for item in arg:
            _collect_variables(item, variables)
    elif op == "with_resource":
        if not isinstance(arg, dict) or "body" not in arg:
            raise ValueError("with_resource requires a body")
        _collect_variables(arg["body"], variables)
    elif op in {"literal", "perform"}:
        return
    else:
        raise ValueError(f"unsupported path expression: {op!r}")


def _selected_branches(
    expression: Any,
    assignment: dict[str, bool],
    path: str = "$",
) -> tuple[tuple[str, bool], ...]:
    op, arg = next(iter(expression.items()))
    if op == "if":
        selected = _evaluate_predicate(arg["condition"], assignment)
        child_path = f"{path}.{'then' if selected else 'else'}"
        return ((path, selected),) + _selected_branches(
            arg["then"] if selected else arg["else"], assignment, child_path,
        )
    if op == "sequence":
        choices = ()
        for index, item in enumerate(arg):
            choices += _selected_branches(item, assignment, f"{path}.sequence[{index}]")
        return choices
    if op == "with_resource":
        return _selected_branches(arg["body"], assignment, f"{path}.body")
    return ()


def enumerate_feasible_paths(expression: Any) -> tuple[FeasiblePath, ...]:
    """Enumerate feasible branch-choice vectors and one input witness each.

    Feasibility is decided by exhaustive assignment enumeration over the finite
    set of immutable Boolean inputs mentioned in branch predicates.
    """
    variables: set[str] = set()
    _collect_variables(expression, variables)
    names = tuple(sorted(variables))
    witnesses: dict[tuple[tuple[str, bool], ...], tuple[tuple[str, bool], ...]] = {}
    for values in product((False, True), repeat=len(names)):
        assignment = dict(zip(names, values))
        choices = _selected_branches(expression, assignment)
        witnesses.setdefault(choices, tuple(assignment.items()))
    return tuple(
        FeasiblePath(branch_choices=choices, witness=witnesses[choices])
        for choices in sorted(witnesses)
    )
