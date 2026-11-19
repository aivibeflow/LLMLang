# Research Scenario 100 — Finite Boolean Path Feasibility

**Status:** exhaustive analysis of a bounded Boolean predicate IR; no SMT solver, parser, or language rule selected  
**Research areas:** RT-03 control-flow observation, RT-04 path-sensitive analysis  
**Updated:** 2026-11-19

## 1. Question

Can a small path analyzer distinguish feasible branch combinations when distinct predicates have logical relationships, while matching concrete executions for every input in a finite domain?

## 2. Predicate fragment and method

The experiment defines a small pure predicate IR:

- immutable Boolean variables (`bool_var`);
- Boolean literals;
- negation (`bool_not`);
- binary conjunction/disjunction (`bool_and`, `bool_or`).

For a given expression tree, the analyzer collects all referenced Boolean variables, enumerates every assignment, evaluates the branch predicates, and groups assignments by the resulting branch-choice vector. It records the first deterministic assignment as a witness for each vector. This is truth-table enumeration over immutable inputs, not general symbolic reasoning.

The fixture executes two sequential branches: first on `x`, then on `x or y`. Each branch arm uses a distinct resource ID. All four assignments of `(x, y)` are materialized into literal-condition ASTs and run through both RT-03 evaluators. Their complete traces and resource maps are compared with each other and with the existing concrete path/resource model.

Reproduce with:

```sh
cd research/PROTOTYPES/RT-04-01
python -m unittest -v test_rt03_predicate_paths
```

## 3. Result

The analyzer finds three feasible branch vectors: `TT`, `FT`, and `FF`. `TF` is infeasible because `x = true` forces `x or y = true`. Four concrete assignments produce exactly those three vectors; every vector has a concrete witness. Both evaluators agree on the full event sequence and final resource map for each assignment, and the existing concrete path model predicts the same branch/resource observations. Unsupported predicate forms fail closed. The complete RT-04-01 suite passes 198 tests.

The experiment extends Scenario 99's repeated-name correlation to a bounded relationship between different predicates. Exactness follows from enumerating the full finite input space, not from a symbolic proof or general solver.

## 4. Limits and next evidence

- The input domain is immutable Boolean values. Integer/range domains, arithmetic predicates, quantifiers, and unbounded inputs are absent.
- The IR treats conjunction and disjunction as pure Boolean operations. It says nothing about source evaluation order, effects, exceptions, or short-circuit observations.
- The analyzer uses exhaustive enumeration, with work growing as `2^n` for `n` distinct variables. No scaling claim is made.
- Mutation, aliasing, calls, loops, concurrency, parser/IR extraction, and source-node coverage are not modeled.
- The model returns branch vectors and witnesses; it does not establish type correctness, resource safety for general programs, or completeness of a language CFG.

Next compare truth-table enumeration with a solver-backed encoding over the same frozen predicate corpus, including a finite integer domain and contradictory/equivalent expressions. Measure construction/solve time and witness replay separately. Keep source correspondence, mutation-versioning, and effects as independent gates.

## 5. Interpretation

The bounded evidence shows that even a small explicit predicate language can eliminate structurally possible but semantically infeasible paths and provide auditable witnesses. For a tiny finite domain, exhaustive enumeration is simple and exact but scales exponentially. The next design comparison should measure a solver encoding against the same cases before considering its cost, trusted boundary, or role in language analysis.
