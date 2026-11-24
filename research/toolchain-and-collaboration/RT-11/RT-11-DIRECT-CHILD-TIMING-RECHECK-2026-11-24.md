# RT-11 — Direct child timing recheck

**Research item:** `PLAN.md` §3.4 — Quantify compilation speedup  
**Date:** 2026-11-24  
**Baseline main:** `1531d5c18d598fd84c037d27c21c499b675ae2ae`  
**Status:** two-run measurement-method comparison for the synthetic C binding fixture; no LLMLang speedup or cache policy selected  
**Question:** Can the existing per-action benchmark avoid the measurement helper process while preserving clean-oracle validation and useful per-action samples?

## Method

The preceding [instrumented binding-action study](RT-11-ACTION-TIMING-INSTRUMENTATION-2026-11-24.md) launches a Python helper process for every measured command. This recheck replaces that helper with direct `subprocess.run` timing in the parent process. It records `perf_counter_ns` around the subprocess call and reads `RUSAGE_CHILDREN` before and after it for the direct child's user/system CPU accounting. Captured output, compiler commands, cache keys, generated inputs, phase order, and acceptance checks are unchanged. The optional timing path remains off by default.

The parent-side `wall_ns` includes process launch, execution, output capture and wait. It does not isolate compiler front-end time, full descendant process-tree CPU, cache lookup, or hashing. The existing `lookup_total_ns` still covers action/key/cache setup and is not a pure lookup measurement. The experimental JSON schema is `rt11-action-benchmark-timing-v2-direct-child`.

Two complete exact/separate paired runs with timing enabled were recorded in [the raw JSON](../benchmarks/rt11-direct-child-timing-linux-2026-11-24.json). A separate two-run invocation with timing disabled was used as an end-to-end harness comparison. Both commands exited successfully; the driver checks each incremental result against a clean build and against the other linkage model for all six phases.

## Results

Environment: CPython 3.12.14; Debian GCC-compatible `cc` 14.2.0; `x86_64-linux-gnu`; Linux `6.18.57`; baseline repository revision `1531d5c`. The direct-timing run contains 12 rows per repetition (two linkage modes × six phases), and all 24 rows across two repetitions passed the driver's exact-output/clean-oracle assertions.

| Implementation-change linkage | Cache-miss actions/run | Direct-child wall sum, two runs (ms) | Previous wrapper study median (ms) | Direct parent action-section sum, two runs (ms) |
|---|---:|---:|---:|---:|
| Exact implementation identity | 53 | 320.48, 329.04 | 369.9 | 325.47, 335.02 |
| Separate stable interface | 45 | 216.82, 224.45 | 234.0 | 219.90, 228.59 |

The direction of the action-count discriminator repeats: the implementation edit executes eight fewer cache-miss actions with a separately linked stable interface in this fixture. The direct-child wall sums vary between the two runs, so the action-count difference is the more stable observation. Their two-run medians (324.76 ms exact; 220.64 ms separate) preserve the same ordering as the prior study but differ in magnitude. These are not controlled same-session measurements and are not a speedup estimate.

The prior helper path reported 1,288.5 ms of helper wall for the exact implementation phase and 935.2 ms for the separate-link phase, including a new Python process per miss. Direct parent action-section sums were 330.25 ms and 224.25 ms respectively (median of these two runs). The new path does not start a per-command helper, so its section contains direct subprocess work plus action/key/cache setup rather than another Python startup and output relay. A two-run end-to-end comparison measured 16.291 seconds with timing disabled and 16.534 seconds with direct timing enabled, a 0.243-second (1.5%) difference. Two unpinned runs do not establish whether that difference comes from measurement overhead or host noise.

## Interpretation and limits

Direct parent timing retains the bounded cache-action comparison while avoiding a second process per cache miss. `RUSAGE_CHILDREN` values describe accounting returned for the waited child; do not assume they include every compiler descendant on every platform. The two methods preserve the direction of the linkage comparison, while their absolute values differ across runs. This is consistent with the observed host/compiler variability and does not isolate helper overhead as the only cause.

This is one synthetic C fixture on one Linux host, with two repeated trials. It does not measure an LLMLang compiler, representative repository workload, parallel critical path, storage/network cost, warm cache-hit rate by attempted action, or hashing cost in isolation. No benchmark speedup, throughput, confidence interval, architecture recommendation, or general cache-policy claim follows.

## Reproduction

From the repository root at the pinned baseline plus this experimental source change:

```sh
cd research/PROTOTYPES/DEPENDENCY-GRAPH-01
python3 -B -m src.binding_build_benchmark --cc cc --timings --repeat 2 \
  --output /tmp/rt11-direct-timing.json
python3 -B -m src.binding_build_benchmark --cc cc --repeat 2 \
  --output /tmp/rt11-no-timing.json
```

Relevant source SHA-256: `c66f5cbed720b0de4fbc3aa47c7d873ab479f56a26d31795dd0d087092a140c1`.  
Raw direct-timing JSON SHA-256: `686a3a49ac07c2bbc7577e2f4d6e7f70693e656534c7f33050172fd1ea7885f1`.

## Remaining dependencies

- Increase paired runs on controlled or pinned hardware and report distributions before comparing durations.
- Time source hashing, dependency discovery, scheduling, storage and verification separately.
- Add representative Rust, Go and C++ projects and LLMLang workloads with clean-output equivalence.
- Include cold, warm, local, component and broad edits, and cases where caching is neutral or slower.
- Keep action-key completeness and evidence-freshness rules as prerequisites for production cache conclusions.

**Conclusion:** direct parent-side subprocess timing is a lower-overhead measurement method for this bounded fixture. The eight-action difference under separate linkage persists, but the production implementation choice and general performance benefit remain unresolved.
