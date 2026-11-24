# Proof Obligation Benchmark — seed corpus and infrastructure

**Status:** proposed, non-normative experimental corpus; not independently adjudicated. Tracks [LL-029 / #393](https://github.com/aivibeflow/LLMLang/issues/393) and [RT-33 / #390](https://github.com/aivibeflow/LLMLang/issues/390). Design: [taxonomy and evaluation plan](../RT-33/PROOF-OBLIGATION-BENCHMARK.md).

## Reproduce

From the repository root, Python 3.11+ (standard library only):

```sh
python research/formal-verification/PROOF-OBLIGATION-BENCHMARK/run.py run > /tmp/pob-smoke.json
python research/formal-verification/PROOF-OBLIGATION-BENCHMARK/test_runner.py
python research/formal-verification/PROOF-OBLIGATION-BENCHMARK/run.py blind > /tmp/pob-stage-b.json
```

The smoke runner enumerates explicit finite input domains, verifies positive reference models and rejects mutations using separate predicate/oracle logic, reports first counterexamples, content hashes, and taxonomy label counts. A successful finite test is **bounded_pass**, never an unbounded proof. A counterexample refutes only the specified abstract claim within its declared scope; the smoke does not establish correspondence to LLMLang. Cases are development examples, not secret evaluation data; public answers and oracles must not be included in model prompts.

## Seed inventory

| Case | Subject | Scope |
|---|---|---|
| [POB-001](cases/POB-001.json) | Sum | All lists of length 0..3 over -1,0,1. |
| [POB-002](cases/POB-002.json) | First match | Lists length 0..3 over -1,0,1; target in -1,0,1. |
| [POB-003](cases/POB-003.json) | Sorting | Lists length 0..3 over -1,0,1. |
| [POB-004](cases/POB-004.json) | Range reversal | Lists length 0..3 over -1,0,1; all legal endpoints. |
| [POB-005](cases/POB-005.json) | Tree rotation | Strictly increasing triples drawn from -2..2; single left rotation at root. |
| [POB-006](cases/POB-006.json) | Ownership cleanup | 0..3 resources with unique IDs; optional failure after acquisition; abstract cleanup trace. |
| [POB-007](cases/POB-007.json) | Atomic transfer | Balances 0..3, amount 0..4, injected failure boolean; mathematical integers. |
| [POB-008](cases/POB-008.json) | FIFO queue | All operation sequences length 0..4 of enqueue 0, enqueue 1, dequeue; sequential histories only, not linearizability. |
| [POB-009](cases/POB-009.json) | Bounded progress | Three ticks, service choice at each tick; continuously pending until service; admitted traces contain service within first two ticks. |
| [POB-010](cases/POB-010.json) | Algebraic reduction | All triples over -2..2; mathematical integers. |
| [POB-011](cases/POB-011.json) | Capability isolation | Public input and secret in 0..2; no read capability; pairwise comparison of secret choices. |
| [POB-012](cases/POB-012.json) | Checked addition | All pairs in -8..7. |

The first twelve cases have a reference and incorrect mutation; the [second cohort](COVERAGE-AND-REVIEW.md) adds twelve cases with a reference, incorrect mutation and alternative valid candidate. Label counts are not a measure of semantic adequacy: sequential FIFO is only a prerequisite for concurrency evaluation, not linearizability; bounded progress is not general fairness; cleanup is not an ownership type system. The initial oracle code is trusted test infrastructure and requires independent review.

## Second cohort

| Case | Subject | Scope |
|---|---|---|
| [POB-013](cases/POB-013.json) | Non-vacuous precondition | Integers -2..4. |
| [POB-014](cases/POB-014.json) | Typed option elimination | None and integers -1,0,1; tagged abstract values only. |
| [POB-015](cases/POB-015.json) | Defined division | Numerator and denominator -2..2; exact rational arithmetic. |
| [POB-016](cases/POB-016.json) | Caller/callee precondition | Finite integers -2..2, one call and no side effects. |
| [POB-017](cases/POB-017.json) | Idempotent retry | All delivery sequences length 0..4 over IDs 0,1; lost acknowledgements modeled only by repeated delivery; single durable atomic receiver. |
| [POB-018](cases/POB-018.json) | Binary rounding boundary | Exact halves n/2 for n=-7..7. |
| [POB-019](cases/POB-019.json) | Finite probabilistic guarantee | Exactly four equally likely outcomes, all enumerated; no PRNG independence claim. |
| [POB-020](cases/POB-020.json) | Concurrent lost update | All six interleavings of two threads, each with read then write; initial zero; atomic reference linearizes at write; sequential consistency only. |
| [POB-021](cases/POB-021.json) | Wire migration default | IDs 0,1; enabled absent,true,false; no unknown fields in model. |
| [POB-022](cases/POB-022.json) | Trace non-interference | Public and secret bits, explicit abstract observation (value, steps); no wall-clock claim. |
| [POB-023](cases/POB-023.json) | Termination measure | Starting n=0..5; examine up to six transitions; no unbounded theorem. |
| [POB-024](cases/POB-024.json) | Dropped translation constraint | Integers -2..4; predicate-level correspondence only. |

See [coverage and review](COVERAGE-AND-REVIEW.md) for hand-derived witnesses, exact source crosswalk, remaining gaps and independent review gate.

## Third cohort: executable coverage target

See [finite coverage matrix](COVERAGE-MATRIX.md) for POB-025–040 and the explicit 80-cell target. Run `python research/formal-verification/PROOF-OBLIGATION-BENCHMARK/run.py coverage` to check the witnesses. All cases remain public development fixtures; coverage is bounded and proposed.

## Extended coverage and generation

See [coverage v2 and the deterministic generator](COVERAGE-V2.md): a multi-axis gap inventory, candidate 300-cell interaction matrix, and an executable finite formula generator with separate direct oracle. The original 80-cell gate remains unchanged. See also the [finite transition generator](TRANSITION-GENERATOR.md) for state, memory, resource, effect and trace profiles, and the [structural and system generator](SYSTEM-GENERATOR.md) for bounded heap graphs, protocol failures, multi-component guarantees and foreign-buffer models.

## Recursive and higher-order profile

See [recursive and higher-order contract generator](RECURSIVE-GENERATOR.md) for inductive data, finite function tables, fixed points and regular infinite traces.

## Format and contribution

[Case schema](case.schema.json), [taxonomy](taxonomy.json), [experiment protocol](EXPERIMENT-PROTOCOL.md), and [human case template](../RT-33/PROOF-OBLIGATION-BENCHMARK-TEMPLATE.md). Each case has a stable ID/revision, contract, assumptions, scope, obligation IDs/dependencies, variants and independent expected outcomes. Preserve old revisions and change logs before replacing an accepted oracle. The current Python runner checks the v1 finite-seed subset and dependency closure; the JSON schema documents the interchange shape, not a normative Contract IR. New oracle implementations require independent review of contract and mutant, at least one distinguishing counterexample, alternative valid implementations where meaningful, and explicit bound/assumption reporting. Do not silently expand a model's claimed scope.

## Remaining work

- [#394: corpus expansion and independent oracle adjudication](https://github.com/aivibeflow/LLMLang/issues/394).
- [#395: pinned Lean, SMT, TLA+ adapters and comparison](https://github.com/aivibeflow/LLMLang/issues/395).
- [#396: controlled LLM experiments and baselines](https://github.com/aivibeflow/LLMLang/issues/396).
- [#397: evidence graph, composition and invalidation](https://github.com/aivibeflow/LLMLang/issues/397).

The initial fixture runner is not a solver, proof checker, semantic obligation matcher or full experiment harness. Do not close RT-33 or declare the corpus complete on smoke success.
