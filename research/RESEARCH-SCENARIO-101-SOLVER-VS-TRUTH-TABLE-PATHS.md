# Research Scenario 101 — Solver-backed versus Truth-table Path Feasibility

**Status:** bounded differential experiment using SymPy's DPLL backend; no path-analysis architecture selected  
**Research areas:** RT-03 control-flow observation, RT-04 path-sensitive analysis  
**Updated:** 2026-11-19

## 1. Question

Can a solver-backed path checker preserve the exact feasible branch vectors and produce replayable witnesses for the finite Boolean predicate IR from Scenario 100? On one controlled formula family, how does its cost compare with exhaustive assignment enumeration?

## 2. Prior-art boundary

SymPy's documented `satisfiable()` API returns a satisfying model or `False` for an unsatisfiable expression. SymPy documents a pure-Python DPLL implementation and optional faster Pycosat/PySAT backends. This experiment pins SymPy 1.14.0 and explicitly calls `algorithm="dpll2"`, avoiding backend auto-selection. See [SymPy 1.14 logic documentation](https://docs.sympy.org/1.14/modules/logic.html) and [SymPy dependency/backend documentation](https://docs.sympy.org/1.14/contributing/dependencies.html).

## 3. Method

For correctness, both Scenario 100's exhaustive analyzer and a new adapter that translates the same pure `bool_var`/`bool_not`/`bool_and`/`bool_or` IR into SymPy expressions enumerate candidate branch routes for the same `x` then `x or y` fixture. The adapter conjoins each route's branch conditions and asks `dpll2` for a model. Tests compare the exact route sets, replay each solver model through the concrete evaluator and RT-03 path/resource model, and check complete evaluator traces/resource maps. A contradiction fixture checks that DPLL drops the impossible arm and returns a replayable witness for the feasible arm.

For a limited timing comparison, both methods process one conditional whose predicate is the left-associated conjunction `x0 ∧ x1 ∧ … ∧ xn`. Its two routes are the all-true arm and the at-least-one-false arm. The truth-table analyzer enumerates every assignment; the DPLL adapter asks for one witness per route. Each timing is the median of three local runs, including adapter formula construction and route checks. The command is `python benchmark_rt03_predicate_paths.py` from `research/PROTOTYPES/RT-04-01/` after installing `requirements-solver.txt`.

## 4. Results

The path sets agree at every tested input size. For the conjunction formula, both find exactly two feasible paths. The local timing results were:

| Boolean variables | Truth-table assignments | Truth-table median | DPLL2 median | Feasible paths |
|---:|---:|---:|---:|---:|
| 8 | 256 | 0.000885 s | 0.000886 s | 2 |
| 12 | 4,096 | 0.018012 s | 0.001292 s | 2 |
| 16 | 65,536 | 0.364190 s | 0.002722 s | 2 |
| 18 | 262,144 | 1.635340 s | 0.002564 s | 2 |

The run used Python 3.12.14, SymPy 1.14.0, mpmath 1.3.0, and Linux x86-64. The full RT-04-01 suite passed 200 tests with these two solver cross-check tests included.

The measurements show a clear difference for this conjunction family: truth-table time grows with the enumerated assignment count, while DPLL quickly finds one model for each of the two routes. This is not a representative worst-case SAT benchmark. DPLL remains a complete search procedure and may also require exponential work on hard formulas; the measured formula family is especially regular.

## 5. Limits and next evidence

- Only one satisfiable formula family and one small contradictory formula were tested. Randomized, adversarial, parity-heavy, and structurally difficult formulas are absent.
- The DPLL witness is one model per feasible route, not a complete enumeration of all satisfying assignments.
- Timing is local microbenchmark evidence with a small fixture, not a CI gate, stable performance guarantee, or compiler/runtime estimate.
- SymPy, its parser-to-expression adapter, and DPLL implementation enter the checker trust boundary. The tests establish agreement with finite truth tables only for their fixtures; they do not prove the solver sound or the adapter complete.
- Predicates remain immutable and pure. Integer theories, mutation/version boundaries, effects, cancellation, loops, source parsing, and CFG extraction remain open.

Next compare multiple formula families across size and structure, replay models against the truth table, test deterministic handling of unbound variables and timeouts, and document whether unknown/solver-failure must conservatively retain paths. Keep solver output as evidence rather than a language semantic rule.
