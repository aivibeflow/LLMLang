# Research Scenario 108 — Path-Sensitive Alias Precision

**Status:** Bounded path-sensitive AST experiment; no LLMLang alias policy selected
**Research areas:** RT-03 path feasibility, RT-04 effects/aliasing, RT-06 dependency completeness, RT-07 evidence limits
**Updated:** 2026-11-20

## 1. Question

Scenario 107 found that a unioned may-alias set can preserve every concrete route while adding infeasible ones when a branch condition correlates the selected reference with the predicate value. This experiment asks whether retaining concrete path states in the same tiny fixture grammar recovers that lost precision without incorrectly removing routes from independent alias choices.

## 2. Compared analyses

The [Scenario 107 adapter](RESEARCH-SCENARIO-107-SOURCE-DERIVED-CALL-ALIASES.md) merges reference targets at branch joins and applies the resulting union to the state-transition relation. The new path-sensitive executor instead enumerates the fixture's finite input valuations, selects the source branch under each valuation, propagates its exact reference target, and applies the AST-derived toggle summary at the call. A separate fixture executor applies the same toggle contract directly. Both parse Python-shaped fixtures with Python's `ast`; neither is a general Python interpreter, LLMLang parser, or independent source-to-CFG oracle.

## 3. Results

The experiment enumerates all 16 combinations of the two Boolean fields, branch selector, and unknown-reference target in the declared two-field region. Ten tests cover the existing Scenario 107 cases and the precision comparison.

| Fixture | Concrete executor | Joined may-alias result | Path-sensitive summary result |
|---|---|---|---|
| Alias choice is correlated with `flag` (`if flag: target = ref(other) else: target = ref(flag)`) | `{(False, True), (True, True)}` | Four pairs; sound but adds two infeasible pairs | Exact match; two routes |
| Alias choice is independent (`if choose: target = ref(other)`) | All four pairs | All four pairs | Exact match; all four routes remain |
| Unknown target is constrained to `flag` or `other` | All four pairs | All four pairs | Exact match; all four routes remain |

This establishes a precision/soundness trade-off in the finite fixture: a non-relational union keeps may-routes but can overapproximate, while enumerating path state preserves the correlation and does not prune routes in these tested cases. It does not show that path enumeration is an efficient or complete strategy for source programs.

## 4. Evidence limits and next discriminators

The path explorer handles two Boolean fields, a single direct reference parameter, a single toggle call, straight-line assignments, and finite conditionals. It enumerates a fixed input product instead of maintaining symbolic path constraints. Both executors share the AST grammar and the same toggle summary contract, so the equality is a bounded implementation cross-check, not an independent semantic proof.

Next compare path-sensitive state enumeration with relational points-to constraints and conservative joins as the number of fields, branches, calls, and alias parameters grows. Include loops/fixed points, nested or aggregate references, call-return effects, unknown callees, source parser/CFG coverage, resource bounds, and proof or trust requirements for pruning infeasible paths. No LLMLang analysis architecture or alias semantics is selected.

## 5. Reproduction

From the repository root:

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt03_source_alias_extraction.py' -v
```

Prototype: [`rt03_source_alias_extraction.py`](../PROTOTYPES/RT-04-01/rt03_source_alias_extraction.py). Tests: [`test_rt03_source_alias_extraction.py`](../PROTOTYPES/RT-04-01/test_rt03_source_alias_extraction.py).
