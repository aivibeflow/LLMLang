# RT-04 — Ordered effect summaries across calls

**Date** · 2026-11-21

**Baseline** · `b0142c27f5632a859c379b78a10cb22f500ebfd8`

**Status** · Bounded experiment for [Plan §1.4.1](../../../PLAN.md#141-type-effect-ownership-and-capability-alternatives-rt-04)

## Question and alternatives

Can a caller compose effect summaries without losing observable order or combining paths that require contradictory values of the same input? Existing effect-label bounds describe what a program may perform. The shared trace fixtures also distinguish order and payloads. [Scenario 37](RESEARCH-SCENARIO-37-EFFECT-ROWS-HANDLERS-AND-OBSERVATION.md) · [RT-03/04 cross-profile traces](RT-04-RT-03-CROSS-PROFILE-TRACES.md)

| Summary | Trade-off |
|---|---|
| Unordered set of effect labels | Compact for capability and upper-bound checks. Loses order and multiplicity, and omits where a failure stops execution. |
| Set of possible ordered outcomes per callee | Preserves each callee's local traces. Independent composition overapproximates correlated calls. It can require unnecessary revalidation or admit an impossible trace if used as an exact witness. |
| Ordered outcome indexed by an exact entry valuation | Preserves guards shared across calls and termination prefixes. Enumeration grows with context size. Symbolic compression, widening and unsupported-input behavior require their own evidence. |

## Method and results

The fragment contains fixed procedures, immutable Boolean inputs, sequencing, guarded branches, event emission and terminal error. The summary maps one entry valuation to an outcome tag and ordered list, or to unknown. Sequencing appends events only after successful subcomputations and retains the prefix on error. A reached absent callee or recursive call cycle yields unknown. The independent interpreter executes a work list with a finite call limit.

Across 32 program variants and four Boolean valuations, all 128 summaries match the operational result and ordered events. The programs vary the relationship between guards, call order, error, repetition and an intermediate procedure. Independent composition of callee trace sets contains every concrete outcome and adds 28 impossible outcomes across 16 programs. In one witness, the first call emits reserve only when the shared guard is true, while the second emits audit only when that same guard is false. Summarizing the calls separately incorrectly permits the sequence reserve/audit.

A reached unresolved or recursive call produces unknown, while the other path remains exact. An unresolved occurrence after a terminal error does not erase the already observed prefix. Swapping two events retains the same unordered labels and changes the trace.

The result supports maintaining two different summaries when their consumers need different guarantees. A capability upper bound can use a set. An exact verification witness needs ordered outcomes and enough call context to preserve correlation. This fixture assumes complete fixed procedure bodies and immutable flags. Dynamic dispatch, state mutation, permissions and foreign effects, resource cleanup with multiple failures, and general recursive summaries remain open. [Dependency map](../../RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

From the repository root use CPython 3.12.14. [Executable model and controls](../PROTOTYPES/ORDERED-EFFECTS-01/compare.py)

```sh
python -B research/language-design/PROTOTYPES/ORDERED-EFFECTS-01/compare.py
```
