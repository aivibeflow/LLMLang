# RT-11 — Instrumented binding action timing

**Date:** 2026-11-24
**Current-main baseline:** `1b1204056cab9ecdf02d4a13a71fd3d44e86eb1d` (PR #411 merge)
**Status:** exploratory two-run timing of a synthetic C fixture; no LLMLang speedup claim
**Question:** what timing evidence can the existing binding invalidation fixture provide, and does the measurement wrapper dominate short actions?

## Method

Extended `binding_build_benchmark.py` with opt-in `--timings`, `--repeat`, and `--output` controls. With timing disabled, the existing benchmark path and keys are unchanged. With timing enabled, each cache miss is executed by a small Python child wrapper which records child `perf_counter_ns` wall time and `RUSAGE_CHILDREN` user/system CPU time, along with action type, output size, and command. The parent separately records the surrounding action/key/cache section. The benchmark also records clean-oracle actions. Two complete paired runs used Debian `cc (Debian 14.2.0-19) 14.2.0`, target `x86_64-linux-gnu`, CPython 3.12. Each incremental phase matched its clean-build oracle; raw per-action samples are preserved in [`rt11-action-timing-linux-2026-11-24.json`](benchmarks/rt11-action-timing-linux-2026-11-24.json).

The timing wrapper adds another Python process and pipes for each measured subprocess. Its wall time is reported separately and must not be interpreted as cache lookup time. The surrounding action timing includes source preparation, key construction, cache checks, wrapper creation/execution and recording. It is an upper bound for that measured section, not an isolated hash/lookup cost. The child CPU fields cover the compiler/linker or fixture executable process, not the wrapper or parent Python CPU.

## Results

Values below are medians of the two complete runs. “Miss wall” sums the child wall durations for cache misses in that incremental phase; “section” sums the parent-measured per-action sections; clean wall is the sum of the phase's oracle child durations. All durations are milliseconds except CPU seconds.

| Linkage | Phase | Misses/run | Miss wall | Child CPU | Instrumented wrapper wall | Parent action section | Clean oracle wall |
|---|---|---:|---:|---:|---:|---:|---:|
| Exact | cold | 66 | 479.6 | 0.469 | 1,572.5 | 1,581.8 | 487.0 |
| Exact | warm | 0 | 0.0 | 0.000 | 0.0 | 0.4 | 503.0 |
| Exact | implementation | 53 | 369.9 | 0.357 | 1,279.3 | 1,288.5 | 492.9 |
| Exact | contract | 45 | 254.2 | 0.247 | 994.8 | 1,002.2 | 469.7 |
| Exact | history | 16 | 13.9 | 0.012 | 273.6 | 274.7 | 480.0 |
| Exact | flags | 66 | 528.7 | 0.512 | 1,647.8 | 1,658.6 | 526.2 |
| Separate | cold | 66 | 455.6 | 0.443 | 1,492.2 | 1,504.2 | 454.1 |
| Separate | warm | 0 | 0.0 | 0.000 | 0.0 | 0.4 | 496.7 |
| Separate | implementation | 45 | 234.0 | 0.228 | 935.2 | 939.8 | 453.0 |
| Separate | contract | 28 | 22.2 | 0.018 | 490.8 | 492.4 | 430.0 |
| Separate | history | 16 | 10.5 | 0.009 | 248.9 | 250.0 | 433.3 |
| Separate | flags | 66 | 508.2 | 0.496 | 1,543.3 | 1,552.9 | 487.6 |

In this fixture, separate linkage requires 45 rather than 53 child actions for the implementation change; the miss wall sums are 234.0 ms versus 369.9 ms. The two-run samples are noisy and each stage consists of many short child jobs. On 45 separate-link implementation misses, wrapper wall is 935.2 ms while the sum of measured child wall durations is 234.0 ms. The instrumentation therefore costs more wall time than it measures for this phase. Warm phases have no cache-miss child actions but still perform the action loop; parent-reported sections total only about 0.4 ms in this fixture.

## Interpretation and limits

The recheck supports the action-count finding that a stable separately linked interface can avoid recompiling prototype-only callers after an implementation edit. It also demonstrates that a per-child Python timing wrapper overwhelms small C compile/link jobs. The section timings combine key and cache work with action construction and instrument overhead, so they cannot estimate pure hashing/cache overhead or an uninstrumented wall-clock speedup. Two repetitions are insufficient for distributions, confidence intervals, or broad conclusions.

This is not a representative LLMLang workload, compiler-cache implementation, or end-user benchmark. It uses one C toolchain on one host, includes fixture setup and clean-oracle processes, and makes no claim about Rust, Go, C++, remote artifacts, parallel critical path, or production dependency completeness. The model's estimated 6–8×/2.2–2.4×/17–34× ranges remain unmeasured hypotheses.

## Follow-up

- Replace the per-command wrapper with lower-overhead in-process/perf-event instrumentation or batch compile work into longer actions before collecting additional trials.
- Report per-action command durations and parent/harness costs separately; do not label the current parent section as cache lookup time.
- Increase paired runs only after measurement overhead is reduced; pin host load and preserve raw JSON.
- Retain representative real-project and LLMLang-workload comparisons, clean-output equivalence, cold/warm/local/component/broad cases, and neutral/slower cases as open §3.4 dependencies.

The report is a measurement-method experiment, not a production implementation choice. `PLAN.md` §3.4 remains open.
