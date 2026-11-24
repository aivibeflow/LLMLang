# Research Scenario 103 — Real Solver Timeout and Worker Isolation

**Status:** reproducible bounded worker experiment; no solver, timeout, or pruning policy selected
**Research areas:** RT-03 path feasibility; RT-06 dependency completeness; RT-07 verification evidence
**Updated:** 2026-11-19

## 1. Question

Can the pinned SymPy DPLL2 backend be given a real per-query wall-clock bound despite its `satisfiable()` API lacking a timeout parameter, and can the analyzer preserve conservative path results when that limit is reached?

## 2. Method

The prototype [`rt03_bounded_solver_worker.py`](../../PROTOTYPES/RT-04-01/rt03_bounded_solver_worker.py) launches one isolated Python process for one query. The worker imports SymPy before announcing `READY`; the query deadline starts only after the parent validates that handshake. It then constructs a pigeonhole CNF and runs pinned SymPy 1.14.0 with `algorithm="dpll2"`. The parent waits for a response until the deadline; timeout kills and reaps the worker. Responses carry a random per-request ID. Startup failure, timeout, malformed output, worker error, crash, and request-ID mismatch map to `unknown`, never `unsat`.

The protocol is deliberately restricted to pigeonhole instances. The `select()` pipe handling is POSIX-specific and is a research harness, not a portable production service. Each query gets a new process, avoiding cross-query stale-response attribution; this does not model a persistent worker pool.

## 3. Results

Environment: Python 3.12.14, SymPy 1.14.0, the repository-pinned `requirements-solver.txt`, Linux/POSIX process and pipe behavior.

| Pigeons | Holes | Expected | Observed | Query deadline / elapsed | Interpretation |
|---:|---:|---|---|---:|---|
| 2 | 2 | SAT | SAT | 2 s / 0.037 s | Worker returns a complete assignment for this fixture; result was checked for all four variables and exactly one hole per pigeon. |
| 3 | 2 | UNSAT | UNSAT | 2 s / 0.040 s | Backend returns UNSAT; because this worker is not an accepted trust basis, the existing path classifier still returns UNKNOWN and retains the route. |
| 8 | 7 | UNSAT | UNSAT | 2 s / 0.445 s | A larger pigeonhole case completes within the limit. |
| 12 | 11 | UNSAT | UNKNOWN (`timeout`) | 0.5 s / ≥0.5 s | A real DPLL2 query did not finish before the deadline; the worker was killed and reaped, and no model was returned. |

The four focused tests in [`test_rt03_bounded_solver_worker.py`](../../PROTOTYPES/RT-04-01/test_rt03_bounded_solver_worker.py) passed. The measurements are local single-run observations, not a benchmark distribution; the 12/11 result is specific to the pinned solver and this machine. Query timing excludes interpreter and SymPy import, but includes fixture formula construction and solving.

## 4. Findings and limits

1. A parent-controlled process boundary can impose an actual wall-clock limit on an API without an internal timeout parameter.
2. A timeout is observable after solver work has begun and can be converted to UNKNOWN while the worker is forcibly reaped.
3. A successful UNSAT response is still not a proof merely because it came over a well-formed worker protocol. The adapter has no checked certificate or authenticated trusted-backend basis, so it must retain the route.
4. A request ID plus a one-process-per-query lifecycle prevents one timed-out worker's late result from being reused for a later query in this prototype. A persistent pool would need explicit cancellation, draining, generation IDs, queue limits, and crash recovery evidence.
5. This harness does not bound memory, CPU separately from wall time, process descendants, or total concurrent workers. It does not handle LLMLang source/CFG extraction, mutations, effects, proof certificates, or hard-formula distributions. The SAT/UNSAT result itself is not independently certified.

The experiment supports the Scenario 102 rule that resource exhaustion remains UNKNOWN. It does not support selecting SymPy, this timeout value, this process architecture, or solver-based path pruning.

## 5. Reproduction

From `research/PROTOTYPES/RT-04-01` with the pinned solver dependencies:

```sh
python -m unittest -v test_rt03_bounded_solver_worker.py
python rt03_bounded_solver_worker.py
```

The second command runs the 10-pigeon/9-hole fixture with a 0.5-second query deadline and prints the machine-readable result. The unit test uses 12 pigeons/11 holes for a more robust timeout fixture.

## 6. Next discriminators

- Repeat timing across cold and warm runs, multiple formula families, and solver/backend versions; record timeout distributions and completed SAT/UNSAT separately.
- Add a proof-producing backend and an independent proof checker before accepting solver UNSAT for pruning.
- Test worker startup timeout, abrupt crash, malformed response, mismatched ID, and memory/CPU limits; separately test persistent-pool cancellation if that architecture remains a candidate.
- Bind queries to immutable predicate/CFG versions and verify source-to-route completeness, including writes and aliasing.
- Compare unknown-path effects on diagnostics, dependency completeness, cache invalidation, and evidence reuse.

## 7. Retrospective alternatives and draft boundary (2026-11-23)

This is a reviewer navigation addition, not a new solver selection or historical timing attestation.

- **Tested hypothesis:** a one-query process boundary can impose a parent-controlled wall-clock limit after the worker is ready, and incomplete results remain UNKNOWN rather than a path-pruning certificate.
- **Alternatives and negative evidence:** a direct in-process call has no parent-controlled kill/reap boundary for the blocking API; a persistent worker pool may reduce startup overhead but was **not implemented**, and would need cancellation, late-response isolation, backpressure and crash recovery. A proof-producing trusted backend is a separate requirement. The observed SymPy UNSAT status is **not** a checked UNSAT proof. The existing report does not compare throughput/CPU/memory costs across these alternatives.
- **Source and scope:** [Shared COR-06 research corpus](../../language-design/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md) and [Scenario 102](RESEARCH-SCENARIO-102-SOLVER-UNKNOWN-AND-SOUND-PATH-PRUNING.md) record the soundness boundary. The [publication/source manifest](../../quality-audit/2026-11-23-publication-provenance.json) pins report, worker, tests and `requirements-solver.txt` to `08c8490e92b472f99abf3117e82bc7b11643fe0d`. Four tests passed in a **new** CPython 3.12.14 / SymPy 1.14.0 archived-source CI recheck, [run #45254862037](https://github.com/aivibeflow/LLMLang/actions/runs/45254862037). This does not prove original machine timings or original uncommitted source state.
- **Draft impact:** **none**. No solver choice, timeout value, pruning policy or general worker architecture is accepted. Future `draft/` changes require certified proof/solver trust and source-to-CFG evidence; track in [issue #285](https://github.com/aivibeflow/LLMLang/issues/285) and dependent RT-03/RT-07 research.
