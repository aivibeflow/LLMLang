"""Replay frontend, generator, elaboration and validation witnesses."""
import argparse
from itertools import product
import json
from pathlib import Path
from subprocess import check_output

from contract import (
    Failed, HERE, PROFILES, Source, check_semantics, diagnostic_record, digest, elaborate,
    frontend, generate, normalize, render,
)
from replay import INPUTS, encode, entry_term, make_program, observe, oracle
from run import source_variant

ROOT = HERE.parents[3]
PIN = "d2c80ff58323a819a54e0455efbaeea41b3c7223"


def fresh(profile, term):
    return Source(profile, render(profile, term).encode())


def parse(source):
    return frontend(source, source.identity)


def trivia(source):
    text = source.data.decode()
    decorated = (json.dumps(json.loads(text), indent=2) + "\n" if source.profile == "hybrid/1"
                 else source_variant(source.profile, text))
    return Source(source.profile, decorated.encode())


def expect(action, stage, source, *, anchor=None, path=(), message=None):
    try:
        action()
    except Failed as error:
        record = diagnostic_record(error)
        assert record["phase"] == stage, record
        assert record["source_sha256"] == source.identity and record["profile"] == source.profile
        assert record["path"] == list(path), record
        if message:
            assert message in record["message"], record
        span = record["location"]
        if anchor is not None:
            assert span is not None, record
            assert source.data[span["start_byte"]:span["end_byte"]] == anchor, record
            prefix = source.data[:span["start_byte"]]
            assert span["line"] == prefix.count(b"\n") + 1
            assert span["byte_column"] == len(prefix.rsplit(b"\n", 1)[-1])
        return record
    raise AssertionError((stage, source))


def controls():
    evidence = {}
    for profile in PROFILES:
        def compile_entry(term):
            return elaborate(parse(fresh(profile, term)), lambda value: make_program("primary", value))

        canonical = entry_term("op", 0, -1)
        clean = fresh(profile, canonical)
        malformed = Source(profile, clean.data[:-1])
        absent = entry_term("op", 0, -1, parameter="unbound")
        bad_type = ["add", True, 1]
        mutation = entry_term("op", 0, -1, swap=True)
        swapped = fresh(profile, mutation)
        parsed_mutation = parse(swapped)
        graph = compile_entry(mutation)
        original = oracle("op", "primary", 0, -1, 0, True)
        witnessed = observe(graph, "entry", (0, True))
        assert witnessed[0] == original[0] and witnessed[1] != original[1]
        diagnostics = {
            "truncated": expect(lambda: parse(malformed), "frontend", malformed),
            "source-mismatch": expect(lambda: frontend(malformed, clean.identity), "source", malformed),
            "generator-version": expect(lambda: generate(parse(clean), "unreleased/2"), "generation", clean),
            "abstract-shape": expect(lambda: normalize(clean, ["missing-form", 1]), "normalization", clean),
            "unknown-argument": expect(lambda: compile_entry(absent), "elaboration", fresh(profile, absent),
                                       message="unknown parameter"),
            "invalid-operand": expect(lambda: compile_entry(bad_type), "elaboration", fresh(profile, bad_type),
                                      message="Int"),
            "ordered-observation": expect(lambda: check_semantics(
                parsed_mutation, graph, lambda _: witnessed == original), "semantic-validation", swapped),
        }
        assert diagnostics["truncated"]["location"] is not None
        assert diagnostics["unknown-argument"]["location"] is None
        assert diagnostics["invalid-operand"]["location"] is None
        evidence[profile] = diagnostics

    special = (
        ("outer-json", Source("hybrid/1", b'{"profile":@}'), "frontend", b"@", ()),
        ("outer-version", Source("hybrid/1", b'{"profile":"hybrid/2","expression":{}}'), "profile", b'"hybrid/2"', ("profile",)),
        ("inner-direct", Source("hybrid/1",
            b'{\n "profile":"hybrid/1",\n "expression":{"kind":"scalar","expr":"x + )"}}'),
            "frontend", b")", ("expression", "expr")),
        ("inner-escaped", Source("hybrid/1",
            b'{\n "profile":"hybrid/1",\n "expression":{"kind":"scalar","expr":"x \\u002b \\u0029"}}'),
            "frontend", b"\\u0029", ("expression", "expr")),
        ("nested-field", Source("hybrid/1",
            b'{"profile":"hybrid/1","expression":{"kind":"call","binding":"op","target":"provider",'
            b'"arguments":[{"kind":"scalar","expr":false}]}}'),
            "frontend", b"false", ("expression", "arguments", 0, "expr")),
        ("precise-sexp", Source("s-expression/1", b"(add\n 1 @)"), "frontend", b"@", ()),
        ("precise-infix", Source("infix/1", b"(1\n + @)"), "frontend", b"@", ()),
        ("precise-json-tree", Source("json-tree/1", b'["add",\n 1, @]'), "frontend", b"@", ()),
    )
    evidence["exact-locations"] = {
        label: expect(lambda: parse(source), stage, source, anchor=anchor, path=path)
        for label, source, stage, anchor, path in special
    }
    for label, detail in evidence["exact-locations"].items():
        assert detail["location"]["precision"] == ("field" if label in {"outer-version", "nested-field"} else "point")
    refused_version = Source("infix/2", b"1")
    bad_utf = Source("infix/1", b"\xff")
    ambiguous_label = fresh("json-tree/1", ["arg", "x-y"])
    evidence["additional"] = {
        "unknown-profile": expect(lambda: parse(refused_version), "profile", refused_version),
        "invalid-utf8": expect(lambda: parse(bad_utf), "source", bad_utf),
        "lossy-conversion": expect(lambda: generate(parse(ambiguous_label), "infix/1"),
                                  "generation", ambiguous_label, message="changes normalized expression"),
    }
    return evidence


def compare():
    routes = 0
    observations = 0
    subjects = []
    for index, (mode, provider, delta) in enumerate(product(("op", "pin"), ("primary", "alternate"), (-1, 3))):
        subject = entry_term(mode, delta, 1)
        graph_digest = None
        for origin in PROFILES:
            plain = fresh(origin, subject)
            variant = trivia(plain)
            assert variant.identity != plain.identity
            for source in (plain, variant):
                parsed = parse(source)
                for target in PROFILES:
                    generated = generate(parsed, target)
                    assert (generated.origin_profile, generated.origin_sha256) == (origin, source.identity)
                    assert generated.normalized_digest == parsed.normalized_digest
                    roundtrip = parse(generated.source)
                    assert roundtrip.normalized == parsed.normalized and generated.source.profile == target
                    graph = elaborate(roundtrip, lambda term: make_program(provider, term))
                    encoded = digest(encode(graph))
                    if graph_digest is None:
                        graph_digest = encoded
                    assert encoded == graph_digest
                    check_semantics(roundtrip, graph, lambda value: all(
                        observe(value, "entry", (x, choose)) == oracle(mode, provider, delta, 1, x, choose)
                        for x, choose in INPUTS))
                    observations += len(INPUTS)
                    routes += 1
        subjects.append({"index": index, "mode": mode, "provider": provider,
                         "delta": delta, "canonical_graph": graph_digest})
    return {"subjects": subjects, "routes": routes, "value_and_trace_observations": observations,
            "diagnostics": controls()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source_files = (
        *sorted((HERE.parent / "HYBRID-PROFILE-01").glob("*.py")),
        HERE.parent / "CROSS-PROFILE-SPG-01/profiles.py",
        HERE.parent / "CROSS-PROFILE-SPG-01/run.py",
        ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_admission.py",
        ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_representation.py",
    )
    pins = {}
    for source in source_files:
        path = source.relative_to(ROOT).as_posix()
        archived = check_output(["git", "show", f"{PIN}:{path}"], cwd=ROOT)
        assert source.read_bytes() == archived
        pins[path] = digest(archived)
    args.output.write_text(json.dumps({"source_revision": PIN, "dependencies": pins, **compare()},
                                      indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
