# RT-25 — Workload fit and current evidence boundaries

**Research item:** Plan §7.1 mandatory RT-25 — memory allocator compatibility and benchmarking  
**Date:** 2026-11-24  
**Baseline main:** `46efc9f7a4afb2b29a6bebcd9643edf96cd3ec4d`  
**Evidence type:** source-bound workload/evidence crosswalk and environment capability probe  
**Status:** bounded gap analysis; no new allocator timing or compatibility result  
**Question:** Which required RT-25 criteria are already evidenced, and which current LLMLang workloads can actually support a representative allocator decision?

## Method

I compared the RT-25 required candidates, compatibility and benchmark checklist with the current RT-01 reference workload catalog, the RT-25 compatibility probe, and the raw 16-process graph benchmark. I also checked the current execution environment for Rust and installed allocator libraries. This is a source/evidence crosswalk, not a retest of the archived allocator runs.

## Findings

The existing compatibility experiment establishes only one bounded integration fact: Rust `System` allocation/free/resize sequences and a direct C failed-resize preservation probe passed with glibc 2.41 and jemalloc 5.3.0 under one dynamically linked Linux x86-64 configuration. It does not establish general FFI safety, static linking, other allocator APIs, Rust `GlobalAlloc` replacement, teardown, or portability.

The archived graph benchmark contains 16 fresh-process runs (eight per provider), one source SHA, one verified traversal checksum, and two candidates: glibc and jemalloc. It constructs 200,000 graph nodes / 995,740 incoming edges, then measures graph construction and dependency traversal/serialization. Observed medians/ranges were:

| Metric | glibc | jemalloc | Interpretation |
|---|---:|---:|---|
| Build time | 59.9 ms (53.5–121.6) | 61.3 ms (58.3–72.4) | ranges overlap; one glibc outlier widens its range |
| Traverse/serialize | 108.1 ms (103.1–118.4) | 106.4 ms (97.2–115.6) | ranges overlap |
| Live RSS | 45,410 KiB | 44,366 KiB | jemalloc lower on this sample |
| Peak RSS | 49,554 KiB | 54,680 KiB | jemalloc higher on this sample |
| RSS after drop | 36,418 KiB | 36,348 KiB | jemalloc has one high outlier (44,440 KiB) |

All 16 checksums match. These observations support keeping build, traversal, live, peak, and post-drop metrics separate. They do not establish an allocator speedup or a general memory advantage. The report's eight samples per provider are too few to give reliable tail latency or confidence intervals, and `after_drop` is one 50 ms sample, not a reclamation/fragmentation measure.

## Coverage against RT-25 requirements and RT-01 workloads

| Required workload / gate | Current evidence | Coverage status | Missing discriminator |
|---|---|---|---|
| Large semantic graph construction and reverse-use impact | Synthetic Rust graph build/traverse/serialize | Partial | Use an actual LLMLang toolchain path once executable source and declared inputs exist; include canonicalization/hash cost distinctly |
| Compilation and incremental/cold/warm cache | RT-01 names provider replacement and RT-11 has a C action graph, but no allocator comparison against it | Not measured | Run same pinned LLMLang or Rust toolchain workflow under each allocator, preserving clean-output/evidence equivalence |
| Package index/archive construction and validation | Package research specifies index/archive metrics, no allocator comparison | Not measured | Reuse actual index/archive fixtures and report archive validation, peak memory and serialization costs |
| Concurrent Toolchain requests/jobs | RT-19 has an in-memory lifecycle prototype and now a protocol comparison, no representative concurrent persistent service | Not available as allocator workload | Need durable service/workspace implementation and repeatable concurrency mix first |
| Short-lived burst plus long-lived retained objects | Graph and traversal buffers coexist; one post-drop RSS sample | Partial | Separate lifetime classes, repeat phases, pressure/quiescence observations and allocator-level statistics |
| Required candidates | Linux glibc and jemalloc only | Partial | Assess modern Google TCMalloc and mimalloc or record scoped exclusion; pin integration path and versions |
| FFI and allocator-pairing safety | Direct C allocation probe and Rust `System` sequences | Partial | Exercise actual LLMLang/native library ownership boundaries, static/dynamic modes, cross-allocator rejection, startup/shutdown |
| Portability / target support | One Linux x86-64 host | Not established | Align with supported RT-10/RT-13 targets and supported libc/link/deployment modes |
| Memory pressure / contention / tail latency | CPU pinned, eight fresh processes; no memory pressure, concurrent allocation stress or p95/p99 | Not measured | Controlled repeated and concurrent runs under defined pressure, report distributions and failure behavior |

RT-01's representative task list covers CLI execution, resource-owning cancellation, call-site refactoring, provider rebuild, agent repair, and bootstrap/toolchain rebuild. For allocator decisions, only the dependency-graph workload currently has an executable allocation-shaped workload. The RT-01 catalog does not yet provide an executable package/archive allocator workload or a persistent Toolchain concurrency workload. This distinction matters: using a synthetic graph benchmark as if it represented all runtime/toolchain work would exceed its scope.

## Environment availability check

At the recheck environment on Debian 13 x86-64 / Linux `6.18.57`, `jemalloc` is available but `rustc` is absent; `ldconfig` reports no TCMalloc or mimalloc libraries. Therefore I could not rerun or extend the Rust benchmark here. No substitute Python/C timing result is presented as allocator evidence. Availability of Rust and the remaining candidates is an external toolchain/environment dependency for the next benchmark wave.

## Decision-relevant conclusion

The current evidence allows only this bounded comparison: the same synthetic Rust graph workload produced overlapping timing ranges, slightly lower live RSS but materially higher peak RSS for jemalloc, with matching checksums on one pinned Linux configuration. This supports retaining the platform default as the baseline while widening workload and candidate coverage; it does not select or reject jemalloc.

A practical next sequence is: (1) make Rust and both missing allocator candidates available on the pinned runner; (2) extend compatibility checks across required allocators before benchmarking; (3) add executable package/archive workload and actual cache/toolchain workload where source paths exist; (4) add long/short lifetime, concurrency and memory-pressure phases; (5) only then compare target support, operational controls, and results across supported RT-10/RT-13 profiles. RT-01 task prevalence/weights, full runtime target matrix, and the currently absent persistent Toolchain workload remain explicit dependencies.

## Reproduction and source references

The pre-existing raw run can be summarized with:

```sh
python3 - <<'PY'
import json, statistics
data = json.load(open("research/runtime-and-systems/PROTOTYPES/ALLOCATOR-BENCH-01/results-linux-x86_64.json"))
for provider in ("glibc", "jemalloc"):
    rows = [r for r in data["samples"] if r["provider"] == provider]
    print(provider, len(rows))
    for key in ("build_ns", "impact_ns", "live_kib", "peak_kib", "after_drop_kib"):
        values = [r[key] for r in rows]
        print(key, statistics.median(values), min(values), max(values))
PY
```

The archived reproduction does not require compiling in this recheck; a fresh Rust run remains blocked by the missing `rustc`. The source compatibility and graph reports remain linked above.

**Conclusion:** one compatible, source-hashed Linux graph comparison exists, but it is not representative enough to make RT-25 implementation decisions. The concrete remaining dependencies are candidate allocator libraries/integration, Rust toolchain availability, executable cache/package/concurrent workloads, supported target/FFI matrix, and controlled stress/pressure measurements.
