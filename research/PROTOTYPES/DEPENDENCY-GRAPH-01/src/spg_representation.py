"""Typed source-to-SPG experiment with two expression surfaces and exact bindings."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import keyword
import re
from typing import Literal, Mapping, TypeVar

from .recursive_identity import Call, Definition, External, publish_definitions
from .semantic_graph import ContentStore, Dependency, Snapshot, canonical_bytes, make_snapshot


Scalar = Literal["Int", "Bool"]
Value = int | bool
Term = list | Value
Policy = Literal["dag-only", "keyed", "structural"]
SCALARS: dict[type, Scalar] = {int: "Int", bool: "Bool"}
T = TypeVar("T")


class RepresentationError(ValueError):
    """The source is outside the checked fixture profile."""


class FuelExhausted(RuntimeError):
    """The observation exceeded its declared call budget."""


@dataclass(frozen=True)
class Prefix:
    text: str


@dataclass(frozen=True)
class Operation:
    export: str
    parameters: tuple[Scalar, ...]
    result: Scalar
    contract: str


@dataclass(frozen=True)
class Implementation:
    operation: str
    parameters: tuple[str, ...]
    body: str | Prefix
    member_key: str | None = None


@dataclass(frozen=True)
class Program:
    contracts: Mapping[str, tuple[tuple[str, ...], ...]]
    operations: Mapping[str, Operation]
    implementations: Mapping[str, Implementation]
    bindings: Mapping[str, str]


@dataclass(frozen=True)
class Graph:
    store: ContentStore
    snapshot: Snapshot


def _lookup(values: Mapping[str, T], name: str, kind: str) -> T:
    try:
        return values[name]
    except KeyError as exc:
        raise RepresentationError(f"unknown {kind}: {name}") from exc


def _check_label(label: str) -> None:
    if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.]*", label):
        raise RepresentationError(f"invalid label: {label!r}")


def _infix(node: ast.expr) -> Term:
    match node:
        case ast.Constant(value=value) if type(value) in SCALARS:
            return value
        case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=value)) if type(value) is int:
            return -value
        case ast.Name(id=name):
            return ["arg", name]
        case ast.BinOp(left=left, op=ast.Add() | ast.Sub() as operator, right=right):
            form = "add" if isinstance(operator, ast.Add) else "sub"
            return [form, _infix(left), _infix(right)]
        case ast.Compare(left=left, ops=[ast.Eq()], comparators=[right]):
            return ["eq", _infix(left), _infix(right)]
        case ast.IfExp(test=test, body=yes, orelse=no):
            return ["if", _infix(test), _infix(yes), _infix(no)]
        case ast.Call(func=ast.Name(id=("emit" | "op" | "pin") as form),
                      args=[ast.Constant(value=str(label)), *args], keywords=[]):
            return [form, label, *map(_infix, args)]
    raise RepresentationError(f"unsupported expression: {type(node).__name__}")


def _parse(body: str | Prefix) -> Term:
    if isinstance(body, Prefix):
        try:
            return json.loads(body.text)
        except ValueError as exc:
            raise RepresentationError("invalid JSON prefix expression") from exc
    if not body.isascii():
        raise RepresentationError("infix fixture source must use ASCII")
    try:
        tree = ast.parse(body.strip(), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise RepresentationError("invalid infix expression") from exc
    return _infix(tree.body)


def _definition(source: Implementation, signature: Operation, program: Program,
                operations: Mapping[str, str]) -> Definition:
    if (len(source.parameters) != len(signature.parameters)
            or len(set(source.parameters)) != len(source.parameters)
            or any(not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) or keyword.iskeyword(name)
                   for name in source.parameters)):
        raise RepresentationError("invalid parameter declarations")
    locals_ = dict(zip(source.parameters, enumerate(signature.parameters)))
    references: list[Call | External] = []

    def lower(term: Term) -> tuple[Scalar, list]:
        match term:
            case _ if type(term) in SCALARS:
                if type(term) is int and not -(2**31) <= term < 2**31:
                    raise RepresentationError("Int literal exceeds the fixture bound")
                return SCALARS[type(term)], ["literal", term]
            case ["arg", str(name)]:
                position, parameter_type = _lookup(locals_, name, "parameter")
                return parameter_type, ["argument", position]
            case [("add" | "sub" | "eq") as form, lhs, rhs]:
                left_type, left = lower(lhs)
                right_type, right = lower(rhs)
                if left_type != "Int" or right_type != "Int":
                    raise RepresentationError(f"{form} expects two Int operands")
                return ("Bool" if form == "eq" else "Int"), [form, left, right]
            case ["if", test, yes, no]:
                test_type, condition = lower(test)
                yes_type, yes_body = lower(yes)
                no_type, no_body = lower(no)
                if test_type != "Bool" or yes_type != no_type:
                    raise RepresentationError("if requires a Bool test and matching arm types")
                return yes_type, ["if", condition, yes_body, no_body]
            case ["emit", str(label), tail]:
                _check_label(label)
                result_type, body = lower(tail)
                return result_type, ["emit", label, body]
            case [("op" | "pin") as form, str(target), *args]:
                if form == "op":
                    callee = _lookup(program.operations, target, "operation")
                    _lookup(program.bindings, target, "operation binding")
                    reference = External(operations[target])
                else:
                    callee_source = _lookup(program.implementations, target, "implementation")
                    callee = _lookup(program.operations, callee_source.operation, "operation")
                    reference = Call(target)
                index = len(references)
                references.append(reference)
                arguments = [lower(arg) for arg in args]
                if tuple(arg_type for arg_type, _ in arguments) != callee.parameters:
                    raise RepresentationError(f"call argument types do not match {target}")
                return callee.result, [form, index, *(arg for _, arg in arguments)]
        raise RepresentationError("unsupported prefix expression")

    result, body = lower(_parse(source.body))
    if result != signature.result:
        raise RepresentationError("implementation result type does not match the interface")
    # The ordered template holds call positions. The SCC publisher resolves the
    # separate reference vector to exact digests or component-local positions.
    return Definition(("rt05-spg-body-v1", External(operations[source.operation]),
                       canonical_bytes(body).decode("ascii"), *references), source.member_key)


def compile_program(program: Program, policy: Policy = "structural") -> Graph:
    """Publish a fresh graph for this closed fixture. The maps declare its inventory."""
    store = ContentStore()
    types = {name: store.put("rt05-spg-scalar-v1", name) for name in SCALARS.values()}
    contracts = {}
    for slot, traces in program.contracts.items():
        _check_label(slot)
        if not traces:
            raise RepresentationError("contract needs an explicit nonempty trace set")
        for trace in traces:
            for event in trace:
                _check_label(event)
        contracts[slot] = store.put("rt05-spg-contract-v1", sorted(set(traces)))

    exported_names: set[str] = set()
    operations = {}
    for slot, operation in program.operations.items():
        _check_label(slot)
        _check_label(operation.export)
        if operation.export in exported_names:
            raise RepresentationError(f"duplicate exported name: {operation.export}")
        exported_names.add(operation.export)
        contract = _lookup(contracts, operation.contract, "contract")
        params = [_lookup(types, name, "scalar type") for name in operation.parameters]
        result = _lookup(types, operation.result, "scalar type")
        dependencies = [Dependency("parameter_type", address, str(position))
                        for position, address in enumerate(params)]
        interface = store.put("rt05-spg-interface-v1", {
            "export": operation.export, "parameters": params, "result": result,
        }, [*dependencies, Dependency("result_type", result)])
        operations[slot] = store.put("rt05-spg-operation-v1", {}, [
            Dependency("interface", interface), Dependency("contract", contract),
        ])

    definitions = {}
    for slot, source in program.implementations.items():
        _check_label(slot)
        signature = _lookup(program.operations, source.operation, "operation")
        definitions[slot] = _definition(source, signature, program, operations)
    implementations = publish_definitions(store, definitions, policy)

    # A binding selects one exact implementation for the exact operation. The
    # declared operation is checked here. Conformance is a separate judgment.
    bindings = {}
    for operation, implementation in program.bindings.items():
        op_address = _lookup(operations, operation, "operation")
        chosen = _lookup(program.implementations, implementation, "implementation")
        if chosen.operation != operation:
            raise RepresentationError("binding does not declare the required operation")
        bindings[operation] = store.put("rt05-spg-binding-v1", {}, [
            Dependency("operation", op_address),
            Dependency("implementation", implementations[implementation]),
        ])

    selections = {f"{kind}:{slot}": address
                  for kind, rows in (("contract", contracts), ("operation", operations),
                                     ("implementation", implementations), ("binding", bindings))
                  for slot, address in rows.items()}
    return Graph(store, make_snapshot(selections))


def _targets(graph: Graph, address: str) -> dict[str, str]:
    return {edge.relation: edge.target_hash for edge in graph.store.get(address).dependencies}


def observe(graph: Graph, entry: str, args: tuple[Value, ...], *,
            fuel: int = 64) -> tuple[Value, tuple[str, ...]]:
    """Interpret stored fixture values with left-to-right arguments and lazy branches."""
    trace: list[str] = []
    bindings = {}
    for slot, address in graph.snapshot.selections:
        if slot.startswith("binding:"):
            binding = _targets(graph, address)
            bindings[binding["operation"]] = binding["implementation"]

    def body_at(address: str) -> tuple[list, list]:
        value = graph.store.get(address)
        if value.kind == "rt05-recursive-member-v1":
            group = graph.store.get(_targets(graph, address)["member_of"]).payload
            return group[value.payload["position"]]["body"], group
        return value.payload, []

    def invoke(tokens: list, group: list, arguments: tuple[Value, ...]) -> Value:
        nonlocal fuel
        if fuel <= 0:
            raise FuelExhausted("call budget exhausted")
        fuel -= 1
        _, _, encoded, *references = tokens

        def evaluate(term: list) -> Value:
            match term:
                case ["literal", value]:
                    return value
                case ["argument", position]:
                    return arguments[position]
                case ["add", left, right]:
                    return evaluate(left) + evaluate(right)
                case ["sub", left, right]:
                    return evaluate(left) - evaluate(right)
                case ["eq", left, right]:
                    return evaluate(left) == evaluate(right)
                case ["if", condition, yes, no]:
                    return evaluate(yes if evaluate(condition) else no)
                case ["emit", label, tail]:
                    trace.append(label)
                    return evaluate(tail)
                case [("op" | "pin") as form, index, *operands]:
                    actual = tuple(evaluate(operand) for operand in operands)
                    reference = references[index]
                    if form == "op":
                        target = bindings[reference["external"]]
                    elif "local_call" in reference:
                        return invoke(group[reference["local_call"]]["body"], group, actual)
                    else:
                        target = reference["exact_call"]
                    body, callee_group = body_at(target)
                    return invoke(body, callee_group, actual)
            raise AssertionError("unknown instruction in a compiled body")

        return evaluate(json.loads(encoded["literal"]))

    address = _lookup(graph.snapshot.mapping, f"implementation:{entry}", "entry")
    body, group = body_at(address)
    interface = _targets(graph, body[1]["external"])["interface"]
    parameters = graph.store.get(interface).payload["parameters"]
    expected = tuple(graph.store.get(value).payload for value in parameters)
    if tuple(SCALARS.get(type(arg)) for arg in args) != expected:
        raise RepresentationError("entry arguments do not match the interface")
    return invoke(body, group, args), tuple(trace)
