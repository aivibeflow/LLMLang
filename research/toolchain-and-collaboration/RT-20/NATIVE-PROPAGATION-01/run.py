"""Validate exact caller propagation using the graph prototype and generated native C."""
import argparse
from dataclasses import dataclass, replace
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(GRAPH))
from src.candidate_graph_audit import audit_candidate_snapshot_graph
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, make_snapshot

ENTRIES = ("chain", "legacy", "modern", "multi", "join", "peer")
INPUTS = range(-16, 17)


@dataclass(frozen=True)
class Body:
    declaration: str
    bias: int = 0
    calls: tuple[tuple[str, int], ...] = ()
    label: str = "original"


def bodies(migrated):
    functions = {
        "old-leaf": Body("leaf", bias=1),
        "old-shared": Body("shared", calls=(("old-leaf", 1),)),
    }
    if migrated:
        functions["new-leaf"] = Body("leaf", bias=3)
        functions["new-shared"] = Body("shared", calls=(("new-leaf", 1),))
    selected_leaf = "new-leaf" if migrated else "old-leaf"
    selected_shared = "new-shared" if migrated else "old-shared"
    functions.update({
        "chain": Body("chain", calls=((selected_shared, 1),)),
        "legacy": Body("legacy", calls=(("old-shared", 2),)),
        "modern": Body("modern", calls=((selected_shared, 2),)),
        "multi": Body("multi", calls=(("old-leaf", 1), (selected_leaf, 3))),
        "left": Body("left", calls=(("old-shared", 1),)),
        "right": Body("right", calls=((selected_shared, 2),)),
        "join": Body("join", calls=(("left", 1), ("right", 1))),
        "peer": Body("peer", bias=9),
    })
    return functions


def cases():
    exact = bodies(True)
    fork_everywhere = dict(exact, legacy=replace(exact["legacy"], calls=(("new-shared", 2),)),
                           left=replace(exact["left"], calls=(("new-shared", 1),)))
    swapped = dict(exact, multi=replace(exact["multi"], calls=(("new-leaf", 1), ("old-leaf", 3))))
    equivalent_leaf = dict(exact, **{"new-leaf": replace(exact["new-leaf"], label="alternate")})
    return {
        "baseline": bodies(False),
        "exact": exact,
        "all-old": bodies(False),
        "unconditional-shared-fork": fork_everywhere,
        "swapped-call-sites": swapped,
        "same-outputs-other-leaf": equivalent_leaf,
    }


def declaration(kind, name, content, **attributes):
    return dict(format=FORMAT, schema_version=SCHEMA_VERSION, kind=kind,
                declaration_id=name, content=content, **attributes)


def materialize(store, contract, functions):
    hashes = {}
    provides = [{"reference_id": "protocol", "relation": "provides_contract",
                 "target_hash": contract, "target_kind": "contract"}]
    for name, function in functions.items():
        calls = []
        weights = {}
        for number, (target, weight) in enumerate(function.calls):
            site = f"site:{number}"
            calls.append({"call_site_id": site, "targets": [
                {"target_id": "direct", "target_hash": hashes[target],
                 "required_contract_hash": contract, "condition": None},
            ]})
            weights[site] = weight
        content = {"bias": function.bias, "weights": weights, "label": function.label}
        hashes[name] = publish_declaration(store, declaration(
            "function", function.declaration, content, references=provides, call_sites=calls,
        ))
    return hashes


def lower(store, entries):
    definitions = []
    names = {}

    def visit(digest):
        if digest in names:
            return names[digest]
        value = store.get(digest).payload
        symbol = f"call_{len(names)}"
        names[digest] = symbol
        instructions = []
        for call_site in value["call_sites"]:
            target = call_site["targets"][0]["target_hash"]
            callee = visit(target)
            weight = value["content"]["weights"][call_site["call_site_id"]]
            instructions.append(f"    result += {weight} * {callee}(x);")
        definitions.append("\n".join([
            f"static int {symbol}(int x) {{",
            f'    mark("{digest}");',
            f'    int result = x + {value["content"]["bias"]};',
            *instructions,
            "    return result;",
            "}",
        ]))
        return symbol

    roots = [(name, visit(digest)) for name, digest in entries.items()]
    table = ", ".join(f'{{"{name}", {symbol}}}' for name, symbol in roots)
    return """
#include <stdio.h>
#include <stdlib.h>
static const char *trace[64];
static size_t length;
static void mark(const char *hash) {
    if (length == sizeof trace / sizeof *trace)
        abort();
    trace[length++] = hash;
}
""" + "\n".join(definitions) + f"""
int main(void) {{
    const struct {{const char *name; int (*entry)(int);}} entries[] = {{{table}}};
    for (size_t i = 0; i < sizeof entries / sizeof *entries; i++) {{
        for (int x = -16; x <= 16; x++) {{
            length = 0;
            const int result = entries[i].entry(x);
            printf("%s,%d,%d", entries[i].name, x, result);
            for (size_t j = 0; j < length; j++)
                printf(",%s", trace[j]);
            puts("");
        }}
    }}
    return 0;
}}
"""


def invoke(*args):
    return subprocess.run(args, capture_output=True, check=True, text=True, timeout=30,
                          env={**os.environ, "LC_ALL": "C"}).stdout.strip()


def measure(store, hashes, workspace, opt):
    source = workspace / "probe.c"
    executable = workspace / "probe"
    source.write_text(lower(store, {name: hashes[name] for name in ENTRIES}))
    invoke("gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{opt}", source, "-o", executable)
    results = {}
    for line in invoke(executable).splitlines():
        entry, value, outcome, *trace = line.split(",")
        key = (entry, int(value))
        assert key not in results
        results[key] = (int(outcome), trace)
    assert set(results) == set(product(ENTRIES, INPUTS))
    return results


def verify_native(functions, hashes, results):
    def reference(name, value):
        body = functions[name]
        children = [reference(target, value) for target, _ in body.calls]
        computed = body.bias + value + sum(
            weight * result for (_, weight), (result, _) in zip(body.calls, children)
        )
        return computed, [hashes[name], *(item for _, trace in children for item in trace)]

    for key, observed in results.items():
        assert observed == reference(*key), (key, observed)


def compare():
    store = ContentStore()
    contract = publish_declaration(store, declaration(
        "contract", "integer-call", {"argument_range": [-16, 16], "result": "integer"},
    ))
    profiles = {}
    with TemporaryDirectory(prefix="llmlang-native-propagation-") as temporary:
        for label, functions in cases().items():
            hashes = materialize(store, contract, functions)
            entries = make_snapshot({name: hashes[name] for name in ENTRIES})
            audit = audit_candidate_snapshot_graph(store, entries)
            assert audit.valid, audit.errors
            native = measure(store, hashes, Path(temporary), 0)
            alternate = measure(store, hashes, Path(temporary), 2)
            assert native == alternate
            verify_native(functions, hashes, native)
            profiles[label] = (hashes, entries.root_hash, native)

    baseline, baseline_root, before = profiles["baseline"]
    exact, exact_root, intended = profiles["exact"]
    assert exact_root != baseline_root
    fixed = {"old-leaf", "old-shared", "legacy", "left", "peer"}
    assert {name for name in baseline if baseline[name] == exact[name]} == fixed
    assert exact["old-shared"] != exact["new-shared"]
    affine = {"chain": (3, 3), "legacy": (5, 2), "modern": (5, 6),
              "multi": (5, 10), "join": (9, 7), "peer": (1, 9)}
    for (entry, value), (expected, _) in intended.items():
        scale, offset = affine[entry]
        assert expected == scale * value + offset
    assert all(before[(entry, value)] == intended[(entry, value)]
               for entry, value in product(("legacy", "peer"), INPUTS))

    assert all(intended[("multi", value)][1] ==
               [exact["multi"], exact["old-leaf"], exact["new-leaf"]] for value in INPUTS)
    assert profiles["all-old"][1] == baseline_root

    results = {}
    for label, (_, root, observations) in profiles.items():
        results[label] = {
            "root": root,
            "scalar_mismatches_vs_plan": sum(observations[key][0] != expected[0]
                                             for key, expected in intended.items()),
            "trace_mismatches_vs_plan": sum(observations[key][1] != expected[1]
                                            for key, expected in intended.items()),
            "example_at_minus_three": {entry: observations[(entry, -3)] for entry in ENTRIES},
        }
    assert results["exact"]["trace_mismatches_vs_plan"] == 0
    assert results["same-outputs-other-leaf"]["scalar_mismatches_vs_plan"] == 0
    assert results["same-outputs-other-leaf"]["trace_mismatches_vs_plan"] == 132
    return {
        "gcc": invoke("gcc", "-dumpfullversion"),
        "native_invocations": len(profiles) * 2 * len(ENTRIES) * len(INPUTS),
        "unchanged_baseline_hashes": sorted(fixed),
        "rebound_existing_hashes": sorted(set(baseline) - fixed),
        "case_results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(), indent=2) + "\n")


if __name__ == "__main__":
    main()
