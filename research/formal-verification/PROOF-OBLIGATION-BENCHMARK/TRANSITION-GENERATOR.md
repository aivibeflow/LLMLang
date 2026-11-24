# Finite transition contract generator v1

Status: proposed synthetic development profile; not normative RT-03, not independently reviewed. Supports [#403](https://github.com/aivibeflow/LLMLang/issues/403) and [#402](https://github.com/aivibeflow/LLMLang/issues/402). Preserves the original finite formula generator unchanged.

## Semantic model and contract families

The [typed transition grammar](generative/transition/grammar.json) defines integer registers, typed expressions, guarded statements, state changes and ordered events. A named action is atomic, with observations at its boundary. Explicit finite schedules and initial overrides are enumerated. Invalid opcodes, types, registers, events and traces are rejected. The heap is an abstract generation-tagged slot, not a real allocator. This does not define LLMLang memory semantics.

| Family | Contract and interaction | Scope |
|---|---|---|
| transfer | Conservation, precondition, failure atomicity | All traces of length 0–3; zero, one and parameterized initial balance |
| lifetime | Generation-based stale handle rejection | Free/allocate/read, length 0–3; no generation wraparound |
| reservation | Concurrent clients compete for resource capacity | Atomic requests/releases, one free unit; length 0–3 |
| authorized_effect | Authority, frame and emitted effects | Authorized/unauthorized actions, length 0–3 |
| cancel_cleanup | Cancellation, resource cleanup and terminal state | Complete/cancel traces, length 0–3 |
| retry | Idempotent duplicate delivery, durable-state abstraction | Two request IDs, length 0–3; no distributed consensus |
| deadline | Discrete time, bounded progress and expiry | Tick/service traces, length 0–3; no real-time clock or fairness guarantee |
| interleaving | Arithmetic and concurrency | All six sequentially consistent read/write schedules of two operations |
| security_trace | Relational public observation non-interference | Two secret values, equal public action trace, length 0–3 |

Each family has a reference, faulty mutation and valid alternative (some alternatives are algebraic rewrites, not independent implementations). Candidate ASTs are executed by the interpreter; a separately expressed direct state/trace oracle and history invariants check state, effects and invariant obligations independently. Non-interference additionally compares paired executions. Each failing obligation retains a concrete initial override, action trace and actual/expected observations. The shrinker tries parameter 1 while preserving the selected failing obligation; it is not a general trace or AST minimizer. Zero mutation failures for an individual obligation are visible in the summary, not silently treated as covered.

## Reproduce

```sh
python research/formal-verification/PROOF-OBLIGATION-BENCHMARK/generative/transition/test_transition.py
python research/formal-verification/PROOF-OBLIGATION-BENCHMARK/generative/transition/generate.py --count 1000 --seed 42
```

Optional `--output gold.jsonl` contains ASTs, variants and expected results; `--blind-output stage-b.jsonl` contains contracts, declared initial state and scenario domain only. The blind output omits gold labels and model code, but public synthetic families are not private held-out tests. Distinct model triples mean syntax and parameter diversity, not independent semantic classes. The summary hashes exact corpus records and source artifacts, reports per-family and per-obligation mutation counts, and never emits proven. CI preserves both original formula and transition summaries.

## Remaining gaps

Real weak-memory executions, non-atomic effects, heap graphs and separation logic, general schedulers/fairness, unbounded temporal proofs, external APIs, richer type/effect systems, real multi-component protocols, full obligation-level isolated mutants, independent review and private evaluation remain open. Coverage registry links are candidates, not adjudicated cells. Backends and evidence composition remain tracked by #395 and #397. No increase in the 80-cell finite target or reviewed 300-cell matrix is claimed from parameter expansion.
