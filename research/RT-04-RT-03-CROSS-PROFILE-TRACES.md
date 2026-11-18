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

A completed evaluation trace has:
- an ordered events sequence; each event has an effect label, operation, request payload, and outcome;
- a result value, which may be an explicit success/error-shaped Result value.

A terminal execution outcome is distinct from a completed Result value: the executable slice represents cancellation as `{"cancelled": reason}`. Cancellation stops pending expression evaluation; it is not an ordinary Result error and is not currently modeled as an effect event.

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
1. Add branching and verify resource cleanup behavior on every terminating path, including success, Result error, cancellation, and release failure.
2. Extend the resource model with explicit ownership/transfer alternatives only after branch-sensitive traces expose the required distinctions.
3. Extend RT-04's effect representation only after the RT-03 observation and handler rules are defined; preserve ordered events where they are semantically observable.
4. Keep the second independent cross-aspect model and independent review as separate gates.

No RT-03 profile or RT-04 type/effect/ownership/capability architecture is selected by this experiment.

## 6. First executable reference-semantics slice

The first interpreter slice is implemented in `PROTOTYPES/RT-04-01/rt03_reference.py`; its tests are in `test_rt03_reference.py`. It is intentionally separate from the RT-04 declaration checker and evaluates a small expression tree directly.

### Expression fragment

- `literal`: immutable scalar/data value.
- `add`: strict integer addition; evaluate left operand before right operand.
- `sequence`: evaluate expressions left-to-right; the last value is the sequence result.
- `result_ok` / `result_error`: construct explicit tagged data values.
- `perform`: request one effect operation with a structured payload.

### Profile A

- Strict, left-to-right evaluation of the supported pure expressions.
- No `perform` operation; encountering one is a semantic rejection.
- Explicit result-shaped errors are ordinary values in this slice; they do not implicitly abort evaluation.

### Profile D

- Retains the same strict expression core.
- A `perform` operation is permitted only when its effect label is in the supplied declared-effect set.
- Finite deterministic handlers are supplied for `fs.read/read`, `fs.write/write`, `state.read/read`, `state.write/write`, and `net.send/send`.
- Each handled operation appends an ordered event containing effect label, operation, request payload, and outcome. State/file effects also update the interpreter's isolated fixture store.
- Missing file/network fixture responses are represented as explicit error-shaped outcomes and remain observable events.

### Trace and comparison

A completed evaluation returns the ordered event sequence, result value, final fixture state, and final fixture file map. Reordering state writes changes both the trace and final state. The RT-04 checker still returns a set-like effect-label summary, so it cannot reproduce the reference trace.

The tests also cover Profile A rejection of effects, undeclared-effect rejection in D, explicit result errors, file reads and missing-file errors, state read/write order, deterministic network fixture responses, unsupported handlers, malformed expressions, and non-mutation of caller-supplied initial fixtures.

### Explicit Result propagation extension

The executable evaluators now include an explicit `result_sequence` form. It evaluates Result-shaped expressions left-to-right, returns the first `error` unchanged, and does not evaluate later expressions after that error. If all items are `ok`, it returns the final `ok` value. A non-Result-shaped item is rejected. This is an explicit construct in the prototype; ordinary `sequence` retains its prior strict behavior and does not implicitly propagate errors.

This extension does not define exceptions, implicit propagation from arbitrary function calls, error conversion, cancellation semantics, cleanup, or resource finalization. In particular, a Result value whose error payload happens to describe cancellation is still only a Result error; it is not an execution-cancellation event.

### Deliberate limits

This is an executable reference *slice*, not a complete or selected RT-03 semantics:
- no parser, source syntax, variable binding, function calls, recursion, or type checker;
- no general effect-handler language, handler algebra, or effect-row inference;
- no implicit Result short-circuiting, exceptions, cancellation, or error propagation rules;
- no resource acquire/release, ownership, cleanup, async, concurrency, nondeterminism, or divergence model;
- deterministic handlers are test fixtures, not real filesystem/network access;
- no proof that a source program maps completely to this expression tree;
- no independent second implementation yet.

Reproduction from the repository root:

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v
```

This command runs the RT-04 checker tests, the original cross-profile fixtures, and the new RT-03 reference interpreter tests together.


## 7. Differential check with an independent small-step evaluator

A second implementation, [`rt03_smallstep.py`](PROTOTYPES/RT-04-01/rt03_smallstep.py), now evaluates the same bounded fragment using an explicit control stack and value stack. It does not import or call the recursive evaluator in `rt03_reference.py`. The two implementations therefore use different evaluation algorithms, while intentionally sharing the written fragment and handler contract.

The differential suite [`test_rt03_differential.py`](PROTOTYPES/RT-04-01/test_rt03_differential.py) compares:
- profile, ordered events, result, final state, and final file map;
- pure expression corpus, including nested addition and explicit Result-shaped values;
- state read/write and file/network effect traces;
- reordered effects;
- a generated finite corpus of all 9 pairs of two writes using values 0, 1, and 2;
- matching fail-closed behavior for pure-profile effects, undeclared effects, and malformed addition.

This provides algorithmically independent implementation cross-checking for the current finite fragment. It is not an independent human review, a formal proof, or a separately derived semantics: both implementations were built from the same exploratory contract and may share specification mistakes. The next gate remains independent review and extension of the observation model.
