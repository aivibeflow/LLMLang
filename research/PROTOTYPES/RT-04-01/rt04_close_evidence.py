"""Analyze completeness and freshness in a small source fragment for close."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import Literal


class UnsupportedSource(ValueError):
    """The source uses syntax or ownership outside this fragment."""


@dataclass(frozen=True)
class Step:
    operation: Literal["prepare", "finalize", "readonly", "foreign", "inspect"]
    line: int
    statement: str = ""


@dataclass(frozen=True)
class Branch:
    condition: str
    when_true: tuple[Step | Branch, ...]
    when_false: tuple[Step | Branch, ...]


@dataclass(frozen=True)
class Program:
    body: tuple[Step | Branch, ...]
    conditions: tuple[str, ...]


Inputs = tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class CloseFact:
    inputs: Inputs
    known_live: frozenset[str]
    complete: bool

    @property
    def verdict(self) -> Literal["PROVEN_EMPTY", "KNOWN_LIVE", "UNKNOWN"]:
        if self.known_live:
            return "KNOWN_LIVE"
        return "PROVEN_EMPTY" if self.complete else "UNKNOWN"


@dataclass(frozen=True)
class Snapshot:
    version: int
    empty: bool


@dataclass(frozen=True)
class Execution:
    inputs: Inputs
    foreign_creations: tuple[bool, ...]
    live_count: int
    version: int
    snapshot: Snapshot | None

    @property
    def would_be_busy(self) -> bool:
        return self.live_count != 0

    @property
    def unchecked_snapshot_allows_close(self) -> bool:
        return self.snapshot is not None and self.snapshot.empty

    @property
    def current_snapshot_allows_close(self) -> bool:
        return self.snapshot is not None and self.snapshot.empty and self.snapshot.version == self.version


_OPERATIONS = {"connect", "prepare", "finalize", "readonly", "foreign", "inspect", "close"}


def _call(node: ast.AST) -> tuple[str, tuple[str, ...]] | None:
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords
            and all(isinstance(arg, ast.Name) for arg in node.args)):
        return node.func.id, tuple(arg.id for arg in node.args)
    return None


def _assignment(node: ast.AST) -> tuple[str, ast.AST] | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    return None


def parse(source: str) -> Program:
    """Parse a fixture with one fresh connection and one terminal close.

    Python supplies the parser only. Calls denote primitives in this fixture,
    and conditions are immutable Boolean inputs. This code never runs Python
    source as a program.
    """
    try:
        statements = ast.parse(source).body
    except SyntaxError as exc:
        raise UnsupportedSource(str(exc)) from exc
    head = _assignment(statements[0]) if len(statements) >= 2 else None
    if head is None or _call(head[1]) != ("connect", ()) or head[0] in _OPERATIONS:
        raise UnsupportedSource("the fragment must start by binding connect()")
    connection = head[0]
    end = statements[-1]
    if not isinstance(end, ast.Expr) or _call(end.value) != ("close", (connection,)):
        raise UnsupportedSource("the fragment must end by closing that connection")

    conditions = set()
    names = {connection}
    foreign_calls = 0

    def lower(nodes: list[ast.stmt]) -> tuple[Step | Branch, ...]:
        nonlocal foreign_calls
        result = []
        for node in nodes:
            assigned = _assignment(node)
            if assigned is not None:
                name, value = assigned
                if name == connection or name in _OPERATIONS or _call(value) != ("prepare", (connection,)):
                    raise UnsupportedSource(f"line {node.lineno}: expected a statement binding from prepare")
                names.add(name)
                result.append(Step("prepare", node.lineno, name))
                continue
            if isinstance(node, ast.If) and isinstance(node.test, ast.Name):
                condition = node.test.id
                conditions.add(condition)
                result.append(Branch(condition, lower(node.body), lower(node.orelse)))
                continue
            if isinstance(node, ast.Pass):
                continue
            call = _call(node.value) if isinstance(node, ast.Expr) else None
            if call is not None and len(call[1]) == 1:
                operation, (arg,) = call
                if operation in ("readonly", "foreign", "inspect") and arg == connection:
                    foreign_calls += operation == "foreign"
                    result.append(Step(operation, node.lineno))
                    continue
                if operation == "finalize" and arg != connection and arg not in _OPERATIONS:
                    names.add(arg)
                    result.append(Step("finalize", node.lineno, arg))
                    continue
            raise UnsupportedSource(f"line {node.lineno}: unsupported statement")
        return tuple(result)

    body = lower(statements[1:-1])
    if conditions & (names | _OPERATIONS):
        raise UnsupportedSource("conditions must be separate inputs")
    if len(conditions) > 4 or foreign_calls > 4:
        raise UnsupportedSource("the fragment supports at most four Boolean inputs and four foreign calls")
    return Program(body, tuple(sorted(conditions)))


def _paths(program: Program) -> Iterator[tuple[Inputs, tuple[Step, ...]]]:
    def steps(nodes: tuple[Step | Branch, ...], inputs: dict[str, bool]) -> Iterator[Step]:
        for node in nodes:
            if isinstance(node, Step):
                yield node
            else:
                yield from steps(node.when_true if inputs[node.condition] else node.when_false, inputs)

    for values in product((False, True), repeat=len(program.conditions)):
        inputs = tuple(zip(program.conditions, values))
        yield inputs, tuple(steps(program.body, dict(inputs)))


def analyze(program: Program) -> tuple[CloseFact, ...]:
    """Infer liveness and coverage from source and the fixture call summaries."""
    results = []
    for inputs, path in _paths(program):
        live = set()
        complete = True
        for step in path:
            name = step.statement
            if step.operation == "prepare":
                if name in live:
                    raise UnsupportedSource(f"line {step.line}: cannot overwrite live statement {name}")
                live.add(name)
            elif step.operation == "finalize":
                if name not in live:
                    raise UnsupportedSource(f"line {step.line}: no live statement {name}")
                live.remove(name)
            elif step.operation == "foreign":
                # The call preserves existing resources but can retain a new
                # statement outside the wrapper's tracked set.
                complete = False
        results.append(CloseFact(inputs, frozenset(live), complete))
    return tuple(results)


def executions(program: Program) -> Iterator[Execution]:
    """Enumerate concrete resource states for the same finite source paths.

    Each foreign call in this model may leave zero or one extra statement.
    Versioning conservatively invalidates evidence at that boundary, including
    on executions where the call leaves no extra statement.
    """
    for inputs, path in _paths(program):
        count = sum(step.operation == "foreign" for step in path)
        for choices in product((False, True), repeat=count):
            creates = iter(choices)
            statements = []
            hidden = version = 0
            snapshot = None
            for step in path:
                if step.operation == "inspect":
                    snapshot = Snapshot(version, not statements and hidden == 0)
                elif step.operation == "prepare":
                    if step.statement in statements:
                        raise UnsupportedSource(f"line {step.line}: cannot overwrite live statement {step.statement}")
                    statements.append(step.statement)
                    version += 1
                elif step.operation == "finalize":
                    if step.statement not in statements:
                        raise UnsupportedSource(f"line {step.line}: no live statement {step.statement}")
                    statements.remove(step.statement)
                    version += 1
                elif step.operation == "foreign":
                    hidden += next(creates)
                    version += 1
            yield Execution(inputs, choices, len(statements) + hidden, version, snapshot)
