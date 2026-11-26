"""Versioned, backend-independent exchange for the scalar Contract IR."""

import ast
import json
import re

from . import contract


SCHEMA = "llmlang-contract-ir/v1"
INTEGER_LITERAL = re.compile(r"(?:0|[1-9][0-9]*)", re.ASCII)
ARITHMETIC = {"add": ast.Add, "subtract": ast.Sub, "multiply": ast.Mult}
ORDER = {
    "less-than": ast.Lt,
    "less-or-equal": ast.LtE,
    "greater-than": ast.Gt,
    "greater-or-equal": ast.GtE,
}
EQUALITY = {"equal": ast.Eq, "not-equal": ast.NotEq}
LOGICAL = {"and": ast.And, "or": ast.Or}
OPERATORS = {
    **ARITHMETIC, **ORDER, **EQUALITY, **LOGICAL, "not": ast.Not, "negate": ast.USub,
}
OPERATOR_NAMES = {operator: name for name, operator in OPERATORS.items()}


def _predicate_types(parameters):
    return {name: "Int" if value_type == "I64" else value_type
            for name, value_type in parameters.items()}


def _encode_expression(node, binders):
    match node:
        case ast.Constant(value=value) if type(value) is bool:
            return {"op": "literal", "type": "Bool", "value": value}
        case ast.Constant(value=value):
            return {"op": "literal", "type": "Int", "value": str(value)}
        case ast.Name(id=name):
            return {"op": "ref", "type": binders[name], "name": name}
        case ast.UnaryOp(op=operator, operand=operand):
            result_type = "Bool" if isinstance(operator, ast.Not) else "Int"
            name, args = OPERATOR_NAMES[type(operator)], (operand,)
        case ast.BinOp(left=left, op=operator, right=right):
            result_type, name, args = "Int", OPERATOR_NAMES[type(operator)], (left, right)
        case ast.Compare(left=left, ops=[operator], comparators=[right]):
            result_type, name, args = "Bool", OPERATOR_NAMES[type(operator)], (left, right)
        case ast.BoolOp(op=operator, values=values):
            result_type, name, args = "Bool", OPERATOR_NAMES[type(operator)], values
        case ast.Call(func=ast.Name(id="quotient"), args=args):
            result_type, name = "Int", "quotient"
        case _:
            raise contract.ContractError("unsupported normalized predicate")
    return {"op": name, "type": result_type,
            "args": [_encode_expression(arg, binders) for arg in args]}


def _wire_contract(value):
    inputs = _predicate_types(dict(value.parameters))
    result = _predicate_types({"result": value.returns})
    return {
        "parameters": [list(parameter) for parameter in value.parameters],
        "returns": value.returns,
        "requires": [_encode_expression(term, inputs) for term in value.requires],
        "ensures": [_encode_expression(term, inputs | result) for term in value.ensures],
        "errors": {name: [_encode_expression(term, inputs) for term in terms]
                   for name, terms in value.errors.items()},
    }


def to_wire(definitions):
    """Represent checked contract pairs as a portable typed JSON object."""
    return {
        "schema": SCHEMA,
        "profile": contract.PROFILE,
        "contracts": {name: {role: _wire_contract(value) for role, value in pair.items()}
                      for name, pair in definitions.items()},
    }


def dumps(definitions):
    """Serialize the typed document with deterministic key order and spacing."""
    return json.dumps(to_wire(definitions), sort_keys=True, separators=(",", ":")) + "\n"


def _expression_members(node, expected_keys, context):
    if set(node) != {"op", "type"} | expected_keys:
        raise contract.ContractError(f"{context}: invalid members for {node['op']!r}")


def _decode_expression(node, binders, context):
    if not isinstance(node, dict) or not isinstance(node.get("op"), str):
        raise contract.ContractError(f"{context}: expected a typed expression object")
    operator = node["op"]
    value_type = node.get("type")
    if value_type not in ("Int", "Bool"):
        raise contract.ContractError(f"{context}: unsupported expression type {value_type!r}")

    if operator == "literal":
        _expression_members(node, {"value"}, context)
        value = node["value"]
        if value_type == "Bool" and type(value) is bool:
            return ast.Constant(value=value)
        if value_type == "Int" and isinstance(value, str) and INTEGER_LITERAL.fullmatch(value):
            try:
                return ast.Constant(value=int(value))
            except ValueError as exc:
                raise contract.ContractError(f"{context}: integer literal exceeds reader limit") from exc
        raise contract.ContractError(f"{context}: invalid {value_type} literal")

    if operator == "ref":
        _expression_members(node, {"name"}, context)
        name = node["name"]
        if not isinstance(name, str) or binders.get(name) != value_type:
            raise contract.ContractError(f"{context}: unbound or mistyped reference {name!r}")
        return ast.Name(id=name, ctx=ast.Load())

    _expression_members(node, {"args"}, context)
    args = node["args"]
    if not isinstance(args, list):
        raise contract.ContractError(f"{context}: {operator!r} arguments must be an array")
    if operator in ARITHMETIC or operator in ORDER or operator in ("negate", "quotient"):
        operand_type = "Int"
    elif operator in LOGICAL or operator == "not":
        operand_type = "Bool"
    elif operator in EQUALITY:
        operand_type = args[0].get("type") if args and isinstance(args[0], dict) else None
    else:
        raise contract.ContractError(f"{context}: unsupported operator {operator!r}")

    result_type = "Int" if operator in ARITHMETIC or operator in ("negate", "quotient") else "Bool"
    if value_type != result_type:
        raise contract.ContractError(f"{context}: {operator!r} must return {result_type}")
    if operator in LOGICAL:
        valid_arity = len(args) >= 2
    else:
        valid_arity = len(args) == (1 if operator in ("negate", "not") else 2)
    if not valid_arity:
        raise contract.ContractError(f"{context}: invalid arity for {operator!r}")

    operands = []
    for index, arg in enumerate(args):
        subcontext = f"{context}/args/{index}"
        operand = _decode_expression(arg, binders, subcontext)
        if arg["type"] != operand_type:
            raise contract.ContractError(f"{subcontext}: {operator!r} requires {operand_type}")
        operands.append(operand)
    if operator == "quotient":
        return ast.Call(func=ast.Name(id=operator, ctx=ast.Load()), args=operands, keywords=[])
    operation = OPERATORS[operator]()
    if operator in LOGICAL:
        return ast.BoolOp(op=operation, values=operands)
    if operator in ("negate", "not"):
        return ast.UnaryOp(op=operation, operand=operands[0])
    if operator in ARITHMETIC:
        return ast.BinOp(left=operands[0], op=operation, right=operands[1])
    return ast.Compare(left=operands[0], ops=[operation], comparators=operands[1:])


def _decode_clauses(value, binders, context):
    if not isinstance(value, list):
        raise contract.ContractError(f"{context}: clauses must be an array")
    clauses = []
    for index, node in enumerate(value):
        term = _decode_expression(node, binders, f"{context}/{index}")
        if node["type"] != "Bool":
            raise contract.ContractError(f"{context}/{index}: expected a Bool clause")
        clauses.append(contract._canonical_expression(term))
    return clauses


def _decode_contract(value, context):
    if not isinstance(value, dict) or set(value) != {
        "parameters", "returns", "requires", "ensures", "errors",
    }:
        raise contract.ContractError(f"{context}: invalid scalar contract members")
    raw_parameters = value["parameters"]
    if not isinstance(raw_parameters, list):
        raise contract.ContractError(f"{context}/parameters: expected an ordered array")
    parameters = {}
    for index, pair in enumerate(raw_parameters):
        location = f"{context}/parameters/{index}"
        if not isinstance(pair, list) or len(pair) != 2:
            raise contract.ContractError(f"{location}: expected a name and type pair")
        name = contract._identifier(pair[0], location)
        if name in parameters:
            raise contract.ContractError(f"{location}: duplicate parameter {name!r}")
        if not isinstance(pair[1], str) or pair[1] not in contract.VALUE_TYPES:
            raise contract.ContractError(f"{location}: unsupported parameter type {pair[1]!r}")
        parameters[name] = pair[1]
    returns = value["returns"]
    if not isinstance(returns, str) or returns not in contract.VALUE_TYPES:
        raise contract.ContractError(f"{context}/returns: unsupported return type {returns!r}")
    if not isinstance(value["errors"], dict):
        raise contract.ContractError(f"{context}/errors: expected named error outcomes")

    inputs = _predicate_types(parameters)
    result = _predicate_types({"result": returns})
    return contract.parse_contract({
        "parameters": parameters,
        "returns": returns,
        "requires": _decode_clauses(value["requires"], inputs, f"{context}/requires"),
        "ensures": _decode_clauses(value["ensures"], inputs | result, f"{context}/ensures"),
        "errors": {name: _decode_clauses(terms, inputs, f"{context}/errors/{name}")
                   for name, terms in value["errors"].items()},
    })


def from_wire(value):
    """Check a typed document, rejecting unknown profiles and wire versions."""
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise contract.ContractError("unsupported Contract IR schema")
    if set(value) != {"schema", "profile", "contracts"}:
        raise contract.ContractError("invalid Contract IR document members")
    if value["profile"] != contract.PROFILE:
        raise contract.ContractError(f"unsupported contract profile {value['profile']!r}")
    if not isinstance(value["contracts"], dict):
        raise contract.ContractError("contracts must map implementation names to pairs")
    definitions = {}
    for name, pair in value["contracts"].items():
        contract._identifier(name, "implementation name")
        if not isinstance(pair, dict) or set(pair) != {"public", "provided"}:
            raise contract.ContractError(f"expected public and provided contracts for {name}")
        definitions[name] = {
            role: _decode_contract(item, f"/contracts/{name}/{role}")
            for role, item in pair.items()
        }
    return definitions


def load_document(text):
    """Read either supported input syntax and identify its clause pointer prefix."""
    try:
        document = json.loads(text, object_pairs_hook=contract._unique_pairs)
        if isinstance(document, dict) and "schema" in document and not isinstance(document["schema"], dict):
            return from_wire(document), "/contracts"
        return contract.parse_contracts(text), ""
    except json.JSONDecodeError as exc:
        raise contract.ContractError(f"invalid contract JSON: {exc}") from exc
    except RecursionError as exc:
        raise contract.ContractError("Contract IR document is too deeply nested") from exc


def loads(text):
    """Read an input document into checked contract pairs."""
    definitions, _ = load_document(text)
    return definitions
