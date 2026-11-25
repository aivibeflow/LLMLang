# RT-00 C — Solver worker protocol audit

**Date:** 2026-11-25
**Baseline:** `6bf099cc937a95a170cdbcc074122cab13210f0c` (`main`)
**Scope:** current-main audit of Scenario 103's one-query SymPy worker, including a bounded test of failure responses and their effect on SAT/UNSAT evidence handling.
**Status:** reproduced and extended for one POSIX/Python worker; no backend or production protocol selected.

## Question

Does the current bounded worker distinguish the failure modes claimed by Scenario 103, and do protocol or solver responses ever turn an incomplete result into an infeasibility claim? This is a content/experiment-level check for PLAN §0.1 and a bounded discriminator for §2.3.

## Alternatives in scope

| Option | Evidence from this audit | Main trade-off left open |
| --- | --- | --- |
| Direct in-process call | The pinned SymPy `satisfiable()` interface used here has no per-query timeout. | Lowest process/IPC overhead, but the caller cannot kill a blocked synchronous call while preserving the host process. Other solver APIs may have native cancellation. |
| One fresh process per query | The current prototype enforces startup and query deadlines, kills and reaps incomplete workers, and binds each response to that query's random ID. Injected failures below remain UNKNOWN. | Pays process startup for every query. POSIX `select` behavior and one Python/SymPy build are the only environment tested here. |
| Persistent worker pool | Not implemented or measured. | Could amortize startup, but needs queue bounds, cancellation, worker generations, draining/restarting, crash isolation, and stale-response tests. |

This is a worker-lifecycle comparison, not a solver-strength comparison. Scenario 103's pigeonhole timing observations remain single-machine observations; no throughput distribution was collected here.

## Method and result

The test harness points the existing parent adapter at short-lived executable stubs that implement the same line protocol. Stubs exercise startup silence, invalid handshake, process exit after request, malformed JSON, wrong request ID, explicit solver error, delayed response, valid UNSAT, and SAT with an incomplete model. Existing tests also run the real pinned SymPy worker for SAT, UNSAT, and a hard-query deadline.

The first audit run found two reason-label mismatches: startup silence was reported as `worker_protocol_error`, and an empty response at EOF was reported as `malformed_response`. Both were already fail-closed (`UNKNOWN`), but obscured whether the worker timed out or exited. The prototype now classifies a live worker that misses `READY` as `worker_startup_timeout`, and EOF/exit during a query as `worker_crashed`. The failure classes remain distinct from a syntactically invalid non-empty response.

The final run passed **5 unittest methods**, including **9 injected protocol subcases**, in 1.499 s. Observed outcomes:

| Injected condition | Adapter result | Conservative path result |
| --- | --- | --- |
| No READY before startup deadline | `UNKNOWN / worker_startup_timeout` | Retained |
| Wrong protocol version in READY | `UNKNOWN / worker_protocol_error` | Retained |
| Worker exits after receiving query | `UNKNOWN / worker_crashed` | Retained |
| Non-JSON response | `UNKNOWN / malformed_response` | Retained |
| Stale/mismatched request ID | `UNKNOWN / request_id_mismatch` | Retained |
| Worker returns an error response | `UNKNOWN / synthetic_solver_error` | Retained |
| Worker responds after query deadline | `UNKNOWN / timeout` | Retained; worker reaped |
| Well-formed UNSAT without accepted evidence basis | Raw `UNSAT` response | Classified `UNKNOWN`; retained |
| Well-formed SAT with incomplete model | Raw `SAT` response | Classified `UNKNOWN`; retained |

The last two rows separate transport validity from result validity. The adapter parses a response; the existing feasibility classifier is what requires a complete replayable SAT model and an explicit accepted UNSAT basis before feasibility/infeasibility is claimed. Agreement with this finite test suite is not a proof of backend correctness.

## Reproduction and provenance

From `research/PROTOTYPES/RT-04-01` on the reported Linux/POSIX environment:

```sh
python3 -m unittest -v test_rt03_bounded_solver_worker.py
```

Observed environment: CPython 3.12.14, SymPy 1.14.0, Linux x86_64. The exact dependency pins are in `requirements-solver.txt`. The machine-readable observations and SHA-256 digests of the tested module, tests and dependency file are in [the evidence record](RT-00-C-SOLVER-WORKER-PROTOCOL-AUDIT-2026-11-25.json). The report does not attest the historical run or the original timing machine.

## Disposition and remaining inputs

- The current one-shot worker's bounded failure cases preserve possible paths; explicit failure labels now match startup timeout and worker exit.
- Keep protocol parsing, SAT witness replay, and UNSAT trust as separate gates. A well-formed response alone cannot authorize pruning.
- This audit supports the one-shot lifecycle for a controlled experiment. It does not show that it is faster or more reliable than a persistent pool on representative workloads, and does not choose SymPy.
- The plan's broader implementation decision still needs a representative formula corpus, other timeout-capable/proof-producing backends, resource measurements (CPU, memory, descendants and concurrency), persistent-pool comparison if that option remains in scope, and integration across the Lean/JSON/Logos/CPC boundary. Production UNSAT use also needs either an explicit trusted-backend decision or independently checked certificates. Cross-platform behavior needs native runners beyond this POSIX environment; maintainers must decide the trust and deployment policy.

No change to `draft/` is supported by this experiment.
