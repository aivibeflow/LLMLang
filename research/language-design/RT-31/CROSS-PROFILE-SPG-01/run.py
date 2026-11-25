"""Run a profile-independent exact SPG corpus and independent observation oracle."""
import argparse
from dataclasses import replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sys

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from profiles import FrontendError, PROFILES, parse, render
from src.spg_admission import validate
from src.spg_representation import (
    Implementation, Operation, Prefix, Program, RepresentationError, compile_program, observe,
)
from tests.test_spg_representation import encode


INPUTS = tuple(product((-17, -2, -1, 0, 1, 7, 23), (False, True)))
FORWARD = ("left", "right", "compute")
REVERSED = ("right", "left", "compute")
FALLBACK = ("fallback",)


def make_program(binding, entry, ordered=(FORWARD, REVERSED, FALLBACK)):
    def body(term):
        return Prefix(json.dumps(term, separators=(",", ":")))

    return Program(
        contracts={"provider": (("compute",),), "entry": ordered},
        operations={
            "provider": Operation("Compute", ("Int", "Int"), "Int", "provider"),
            "entry": Operation("Entry", ("Int", "Bool"), "Int", "entry"),
        },
        implementations={
            "primary": Implementation("provider", ("a", "b"),
                                      body(["emit", "compute", ["sub", ["arg", "a"], ["arg", "b"]]])),
            "alternate": Implementation("provider", ("a", "b"),
                body(["emit", "compute", ["add", 5, ["sub", ["arg", "b"], ["arg", "a"]]]])),
            "entry": Implementation("entry", ("x", "choose"), body(entry)),
        },
        bindings={"provider": binding},
    )


def entry_term(mode, delta, adjustment, *, swap=False, parameter="x"):
    x = ["arg", parameter]
    args = [["emit", "left", x], ["emit", "right", ["add", x, delta]]]
    if swap:
        args.reverse()
    return ["if", ["arg", "choose"], [mode, "provider" if mode == "op" else "primary", *args],
            ["emit", "fallback", ["add", x, adjustment]]]


def source_variant(profile, source):
    if profile == "infix/1":
        return f"({source})  # fixture trivia\n"
    if profile == "json-tree/1":
        return json.dumps(json.loads(source), indent=2) + "\n"
    return source.replace("(if ", "(if\n  ", 1) + "\n"


def oracle(mode, binding, delta, adjustment, x, choose):
    if not choose:
        return x + adjustment, FALLBACK
    if mode == "pin" or binding == "primary":
        return -delta, FORWARD
    return delta + 5, FORWARD


def subject(mode, binding, delta, adjustment):
    canonical = entry_term(mode, delta, adjustment)
    program = make_program(binding, canonical)
    baseline = compile_program(program)
    graph_bytes = encode(baseline)
    observations = []
    sources = []
    for origin in PROFILES:
        source = render(origin, canonical)
        original = parse(origin, source)
        assert original == parse(origin, source_variant(origin, source)) == canonical
        for target in PROFILES:
            generated = render(target, original)
            term = parse(target, generated)
            assert term == original and render(origin, term) == source
            graph = compile_program(make_program(binding, term))
            validate(graph)
            assert encode(graph) == graph_bytes, (origin, target)
            for x, choose in INPUTS:
                observed = observe(graph, "entry", (x, choose))
                assert observed == oracle(mode, binding, delta, adjustment, x, choose)
                observations.append(observed)
        sources.append({"profile": origin, "sha256": sha256(source.encode()).hexdigest(),
                        "bytes": len(source.encode()),
                        "trivia_sha256": sha256(source_variant(origin, source).encode()).hexdigest()})

    parameters = ("input", "choose")
    renamed = entry_term(mode, delta, adjustment, parameter=parameters[0])
    for profile in PROFILES:
        converted = parse(profile, render(profile, renamed))
        program = make_program(binding, converted)
        source = replace(program.implementations["entry"], parameters=parameters)
        graph = compile_program(replace(program, implementations={**program.implementations, "entry": source}))
        assert encode(graph) == graph_bytes
    return {"mode": mode, "binding": binding, "delta": delta, "adjustment": adjustment,
            "root": baseline.snapshot.root_hash, "graph_sha256": sha256(graph_bytes).hexdigest(),
            "observations_sha256": sha256(json.dumps(observations).encode()).hexdigest(),
            "profile_sources": sources, "observation_count": len(observations)}


def negative_controls():
    mode, binding, delta, adjustment = "op", "primary", 0, -1
    base = entry_term(mode, delta, adjustment)
    program = make_program(binding, base)
    graph = compile_program(program)
    negatives = {}

    def rejected(callback, error_type, substring):
        try:
            callback()
        except error_type as exc:
            assert substring in str(exc), (substring, exc)
            return exc
        raise AssertionError(("accepted negative control", substring))

    for profile in PROFILES:
        source = render(profile, base)
        broken = rejected(lambda: parse(profile, source[:-1]), FrontendError, "expression")
        assert broken.offset is not None, profile
        unknown = parse(profile, render(profile, entry_term(mode, delta, adjustment, parameter="unknown")))
        rejected(lambda: compile_program(make_program(binding, unknown)), RepresentationError,
                 "unknown parameter")
        bad_type = ["add", True, 5]
        typed = parse(profile, render(profile, bad_type))
        rejected(lambda: compile_program(make_program(binding, typed)), RepresentationError,
                 "expects two Int operands")

        mutation = parse(profile, render(profile, entry_term(mode, delta, adjustment, swap=True)))
        mutated = compile_program(make_program(binding, mutation))
        first = observe(graph, "entry", (1, True))
        second = observe(mutated, "entry", (1, True))
        assert first[0] == second[0] and first[1] == FORWARD and second[1] == REVERSED
        assert mutated.snapshot.root_hash != graph.snapshot.root_hash
        contract_program = make_program(binding, mutation, (FORWARD, FALLBACK))
        outcome = observe(compile_program(contract_program), "entry", (1, True))
        assert outcome[1] not in contract_program.contracts["entry"]
        negatives[profile] = {"syntax_error_offset": broken.offset, "unknown_parameter": "rejected",
                              "type_error": "rejected", "effect_order_only": [first, second],
                              "contract_oracle": "rejected", "mutated_root": mutated.snapshot.root_hash}
    rejected(lambda: parse("s-expression/1", "(add 01)"), FrontendError, "unexpected token")
    rejected(lambda: parse("infix/2", "1"), FrontendError, "unknown syntax profile")
    return negatives


def compare():
    rows = [subject(*case) for case in product(
        ("op", "pin"), ("primary", "alternate"), (-7, -1, 0, 3), (-2, 1),
    )]
    assert len({case["root"] for case in rows}) == len(rows)
    assert all(len({record["sha256"] for record in row["profile_sources"]}) == len(PROFILES) for row in rows)
    return {"format": "rt31-cross-profile-spg/1", "python": sys.version.split()[0],
            "parameters": INPUTS, "profiles": PROFILES, "cases": rows,
            "negative_controls": negative_controls()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    command = parser.parse_args()
    command.output.write_text(json.dumps(compare(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
