"""Small Python-AST adapter for source-derived alias/call path experiments.

This intentionally accepts only a tiny, explicitly checked fixture grammar. It
is not a Python interpreter or an LLMLang parser.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from itertools import product

from rt03_alias_sensitive_call_paths import FIELDS, Route, routes_for_alias_targets


class UnsupportedSource(ValueError):
    """The fixture uses a construct outside the audited source subset."""


@dataclass(frozen=True)
class Extraction:
    call_targets: frozenset[str]
    summary: str


def _call_name(node: ast.AST) -> str | None:
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def _summarize_toggle(function: ast.FunctionDef) -> str:
    """Recognize only `ref.value = not ref.value` as a toggle summary."""
    if len(function.args.args) != 1 or len(function.body) != 1:
        raise UnsupportedSource("mutator must have one parameter and one statement")
    param = function.args.args[0].arg
    stmt = function.body[0]
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        raise UnsupportedSource("mutator must contain one simple assignment")
    target, value = stmt.targets[0], stmt.value
    if not (
        isinstance(target, ast.Attribute)
        and target.attr == "value"
        and isinstance(target.value, ast.Name)
        and target.value.id == param
        and isinstance(value, ast.UnaryOp)
        and isinstance(value.op, ast.Not)
        and isinstance(value.operand, ast.Attribute)
        and value.operand.attr == "value"
        and isinstance(value.operand.value, ast.Name)
        and value.operand.value.id == param
    ):
        raise UnsupportedSource("only a direct reference-field toggle is summarized")
    return "toggle"


def _union_environments(left: dict[str, frozenset[str]], right: dict[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    return {name: left.get(name, frozenset()) | right.get(name, frozenset()) for name in left.keys() | right.keys()}


def _analyze_alias_statements(
    statements: list[ast.stmt], env: dict[str, frozenset[str]], summary: str,
    calls: list[frozenset[str]],
) -> dict[str, frozenset[str]]:
    for stmt in statements:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            value = stmt.value
            call = _call_name(value)
            if call == "ref" and isinstance(value, ast.Call) and len(value.args) == 1 and isinstance(value.args[0], ast.Name):
                field = value.args[0].id
                if field not in FIELDS:
                    raise UnsupportedSource(f"reference to unmodeled field {field!r}")
                env[name] = frozenset({field})
            elif call == "unknown_ref" and isinstance(value, ast.Call) and not value.args:
                env[name] = FIELDS
            elif isinstance(value, ast.Name) and value.id in env:
                env[name] = env[value.id]
            else:
                env.pop(name, None)
        elif isinstance(stmt, ast.If):
            left = _analyze_alias_statements(stmt.body, env.copy(), summary, calls)
            right = _analyze_alias_statements(stmt.orelse, env.copy(), summary, calls)
            env = _union_environments(left, right)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if _call_name(call) == "flip" and len(call.args) == 1 and isinstance(call.args[0], ast.Name):
                target = env.get(call.args[0].id)
                if target is None:
                    # A reference with no complete points-to information may
                    # reach any field in the explicitly modeled region.
                    target = FIELDS
                calls.append(target)
            elif _call_name(call) in {"mark", "input_bool"}:
                continue
            else:
                raise UnsupportedSource("unsupported call in caller body")
        else:
            raise UnsupportedSource(f"unsupported caller statement: {type(stmt).__name__}")
    return env


def extract_call_aliases(source: str) -> Extraction:
    """Extract the union of possible reference targets at each `flip` call."""
    module = ast.parse(source)
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef)]
    callers = [node for node in module.body if not isinstance(node, ast.FunctionDef)]
    flip_defs = [node for node in functions if node.name == "flip"]
    if len(flip_defs) != 1 or len(functions) != 1:
        raise UnsupportedSource("fixture must define exactly one function named flip")
    summary = _summarize_toggle(flip_defs[0])
    calls: list[frozenset[str]] = []
    _analyze_alias_statements(callers, {}, summary, calls)
    if len(calls) != 1:
        raise UnsupportedSource("fixture must contain exactly one flip call")
    return Extraction(calls[0], summary)


def execute_concrete_fixture(source: str) -> frozenset[Route]:
    """Enumerate all Bool inputs and execute the recognized fixture program."""
    module = ast.parse(source)
    flip = next((node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "flip"), None)
    if flip is None:
        raise UnsupportedSource("missing flip function")
    _summarize_toggle(flip)
    callers = [node for node in module.body if not isinstance(node, ast.FunctionDef)]
    routes: set[Route] = set()

    def run_statement(stmt: ast.stmt, env: dict[str, object], initial_flag: bool) -> None:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name, value = stmt.targets[0].id, stmt.value
            call = _call_name(value)
            if call == "input_bool" and isinstance(value, ast.Call) and len(value.args) == 1 and isinstance(value.args[0], ast.Constant):
                field = value.args[0].value
                if field not in {"flag", "other", "choose"}:
                    raise UnsupportedSource("unknown input name")
                env[name] = env[f"input:{field}"]
            elif call == "ref" and isinstance(value, ast.Call) and len(value.args) == 1 and isinstance(value.args[0], ast.Name):
                env[name] = ["ref", value.args[0].id]
            elif call == "unknown_ref" and isinstance(value, ast.Call) and not value.args:
                env[name] = ["ref", env["input:unknown_target"]]
            elif isinstance(value, ast.Name):
                env[name] = env[value.id]
            else:
                raise UnsupportedSource("unsupported concrete assignment")
        elif isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Name):
            branch = stmt.body if bool(env[stmt.test.id]) else stmt.orelse
            for inner in branch:
                run_statement(inner, env, initial_flag)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if _call_name(call) == "flip" and len(call.args) == 1 and isinstance(call.args[0], ast.Name):
                ref = env[call.args[0].id]
                if not (isinstance(ref, list) and ref[0] == "ref"):
                    raise UnsupportedSource("flip argument is not a reference")
                env[ref[1]] = not bool(env[ref[1]])
            elif _call_name(call) in {"mark", "input_bool"}:
                return
            else:
                raise UnsupportedSource("unsupported concrete call")
        else:
            raise UnsupportedSource(f"unsupported concrete statement: {type(stmt).__name__}")

    for flag, other, choose, unknown_target in product((False, True), repeat=4):
        env: dict[str, object] = {
            "input:flag": flag,
            "input:other": other,
            "input:choose": choose,
            "input:unknown_target": "flag" if unknown_target else "other",
        }
        for stmt in callers:
            run_statement(stmt, env, flag)
        routes.add((flag, bool(env["flag"])))
    return frozenset(routes)


def execute_path_sensitive_summary(source: str) -> frozenset[Route]:
    """Enumerate fixture paths while applying the AST-derived call summary.

    This is an exact finite-state path explorer for the fixture grammar, not a
    scalable symbolic or general path-sensitive points-to algorithm.
    """
    module = ast.parse(source)
    # Reuse the checked source-subset gate: require exactly one recognized call
    # and reject constructs the joined alias adapter cannot classify.
    extract_call_aliases(source)
    flip = next((node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "flip"), None)
    if flip is None:
        raise UnsupportedSource("missing flip function")
    summary = _summarize_toggle(flip)
    callers = [node for node in module.body if not isinstance(node, ast.FunctionDef)]
    routes: set[Route] = set()

    def run_statement(stmt: ast.stmt, env: dict[str, object], initial_flag: bool) -> None:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name, value = stmt.targets[0].id, stmt.value
            call = _call_name(value)
            if call == "input_bool" and isinstance(value, ast.Call) and len(value.args) == 1 and isinstance(value.args[0], ast.Constant):
                field = value.args[0].value
                if field not in {"flag", "other", "choose"}:
                    raise UnsupportedSource("unknown input name")
                env[name] = env[f"input:{field}"]
            elif call == "ref" and isinstance(value, ast.Call) and len(value.args) == 1 and isinstance(value.args[0], ast.Name):
                field = value.args[0].id
                if field not in FIELDS:
                    raise UnsupportedSource(f"reference to unmodeled field {field!r}")
                env[name] = ["ref", field]
            elif call == "unknown_ref" and isinstance(value, ast.Call) and not value.args:
                env[name] = ["ref", env["input:unknown_target"]]
            elif isinstance(value, ast.Name):
                env[name] = env[value.id]
            else:
                raise UnsupportedSource("unsupported path-analysis assignment")
        elif isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Name):
            branch = stmt.body if bool(env[stmt.test.id]) else stmt.orelse
            for inner in branch:
                run_statement(inner, env, initial_flag)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if _call_name(call) == "flip" and len(call.args) == 1 and isinstance(call.args[0], ast.Name):
                ref = env[call.args[0].id]
                if not (isinstance(ref, list) and ref[0] == "ref"):
                    raise UnsupportedSource("flip argument is not a reference")
                if summary != "toggle":
                    raise UnsupportedSource("unsupported call summary")
                env[ref[1]] = not bool(env[ref[1]])
            elif _call_name(call) in {"mark", "input_bool"}:
                return
            else:
                raise UnsupportedSource("unsupported call during path analysis")
        else:
            raise UnsupportedSource(f"unsupported path-analysis statement: {type(stmt).__name__}")

    for flag, other, choose, unknown_target in product((False, True), repeat=4):
        env: dict[str, object] = {
            "input:flag": flag,
            "input:other": other,
            "input:choose": choose,
            "input:unknown_target": "flag" if unknown_target else "other",
        }
        for stmt in callers:
            run_statement(stmt, env, flag)
        routes.add((flag, bool(env["flag"])))
    return frozenset(routes)


def compare_source_fixture(source: str) -> tuple[Extraction, frozenset[Route], frozenset[Route]]:
    """Return extraction, concrete route set, and alias-summary route set."""
    extracted = extract_call_aliases(source)
    concrete = execute_concrete_fixture(source)
    analyzed = routes_for_alias_targets(extracted.call_targets)
    return extracted, concrete, analyzed
