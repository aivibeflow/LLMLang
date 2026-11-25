"""Replay path fixtures and compare source-call routes with a finite table."""

import io
import json
import platform
import subprocess
import sys
import tarfile
import tempfile
import unittest
from itertools import product
from pathlib import Path

import sympy

BASELINE = "873556ad43892c7c2ffcae602881ffd544020eca"
FIXTURE = "research/PROTOTYPES/RT-04-01"
MODULES = (
    "test_rt03_path_model",
    "test_rt03_predicate_paths",
    "test_rt03_sympy_predicate_paths",
    "test_rt03_feasibility_outcomes",
    "test_rt03_bounded_solver_worker",
    "test_rt03_mutable_predicate_identity",
    "test_rt03_call_mutation_summaries",
    "test_rt03_alias_sensitive_call_paths",
    "test_rt03_source_alias_extraction",
)
PREAMBLE = """\
def flip(ref):
    ref.value = not ref.value

flag = input_bool("flag")
other = input_bool("other")
choose = input_bool("choose")
target = ref({target})
"""


def run_suite(module):
    suite = unittest.defaultTestLoader.loadTestsFromName(module)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    if not result.wasSuccessful() or result.testsRun == 0:
        raise RuntimeError(log.getvalue())
    return {"ran": result.testsRun, "skipped": len(result.skipped)}


def route_words(routes):
    return sorted("".join("T" if value else "F" for value in route) for route in routes)


def compare_alias_routes():
    from rt03_source_alias_extraction import compare_source_fixture, execute_path_sensitive_summary

    names = ("flag", "other", "choose")
    guards = [(None, True), *product(names, (False, True))]
    rows = []
    for target, (guard, when) in product(("flag", "other"), guards):
        source = PREAMBLE.format(target=target)
        if guard is None:
            source += "flip(target)\n"
        elif when:
            source += f"if {guard}:\n    flip(target)\n"
        else:
            source += f"if {guard}:\n    mark()\nelse:\n    flip(target)\n"

        exact = set()
        for assignment in product((False, True), repeat=len(names)):
            inputs = dict(zip(names, assignment, strict=True))
            initial = inputs["flag"]
            called = guard is None or inputs[guard] == when
            exact.add((initial, initial ^ (called and target == "flag")))

        extracted, concrete, joined = compare_source_fixture(source)
        sensitive = execute_path_sensitive_summary(source)
        with_skip = joined
        if guard is not None:
            with_skip = joined | {(False, False), (True, True)}
        assert extracted.call_targets == {target}
        assert concrete == exact and sensitive == exact, source
        assert exact <= with_skip, source
        rows.append({
            "source": source,
            "target": target,
            "guard": guard,
            "call_when": when if guard is not None else None,
            "oracle_routes": route_words(exact),
            "concrete_routes": route_words(concrete),
            "joined_routes": route_words(joined),
            "path_sensitive_routes": route_words(sensitive),
            "joined_with_skip_routes": route_words(with_skip),
            "extra_joined_with_skip_routes": route_words(with_skip - exact),
            "missing_joined_routes": route_words(exact - joined),
            "extra_joined_routes": route_words(joined - exact),
        })
    return rows


def main():
    archive = subprocess.check_output(["git", "archive", BASELINE, FIXTURE])
    with tempfile.TemporaryDirectory(prefix="llmlang-path-replay-") as temporary:
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(temporary, filter="data")
        sys.path.insert(0, str(Path(temporary) / FIXTURE))
        suites = {module: run_suite(module) for module in MODULES}
        controls = compare_alias_routes()
    print(json.dumps({
        "baseline": BASELINE,
        "fixture": FIXTURE,
        "python": platform.python_version(),
        "sympy": sympy.__version__,
        "linux": platform.release(),
        "architecture": platform.machine(),
        "suite_results": suites,
        "caller_fixtures": len(controls),
        "inputs_per_caller": 8,
        "joined_unsound_fixtures": sum(bool(row["missing_joined_routes"]) for row in controls),
        "controls": controls,
    }, indent=2))


if __name__ == "__main__":
    main()
