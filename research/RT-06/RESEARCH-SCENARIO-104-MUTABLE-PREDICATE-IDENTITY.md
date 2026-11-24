# Research Scenario 104 — Mutable Values and Predicate Identity

**Status:** exhaustive finite counterexample; no source-language rule selected
**Research areas:** RT-03 control-flow semantics; RT-06 path/dependency analysis; RT-07 evidence binding
**Updated:** 2026-11-19

## 1. Question

When a condition reads a mutable value more than once, what identity must connect path constraints to concrete program states? Can a source variable name safely serve as the symbolic predicate identity across a write?

## 2. Fixture and alternatives

The fixture has a Boolean local `x`, two sequential branches, and a write between them:

```text
if x then record T else record F
x := not x
if x then record T else record F
```

The exact finite input domain has two initial states. The executable comparison is in [`rt03_mutable_predicate_identity.py`](../PROTOTYPES/RT-04-01/rt03_mutable_predicate_identity.py), with exhaustive checks in [`test_rt03_mutable_predicate_identity.py`](../PROTOTYPES/RT-04-01/test_rt03_mutable_predicate_identity.py).

| Model | Symbolic treatment | Route set | Result |
|---|---|---|---|
| Concrete execution | Evaluate initial `x`, toggle it, then evaluate the new value | `FT`, `TF` | Exact reference for the two-state fixture |
| Name-conflated | Treat both reads of source name `x` as the same immutable Boolean | `FF`, `TT` | Unsound: drops both concrete routes; e.g. the reachable `FT` query becomes `¬x ∧ x` and looks infeasible |
| Fresh versions, no write relation | Use independent `x@0`, `x@1` | `FF`, `FT`, `TF`, `TT` | Conservative overapproximation, but admits two spurious routes |
| Versions plus transition | Use `x@0`, `x@1` and constrain `x@1 = ¬x@0` for the assignment | `FT`, `TF` | Matches exhaustive concrete routes |

All four assignments in the two-version domain are enumerated, so the route-set comparison is exhaustive for this fixture. The focused three-test suite passes.

## 3. Findings

1. A source-level variable name is not a value identity when writes can occur between reads. Reusing one symbolic variable across mutation can turn a reachable route into an apparent contradiction and unsoundly remove it from a may-analysis.
2. Renaming each read/version avoids that false negative only if the state transition is represented. Independent versions safely overapproximate but lose precision.
3. A sound symbolic path model therefore needs both versioned values and a sound write/alias transition relation. If mutation or alias effects are not known completely, the analyzer must preserve UNKNOWN/possible routes rather than infer stability from a name.
4. Predicate/version identity must be bound to the immutable source or IR snapshot used to build the route query; replay against a different version cannot be silently reused.

These observations constrain path-analysis/evidence models. They do not select mutability, SSA, ownership, or source syntax for LLMLang.

## 4. Limits and next discriminators

The fixture has one Boolean local, a direct assignment, no aliasing, and no effects in conditions. It does not parse source, derive SSA, model heap locations, calls that mutate through aliases, loops, concurrency, or solver performance. The formulas and concrete runner share a hand-authored fixture; the result is an exhaustive finite counterexample, not evidence of source-extractor completeness.

Next compare aliased writes, branch joins, loop-carried values, calls with mutation effects, and unknown call summaries. Bind each query to source/IR snapshot and CFG node identity; inject a source revision change between solve and replay; preserve UNKNOWN when extraction cannot prove the write set complete.

## 5. Reproduction

From `research/PROTOTYPES/RT-04-01`:

```sh
python -m unittest -v test_rt03_mutable_predicate_identity.py
python rt03_mutable_predicate_identity.py
```
