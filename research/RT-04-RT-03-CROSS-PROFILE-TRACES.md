# RT-03 A/D × RT-04 A/B — Shared Observable-Trace Cross-Check

**Status:** first finite cross-profile fixture set; exploratory only  
**Date:** 2026-11-18  
**Profiles:** RT-03 semantic profiles A (Pure Functional Core) and D (Effectful Functional Core); RT-04 checker vectors A (closed effects/ambient capabilities) and B (effect-row annotation/scoped capabilities)  
**Executable fixtures:** [test_rt03_rt04_cross_profile.py](PROTOTYPES/RT-04-01/test_rt03_rt04_cross_profile.py)

## 1. Purpose

The RT-04 checker vectors must not be mistaken for RT-03 execution semantics. This experiment places both on a small shared vocabulary of observable traces and records where their guarantees do and do not line up.

The fixture oracle checks only the RT-03 observation envelope:
- Profile A admits a trace only when it has no external effect events.
- Profile D admits events only when every event's effect label is explicitly declared; event order and event payload remain part of the trace.

This is deliberately not an interpreter, evaluator, handler implementation, or proof of language semantics. It tests a narrow compatibility hypothesis using hand-authored traces.

## 2. Shared trace vocabulary

A trace has:
- an ordered events sequence; each event has an effect label and optional resource/value data;
- a result, represented here as an explicit success/error-shaped value.

The initial fixtures cover pure return, filesystem read, ordered repeated writes, and an undeclared network effect. They do not yet define exceptions, state-store semantics, resource acquisition/finalization, cancellation, concurrency, divergence, or environmental nondeterminism.

## 3. Results

| Fixture | RT-03 A | RT-03 D | RT-04 checker A | RT-04 checker B | Interpretation |
|---|---|---|---|---|---|
| Pure return | Admissible | Admissible | Accept | Accept | Shared baseline |
| fs.read event | Reject: effect absent from pure profile | Admissible when declared | Accept with ambient fs.read | Accept with explicit scoped grant and effect-row annotation | RT-04 A's ability to check a closed effect does not make that effect part of RT-03 A semantics |
| Two ordered fs.write events | Reject | Admissible when declared; order remains observable | Label-only summary | Label-only summary | Current RT-04 effect summaries lose event order and payload |
| net.send without declaration | Reject | Reject | Reject unknown closed label | Accepts with open-row annotation | RT-04 B's row variable is currently only an annotation; no row unification or handler semantics exist |

“Admissible” here means only that the fixture oracle's profile boundary is met. It does not mean a complete program is well-typed, authorized at runtime, terminating, or behaviorally correct.

## 4. Findings

1. **Keep semantic profile and checker vector as separate axes.** RT-04 checker A can accept a closed I/O effect under ambient authority, while RT-03 semantic profile A is pure. This is a cross-profile mismatch that must be resolved by the eventual language/profile composition, not hidden by reusing the letter A.
2. **Effect-label summaries are not observable traces.** The RT-04 model computes set-like transitive effect summaries. It cannot distinguish two programs that emit the same labels in different orders or with different payloads.
3. **An open-row annotation is not an effect-row implementation.** Profile B currently accepts an otherwise unknown effect label when an open-row variable is present. It does not unify rows, establish handler coverage, or prove the effect is handled.
4. **Capability authorization and observable behavior remain distinct.** A scoped grant fixture establishes only a declaration-level authority relation. It does not establish that the effect actually occurs, succeeds, or is implemented according to its contract.
5. **Explicit result-shaped values do not settle all error semantics.** The trace envelope can carry a result, but no rule has yet been selected for exceptions, cancellation, resource failures, or handler propagation.

## 5. Limits and next experiments

- The trace oracle is intentionally independent and tiny; it is not a second complete reference semantics.
- Traces are hand-authored. There is no source parser, interpreter, compiler, or source-to-trace completeness evidence.
- The RT-04 checker remains declaration-level and does not consume trace evidence.
- The corpus does not cover state transitions, resource lifecycle, cancellation, nondeterministic scheduling, or divergence.
- The current checker does not preserve event order/payload, so it cannot serve as an oracle for RT-03 observational equivalence.

Next:
1. Extend the shared trace corpus with state read/write ordering, explicit errors, resource acquire/use/release, and cancellation outcomes.
2. Build a small executable reference semantics for RT-03 A and D over exactly that corpus; compare independently generated traces.
3. Extend RT-04's effect representation only after the RT-03 observation and handler rules are defined; preserve ordered events where they are semantically observable.
4. Keep the second independent cross-aspect model and independent review as separate gates.

No RT-03 profile or RT-04 type/effect/ownership/capability architecture is selected by this experiment.