"""Compare finite truth-table path enumeration with SymPy's DPLL backend.

Run after installing requirements-solver.txt. The results are exploratory wall
times, not a CI threshold or a language/compiler performance estimate.
"""
from __future__ import annotations

import platform
import statistics
import sys
from time import perf_counter

import mpmath
import sympy

from rt03_predicate_paths import enumerate_feasible_paths
from rt03_sympy_predicate_paths import enumerate_solver_paths


def conjunction_of_variables(size: int):
    predicate = {"bool_var": "x0"}
    for index in range(1, size):
        predicate = {"bool_and": [predicate, {"bool_var": f"x{index}"}]}
    return {"if": {
        "condition": predicate,
        "then": {"literal": "all-true"},
        "else": {"literal": "some-false"},
    }}


def measure(function, expression, repeats: int) -> float:
    samples = []
    for _ in range(repeats):
        started = perf_counter()
        function(expression)
        samples.append(perf_counter() - started)
    return statistics.median(samples)


def main() -> None:
    enumerate_solver_paths(conjunction_of_variables(2))  # warm imports/backend
    print(f"Python {sys.version.split()[0]}, SymPy {sympy.__version__}, mpmath {mpmath.__version__}")
    print(f"Platform: {platform.platform()}; median of 3 runs; backend=dpll2")
    print("variables assignments truth-table-seconds dpll2-seconds feasible-paths")
    for size in (8, 12, 16, 18):
        expression = conjunction_of_variables(size)
        truth_table = measure(enumerate_feasible_paths, expression, repeats=3)
        dpll = measure(enumerate_solver_paths, expression, repeats=3)
        reference_paths = enumerate_feasible_paths(expression)
        solver_paths = enumerate_solver_paths(expression)
        if {path.branch_choices for path in reference_paths} != {
            path.branch_choices for path in solver_paths
        }:
            raise AssertionError(f"path-set disagreement at {size} variables")
        print(
            f"{size} {2 ** size} {truth_table:.6f} {dpll:.6f} "
            f"{len(solver_paths)}"
        )


if __name__ == "__main__":
    main()
