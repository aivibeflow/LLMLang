# Prototype 21 Results — Counterfactual Dependency Analysis

## Scope

Implemented a standard-library-only analyzer in src/counterfactual_analysis.py and 13 focused tests in tests/test_counterfactual_analysis.py.

The analyzer consumes normalized paired-run records. It checks exact artifact/context/observation-model/factor binding, one declared changed factor, distinct baseline/treatment input digests, complete repeated pairs, and stability of outcomes and traces.

It compares observable outcome digests separately from execution trace digests and emits OBSERVED_BEHAVIORAL_INFLUENCE, INTERNAL_PATH_CHANGE_ONLY, NO_OBSERVED_DIFFERENCE, or INCONCLUSIVE.

A deterministic evidence digest pins the experiment inputs, run identities, outputs, traces, and result.

## Deliberate limitations

- No program execution engine, mutator, fuzzer, taint tracker, or trace collector is implemented.
- The analyzer trusts supplied canonical digests and exact context identities.
- It assumes the declared changed factor is accurate; it does not inspect input structures.
- Repetition uses exact equality, not statistical inference.
- It does not model stateful cross-run carryover, distributed systems, concurrency, or external-effect compensation.
- It does not discover interaction effects automatically.
- It does not infer INCIDENTAL_ACCESS or prove non-dependence.
- It is not yet integrated into Scenario 20 dependency audits or Scenario 19 plan identity.

## Tests

Thirteen focused tests were added for positive behavioral influence, equal outcomes, trace-only differences, context mismatch, multiple factors, identical input digests, unstable outcomes, missing pairs, insufficient pairs, empty evidence, duplicate sides, observation-model mismatch, and evidence digest sensitivity.

**Execution status:** tests have not yet been run in this commit.
