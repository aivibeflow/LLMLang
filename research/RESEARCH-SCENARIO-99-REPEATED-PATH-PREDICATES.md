# Research Scenario 99 — Repeated Predicate Correlation in Path Enumeration

**Status:** bounded structural-path experiment; marker identity is a fixture convention, not a source-language rule  
**Research areas:** RT-03 control-flow observation, RT-04 path-sensitive resource obligations  
**Updated:** 2026-11-19

## 1. Question

When the same unknown Boolean input occurs in multiple branch conditions, should the structural path model treat each occurrence independently, or preserve the earlier choice? Does this identity-based constraint remove impossible paths while retaining every concrete execution for the declared fragment?

## 2. Fixture and method

The fixture is a sequence of two `if` expressions whose conditions both use the marker `same-input`. Each of the four leaves acquires/releases a uniquely named resource, so the ordered resource-event trace distinguishes branch outcomes. The concrete input domain contains the two assignments `same-input = false` and `same-input = true`.

The path model now indexes direct `unknown_bool` conditions by AST path. At a later occurrence, it finds the earlier choice for the same marker on the current path and follows only that branch. A first occurrence still forks into true and false. The test materializes each concrete assignment, runs both RT-03 evaluators, compares their complete event sequences and final resources, and matches each outcome to the path model's resource/result projection.

Reproduction from `research/PROTOTYPES/RT-04-01/`:

```sh
python -m unittest -v test_rt03_path_model.RT03IndependentPathModelTests.test_repeated_unknown_condition_reuses_its_path_choice
```

## 3. Result

Independent occurrence treatment would produce four choice tuples: `TT`, `TF`, `FT`, and `FF`. Under the fixture's stable-marker identity convention, only `TT` and `FF` are feasible. Both paths have distinct resource witnesses, and the two concrete assignments map exactly to those paths. The recursive and small-step evaluators agree on complete events and final resource maps for both assignments. The whole focused path-model suite passes (13 tests).

This result supports retaining repeated *identical marker* assignments in the bounded path model. It does not establish general path satisfiability.

## 4. Limits and next evidence

- Marker identity is assigned by the test fixture. A real parser/name resolver must establish whether two source references denote the same Boolean value and which mutation/effect boundaries can change it.
- The model does not recognize logical equivalence or contradiction between different predicates, such as `x` and `not x`, `x == 1` and `x != 1`, or predicates over mutable state.
- It has no symbolic expression language, solver, path-condition simplifier, or proof of feasibility for arbitrary inputs.
- Only direct branch conditions, sequential evaluation, resource witnesses, and the existing bounded outcome protocol are covered. Calls, effects that mutate predicate inputs, loops, and concurrency are out of scope.
- The path and evaluator implementations remain tied to an exploratory contract and hand-built ASTs; source-to-AST/CFG correspondence and independent review remain open.

Next, define a small typed Boolean predicate IR with explicit immutable input identities, negation, conjunction/disjunction, and equality over finite domains. Compare exhaustive concrete assignments with path-condition evaluation for satisfiable and unsatisfiable paths, including mutation/version boundaries. Keep parser-to-IR coverage as a separate gate.

## 5. Interpretation

This experiment exposes a useful separation: repeated reference identity can remove a concrete class of infeasible paths without requiring a general SMT solver, while semantic relationships between distinct expressions still require stronger modeling. It supplies evidence for a conservative, finite path-analysis step; no language feature, syntax, or solver choice is selected.
