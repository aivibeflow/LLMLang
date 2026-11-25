"""Admit, interpret and lower a finite structured bootstrap language."""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import operator
import re
from types import MappingProxyType


PROFILES = {"rt21-mask4-v1"}
TYPES = {"Mask4": "uint8_t", "Bool": "bool", "Result": "Result"}
NAMES = re.compile(r"[a-z][a-z0-9_]*")


class InvalidSource(ValueError):
    """The source cannot be interpreted or lowered in this fragment."""


@dataclass(frozen=True)
class Expression:
    kind: str
    type: str
    arguments: tuple = ()
    name: str | None = None


@dataclass(frozen=True)
class Procedure:
    name: str
    parameters: tuple
    body: Expression


@dataclass(frozen=True)
class Program:
    procedures: Mapping[str, Procedure]
    entry: str
    semantic_sha256: str


def require(condition, explanation):
    if not condition:
        raise InvalidSource(explanation)


def json_members(pairs):
    document = {}
    for key, value in pairs:
        require(key not in document, f"duplicate JSON member {key}")
        document[key] = value
    return document


def controlled_name(name):
    return isinstance(name, str) and NAMES.fullmatch(name)


def admit(raw):
    source = json.loads(raw, object_pairs_hook=json_members)
    require(isinstance(source, dict) and set(source) == {"profile", "entry", "functions"},
            "program envelope")
    require(isinstance(source["profile"], str) and source["profile"] in PROFILES, "profile")
    require(controlled_name(source["entry"]) and isinstance(source["functions"], list), "program entry")
    procedures = {}
    for item in source["functions"]:
        require(isinstance(item, dict) and set(item) == {"name", "parameters", "returns", "body"},
                "invalid function declaration")
        name, params, result = (item[key] for key in ("name", "parameters", "returns"))
        require(controlled_name(name) and name not in procedures, "script function name")
        require(isinstance(params, list) and all(controlled_name(parameter) for parameter in params)
                and len(set(params)) == len(params), "parameters must be unique Mask4 bindings")
        require(isinstance(result, str) and result in TYPES, "result type")
        expression = parse_expression(item["body"], set(params), procedures)
        require(expression.type == result, f"wrong result type in {name}")
        procedures[name] = Procedure(name, tuple(params), expression)
    entry = procedures.get(source["entry"])
    require(entry is not None and len(entry.parameters) == 6 and entry.body.type == "Result",
            "entry must accept six Mask4 arguments and return Result")
    canonical = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    return Program(MappingProxyType(procedures), entry.name, sha256(canonical).hexdigest())


def parse_expression(source, params, definitions):
    if type(source) is bool:
        return Expression("constant", "Bool", (source,))
    if type(source) is int:
        require(0 <= source < 16, "Mask4 literal out of range")
        return Expression("constant", "Mask4", (source,))
    if isinstance(source, str):
        require(source in params, "unbound local")
        return Expression("variable", "Mask4", name=source)
    require(isinstance(source, dict) and len(source) == 1, "expression envelope")
    operator, raw = next(iter(source.items()))
    require(isinstance(raw, list), "expression arguments")
    if operator == "call":
        require(raw and controlled_name(raw[0]) and raw[0] in definitions,
                "call must name an earlier procedure")
        target = definitions[raw[0]]
        arguments = tuple(parse_expression(operand, params, definitions) for operand in raw[1:])
        require(len(arguments) == len(target.parameters) and all(arg.type == "Mask4" for arg in arguments),
                "incorrect Mask4 call arguments")
        return Expression("call", target.body.type, arguments, target.name)
    arguments = tuple(parse_expression(operand, params, definitions) for operand in raw)
    types = tuple(argument.type for argument in arguments)
    if operator == "if":
        require(len(types) == 3 and types[0] == "Bool" and types[1] == types[2],
                "if expects a Bool and two same-typed branches")
        return Expression(operator, types[1], arguments)
    if operator in ("eq", "result"):
        require(types == ("Mask4", "Mask4"), "binary Mask4 arguments required")
        return Expression(operator, "Bool" if operator == "eq" else "Result", arguments)
    groups = {"bits_and": "Mask4", "bits_or": "Mask4", "all": "Bool", "any": "Bool"}
    require(operator in groups and len(types) >= 2 and all(kind == groups[operator] for kind in types),
            "unsupported operation or ill-typed arguments")
    return Expression(operator, groups[operator], arguments)


def interpret(program, inputs):
    def call(name, args):
        procedure = program.procedures[name]
        return run(procedure.body, dict(zip(procedure.parameters, args)))

    def run(expression, locals_):
        kind, args = expression.kind, expression.arguments
        if kind == "constant":
            return args[0]
        if kind == "variable":
            return locals_[expression.name]
        if kind == "if":
            guard, yes, no = args
            return run(yes if run(guard, locals_) else no, locals_)
        if kind == "call":
            return call(expression.name, [run(argument, locals_) for argument in args])
        if kind == "all":
            return all(run(argument, locals_) for argument in args)
        if kind == "any":
            return any(run(argument, locals_) for argument in args)
        values = tuple(run(argument, locals_) for argument in args)
        if kind == "result":
            return values
        if kind == "eq":
            return values[0] == values[1]
        combine = operator.and_ if kind == "bits_and" else operator.or_
        accumulator = values[0]
        for value in values[1:]:
            accumulator = combine(accumulator, value)
        return accumulator

    require(len(inputs) == 6 and all(type(item) is int and 0 <= item < 16 for item in inputs),
            "runtime Mask4 carrier")
    return call(program.entry, inputs)


def generate(program):
    joins = {"bits_and": " & ", "bits_or": " | ", "all": " && ", "any": " || ", "eq": " == "}

    def emit(expression):
        kind, args = expression.kind, expression.arguments
        if kind == "constant":
            if expression.type == "Bool":
                return "true" if args[0] else "false"
            return str(args[0])
        if kind == "variable":
            return f"var_{expression.name}"
        values = [emit(argument) for argument in args]
        if kind == "call":
            return f"impl_{expression.name}(" + ", ".join(values) + ")"
        if kind == "if":
            return f"({values[0]} ? {values[1]} : {values[2]})"
        if kind == "result":
            return "(Result){" + ", ".join(values) + "}"
        return "(" + joins[kind].join(values) + ")"

    lines = ["#include <stdbool.h>", "#include <stdint.h>", "#include <stdio.h>",
             "typedef struct { uint8_t status; uint8_t reachable; } Result;",
             f"/* Exact candidate program {program.semantic_sha256}. */"]
    for function in program.procedures.values():
        parameters = ", ".join(f"uint8_t var_{name}" for name in function.parameters) or "void"
        lines.extend([f"static {TYPES[function.body.type]} impl_{function.name}({parameters})",
                      "{", f"    return {emit(function.body)};", "}"])
    variables = ", ".join(f"input[{index}]" for index in range(6))
    lines.extend([
        "int main(void)", "{", "    uint8_t input[6];",
        "    for (;;) {",
        "        size_t size = fread(input, 1, sizeof(input), stdin);",
        "        if (!size && feof(stdin)) return fflush(stdout) == 0 ? 0 : 3;",
        "        if (size != sizeof(input)) return 2;",
        "        for (size_t i = 0; i < sizeof(input); i++)",
        "            if (input[i] >= 16) return 2;",
        f"        Result selected = impl_{program.entry}({variables});",
        "        const uint8_t output[] = { selected.status, selected.reachable };",
        "        if (fwrite(output, 1, sizeof(output), stdout) != sizeof(output)) return 3;",
        "    }", "}",
    ])
    return "\n".join(lines) + "\n"
