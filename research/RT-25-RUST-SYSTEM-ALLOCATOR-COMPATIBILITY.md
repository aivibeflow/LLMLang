# RT-25 — Rust System allocator compatibility on Linux

**Date** · 2026-11-21

**Baseline** · `55f9c27`

**Status** · Bounded native compatibility experiment for [Plan §7.1](../PLAN.md#71-performance-and-scalability)

## Question and integration variants

Does Rust's explicit `System` boundary preserve zeroing, alignment and resize ownership when glibc and jemalloc supply the process allocation symbols? This test compares the same dynamically linked Rust executable in separate processes. It records the actual provider of `malloc`, `calloc`, `realloc`, `free` and `posix_memalign` through `dladdr`.

| Variant | Trade-off |
|---|---|
| Rust `System` with the platform allocator | Baseline supported by the toolchain. Linux dynamic linkage determines the provider in this fixture. |
| Rust `System` through process-wide symbol interposition | Allows a controlled provider comparison with one executable. It covers dynamically interposed symbols and depends on loader behavior, startup and library boundaries. |
| Use a named allocator or scoped allocator API | Can make integration and isolation explicit. Requires handling ownership at every FFI boundary and evaluating static linkage, initialization and platform support. This probe does not implement this variant. |

[Rust System documentation](https://doc.rust-lang.org/std/alloc/struct.System.html) · [Rust GlobalAlloc contract](https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html) · [RT-25 requirements](RT-25-MEMORY-ALLOCATOR-COMPATIBILITY-AND-BENCHMARKING.md)

## Results

Four threads each run 16 rounds of ten allocation sizes and five alignments. Each round checks zeroing and alignment, fills a known pattern, grows the allocation, checks the preserved prefix and original alignment, shrinks it, and releases it with its matching layout through `System`. A separate ordinary C allocation checks that an impossible resize returns null and leaves the original buffer valid for reading and deallocation.

| Provider verified at runtime | Rust sequences | C failure probe |
|---|---:|---|
| glibc 2.41 | 3,200 passed | Original storage and all 32 bytes preserved |
| jemalloc 5.3.0 | 3,200 passed | Original storage and all 32 bytes preserved |

Every direct C symbol in the probe resolved to the expected provider. This is evidence for native allocator compatibility under one dynamic Linux configuration. It does not justify freeing storage through a different allocator API. It does not cover all native library allocations, Rust global allocator replacement, binary-only or statically linked libraries, allocator teardown, TCMalloc, mimalloc or representative runtime performance. The Linux default remains the baseline until RT-25's wider correctness, portability and benchmark gates are met.

## Reproduction

On Linux x86-64 use Rust 1.85.1 and optimization level 3. The observed packages were glibc `2.41-12+deb13u4` and jemalloc `5.3.0-3`. [Native probe](PROTOTYPES/ALLOCATOR-COMPAT-01/probe.rs)

```sh
out=$(mktemp -d)
rustc --edition=2024 -C opt-level=3 -D warnings \
  research/PROTOTYPES/ALLOCATOR-COMPAT-01/probe.rs -o "$out/allocator-probe"
env -u LD_PRELOAD "$out/allocator-probe" libc.so.6
env LD_PRELOAD=/path/to/libjemalloc.so.2 "$out/allocator-probe" libjemalloc.so.2
```
