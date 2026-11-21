"""Independent admission experiment for stored, acyclic RT-05 SPG values."""

import json
import re

from .semantic_graph import Dependency, canonical_bytes
from .spg_representation import Graph, RepresentationError, SCALARS


KINDS = {
    "contract": "rt05-spg-contract-v1",
    "operation": "rt05-spg-operation-v1",
    "implementation": "rt05-definition-v1",
    "binding": "rt05-spg-binding-v1",
}


def _require(condition, reason):
    if not condition:
        raise RepresentationError(reason)


def _label(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.]*", value)


def _term_type(term, parameters, call):
    match term:
        case ["literal", value] if type(value) in SCALARS:
            _require(type(value) is bool or -(2**31) <= value < 2**31, "literal out of range")
            return SCALARS[type(value)]
        case ["argument", pos] if type(pos) is int and 0 <= pos < len(parameters):
            return parameters[pos]
        case [("add" | "sub" | "eq") as form, left, right]:
            _require(_term_type(left, parameters, call) == "Int"
                    and _term_type(right, parameters, call) == "Int", "arithmetic operand type")
            return "Bool" if form == "eq" else "Int"
        case ["if", condition, yes, no]:
            _require(_term_type(condition, parameters, call) == "Bool", "condition type")
            yes_type = _term_type(yes, parameters, call)
            _require(yes_type == _term_type(no, parameters, call), "branch type mismatch")
            return yes_type
        case ["emit", event, tail] if _label(event):
            return _term_type(tail, parameters, call)
        case [("op" | "pin") as mode, index, *operands] if type(index) is int:
            expected, result = call(mode, index)
            _require(tuple(_term_type(arg, parameters, call) for arg in operands) == expected,
                    "call argument types")
            return result
        case _:
            raise RepresentationError("unsupported instruction")


def validate(graph: Graph) -> None:
    """Check selected values after persistence validation, without parsing source."""
    selected = {kind: {} for kind in KINDS}
    for slot, address in graph.snapshot.selections:
        kind, _, name = slot.partition(":")
        _require(kind in KINDS and _label(name), "invalid selection")
        _require(graph.store.get(address).kind == KINDS[kind], f"unsupported {kind} value")
        selected[kind][name] = address

    def edges(address, *relations):
        value = graph.store.get(address)
        actual = {e.relation: e.target_hash for e in value.dependencies}
        _require(value.payload == {} and tuple(value.dependencies) ==
                tuple(sorted(Dependency(r, actual[r]) for r in actual))
                and actual.keys() == set(relations), "unexpected typed edges")
        return tuple(actual[r] for r in relations)

    def scalar(address):
        value = graph.store.get(address)
        _require(value.kind == "rt05-spg-scalar-v1" and not value.dependencies
                and value.payload in ("Int", "Bool"), "invalid scalar")
        return value.payload

    contracts = set(selected["contract"].values())
    for address in sorted(contracts):
        value = graph.store.get(address)
        traces = value.payload
        _require(isinstance(traces, list) and traces and not value.dependencies
                and all(isinstance(trace, list) and all(map(_label, trace)) for trace in traces)
                and [tuple(trace) for trace in traces] == sorted({tuple(trace) for trace in traces}),
                "invalid contract trace set")

    signatures = {}
    exports = set()
    for address in selected["operation"].values():
        interface, contract = edges(address, "interface", "contract")
        _require(contract in contracts, "contract missing from selection")
        value = graph.store.get(interface)
        row = value.payload
        _require(value.kind == "rt05-spg-interface-v1" and isinstance(row, dict)
                and row.keys() == {"export", "parameters", "result"} and _label(row["export"])
                and isinstance(row["parameters"], list)
                and all(isinstance(item, str) for item in [*row["parameters"], row["result"]]),
                "invalid interface")
        _require(row["export"] not in exports, "duplicate export")
        exports.add(row["export"])
        expected = [Dependency("parameter_type", p, str(i)) for i, p in enumerate(row["parameters"])]
        expected.append(Dependency("result_type", row["result"]))
        _require(value.dependencies == tuple(sorted(expected)), "interface edge mismatch")
        signatures[address] = (tuple(map(scalar, row["parameters"])), scalar(row["result"]))

    bodies = {}
    for address in sorted(set(selected["implementation"].values())):
        tokens = graph.store.get(address).payload
        _require(isinstance(tokens, list) and len(tokens) >= 3
                and tokens[0] == {"literal": "rt05-spg-body-v1"}, "invalid body envelope")
        owner, encoded, *references = tokens[1:]
        _require(isinstance(owner, dict) and owner.keys() == {"external"}
                and isinstance(owner["external"], str) and owner["external"] in signatures,
                "body owner missing from selection")
        _require(isinstance(encoded, dict) and encoded.keys() == {"literal"}
                and isinstance(encoded["literal"], str), "invalid body encoding")
        bodies[address] = owner["external"], encoded["literal"], references

    for name, address in selected["binding"].items():
        operation, provider = edges(address, "operation", "implementation")
        _require(operation == selected["operation"].get(name) and provider in bodies
                and bodies[provider][0] == operation, "binding provider mismatch")
    bound = {selected["operation"][name] for name in selected["binding"]}

    for address, (owner, encoded, references) in bodies.items():
        targets = {owner}
        consumed = 0

        def call(mode, index):
            nonlocal consumed
            _require(index == consumed and index < len(references), "invalid call position")
            consumed += 1
            key = "external" if mode == "op" else "exact_call"
            reference = references[index]
            _require(isinstance(reference, dict) and reference.keys() == {key}
                    and isinstance(reference[key], str), "invalid call reference")
            target = reference[key]
            targets.add(target)
            if mode == "op":
                _require(target in bound, "operation binding missing")
                return signatures[target]
            _require(target in bodies, "exact call target missing from selection")
            return signatures[bodies[target][0]]

        parameters, result = signatures[owner]
        try:
            term = json.loads(encoded)
            _require(canonical_bytes(term).decode("utf-8") == encoded, "noncanonical body encoding")
            _require(_term_type(term, parameters, call) == result, "body result type")
        except (ValueError, RecursionError) as exc:
            if isinstance(exc, RepresentationError):
                raise
            raise RepresentationError("invalid serialized body") from exc
        _require(consumed == len(references), "unused call references")
        _require(graph.store.get(address).dependencies ==
                tuple(Dependency("uses", target) for target in sorted(targets)),
                "body reference/edge mismatch")
