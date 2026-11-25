# Mixed-language ownership through one C runtime

[GitHub #328](https://github.com/aivibeflow/LLMLang/issues/328) · 2026-11-25

C17, C++20, Go cgo and Rust adapters use the same dynamically linked C provider in one process. The provider owns a single live slot and mediates create, transfer, read and release through a fixed-width C ABI. A generation identifies the live handle, and its current owner determines admissible operations. A separate source-level Python state machine defines the expected result and state transition.

## Behavior and incremental replacement

Every ordered assignment of the four languages to create, transfer, read and release is exercised. For each assignment the runner checks all ordered pairs of distinct owners and four payloads. The resulting 1,152 mixed-language scenarios cover 12,672 steps. They check duplicate create, invalid recipients, observable ownership after transfer, former-owner denial, release, stale generations and reuse of the slot. The runner observes both the packed call result and the actual provider state after each step. All observations match the source-level model.

A separate run creates and releases all 65,535 generations. Go then attempts another allocation, which returns exhaustion, and Rust attempts a stale read. All 131,072 calls match the oracle. This exercise establishes the one-slot lifetime bound and refusal behavior within a single runtime session. The fixture reset is a test operation.

The runner then rebuilds only the C++ adapter. The new adapter keeps the ABI and dependency list, but requests a transfer back to the caller. It changes 2,304 full observations, of which 288 initially retain the expected call result while changing provider state. Provider and other adapter bytes remain identical. The downstream mismatches include other languages because they observe the changed common state. Two independent working directories and separate Go build caches reproduce the same ELF digests and native trace ledger.

## Cost observed on the shared Linux runner

GCC and G++ 14.2.0, Go 1.23.6 and Rust 1.85.1 build the Linux x86-64 binaries. The common provider measures 15,208 ELF bytes and 507 bytes of text. All adapters declare `libowned.so`. Go and Rust have additional dynamic dependencies recorded in the ledger.

| Adapter | ELF bytes | ELF bytes after debug stripping | .text bytes | Read latency min / median / max, ns |
| --- | ---: | ---: | ---: | ---: |
| C | 15,128 | 15,008 | 197 | 2.98 / 2.98 / 3.77 |
| C++ | 15,128 | 15,008 | 197 | 2.98 / 3.55 / 5.61 |
| Go cgo | 1,644,200 | 1,196,320 | 429,859 | 114.19 / 125.91 / 144.27 |
| Rust | 3,554,152 | 15,264 | 231 | 2.98 / 3.36 / 5.51 |

The native timing driver pins the process to one logical CPU in this recorded run. After a warm-up, it measures wall time for 100,000 successful reads per adapter in each of seven rotated rounds and checks every round's checksum. Each figure is elapsed time per call across the driver, adapter and provider. The [raw timing samples](SHARED-OWNERSHIP-RUNTIME-01/timing-host.json) describe this runner only. They leave cold initialization, contention, allocator overhead, other platforms and representative application workloads open.

The candidate covers a serialized ownership service. It leaves concurrent ownership, bounded allocation with multiple objects, session identity, exception containment, provider upgrade compatibility and integration with a production compiler open.

## Replay

Use CPython 3.12.14, GNU binutils 2.44 and the tool versions above.

```sh
fixture=research/compiler-and-translation/RT-30/SHARED-OWNERSHIP-RUNTIME-01
scratch=$(mktemp -d)
python "$fixture/run.py" --go /path/to/go1.23.6 --go-cache "$scratch/go-cache" \
  --output "$scratch/evidence.json"
cmp "$fixture/evidence.json" "$scratch/evidence.json"
```

To collect timing separately, run the same command with `--timing "$scratch/timing.json"` under `taskset` for an allowed logical CPU. Native semantics, artifact sizes and exact identities are in the [reproducible ledger](SHARED-OWNERSHIP-RUNTIME-01/evidence.json).
