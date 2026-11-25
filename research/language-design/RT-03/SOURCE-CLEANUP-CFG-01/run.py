#!/usr/bin/env python3
"""Compare source-derived CFGs with actual short-circuit and unwinding behavior."""

import ast
from dataclasses import asdict
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
from textwrap import dedent

import flow
import reference

HERE = Path(__file__).resolve().parent
CONDITIONS = {
    "and": 'probe("left", x) and probe("right", y)',
    "or": 'probe("left", x) or probe("right", y)',
    "nested_and": '(probe("left", x) or probe("right", y)) and probe("tail", True)',
    "nested_or": '(probe("left", x) and probe("right", y)) or probe("tail", False)',
}
POLICIES = ("full", "eager", "return_bypasses_cleanup", "last_error_only")


def make_source(condition, true_outcome, false_outcome):
    return dedent(f"""\
        def entry(x, y):
            open_slot("outer")
            try:
                open_slot("inner")
                try:
                    if {condition}:
                        emit("selected")
                        {true_outcome}
                    emit("fallback")
                    {false_outcome}
                finally:
                    close_slot("inner")
            finally:
                close_slot("outer")
        """)


def unsupported_controls(base):
    controls = {
        "unknown_call": base.replace('emit("selected")', 'foreign("selected")'),
        "unmodeled_resource_call": base.replace('close_slot("inner")', 'object.close("inner")'),
        "unknown_predicate": base.replace('probe("left", x)', 'probe("left", other)'),
        "dynamic_handle": base.replace('stage("handle")', 'stage(x)'),
        "unadmitted_finally": base.replace('close_slot("outer")', 'close_slot("outer")\n        emit("extra")'),
        "async": base.replace('def entry', 'async def entry'),
    }
    for name, source in controls.items():
        ast.parse(source)
        try:
            flow.lower(source)
        except flow.UnsupportedSource:
            yield {"case": name, "expected": "unsupported", "source": source}
        else:
            raise AssertionError(f"Unrecognized source admitted for {name}")


def main():
    fixtures = {}
    counts = {policy: {key: 0 for key in ("any", "trace", "result", "errors", "slots", "handle")}
              for policy in POLICIES}
    rows = []
    variations = (("return_on_true", 'return stage("handle")', 'fail("primary")'),
                  ("return_on_false", 'fail("primary")', 'return stage("handle")'))
    good = {"ok": 0, "pending": 0, "nested_causes": 0, "covered_source_calls": 0}
    for (condition_name, condition), (branch_name, when_true, when_false) in product(
        CONDITIONS.items(), variations
    ):
        name = f"{condition_name}/{branch_name}"
        source = make_source(condition, when_true, when_false)
        exact = flow.lower(source)
        eager = flow.lower(source, eager=True)
        bypass = flow.lower(source, skip_return_cleanup=True)
        source_calls = {flow.source_span(node) for node in ast.walk(ast.parse(source))
                        if isinstance(node, ast.Call)}
        covered = set()
        graph_payload = json.dumps([exact[0], [asdict(node) for node in exact[1]]], sort_keys=True)
        fixtures[name] = {"source": source, "sha256": sha256(source.encode()).hexdigest(),
                          "graph_sha256": sha256(graph_payload.encode()).hexdigest(),
                          "full_cfg_nodes": len(exact[1]), "entry": exact[0],
                          "call_spans": sorted(source_calls)}
        for x, y, inner_err, outer_err in product((False, True), repeat=4):
            flags = {"x": x, "y": y}
            failure = {"inner": inner_err, "outer": outer_err}
            expected = reference.execute(source, flags, failure)
            covered.update(tuple(event[0]) for event in expected["trace"])
            candidates = {
                "full": flow.execute(exact, flags, failure),
                "eager": flow.execute(eager, flags, failure),
                "return_bypasses_cleanup": flow.execute(bypass, flags, failure),
                "last_error_only": flow.execute(exact, flags, failure, replace_error=True),
            }
            assert candidates["full"] == expected, (name, flags, failure, expected, candidates["full"])
            diffs = {}
            for policy, result in candidates.items():
                changed = [key for key in expected if result[key] != expected[key]]
                if changed:
                    diffs[policy] = changed
                    counts[policy]["any"] += 1
                    for key in changed:
                        counts[policy][key] += 1
            good["ok"] += expected["handle"] == "caller"
            good["pending"] += expected["handle"] == "pending"
            good["nested_causes"] += len(expected["errors"]) == 3
            rows.append({"fixture": name, "inputs": flags, "release_failures": failure,
                         "source_observation": expected, "disagreements": diffs})
        assert covered == source_calls, (name, covered, source_calls)
        good["covered_source_calls"] += len(covered)

    for policy in POLICIES[1:]:
        assert counts[policy]["any"] > 0
    assert all(good.values())
    controls = list(unsupported_controls(fixtures["and/return_on_true"]["source"]))
    header = json.dumps({
        "schema": "llmlang-source-cleanup-cfg/1", "python": platform.python_version(),
        "runner_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "flow.py", "reference.py")},
        "fixtures": fixtures, "executions_per_policy": len(rows), "mismatches": counts,
        "observed_cases": good, "controls": controls,
    }, indent=2).removesuffix("\n}")
    print(header + ',\n  "executions": [')
    print(",\n".join("    " + json.dumps(row) for row in rows))
    print("  ]\n}")


if __name__ == "__main__":
    main()
