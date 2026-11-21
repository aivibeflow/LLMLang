"""Normalize the existing typed scalar SPG into an ordered instruction fixture."""

from dataclasses import dataclass
import json

from .semantic_graph import digest
from .spg_representation import FuelExhausted, Graph, RepresentationError, SCALARS, Value


Instruction = tuple


@dataclass(frozen=True)
class Function:
    args: tuple[str, ...]
    code: tuple[Instruction, ...]


@dataclass(frozen=True)
class Artifact:
    entry: str
    functions: tuple[tuple[str, Function], ...]

    @property
    def identity(self):
        return digest(("rt09-ordered-lowering/1", self.entry,
                       [(key, fn.args, fn.code) for key, fn in self.functions]))


def lower(graph: Graph, slot: str) -> Artifact:
    """Lower the reachable closure of compiler-produced SPG values."""
    store = graph.store
    selections = graph.snapshot.mapping
    entry = selections.get(f"implementation:{slot}")
    if entry is None:
        raise RepresentationError(f"unknown entry: {slot}")

    def edges(address):
        return {edge.relation: edge.target_hash for edge in store.get(address).dependencies}

    bindings = {}
    for name, address in selections.items():
        if name.startswith("binding:"):
            binding = edges(address)
            bindings[binding["operation"]] = binding["implementation"]

    functions = {}
    pending = [entry]
    while pending:
        address = pending.pop()
        if address in functions:
            continue
        definition = store.get(address)
        if definition.kind != "rt05-definition-v1":
            raise RepresentationError("ordered lowering does not support exact recursive groups")
        _, owner, encoded, *refs = definition.payload
        interface = store.get(edges(owner["external"])["interface"]).payload
        args = tuple(store.get(item).payload for item in interface["parameters"])
        code = []
        result_register = len(args)
        next_register = result_register + 1

        def emit(term, destination):
            nonlocal next_register

            def operand(child):
                nonlocal next_register
                register = next_register
                next_register += 1
                emit(child, register)
                return register

            match term:
                case ["literal", value]:
                    code.append(("constant", destination, value))
                case ["argument", index]:
                    code.append(("copy", destination, index))
                case [("add" | "sub" | "eq") as op, left, right]:
                    lhs = operand(left)
                    rhs = operand(right)
                    code.append((op, destination, lhs, rhs))
                case ["emit", label, body]:
                    code.append(("emit", label))
                    emit(body, destination)
                case ["if", condition, yes, no]:
                    test = operand(condition)
                    branch = len(code)
                    code.append(())
                    emit(yes, destination)
                    jump = len(code)
                    code.append(())
                    code[branch] = ("branch-false", test, len(code))
                    emit(no, destination)
                    code[jump] = ("jump", len(code))
                case [("op" | "pin") as mode, pos, *children]:
                    ref = refs[pos]
                    target = (bindings[ref["external"]] if mode == "op" else ref["exact_call"])
                    pending.append(target)
                    operands = tuple(operand(child) for child in children)
                    code.append(("call", destination, target, operands))
                case _:
                    raise RepresentationError("unsupported lowered expression")

        emit(json.loads(encoded["literal"]), result_register)
        code.append(("return", result_register))
        functions[address] = Function(args, tuple(code))
    return Artifact(entry, tuple(sorted(functions.items())))


def execute(artifact: Artifact, values: tuple[Value, ...], *, fuel: int = 64):
    functions = dict(artifact.functions)
    if tuple(SCALARS.get(type(value)) for value in values) != functions[artifact.entry].args:
        raise RepresentationError("entry arguments do not match the interface")
    trace = []

    def run(address, args):
        nonlocal fuel
        if fuel <= 0:
            raise FuelExhausted("call budget exhausted")
        fuel -= 1
        registers = dict(enumerate(args))
        pc = 0
        code = functions[address].code
        while True:
            instruction = code[pc]
            pc += 1
            match instruction:
                case ("constant", target, value):
                    registers[target] = value
                case ("copy", target, source):
                    registers[target] = registers[source]
                case ("add", target, left, right):
                    registers[target] = registers[left] + registers[right]
                case ("sub", target, left, right):
                    registers[target] = registers[left] - registers[right]
                case ("eq", target, left, right):
                    registers[target] = registers[left] == registers[right]
                case ("emit", label):
                    trace.append(label)
                case ("branch-false", test, target) if not registers[test]:
                    pc = target
                case ("branch-false", _, _):
                    pass
                case ("jump", target):
                    pc = target
                case ("call", target, callee, operands):
                    registers[target] = run(callee, tuple(registers[arg] for arg in operands))
                case ("return", source):
                    return registers[source]
                case _:
                    raise RepresentationError("unsupported ordered instruction")

    result = run(artifact.entry, values)
    return result, tuple(trace)
