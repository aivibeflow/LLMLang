# Prototype 20 Results — Dependency Discovery and Classification

## Scope

Implemented a standard-library-only model in `src/dependency_discovery.py` and focused tests in `tests/test_dependency_discovery.py`.

The prototype covers evidence-preserving merge of multiple discovery sources, exact artifact/scope binding, explicit semantic classification, separation of hash-relevant dependencies from provenance/incidental observations, four audit statuses, and a deterministic evidence digest including tool identity and evidence references.

## Deliberate limitations

- No source parser, static analyzer, runtime tracer, eBPF collector, or sandbox is implemented.
- The prototype trusts normalized observations supplied by its caller.
- Classification is explicit input, not inferred from code.
- It does not prove discovery tools sound or complete.
- It does not yet integrate its evidence digest into Scenario 19's impact-plan identity.
- It does not execute actions or persist audit records.

## Tests

Twelve focused tests were added for evidence merging, static/dynamic unknowns, missing dependencies, scoped support, provenance-only and incidental observations, empty evidence, artifact/scope mismatch, classification without evidence, and digest sensitivity.

**Execution status:** tests have been added but have not been run in this commit.
