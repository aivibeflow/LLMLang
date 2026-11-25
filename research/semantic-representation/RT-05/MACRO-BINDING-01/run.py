#!/usr/bin/env python3
"""Compare native Rust macro binding with source, expanded and resolved SPG identities."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

RUST_COMMIT = "4eb161250e340c8f48f66e2b929ef4a5bed7c181"
INPUTS = ((5, 11), (-2, 4), (7, -9))
EMITTERS = """\
fn first(value: i32) { println!("first:{value}"); }
fn second(value: i32) { println!("second:{value}"); }
"""
MAIN = """\
fn main() {
    for (x, y) in [(5, 11), (-2, 4), (7, -9)] {
        println!("result:{}", subject(x, y));
    }
}
"""


def digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def make_source(capture, surface, names, layout, order):
    outside, inside = ("temporary", "shadow") if names == "long" else ("item", "near")
    definition, inner_definition = "", ""
    if surface == "definition":
        inside = outside
        macro = f"macro_rules! select {{ () => {{ {outside} }} }}"
        if capture == "outside":
            definition = macro
        else:
            inner_definition = macro
        selected = "select!()"
    else:
        selected = outside if capture == "outside" else inside
        if surface == "metavariable":
            definition = "macro_rules! select { ($operand:ident) => { $operand } }"
            selected = f"select!({selected})"

    first = f"        first({selected});"
    second = f"        second({inside});"
    effects = (first, second) if order == "first" else (second, first)
    padding = "" if layout == "tight" else "        // presentation-only comment\n\n"
    return (
        "#![allow(unused_macros, unused_variables)]\n" + EMITTERS
        + "fn subject(x: i32, y: i32) -> i32 {\n"
        + f"    let {outside} = x;\n"
        + (f"    {definition}\n" if definition else "") + "    {\n"
        + f"        let {inside} = y;\n"
        + (f"        {inner_definition}\n" if inner_definition else "")
        + padding + "\n".join(effects)
        + "\n    }\n    x\n}\n" + MAIN
    )


def expanded_tokens(text):
    """Compare expanded tokens after removing retained macro declarations."""
    pattern = r"(?m)^ *macro_rules! select \{[^\n]*\}\n"
    without_declarations = re.sub(pattern, "", text)
    if "macro_rules!" in without_declarations:
        raise ValueError("Unexpected retained macro declaration in expansion")
    return " ".join(re.findall(r"\w+|[^\s\w]", without_declarations))


def subject_mir(text):
    matched = re.search(
        r"^fn subject\(_1: i32, _2: i32\) -> i32 \{\n(.*?)^\}", text, re.M | re.S,
    )
    if matched is None:
        raise ValueError("Expected a typed subject in the MIR dump")
    return matched.group(0)


def project_graph(text):
    """Resolve typed local copies and follow the explicitly supported call continuations."""
    blocks = dict(re.findall(r"^    bb(\d+): \{\n(.*?)^    \}", text, re.M | re.S))
    types = dict(re.findall(r"^ +let (?:mut )?(_\d+): (i32|\(\));", text, re.M))
    types.update({"_1": "i32", "_2": "i32"})
    env = {"_1": 0, "_2": 1}
    effects = []
    current = "0"
    visited = set()
    while current not in visited:
        visited.add(current)
        statements = [line.strip() for line in blocks[current].splitlines() if line.strip()]
        for statement in statements[:-1]:
            storage = re.fullmatch(r"Storage(?:Live|Dead)\((_\d+)\);", statement)
            if storage is not None:
                env.pop(storage[1], None)
                continue
            unit = re.fullmatch(r"(_\d+) = const \(\);", statement)
            if unit is not None and types[unit[1]] == "()":
                continue
            copy = re.fullmatch(r"(_\d+) = (copy|move) (_\d+);", statement)
            if copy is None:
                raise ValueError(f"Unsupported MIR statement {statement!r}")
            target, mode, original = copy.groups()
            if types[target] != "i32" or types[original] != "i32":
                raise ValueError(f"Unmodeled MIR copy types in {statement!r}")
            argument = env.pop(original) if mode == "move" else env[original]
            env[target] = argument

        terminal = statements[-1]
        jump = re.fullmatch(
            r"(_\d+) = (first|second)\((copy|move) (_\d+)\)"
            r" -> \[return: bb(\d+), unwind continue\];", terminal,
        )
        if jump is not None:
            target, callee, mode, operand, current = jump.groups()
            if types[target] != "()" or types[operand] != "i32":
                raise ValueError(f"Unmodeled MIR call types in {terminal!r}")
            argument = env.pop(operand) if mode == "move" else env[operand]
            effects.append([callee, argument])
        elif terminal == "return;" and visited == set(blocks) and len(effects) == 2:
            return {"inputs": ["i32", "i32"], "ordered_calls": effects,
                    "return_argument": env["_0"], "emitter_source": digest(EMITTERS)}
        else:
            raise ValueError(f"Unsupported MIR terminal {terminal!r}")
    raise ValueError("Unexpected cyclic MIR")


def evaluate(graph):
    return [
        [*(f"{effect}:{pair[argument]}" for effect, argument in graph["ordered_calls"]),
         f"result:{pair[graph['return_argument']]}"]
        for pair in INPUTS
    ]


def run_command(args, root, *, inspecting=False):
    env = os.environ.copy()
    if inspecting:
        env["RUSTC_BOOTSTRAP"] = "1"
    done = subprocess.run(args, cwd=root, env=env, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if done.stderr:
        raise ValueError(f"Unexpected diagnostics during {args!r}: {done.stderr}")
    return done.stdout


def inspect_version(compiler):
    version = run_command([compiler, "--version", "--verbose"], None)
    if f"commit-hash: {RUST_COMMIT}\n" not in version:
        raise ValueError(f"Expected pinned Rust {RUST_COMMIT}, got {version}")
    return version.splitlines()


def report(compiler):
    rust = inspect_version(compiler)
    cases = []
    with TemporaryDirectory(prefix="llmlang-macro-binding-") as temporary:
        root = Path(temporary)
        invocation = [compiler, "--edition=2021", "--crate-name", "macro_binding", "fixture.rs"]
        for capture, surface, names, layout, order in product(
            ("outside", "inside"), ("definition", "metavariable", "explicit"),
            ("short", "long"), ("tight", "spaced"), ("first", "second"),
        ):
            source = make_source(capture, surface, names, layout, order)
            (root / "fixture.rs").write_text(source, encoding="utf-8")
            expanded = run_command([*invocation, "-Zunpretty=expanded"], root, inspecting=True)
            hygiene = run_command([*invocation, "-Zunpretty=expanded,hygiene"], root, inspecting=True)
            run_command([*invocation, "-Zmir-opt-level=0", "--emit=mir=fixture.mir"],
                        root, inspecting=True)
            mir = subject_mir((root / "fixture.mir").read_text(encoding="utf-8"))
            graph = project_graph(mir)
            run_command([*invocation, "-C", "opt-level=0", "-o", "fixture"], root)
            native = run_command(["./fixture"], root).splitlines()
            observed = [native[start:start+3] for start in range(0, len(native), 3)]
            expected_calls = [["first", 0 if capture == "outside" else 1], ["second", 1]]
            if order == "second":
                expected_calls.reverse()
            assert graph["ordered_calls"] == expected_calls and graph["return_argument"] == 0
            assert evaluate(graph) == observed, (capture, surface, names, layout, order, observed)
            cases.append({
                "fixture": "/".join((capture, surface, names, layout, order)), "source": source,
                "keys": {"source": digest(source), "expanded": digest(expanded),
                         "expanded_without_definitions": digest(expanded_tokens(expanded)),
                         "expansion_hygiene": digest(hygiene), "mir": digest(mir),
                         "bound_spg": digest(json.dumps(graph, sort_keys=True))},
                "graph": graph, "observed": observed,
            })

    policies = list(cases[0]["keys"])
    counts = {policy: Counter() for policy in policies}
    witnesses = {}
    for first, second in combinations(cases, 2):
        same_observation = first["observed"] == second["observed"]
        for policy in policies:
            same_address = first["keys"][policy] == second["keys"][policy]
            category = {
                (True, True): "same_observation_same_key",
                (True, False): "same_observation_distinct_key",
                (False, True): "different_observation_same_key",
                (False, False): "different_observation_distinct_key",
            }[same_observation, same_address]
            counts[policy][category] += 1
            if category == "different_observation_same_key":
                witnesses.setdefault(policy, [first["fixture"], second["fixture"]])

    assert counts["expanded_without_definitions"]["different_observation_same_key"] > 0
    assert counts["bound_spg"]["same_observation_distinct_key"] == 0
    assert counts["bound_spg"]["different_observation_same_key"] == 0
    return {
        "schema": "llmlang-native-macro-binding/1", "toolchain": rust,
        "replay_sha256": digest(Path(__file__).read_text(encoding="utf-8")),
        "inputs": INPUTS, "emitter_source": EMITTERS, "native_observations": len(cases) * len(INPUTS),
        "fixture_pairs": sum(counts[policies[0]].values()), "counts": {
            policy: dict(sorted(counts[policy].items())) for policy in policies
        }, "witnesses": witnesses, "fixtures": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    args = parser.parse_args()
    results = report(args.rustc)
    fixtures = results.pop("fixtures")
    print(json.dumps(results, indent=2).removesuffix("\n}") + ',\n  "fixtures": [')
    print(",\n".join("    " + json.dumps(row) for row in fixtures))
    print("  ]\n}")


if __name__ == "__main__":
    main()
