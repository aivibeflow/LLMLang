# RT-13 — Preserving logical byte views in WebAssembly memory32

**Date** · 2026-11-21

**Baseline** · `8cfb0b7`

**Status** · Bounded native-engine comparison for [Plan §6.3](../../PLAN.md#63-llvm-backend)

## Question and candidate profiles

How should a memory32 target preserve a logical byte view with signed 64-bit offset arithmetic? WebAssembly checks linear-memory bounds at load or store. A successful linear-memory access can still cross a source view's boundary. Likewise, narrowing an i64 offset to i32 before applying the logical bound can turn an invalid offset into a valid-looking address.

| Profile | Required evidence |
|---|---|
| Rely on WebAssembly linear-memory bounds | Suitable only when the declared source bound actually coincides with that linear memory boundary. It cannot encode the view identity and per-view range in this fixture. |
| Check the logical view before narrowing | Retains identity, overflow, and strict logical bounds. Requires a valid descriptor whose physical interval is inside memory and fits the addressing model. |
| Use a checked descriptor or runtime call | Can move descriptor validation and policy into a reusable boundary. Adds runtime and ABI obligations. The fixture supplies descriptors from the host rather than implementing this option. |

[WebAssembly Core 2.0 memory instructions](https://www.w3.org/TR/wasm-core-2/#memory-instructions) · [LLVM and C++ mutable views](../RT-09/RT-09-13-MUTABLE-BYTE-VIEW-PRESERVATION.md)

## Method and results

A handwritten Wasm module implements byte read and replace over five trusted descriptors for one six-byte slab. It first checks logical identity, then rejects signed addition overflow and checks a strict bound using the full sum. Success narrows to i32, accesses the byte, and optionally writes a fixed value. A JavaScript BigInt oracle evaluates the same operation independently. Each observation compares the status or previous byte, complete slab, and the two surrounding canaries.

The corpus covers every ordered view pair, every pair of 16 offset operands, and read versus replacement. All 12,800 observations matched, including zero-length, adjacent and overlapping views, i64 boundaries, and offsets near 2³².

| Control | Observation |
|---|---|
| Narrow before testing the view bound | Offset 2³² + 1 writes byte 1 of the left view. The source oracle rejects the full-width offset. |
| Remove the logical bound and rely on linear memory | A write immediately after the end of the left view changes the first byte of the adjacent view. Both addresses lie inside the same memory. |

Both modified modules validate and execute. The successful engine access in each control is evidence that source-level bounds need independent preservation checks. The pointer addition in the correct probe is safe under its trusted small descriptor construction. Arbitrary descriptors, capability forgery, memory growth, allocation lifetimes, instrumentation, compiler generation, and real cross-engine comparison remain open.

## Reproduction

Run from the repository root with Node v24.22.1 and WABT 1.0.36. The Debian amd64 WABT archive used here has SHA-256 `55e41a019c5cdade5792a8a6179d4ca1139c4f42ba235c259c476918ac314de6`. The checked WAT input hashes to `f3bc341a41fabd8bab1490dfd9aa8dd23c0fb88cd8b0b61daeaca179cbd6c24e`.

```sh
node research/PROTOTYPES/WASM-VIEWS-01/compare.mjs /path/to/wat2wasm
```

[Executable comparison and controls](../PROTOTYPES/WASM-VIEWS-01/compare.mjs)
