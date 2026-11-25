"""Exercise all four profile conversions against the existing independent SPG oracle."""
import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from statistics import median
import sys

HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / "CROSS-PROFILE-SPG-01"
sys.path.insert(0, str(LEGACY))
# The adapter uses the previous profile contract and its independent arithmetic/trace fixture.
from run import (INPUTS, entry_term, make_program, oracle, encode, validate as validate_graph,
                 RepresentationError, compile_program, observe)
from profiles import PROFILES as EXISTING, parse as parse_legacy, render as render_legacy
import hybrid

PROFILES = (*EXISTING, hybrid.VERSION)


def parse(profile, source):
    return hybrid.parse(source) if profile == hybrid.VERSION else parse_legacy(profile, source)


def render(profile, term):
    return hybrid.render(term) if profile == hybrid.VERSION else render_legacy(profile, term)


def digest(data):
    return sha256(data).hexdigest()


def expect(callback, error, substring):
    try:
        callback()
    except error as err:
        assert substring in str(err), (substring, err)
        return err
    raise AssertionError(f"expected {error.__name__}: {substring}")


def controls():
    term = entry_term("op", 0, -1)
    source = hybrid.render(term)
    pretty = json.dumps(json.loads(source), indent=2)
    assert hybrid.parse(pretty) == term and digest(pretty.encode()) != digest(source.encode())
    outer = expect(lambda: hybrid.parse(source[:-1]), hybrid.HybridError, "structured expression")
    assert outer.offset is not None and outer.inner_offset is None

    modified = json.loads(source)
    modified["expression"]["condition"]["expr"] = "x +"
    problem = expect(lambda: hybrid.parse(json.dumps(modified)), hybrid.HybridError, "embedded scalar")
    assert problem.path == ("expression", "condition", "expr")
    assert problem.offset is None and problem.inner_offset is not None

    modified["expression"]["condition"]["expr"] = 'emit("effect", True)'
    expect(lambda: hybrid.parse(json.dumps(modified)), hybrid.HybridError, "effects require")
    modified = json.loads(source)
    modified["profile"] = "hybrid/2"
    expect(lambda: hybrid.parse(json.dumps(modified)), hybrid.HybridError, "unsupported hybrid")
    expect(lambda: hybrid.parse(source.replace('"profile":', '"profile":"hybrid/1","profile":', 1)),
           hybrid.HybridError, "duplicate JSON")
    modified = json.loads(source)
    modified["expression"]["unknown"] = "extra"
    expect(lambda: hybrid.parse(json.dumps(modified)), hybrid.HybridError, "expression node")

    unknown = hybrid.parse(hybrid.render(entry_term("op", 0, -1, parameter="absent")))
    expect(lambda: compile_program(make_program("primary", unknown)), RepresentationError, "unknown parameter")
    wrong_type = hybrid.parse(hybrid.render(["add", True, 1]))
    expect(lambda: compile_program(make_program("primary", wrong_type)), RepresentationError, "Int")

    swapped = hybrid.parse(hybrid.render(entry_term("op", 0, -1, swap=True)))
    observed = observe(compile_program(make_program("primary", swapped)), "entry", (0, True))
    baseline = oracle("op", "primary", 0, -1, 0, True)
    assert observed[0] == baseline[0] and observed[1] == ("right", "left", "compute")
    assert observed[1] != baseline[1]

    nested = ["add", ["emit", "left", ["arg", "x"]], ["emit", "right", 1]]
    for profile, (x, choose) in product(PROFILES, INPUTS):
        compiled = compile_program(make_program(
            "primary", parse(profile, render(profile, nested)), ordered=(("left", "right"),)
        ))
        assert observe(compiled, "entry", (x, choose)) == (x + 1, ("left", "right"))

    return {
        "formatting_preserves_graph_input": True,
        "outer_json_error_offset": outer.offset,
        "embedded_error_path": problem.path,
        "embedded_error_relative_offset": problem.inner_offset,
        "effect_inside_scalar": "refused",
        "alternate_profile_version": "refused",
        "duplicate_field": "refused",
        "unknown_key": "refused",
        "unknown_parameter": "elaboration error",
        "invalid_operand": "type error",
        "swapped_arguments": "equal integer, different ordered trace",
        "arithmetic_with_ordered_nested_effect_observations": len(PROFILES) * len(INPUTS),
    }


def compare():
    subjects = []
    source_metrics = {profile: [] for profile in PROFILES}
    archived = json.loads((LEGACY / "evidence.json").read_text())
    for previous in archived["cases"]:
        mode, binding, delta, adjustment = (
            previous[key] for key in ("mode", "binding", "delta", "adjustment")
        )
        expected_term = entry_term(mode, delta, adjustment)
        expected_bytes = encode(compile_program(make_program(binding, expected_term)))
        assert digest(expected_bytes) == previous["graph_sha256"]
        observations = []
        for origin in PROFILES:
            source = render(origin, expected_term)
            source_metrics[origin].append(len(source.encode()))
            original = parse(origin, source)
            assert original == expected_term
            for target in PROFILES:
                converted = parse(target, render(target, original))
                assert converted == original
                assert render(origin, converted) == source
                graph = compile_program(make_program(binding, converted))
                validate_graph(graph)
                assert encode(graph) == expected_bytes
                for x, choose in INPUTS:
                    actual = observe(graph, "entry", (x, choose))
                    assert actual == oracle(mode, binding, delta, adjustment, x, choose)
                    observations.append(actual)
        subjects.append({
            "mode": mode, "binding": binding, "delta": delta, "adjustment": adjustment,
            "graph_digest": digest(expected_bytes), "observation_digest": digest(json.dumps(observations).encode()),
            "observation_count": len(observations),
        })
    count = sum(subject["observation_count"] for subject in subjects)
    assert count == 7168
    return {
        "profiles": PROFILES, "subjects": len(subjects), "observations": count,
        "generated_bytes": {name: [min(sizes), median(sizes), max(sizes)]
                            for name, sizes in source_metrics.items()},
        "controls": controls(), "cases": subjects,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(), indent=2) + "\n")


if __name__ == "__main__":
    main()
