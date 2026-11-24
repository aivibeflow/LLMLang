# RT-00 — DEP-012 Cache Identity Recheck (2026-11-23)

**Plan item:** §0.3, validate dependency edges as evidence accumulates  
**Edge:** DEP-012, RT-05 → RT-11 (`Requires`)  
**Baseline:** current `main` `6df9ced732bf41fb800a967ef4273c577bd87250`  
**Disposition:** Retain the scoped counterexample. A cache key based only on the operation caller's value is unsound when the operation-call binding can change independently. A key over the exact executable dependency closure is the narrower supported requirement; whole-snapshot hashing is safe but may invalidate unrelated work. No performance winner is established.

## Compared cache-key choices

| Key choice | Fixture outcome | Trade-off |
|---|---|---|
| Caller value/hash only | Rejected: the `late` caller has the same value hash but returns 5 before and 6 after `provider` is rebound | Can reuse stale execution results when a call resolves through mutable snapshot selection. |
| Whole snapshot identity | Safe for this fixture because the snapshot changes with the binding | Simple conservative boundary, but any unrelated snapshot change can invalidate the action. No cost/latency measurement here. |
| Caller plus exact call dependency closure | Supported by the observed graph: operation caller includes its binding and selected provider; direct pinned caller depends on its exact implementation and stays unchanged when the operation binding changes | Preserves the necessary distinction while avoiding unrelated bindings. Completeness and chosen action granularity require wider workload evidence. |
| Caller plus only the callee body value | Rejected for operation calls: the selected binding can point at another implementation while caller body and operation remain fixed | The identity must include resolved selection state, not just the referenced operation's static body. |

## Current-main reproduction

The existing SPG test constructs `late`, which calls operation `provider` through a binding, and `direct`, which pins the `primary` implementation. It then changes only the binding from `primary` to `alternate`:

- exactly one of the fixture's 13 selected entries changes: `binding:provider`;
- `late(4)` changes from `(5, ("first", "last"))` to `(6, ("first", "last"))` with the same caller hash;
- `direct(4)` remains `(5, ("first", "last"))` because its call pins `primary`.

The test also edits a provider body and verifies that the binding, edited body, and exact caller are the changed selections. This distinguishes operation calls from direct implementation calls rather than treating all calls as one global dependency.

Command from `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python -B -m unittest -v tests.test_spg_representation
```

CPython 3.12.14 result: **11 tests passed**. Test and implementation source SHA-256 values at baseline:

- `tests/test_spg_representation.py`: `385a6fe2ffd5267a45760a1f9b460ec4a97bb1434faeff27a7cbe60283c58ea1`
- `src/spg_representation.py`: `44c61db14a6b4bd467c85382174020216dacdb5749dfd436f162cd3e053e1517`

The original [RT-05 report, SPG-03](../RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md#7-results-and-falsifiers) records the same bounded result. This recheck confirms the reproduction on the current main code.

## Limits and remaining dependencies

The fixture has one provider binding, a closed scalar grammar, and a small selected graph. It does not measure key-construction cost, graph sizes, cache hit rates, concurrent binding changes, dynamic dispatch, external providers, recursion, or invalidation under incomplete dependency discovery. General semantic cache safety also depends on a sound effect/observation model and RT-06's complete dependency closure.

No external service or maintainer decision was needed for this recheck. The remaining dependency is internal: validate the minimal closure against representative programs, dynamic/external calls, and concurrent snapshots, then compare action-level versus smaller object-level reuse. DEP-012 remains a strong hypothesis with a scoped counterexample, not a selected production cache design.
