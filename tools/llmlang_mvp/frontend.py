"""Parse the scalar LLMLang source profile and resolve its implementation pins."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Mapping


SCHEMA = "llmlang-spg/v1"
MIN_I64 = -(2**63)
MAX_I64 = 2**63 - 1
SOURCE_TYPES = {"int": "i64", "bool": "bool"}
ARITHMETIC_OPERATORS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
COMPARISON_OPERATORS = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
}
ERROR_NAMES = frozenset({"ArithmeticOverflow", "DivisionByZero", "InvalidInput"})
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
HASH = re.compile(r"sha256:[0-9a-f]{64}")


class FrontendError(ValueError):
    """Source cannot be admitted to the scalar SPG profile."""


def _error(node: ast.AST, message: str) -> FrontendError:
    return FrontendError(f"line {node.lineno}, column {node.col_offset + 1}: {message}")


def _identifier(node: ast.AST, name: str) -> str:
    if IDENTIFIER.fullmatch(name) is None or name.startswith("builtin__"):
        raise _error(node, f"unsupported identifier {name!r}")
    return name


def _source_type(annotation: ast.expr | None, node: ast.AST) -> str:
    if isinstance(annotation, ast.Name) and annotation.id in SOURCE_TYPES:
        return SOURCE_TYPES[annotation.id]
    raise _error(annotation or node, "type annotation must be int or bool")


def _signature(node: ast.FunctionDef) -> dict:
    args = node.args
    if (
        node.decorator_list
        or getattr(node, "type_params", [])
        or args.posonlyargs
        or args.kwonlyargs
        or args.vararg
        or args.kwarg
        or args.defaults
    ):
        raise _error(node, "only plain functions with named typed parameters are supported")
    params = [[_identifier(a, a.arg), _source_type(a.annotation, a)] for a in args.args]
    if len({name for name, _ in params}) != len(params):
        raise _error(node, "duplicate parameter")
    return {"params": params, "result": _source_type(node.returns, node)}


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(b"llmlang-mvp/implementation/v1\0" + encoded.encode("ascii"))
    return f"sha256:{digest.hexdigest()}"


class _Lowerer:
    def __init__(self, nodes: dict[str, ast.FunctionDef], contracts: Mapping[str, str]) -> None:
        self.nodes = nodes
        self.signatures = {name: _signature(node) for name, node in nodes.items()}
        self.contracts = contracts
        self.functions: dict[str, dict] = {}
        self.active: set[str] = set()

    def lower(self, name: str, reference: ast.AST) -> dict:
        if name in self.functions:
            return self.functions[name]
        if name in self.active:
            raise _error(reference, f"recursive call to {name!r} is outside the scalar profile")
        self.active.add(name)
        node = self.nodes[name]
        signature = self.signatures[name]
        body, complete = self.block(node.body, dict(signature["params"]), signature["result"])
        if not complete:
            raise _error(node, f"function {name!r} must return or fail on every path")
        result = {
            **signature,
            "body": body,
            "provided_contract_hash": self.contracts.get(name),
        }
        result["impl_hash"] = _digest(result)
        self.functions[name] = result
        self.active.remove(name)
        return result

    def block(
        self, statements: list[ast.stmt], bindings: dict[str, str], result: str
    ) -> tuple[list[list], bool]:
        body = []
        complete = False
        for statement in statements:
            if complete:
                raise _error(statement, "unreachable statement")
            match statement:
                case ast.Assign(targets=[ast.Name(id=name)], value=value):
                    _identifier(statement, name)
                    if name in bindings:
                        raise _error(statement, f"binding {name!r} already exists")
                    expr, typ = self.expression(value, bindings)
                    bindings[name] = typ
                    body.append(["let", name, expr])
                case ast.If(test=test, body=yes, orelse=no):
                    condition, typ = self.expression(test, bindings)
                    if typ != "bool":
                        raise _error(test, "if condition must have type bool")
                    then_body, then_complete = self.block(yes, bindings.copy(), result)
                    else_body, else_complete = self.block(no, bindings.copy(), result)
                    body.append(["if", condition, then_body, else_body])
                    complete = then_complete and else_complete
                case ast.Return(value=ast.Call(func=ast.Name(id="builtin__fail")) as call):
                    body.append(self.failure(call))
                    complete = True
                case ast.Expr(value=ast.Call(func=ast.Name(id="builtin__fail")) as call):
                    body.append(self.failure(call))
                    complete = True
                case ast.Return(value=value) if value is not None:
                    expr, typ = self.expression(value, bindings)
                    if typ != result:
                        raise _error(value, f"expected return type {result}, got {typ}")
                    body.append(["return", expr])
                    complete = True
                case _:
                    raise _error(statement, f"unsupported statement {type(statement).__name__}")
        return body, complete

    @staticmethod
    def failure(call: ast.Call) -> list:
        if not call.keywords and len(call.args) == 1:
            argument = call.args[0]
            if isinstance(argument, ast.Constant) and type(argument.value) is str:
                if argument.value in ERROR_NAMES:
                    return ["fail", argument.value]
        raise _error(call, "builtin__fail requires a supported literal error name")

    def expression(self, node: ast.expr, bindings: dict[str, str]) -> tuple[list, str]:
        match node:
            case ast.Constant(value=value) if type(value) is bool:
                return ["bool", value], "bool"
            case ast.Constant(value=value) if type(value) is int:
                return self.integer(node, value)
            case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=value)) if type(value) is int:
                return self.integer(node, -value)
            case ast.Name(id=name):
                if name not in bindings:
                    raise _error(node, f"unknown variable {name!r}")
                return ["var", name], bindings[name]
            case ast.BinOp(left=left, op=op, right=right) if type(op) in ARITHMETIC_OPERATORS:
                lhs, lhs_type = self.expression(left, bindings)
                rhs, rhs_type = self.expression(right, bindings)
                if lhs_type != "i64" or rhs_type != "i64":
                    raise _error(node, "arithmetic operands must have type i64")
                return ["bin", ARITHMETIC_OPERATORS[type(op)], lhs, rhs], "i64"
            case ast.Compare(left=left, ops=[op], comparators=[right]) if type(op) in COMPARISON_OPERATORS:
                lhs, lhs_type = self.expression(left, bindings)
                rhs, rhs_type = self.expression(right, bindings)
                if lhs_type != rhs_type or (
                    lhs_type != "i64" and not isinstance(op, (ast.Eq, ast.NotEq))
                ):
                    raise _error(node, "incompatible comparison operands")
                return ["bin", COMPARISON_OPERATORS[type(op)], lhs, rhs], "bool"
            case ast.Call(func=ast.Name(id=name), args=args, keywords=[]):
                if name not in self.nodes:
                    raise _error(node, f"unknown function {name!r}")
                signature = self.signatures[name]
                if len(args) != len(signature["params"]):
                    raise _error(node, f"argument count mismatch in call to {name!r}")
                call_args = []
                for arg, (_, expected) in zip(args, signature["params"], strict=True):
                    expr, actual = self.expression(arg, bindings)
                    if actual != expected:
                        raise _error(arg, f"expected argument type {expected}, got {actual}")
                    call_args.append(expr)
                callee = self.lower(name, node)
                return ["call", name, call_args, callee["impl_hash"]], signature["result"]
            case _:
                raise _error(node, f"unsupported expression {type(node).__name__}")

    @staticmethod
    def integer(node: ast.AST, value: int) -> tuple[list, str]:
        if not MIN_I64 <= value <= MAX_I64:
            raise _error(node, "integer literal out of signed 64-bit range")
        return ["i64", value], "i64"


def parse(source: str, *, provided_contract_hashes: Mapping[str, str] | None = None) -> dict:
    """Return canonical scalar SPG with all direct calls pinned to exact callees."""
    try:
        module = ast.parse(source)
    except (SyntaxError, ValueError) as error:
        raise FrontendError(str(error)) from error
    nodes = {}
    for node in module.body:
        if not isinstance(node, ast.FunctionDef):
            raise _error(node, "only function declarations are supported at module scope")
        name = _identifier(node, node.name)
        if name in nodes:
            raise _error(node, f"duplicate function {name!r}")
        nodes[name] = node
    if not nodes:
        raise FrontendError("expected at least one function declaration")

    contracts = dict(provided_contract_hashes or {})
    if provided_contract_hashes is not None:
        if contracts.keys() != nodes.keys():
            raise FrontendError("provided contract hashes must name exactly the declared functions")
        if any(not isinstance(value, str) or HASH.fullmatch(value) is None for value in contracts.values()):
            raise FrontendError("invalid provided contract hash")

    lowerer = _Lowerer(nodes, contracts)
    functions = {name: lowerer.lower(name, nodes[name]) for name in sorted(nodes)}
    return {"schema": SCHEMA, "functions": functions}
