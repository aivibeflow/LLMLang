# RT-25 — Memory Allocator Compatibility, Selection, and Benchmarking

**Status:** Not started — mandatory research item in `PLAN.md` §7.1  
**Research area:** RT-25  
**Priority:** P1  
**Scope:** Rust-based LLMLang runtime and toolchain; initial focus on supported native targets  
**Decision boundary:** this study may recommend an allocator or a selection policy, but it must not silently turn allocator choice into a language-semantic requirement.

## 1. Goal

Determine whether LLMLang should use an allocator other than the platform/Rust default, which alternatives are technically compatible with its Rust implementation and native dependencies, and whether any alternative produces a reproducible improvement on representative LLMLang workloads without unacceptable memory, portability, operational, or correctness costs.

The study must be comparative and evidence-based. It must not assume that TCMalloc, jemalloc, mimalloc, or any other allocator is faster or more memory-efficient for LLMLang before measurement.

## 2. Questions to answer

1. Which allocator is used by the current Rust executable on each supported target, and how is it selected by the Rust toolchain and target runtime?
2. Can each candidate be installed as Rust's process-wide global allocator? What crate, FFI, ABI, initialization, shutdown, and linking requirements apply?
3. Can allocator selection be isolated per executable/process, or is there a justified need for multiple allocators within one process? What are the safety and ownership implications?
4. Which allocations originate in Rust, C/C++ libraries, system libraries, and generated/native components? Which component frees each allocation?
5. What happens when memory allocated by one allocator is released or reallocated through another? Define safe FFI ownership and allocator-pairing rules.
6. Which targets, architectures, libc variants, static/dynamic linking modes, and deployment environments are supported by each candidate?
7. How do candidates compare on allocation/deallocation throughput, tail latency, peak RSS, retained memory, fragmentation, contention, startup cost, and behavior under memory pressure?
8. Do allocator-specific background threads, caches, tuning controls, or environment variables affect determinism, resource use, security, or operational complexity?
9. What is the fallback behavior when an allocator is unavailable or unsupported on a target?
10. Should allocator selection be a build-time feature, a runtime/deployment setting, or remain an implementation detail?

## 3. Candidate set

At minimum compare:

- Current Rust/platform default allocator on every target under evaluation (for example, the platform system allocator; identify the actual implementation rather than assuming it is always glibc malloc).
- Google TCMalloc (distinguish modern Google TCMalloc from the older gperftools implementation).
- jemalloc.
- mimalloc.

Add another candidate only when it has a clear technical rationale and can be tested under the same conditions. Record exact versions, Rust toolchain, target triple, libc/runtime, build flags, and integration crate or FFI layer.

## 4. Required compatibility analysis

For each candidate, record:

- Rust `GlobalAlloc` integration path, maintenance status, safety assumptions, and known limitations.
- Whether the allocator is process-wide or can safely be scoped; do not imply that Rust's global allocator can be changed independently for arbitrary modules after startup.
- C/C++ and system-library interoperability, allocation ownership, cross-allocator free/realloc hazards, and the required API discipline.
- Static/dynamic linking, symbol interposition, duplicate allocator instances, initialization order, background thread behavior, and shutdown semantics.
- Supported operating systems, architectures, libc variants, and packaging/deployment requirements.
- License, upstream maintenance, release cadence, and security response posture.
- Operational controls: configuration knobs, diagnostics, profiling, statistics, and safe defaults.

A candidate is not considered compatible merely because it compiles. The study must establish that all relevant allocation/free pairs and FFI ownership boundaries are safe for the tested configuration.

## 5. Required workload and benchmark design

Use reproducible workloads drawn from actual or planned LLMLang behavior. Include, where available:

- Parsing and construction of large semantic graphs.
- Dependency graph traversal, reverse lookup, and impact planning.
- Canonicalization, hashing, and serialization.
- Compilation and incremental/cold/warm cache workloads.
- Package index/archive construction and validation.
- Concurrent requests or jobs in the Toolchain Server.
- Short-lived allocation bursts and long-lived retained object graphs.

Include microbenchmarks to characterize allocation-size/lifetime distributions, but do not use them as the sole basis for a recommendation.

For each allocator and workload, measure:

- Wall-clock throughput and latency distributions, including p50/p95/p99 where meaningful.
- Allocation and deallocation rate by size class where measurable.
- Peak and steady-state RSS, retained/committed memory, and memory after workload quiescence.
- Fragmentation or allocator-reported equivalent metrics, with definitions.
- CPU utilization, contention, thread count, and background work.
- Startup/shutdown overhead and behavior under memory pressure.
- Run-to-run variance and confidence intervals.

Control machine, OS, kernel, libc, CPU affinity where applicable, Rust/toolchain versions, build profile, optimization flags, concurrency, input corpus, and warm-up. Publish commands, fixtures, raw machine-readable results, and analysis scripts. Run candidates in isolated processes with identical workloads; do not let benchmark order or allocator-specific tuning create an unfair comparison.

## 6. Correctness and regression gates

- Run the same functional and stress test suites under every candidate.
- Include concurrent allocation/deallocation stress and repeated startup/shutdown.
- Exercise FFI ownership paths and prove that memory is freed by the allocator that owns it.
- Use sanitizers or allocator diagnostics where available; document unsupported combinations.
- Test out-of-memory and allocation-failure behavior to the extent supported by the platform and Rust integration.
- Verify that allocator choice does not alter observable LLMLang semantics or hide resource-lifecycle defects.
- Preserve the platform default as a working fallback unless evidence justifies a narrower target policy.

## 7. Required outputs

1. A compatibility matrix by allocator, target, Rust integration method, FFI boundary, and deployment mode.
2. A workload/allocation profile for LLMLang with representative input provenance.
3. Reproducible benchmark harness, commands, raw results, and statistical analysis.
4. Correctness/stress-test results and explicit unsupported combinations.
5. A comparison of process-wide, per-executable, and any justified component-level selection models.
6. A recommendation with confidence, limitations, target scope, rollback/fallback plan, and explicit reasons for rejecting alternatives.
7. If evidence is insufficient or gains are workload-specific, a documented decision to retain the default allocator or defer selection.

## 8. Exit criteria

RT-25 is complete only when:

- All mandatory candidates have been assessed or explicitly excluded with reasons.
- Compatibility and FFI ownership constraints are demonstrated, not inferred from successful compilation.
- Representative LLMLang workloads have been benchmarked reproducibly with comparable configurations.
- Correctness and stress tests pass for every candidate recommended for use.
- Performance and memory trade-offs, variance, platform coverage, and operational costs are reported.
- The recommendation is explicitly scoped; no allocator is selected solely from synthetic microbenchmarks or external claims.

Until these criteria are met, allocator selection remains open and the platform/Rust default remains the baseline.
