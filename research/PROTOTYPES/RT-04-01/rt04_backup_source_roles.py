"""Derive a finite relation between source call roles and live reservations."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import Literal

from rt04_backup_roles import BackupPair, permits


_KNOWN = ("a", "b", "c")
_FLAGS = {"p", "q"}
_INPUTS = set(_KNOWN) | {"external"}
Precision = Literal["role_sets", "call_pairs", "full_route"]
Result = Literal["first_refused", "second_refused", "started"]


class UnsupportedSource(ValueError):
    """The fixture uses a declaration or operation outside this source fragment."""


@dataclass(frozen=True)
class Select:
    flag: str
    when_true: str
    when_false: str


Alias = str | Select


@dataclass(frozen=True)
class Bind:
    name: str
    alias: Alias


@dataclass(frozen=True)
class Start:
    source: Alias
    destination: Alias


@dataclass(frozen=True)
class Finish:
    flag: str | None


Program = tuple[Bind | Start | Finish, ...]


@dataclass(frozen=True)
class Route:
    first: BackupPair
    second: BackupPair
    retains_first: bool


@dataclass(frozen=True)
class Observation:
    result: Result
    live_backups: tuple[BackupPair, ...]


def _reference(node: ast.AST, visible: set[str], kind: str = "resource") -> str:
    if isinstance(node, ast.Name) and node.id in visible:
        return node.id
    raise UnsupportedSource(f"line {node.lineno}: expected a declared {kind} name")


def _alias(node: ast.AST, visible: set[str]) -> Alias:
    if isinstance(node, ast.IfExp):
        return Select(
            _reference(node.test, _FLAGS, "Boolean"),
            _reference(node.body, visible),
            _reference(node.orelse, visible),
        )
    return _reference(node, visible)


def _call_expr(node: ast.stmt) -> ast.Call | None:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        call = node.value
        if isinstance(call.func, ast.Name) and not call.keywords:
            return call
    return None


def parse(source: str) -> Program:
    """Use the Python parser for the fixture grammar without executing the code."""
    try:
        statements = ast.parse(source).body
    except SyntaxError as exc:
        raise UnsupportedSource(str(exc)) from exc

    visible = set(_INPUTS)
    operations = []
    starts = 0
    finish_seen = False
    for node in statements:
        if starts == 2:
            raise UnsupportedSource("the second backup must end the fixture")
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in _INPUTS | _FLAGS | {"backup", "finish_first"}:
                raise UnsupportedSource(f"line {node.lineno}: cannot replace {name}")
            operations.append(Bind(name, _alias(node.value, visible)))
            visible.add(name)
            continue

        call = _call_expr(node)
        if call is not None and call.func.id == "backup" and len(call.args) == 2:
            left, right = call.args
            operations.append(Start(_alias(left, visible), _alias(right, visible)))
            starts += 1
            continue

        flag = None
        if isinstance(node, ast.If) and len(node.body) == 1 and not node.orelse:
            flag = _reference(node.test, _FLAGS, "Boolean")
            call = _call_expr(node.body[0])
        if (call is not None and call.func.id == "finish_first" and not call.args
                and starts == 1 and not finish_seen):
            operations.append(Finish(flag))
            finish_seen = True
            continue
        raise UnsupportedSource(f"line {node.lineno}: unsupported operation")

    if starts != 2:
        raise UnsupportedSource("expected two backup calls")
    return tuple(operations)


def routes(program: Program) -> Iterator[Route]:
    """Resolve the two calls on each declared Boolean and external-alias input."""
    for p, q, external in product((False, True), (False, True), _KNOWN):
        flags = {"p": p, "q": q}
        values = {name: name for name in _KNOWN}
        values["external"] = external
        pairs = []
        retains_first = True

        def value(alias: Alias) -> str:
            if isinstance(alias, Select):
                alias = alias.when_true if flags[alias.flag] else alias.when_false
            return values[alias]

        for operation in program:
            if isinstance(operation, Bind):
                values[operation.name] = value(operation.alias)
            elif isinstance(operation, Start):
                pairs.append(BackupPair(value(operation.source), value(operation.destination)))
            elif operation.flag is None or flags[operation.flag]:
                retains_first = False

        first, second = pairs
        yield Route(first, second, retains_first)


def observe(route: Route) -> Observation:
    """Check each call before granting its roles, keeping earlier live grants."""
    if not permits((), route.first):
        return Observation("first_refused", ())
    live = (route.first,) if route.retains_first else ()
    if not permits(live, route.second):
        return Observation("second_refused", live)
    return Observation("started", (*live, route.second))


def widen(relation: frozenset[Route], precision: Precision) -> frozenset[Route]:
    """Forget relationships while retaining all routes from the fixture."""
    if precision == "full_route":
        return relation
    firsts = {route.first for route in relation}
    seconds = {(route.second, route.retains_first) for route in relation}
    if precision == "call_pairs":
        return frozenset(Route(first, second, retains) for first, (second, retains) in product(firsts, seconds))
    if precision != "role_sets":
        raise ValueError("unsupported alias precision")

    first_sources = {pair.source for pair in firsts}
    first_destinations = {pair.destination for pair in firsts}
    second_sources = {pair.source for pair, _ in seconds}
    second_destinations = {pair.destination for pair, _ in seconds}
    retention = {retains for _, retains in seconds}
    return frozenset(
        Route(BackupPair(a, b), BackupPair(c, d), retains)
        for a, b, c, d, retains in product(first_sources, first_destinations, second_sources, second_destinations, retention)
    )
