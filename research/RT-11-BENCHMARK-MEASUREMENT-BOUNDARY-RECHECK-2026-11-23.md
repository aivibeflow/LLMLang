# RT-11 — Benchmark measurement boundary recheck

**Research item:** `PLAN.md` §3.4 — Quantify compilation speedup  
**Date:** 2026-11-23  
**Current-main baseline:** `85f54acf6ba9c6e3880d438b22fd7fa5cc482111`  
**Status:** Measurement-method comparison; no cache or compiler architecture selected  
**Question:** Which next benchmark implementation step can produce interpretable evidence about choosing exact versus separately linked caller identity and cache granularity?

## Existing alternatives and evidence

The current [RT-11 Binding Invalidation Benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md) generates sixteen C consumers and executes a six-phase change sequence under exact-address and separate-stable-symbol linkage. It measures cache misses by action class and checks each incremental output against both a clean build and the other linkage model.

The current-main benchmark was run on CPython 3.12.14, Debian GCC-compatible `cc` 14.2.0, target `x86_64-linux-gnu`. Its twelve measured linkage/phase rows matched the clean oracles. Across the one complete run, the incremental paths executed **467** cache actions in aggregate; the driver also performed **12 clean-oracle builds**. These are observed action counts. They do not state CPU time, wall latency, memory, hit ratio under a representative project, or end-user speedup.

A timing attempt ran seven repeated whole-experiment invocations but did not produce a completed result in the available time. The loop was stopped after process inspection showed it was still compiling the many fixture executables. No partial timing values are retained or treated as benchmark results. This indicates that total `experiment()` runtime includes substantial benchmark/oracle subprocess overhead and is not a valid proxy for one compile or cache action.

## Candidate next steps

| Option | Change | Evidence it can support | Main limitation / cost |
|---|---|---|---|
| **A — Instrument the existing driver** | Record `perf_counter_ns`, process user/system time, and output size around each compile/link/verify cache miss and clean-oracle action; collect repeated paired trials and raw JSON. Keep keys, generated sources, and acceptance checks unchanged. | Cost distribution for this controlled synthetic workload; whether separate linkage reduces executed caller compiler work and how much orchestration dominates. | Measures short-lived fixture commands on one host. Cache-hit checks and Python hashing/discovery still need separate timers; host noise and tiny C jobs make sub-millisecond estimates fragile. |
| **B — Add broader simulated graph sizes** | Parameterize consumers, providers, graph edges, and change locality; retain the same real compiler/linker. | Scaling behavior and crossover as caller fanout and affected fraction change. | Still synthetic; can obscure compiler versus harness costs. Requires a workload matrix and careful result normalization. |
| **C — Benchmark real Rust/Go/C++ repositories** | Build language-specific adapters and run cold/warm/local/component/broad edits in representative repositories. | Practical end-to-end cache benefit and comparison with conventional incremental builds. | Highest setup and attribution cost; repository revision, dependency downloads, tool versions, environment, and clean-output equivalence must be pinned. This is the only option that can support general product workload claims. |
| **D — Build an LLMLang compiler/cache prototype first** | Add action cache and dependency discovery to the product implementation. | Direct product-path evidence. | Premature: no implementation or stable semantics exist, so the cache contract and workload attribution could confound the result. |

## Result and recommended sequence

**A is the lowest-dependency next experiment.** It changes only measurement instrumentation around existing actions and preserves the verified build semantics. Run repeated paired trials on pinned hardware; report action class, command/toolchain, wall and CPU time, sample count, median and spread, and clean-oracle result. Time hashing/dependency-key construction separately from subprocess work. Compare both linkage policies against identical generated inputs and report per-phase deltas, not one aggregate speedup.

If A shows the harness or fixed compiler startup dominates, proceed to B with larger compile workloads and varied fanout/change locality. Use C only after the ActionKey and dependency contract are stable enough to instrument a real project without changing its behavior. D depends on the unresolved identity/dependency and compiler integration work and should not be the next performance study.

This sequence can compare cache-policy candidates for a bounded fixture. It cannot choose the final LLMLang implementation, establish a universal speedup, or replace representative Rust/Go/C++ measurements.

## Reproduction and scope

```sh
cd research/PROTOTYPES/DEPENDENCY-GRAPH-01
python3 -B -m src.binding_build_benchmark --cc cc
```

The measured run reported 12 cache-action rows and passed the clean-build oracle in both linkage modes and all six phases. Environment: CPython 3.12.14, Debian GCC-compatible `cc` 14.2.0, x86_64 Linux. The 467 aggregate action count includes provider and caller compilation, linking, and the two verification policies; the 12 clean-oracle executions are additional work.

The interrupted repeated timing attempt is recorded only as a method limitation; it has no numeric result. This report introduces no per-action timing instrumentation or code change. Consequently no duration, throughput, cache hit-rate percentage, or confidence interval is claimed.

## Remaining dependencies

- Implement per-action timing/resource instrumentation with raw machine-readable output and repeatable paired runs.
- Use pinned or controlled hardware and report scheduler/host variability.
- Extend the synthetic fixture or select representative Rust/Go/C++ projects with pinned revisions and clean-output equivalence.
- Measure hashing, dependency discovery, scheduling, storage, and verification overhead separately.
- Compare cold, warm, local, component, and broad changes, including cases where caching is neutral or slower.
- Stabilize ActionKey/dependency completeness and verification freshness rules before transferring conclusions to an LLMLang compiler.

**Conclusion:** current evidence compares invalidation work, not speed. Instrumenting the existing fixture is the most economical next study; production implementation choice remains contingent on timed, representative workloads and sound dependency boundaries.
