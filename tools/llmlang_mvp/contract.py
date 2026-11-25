"""Scalar Contract IR and a checked controlled natural-language projection.

The scalar-v1 profile uses Bool and I64 for values crossing the interface.
Predicate arithmetic is mathematical integer arithmetic. The total quotient
truncates toward zero and returns zero for a zero divisor. Program errors
are represented separately as outcomes with explicit guards.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import keyword
import re


PROFILE = "scalar-v1"
VALUE_TYPES = frozenset({"Bool", "I64"})
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)

# Each phrase is a production in the controlled language. Parentheses
# delimit operands, so even nested negation and comparisons have one parse.
UNARY_PHRASES = {
    ast.Not: ("it is false that", "not "),
    ast.USub: ("the negation of", "-"),
}
BINARY_PHRASES = {
    ast.Add: ("the sum of", "and", "+"),
    ast.Sub: ("the difference between", "and", "-"),
    ast.Mult: ("the product of", "and", "*"),
    ast.Eq: ("it is true that", "equals", "=="),
    ast.NotEq: ("it is true that", "differs from", "!="),
    ast.Lt: ("it is true that", "is less than", "<"),
    ast.LtE: ("it is true that", "is at most", "<="),
    ast.Gt: ("it is true that", "is greater than", ">"),
    ast.GtE: ("it is true that", "is at least", ">="),
    ast.And: ("both", "and", "and"),
    ast.Or: ("either", "or", "or"),
}
QUOTIENT_PHRASE = "the truncating quotient of"
NUMERIC_MODEL = (
    "Predicate arithmetic uses mathematical integers. "
    "Quotient truncates toward zero and is zero when its divisor is zero."
)
OUTCOME_HEADER = re.compile(r"The error ([A-Za-z_][A-Za-z0-9_]*) is declared\.")
CLAUSE_HEADER = re.compile(r"Clause ([A-Za-z0-9_-]+)\. ")


class ContractError(ValueError):
    """Contract data or controlled text violates the supported profile."""


def _expression(source: str) -> ast.expr:
    try:
        return ast.parse(source, mode="eval").body
    except (SyntaxError, RecursionError, ValueError) as exc:
        raise ContractError(f"invalid scalar contract expression: {source!r}") from exc


def _identifier(value: object, context: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or keyword.iskeyword(value):
        raise ContractError(f"{context} must be an identifier")
    return value


def _kind(node: ast.expr, symbols: dict[str, str]) -> str:
    if isinstance(node, ast.Constant):
        kind = type(node.value)
        if kind is bool:
            return "Bool"
        if kind is int:
            return "I64"
    elif isinstance(node, ast.Name):
        if node.id not in symbols:
            raise ContractError(f"unbound contract operand {node.id!r}")
        return symbols[node.id]
    elif isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_PHRASES:
        expected = "Bool" if isinstance(node.op, ast.Not) else "I64"
        return _check_operands((node.operand,), symbols, expected, expected)
    elif isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult):
        return _check_operands((node.left, node.right), symbols, "I64", "I64")
    elif isinstance(node, ast.BoolOp) and type(node.op) in (ast.And, ast.Or):
        return _check_operands(node.values, symbols, "Bool", "Bool")
    elif isinstance(node, ast.Compare):
        vec = (node.left, *node.comparators)
        for left, operator, right in zip(vec[:-1], node.ops, vec[1:], strict=True):
            if type(operator) not in BINARY_PHRASES:
                break
            expected = _kind(left, symbols) if isinstance(operator, (ast.Eq, ast.NotEq)) else "I64"
            _check_operands((left, right), symbols, expected, "Bool")
        else:
            return "Bool"
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "quotient"
        and len(node.args) == 2
        and not node.keywords
    ):
        return _check_operands(node.args, symbols, "I64", "I64")
    raise ContractError(f"unsupported scalar contract operand: {ast.dump(node)}")


def _check_operands(
    operands: list[ast.expr] | tuple[ast.expr, ...],
    symbols: dict[str, str],
    expected: str,
    result: str,
) -> str:
    for operand in operands:
        actual = _kind(operand, symbols)
        if actual != expected:
            raise ContractError(f"contract operand must be {expected}, got {actual}")
    return result


def _normalize(node: ast.expr) -> ast.expr:
    # A pure chain evaluates as a conjunction over adjacent comparisons.
    # Flatten equal associative boolean operators for coding-independent identity.
    if isinstance(node, ast.Compare) and len(node.ops) > 1:
        operands = (node.left, *node.comparators)
        return _normalize(
            ast.BoolOp(
                op=ast.And(),
                values=[
                    ast.Compare(left=l, ops=[op], comparators=[r])
                    for l, op, r in zip(operands[:-1], node.ops, operands[1:], strict=True)
                ],
            )
        )
    for field, value in ast.iter_fields(node):
        if isinstance(value, ast.expr):
            setattr(node, field, _normalize(value))
        elif isinstance(value, list) and all(isinstance(item, ast.expr) for item in value):
            setattr(node, field, [_normalize(item) for item in value])
    if isinstance(node, ast.BoolOp):
        node.values = [
            operand
            for item in node.values
            for operand in (item.values if isinstance(item, ast.BoolOp) and type(item.op) is type(node.op) else [item])
        ]
    return node


def _canonical_expression(node: ast.expr) -> str:
    """Encode validated nodes independently of Python's source pretty-printer."""
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.UnaryOp):
        operator = UNARY_PHRASES[type(node.op)][1]
        return f"({operator}{_canonical_expression(node.operand)})"
    if isinstance(node, ast.Call):
        arguments = ",".join(map(_canonical_expression, node.args))
        return f"quotient({arguments})"
    if isinstance(node, ast.BinOp):
        operator, operands = node.op, (node.left, node.right)
    elif isinstance(node, ast.Compare):
        operator, operands = node.ops[0], (node.left, node.comparators[0])
    elif isinstance(node, ast.BoolOp):
        operator, operands = node.op, node.values
    else:
        raise ContractError("unsupported node in canonical encoding")
    spelling = BINARY_PHRASES[type(operator)][2]
    joined = f" {spelling} ".join(map(_canonical_expression, operands))
    return f"({joined})"


def _clause_sources(raw: object, symbols: dict[str, str], context: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ContractError(f"{context} must be an array of expressions")
    result = []
    for source in raw:
        if not isinstance(source, str):
            raise ContractError(f"{context} expressions must be strings")
        term = _expression(source)
        if _kind(term, symbols) != "Bool":
            raise ContractError(f"{context} expressions must be Bool")
        result.append(_canonical_expression(_normalize(term)))
    return tuple(result)


@dataclass(frozen=True)
class Contract:
    """Checked immutable scalar clauses. AST properties return fresh trees."""

    parameters: tuple[tuple[str, str], ...]
    returns: str
    _requires: tuple[str, ...]
    _ensures: tuple[str, ...]
    _errors: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def requires(self) -> tuple[ast.expr, ...]:
        return tuple(map(_expression, self._requires))

    @property
    def ensures(self) -> tuple[ast.expr, ...]:
        return tuple(map(_expression, self._ensures))

    @property
    def errors(self) -> dict[str, tuple[ast.expr, ...]]:
        return {name: tuple(map(_expression, clauses)) for name, clauses in self._errors}


def parse_contract(data: object) -> Contract:
    """Decode, type-check, and canonicalize a scalar-v1 contract object."""
    keys = {"parameters", "returns", "requires", "ensures", "errors"}
    if not isinstance(data, dict) or set(data) not in (keys, keys | {"profile"}):
        raise ContractError("expected parameters, returns, requires, ensures and errors")
    if data.get("profile", PROFILE) != PROFILE:
        raise ContractError(f"unsupported contract profile {data['profile']!r}")
    raw_parameters = data["parameters"]
    if not isinstance(raw_parameters, dict):
        raise ContractError("parameters must be an ordered object of names and types")
    parameters = {}
    for name, value_type in raw_parameters.items():
        name = _identifier(name, "parameter name")
        if name in {"result", "quotient"}:
            raise ContractError(f"reserved contract parameter name {name!r}")
        if not isinstance(value_type, str) or value_type not in VALUE_TYPES:
            raise ContractError(f"unsupported parameter type {value_type!r}")
        parameters[name] = value_type
    returns = data["returns"]
    if not isinstance(returns, str) or returns not in VALUE_TYPES:
        raise ContractError(f"unsupported return type {returns!r}")
    raw_errors = data["errors"]
    if not isinstance(raw_errors, dict):
        raise ContractError("errors must map each declared outcome to its clauses")
    errors = {}
    for name, clauses in raw_errors.items():
        name = _identifier(name, "error outcome")
        errors[name] = _clause_sources(clauses, parameters, f"error {name}")
    return Contract(
        parameters=tuple(parameters.items()),
        returns=returns,
        _requires=_clause_sources(data["requires"], parameters, "requires"),
        _ensures=_clause_sources(data["ensures"], parameters | {"result": returns}, "ensures"),
        _errors=tuple(sorted(errors.items())),
    )


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate contract JSON member {key!r}")
        value[key] = item
    return value


def parse_contracts(text: str) -> dict[str, dict[str, Contract]]:
    """Decode implementation names and their exact public/provided contracts."""
    try:
        data = json.loads(text, object_pairs_hook=_unique_pairs)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid contract JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError("contract file must map implementation names to contract pairs")
    contracts = {}
    for name, pair in data.items():
        _identifier(name, "implementation name")
        if not isinstance(pair, dict) or set(pair) != {"public", "provided"}:
            raise ContractError(f"expected public and provided contracts for {name}")
        contracts[name] = {role: parse_contract(contract) for role, contract in pair.items()}
    return contracts


def contract_hash(contract: Contract) -> str:
    """Hash the specified normalized profile, types and clauses."""
    value = {
        "profile": PROFILE,
        "parameters": contract.parameters,
        "returns": contract.returns,
        "requires": contract._requires,
        "ensures": contract._ensures,
        "errors": contract._errors,
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(b"LLMLang Contract IR\x00" + payload).hexdigest()


def _binary_phrase(operator: type, left: str, right: str) -> str:
    prefix, connector, _ = BINARY_PHRASES[operator]
    return f"{prefix} ({left}) {connector} ({right})"


def _describe(node: ast.expr) -> str:
    if isinstance(node, ast.Constant):
        if type(node.value) is bool:
            return str(node.value).lower()
        return str(node.value)
    if isinstance(node, ast.Name):
        return f"the value {node.id}"
    if isinstance(node, ast.UnaryOp):
        return f"{UNARY_PHRASES[type(node.op)][0]} ({_describe(node.operand)})"
    if isinstance(node, ast.BinOp):
        return _binary_phrase(type(node.op), _describe(node.left), _describe(node.right))
    if isinstance(node, ast.Compare):
        return _binary_phrase(type(node.ops[0]), _describe(node.left), _describe(node.comparators[0]))
    if isinstance(node, ast.BoolOp):
        current = _describe(node.values[0])
        for item in node.values[1:]:
            current = _binary_phrase(type(node.op), current, _describe(item))
        return current
    if isinstance(node, ast.Call):
        return f"{QUOTIENT_PHRASE} ({_describe(node.args[0])}) by ({_describe(node.args[1])})"
    raise ContractError("unsupported node in controlled rendering")


def render_contract(contract: Contract) -> str:
    """Render every clause with an explicit role, scope, and ordinal."""
    lines = [f"Contract profile {PROFILE}.", NUMERIC_MODEL]
    for name, kind in contract.parameters:
        lines.append(f"The parameter {name} has type {kind}.")
    lines.append(f"The success result has type {contract.returns}.")
    for i, clause in enumerate(contract.requires, 1):
        lines.append(f"Clause requirement-{i}. The caller must ensure that {_describe(clause)}.")
    for i, clause in enumerate(contract.ensures, 1):
        lines.append(f"Clause guarantee-{i}. On success, guarantee that {_describe(clause)}.")
    for name, clauses in contract.errors.items():
        lines.append(f"The error {name} is declared.")
        for i, clause in enumerate(clauses, 1):
            lines.append(f"Clause error-{name}-{i}. On error {name}, guarantee that {_describe(clause)}.")
    return "\n".join(lines) + "\n"


def _parenthesized(text: str) -> tuple[str, str]:
    if text.startswith("("):
        depth = 0
        for i, char in enumerate(text):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if not depth:
                    return text[1:i], text[i + 1:]
    raise ContractError(f"expected a parenthesized controlled operand near {text!r}")


def _operands(text: str, connector: str) -> tuple[str, str]:
    left, tail = _parenthesized(text)
    left = _read_phrase(left)
    rest = tail.removeprefix(f" {connector} ")
    if rest == tail:
        raise ContractError(f"expected controlled connector {connector!r}")
    right, tail = _parenthesized(rest)
    if tail:
        raise ContractError(f"unexpected controlled suffix {tail!r}")
    return left, _read_phrase(right)


def _read_phrase(text: str) -> str:
    if text in {"true", "false"}:
        return text.capitalize()
    if re.fullmatch(r"(?:0|[1-9][0-9]*)", text):
        return text
    if text.startswith("the value "):
        return _identifier(text.removeprefix("the value "), "controlled operand")
    for prefix, operator in UNARY_PHRASES.values():
        if text.startswith(prefix + " "):
            operand, tail = _parenthesized(text[len(prefix) + 1:])
            if not tail:
                return f"({operator}({_read_phrase(operand)}))"
            break
    if text.startswith(QUOTIENT_PHRASE + " "):
        left, right = _operands(text[len(QUOTIENT_PHRASE) + 1:], "by")
        return f"quotient({left}, {right})"
    for prefix, connector, operator in BINARY_PHRASES.values():
        if text.startswith(prefix + " "):
            phrase = text[len(prefix) + 1:]
            _, tail = _parenthesized(phrase)
            if tail.startswith(f" {connector} "):
                left, right = _operands(phrase, connector)
                return f"(({left}) {operator} ({right}))"
    raise ContractError(f"unrecognized controlled expression {text!r}")


def parse_controlled(text: str) -> Contract:
    """Parse a controlled-language document into independently checked IR."""
    if not isinstance(text, str):
        raise ContractError("controlled contract must be text")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines[:2] != [f"Contract profile {PROFILE}.", NUMERIC_MODEL]:
        raise ContractError("unsupported or missing controlled-language profile or numeric model")
    data: dict[str, object] = {
        "profile": PROFILE,
        "parameters": {},
        "returns": None,
        "requires": [],
        "ensures": [],
        "errors": {},
    }
    parameters, errors = data["parameters"], data["errors"]
    for line in lines[2:]:
        parameter = re.fullmatch(r"The parameter (\w+) has type (\w+)\.", line)
        returns = re.fullmatch(r"The success result has type (\w+)\.", line)
        error = OUTCOME_HEADER.fullmatch(line)
        if parameter:
            name, kind = parameter.groups()
            if name in parameters:
                raise ContractError(f"duplicate controlled parameter {name!r}")
            parameters[name] = kind
        elif returns:
            if data["returns"] is not None:
                raise ContractError("duplicate controlled success result")
            data["returns"] = returns[1]
        elif error:
            if error[1] in errors:
                raise ContractError(f"duplicate controlled error {error[1]!r}")
            errors[error[1]] = []
        else:
            _read_clause(line, data)
    return parse_contract(data)


def _read_clause(line: str, data: dict[str, object]) -> None:
    match = CLAUSE_HEADER.match(line)
    if not match or not line.endswith("."):
        raise ContractError(f"invalid controlled clause {line!r}")
    body = line[match.end():-1]
    if body.startswith("The caller must ensure that "):
        prefix, target = "requirement", data["requires"]
        phrase = body.removeprefix("The caller must ensure that ")
    elif body.startswith("On success, guarantee that "):
        prefix, target = "guarantee", data["ensures"]
        phrase = body.removeprefix("On success, guarantee that ")
    else:
        error = re.match(r"On error ([A-Za-z_][A-Za-z0-9_]*), guarantee that ", body)
        if not error or error[1] not in data["errors"]:
            raise ContractError(f"invalid controlled clause role {body!r}")
        prefix, target = f"error-{error[1]}", data["errors"][error[1]]
        phrase = body[error.end():]
    if match[1] != f"{prefix}-{len(target) + 1}":
        raise ContractError(f"out-of-order or mismatched controlled clause {match[1]!r}")
    target.append(_read_phrase(phrase))


def checked_render(contract: Contract) -> str:
    """Reject a rendering whose independently parsed clauses differ."""
    rendered = render_contract(contract)
    if parse_controlled(rendered) != contract:
        raise ContractError("controlled rendering changes the normalized contract")
    return rendered
