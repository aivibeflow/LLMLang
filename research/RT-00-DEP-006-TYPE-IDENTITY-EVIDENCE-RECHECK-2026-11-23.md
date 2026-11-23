# RT-00 — DEP-006 Type and Identity Evidence Recheck (2026-11-23)

**Plan item:** §0.3, validate dependency edges as evidence accumulates  
**Edge:** DEP-006, RT-04 → RT-05 (`Influences`)  
**Baseline:** `main` `71ff5c3de8b182eeb69dc3f723062693e21cdf24`  
**Disposition:** Retain DEP-006 as an open hypothesis. The bounded SPG recheck shows that changing an operation's parameter or result type changes the represented operation and implementation selections and the serialized graph, even when the implementation body is reduced to a literal. Scenario 119 shows that ownership obligations can change caller compatibility while result tags stay the same. These results support treating typed contracts as identity or dependency inputs; they do not establish a universal identity rule for all type/effect/capability data.

## Candidate identity strategies

| Strategy | Potential benefit | Evidence and unresolved cost |
|---|---|---|
| Embed the full resolved type/effect/ownership/capability shape in each implementation identity | Local, self-contained identity; consumers need fewer lookups | No fixture compares this layout. It may duplicate shared interfaces and conflate interface and body revisions. |
| Keep separate immutable interface/contract values and include exact references in implementation and snapshot dependency closure | Interface changes can invalidate dependent selections while leaving unrelated values reusable | The current SPG fixture follows this direction for operation and contract values. Recheck below demonstrates propagation for scalar parameter/result types and declared traces. Completeness of the references is only fixture-local. |
| Exclude type/effect data from identity unless a runtime observation changes | Maximizes value reuse | Scenario 119 changes reachable obligation shapes and caller match exhaustiveness without changing the broad result-tag set. No general equivalence proof supports omission. |
| Hash a normalized compatibility summary instead of the full contract | Could preserve identity across source-level changes that are behaviorally compatible | The required summary and proof obligation are not defined or evaluated by these experiments. |

These are implementation strategies, not a selection. In the second strategy, a compatible split is to hash implementation body separately from its exact operation/interface reference, while hashing the project snapshot over both. This preserves body reuse without omitting the typed dependency.

## Current-main recheck

### SPG fixture

The existing `tests.test_spg_representation` module exercises operation and contract values in a closed scalar grammar. A small mutation check used the existing `dispatch_program()` fixture and `compile_program()` from the SPG prototype. In both mutations the `other` implementation was changed to a literal body so the changed scalar signature was not needed to compute that body:

1. Parameter type: `Int` → `Bool`; the typed operation and its implementation selections changed, and serialized graph bytes differed.
2. Result type: `Int` → `Bool`, with the literal body changed from `1` to `True` to remain type-correct; the operation and implementation selections changed, and serialized graph bytes differed.

Command, from `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python -B - <<'PY'
from dataclasses import replace
from tests.test_spg_representation import dispatch_program, encode, changed_selections
from src.spg_representation import compile_program
p = dispatch_program()
impl = dict(p.implementations)
impl['other'] = replace(impl['other'], body='1')
p = replace(p, implementations=impl)
baseline = compile_program(p)
ops = dict(p.operations)
ops['other'] = replace(ops['other'], parameters=('Bool',))
parameter_change = compile_program(replace(p, operations=ops))
assert changed_selections(baseline, parameter_change) == {'operation:other', 'implementation:other'}
assert encode(baseline) != encode(parameter_change)
impl = dict(p.implementations)
impl['other'] = replace(impl['other'], body='True')
ops = dict(p.operations)
ops['other'] = replace(ops['other'], result='Bool')
result_change = compile_program(replace(p, operations=ops, implementations=impl))
assert changed_selections(baseline, result_change) == {'operation:other', 'implementation:other'}
assert encode(baseline) != encode(result_change)
PY
```

The SPG report and test already compare declared effect contracts: reordering the *outer set* of permitted traces preserves encoding; reversing or duplicating events *inside a trace* changes operation/implementation selections. This supports distinguishing set-valued contract alternatives from sequence-valued observations. It does not establish behavior for arbitrary effects.

The existing focused SPG suite was also rerun from the prototype directory:

```sh
python -B -m unittest -v tests.test_spg_ordered_lowering tests.test_spg_representation
```

CPython 3.12.14 result: **16 passed**. The ownership-result checker was rerun with the command from Scenario 119:

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_owned_call_match.py' -v
```

CPython 3.12.14 result: **10 passed**. Its result-shape enumeration covers four close outcomes, two transfer timings, and forwarding obligations. Changing a cleanup contract can add reachable payload shapes and require new caller match arms even when the result tags are unchanged.

Relevant source SHA-256 values at the baseline:

- SPG test: `385a6fe2ffd5267a45760a1f9b460ec4a97bb1434faeff27a7cbe60283c58ea1`
- SPG implementation: `44c61db14a6b4bd467c85382174020216dacdb5749dfd436f162cd3e053e1517`
- ownership match test: `829ff02bb194f325938b7f92518fed945a2c5e0a906fa5dd46f29e39d67ce9a5`
- ownership match model: `48600753efd64b43061277463ece1ab86460723b2b239f663126a1f625f5e373`
- disposition model: `23f8eadbc83cdcd140f994b78fe33a4afeebdc42a5c6c0d9621b9172423cbb5e`

## What remains external or untested

No external service or maintainer decision was needed for these bounded rechecks. The key unresolved dependency for a full implementation choice is internal research: define the language's effect/ownership/capability observation model, then validate source-to-typed-graph completeness and exact dependency closure. The fixtures have no parser-backed source, nominal type aliases, capability grants, general effect handlers, subtyping, separate compilation, or cache invalidation workload. Scenario 119's test reuses a hand-encoded disposition model and is not a real OS/provider test.

The current evidence favors an exact typed dependency in snapshot identity over omission, while leaving inline versus separately referenced typed data unresolved. It does not justify marking DEP-006 established or closing §0.3 edge validation.
