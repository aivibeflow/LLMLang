# RT-25 — Allocation behavior on a synthetic dependency graph

**Date** · 2026-11-24

**Baseline** · `991c053`

**Status** · Comparative measurement for [Plan §7.1](../../PLAN.md#71-performance-and-scalability)

## Question and method

Does changing the process allocator produce a consistent time or resident-memory advantage on an allocation pattern resembling dependency analysis? This experiment holds one Rust executable fixed and compares its Linux default glibc provider with jemalloc via dynamic interposition. The earlier compatibility probe checked alignment and resize ownership. This probe checks what the two configurations cost on one larger workload. [Compatibility evidence](RT-25-RUST-SYSTEM-ALLOCATOR-COMPATIBILITY.md)

The program constructs 200,000 named nodes and 995,740 incoming edges. It retains a name map and reverse-use index, traverses from four roots, and serializes visited nodes into temporary text buffers. All 16 processes returned the same traversal checksum. The measured phases start after a small warm-up and provider verification. There are eight fresh processes per provider, alternating order. Each ran on logical CPU 0 under the same container quota. Memory is absolute process RSS, including runtime startup and allocator overhead. Post-drop RSS is sampled 50 ms after releasing the graph and is neither a fragmentation estimate nor evidence of eventual reclamation.

## Results

Time is in milliseconds. Memory is in KiB. Entries report median and observed range.

| Measurement | glibc | jemalloc |
|---|---:|---:|
| Build | 59.9 (53.5–121.6) | 61.3 (58.3–72.4) |
| Traverse and serialize | 108.1 (103.1–118.4) | 106.4 (97.2–115.6) |
| Live graph RSS | 45,410 (45,312–45,436) | 44,366 (44,348–44,472) |
| Peak RSS | 49,554 (49,456–49,580) | 54,680 (54,676–54,684) |
| RSS after drop | 36,418 (36,320–36,444) | 36,348 (36,232–44,440) |

The observed time ranges overlap. Jemalloc had lower RSS with the graph live and higher peak RSS once the traversal buffers were included. Its post-drop samples varied more. The measurements support retaining separate time, live, peak and quiescent metrics. They do not establish a portable latency advantage, derive confidence intervals from eight samples, or justify selecting either provider for production. Independent host load, other allocator versions, parallel graph workloads, non-Linux targets, TCMalloc, mimalloc, and measured workload provenance from the actual toolchain remain open.

## Reproduction

The raw artifact includes order, durations, sampled memory, provider package versions, CPU/quota, compiler version and the workload source hash. The observed settings were CPython 3.12.14, Rust 1.85.1 at O3, glibc 2.41, jemalloc 5.3.0 and Linux x86-64.

```sh
python -B research/PROTOTYPES/ALLOCATOR-BENCH-01/run.py \
  --jemalloc /path/to/libjemalloc.so.2 --samples 8 --output /tmp/allocator-samples.json
```

[Raw observations](../PROTOTYPES/ALLOCATOR-BENCH-01/results-linux-x86_64.json) · [Runner](../PROTOTYPES/ALLOCATOR-BENCH-01/run.py) · [Workload](../PROTOTYPES/ALLOCATOR-BENCH-01/graph.rs)
