# RT-13 — Lower the existing byte-view IR to WebAssembly through LLVM

**Date** · 2026-11-21

**Baseline** · `78b0627`

**Status** · Bounded compiler and engine comparison for [Plan §6.3](../../../PLAN.md#63-llvm-backend)

## Question and approach

Can one checked LLVM IR representation realize the same view semantics on native and memory32 targets? Scenario 96B supplied a native LLVM formation and read probe. This experiment reuses its operations and exact Python reference evaluator, changes the target triple to `wasm32-unknown-unknown`, and adds offsets at both edges of the 32-bit narrowing boundary. [Scenario 96B](RESEARCH-SCENARIO-96B-LLVM-BYTE-VIEW-PRESERVATION.md) · [LLVM pointer indexing rules](https://llvm.org/docs/LangRef.html#getelementptr-instruction) · [LLVM lld WebAssembly port](https://lld.llvm.org/WebAssembly.html)

| Generation route | Evidence and cost |
|---|---|
| LLVM IR reused across native and Wasm | Shares checked bounds and formation rules. Still requires target-specific ABI and a separate code-generation check. |
| Generate Wasm directly | Can express the memory32 ABI and target instructions deliberately. Requires a separate lowering or translator and preservation evidence. |
| Call a target runtime for all view operations | Can centralize descriptor validation and special cases. Requires an explicit ABI, deployment and toolchain contract for the runtime. |

The LLVM path uses the existing verified O0 and O3 pipelines, then `llc` and `wasm-ld`. The linked module exports the two entry points and memory, with no imports required by this fixture. A Node host uses Wasm i64 BigInt arguments without numeric narrowing. For successful formation, the host measures the returned integer address relative to the slab. For read, it compares the referenced byte. Both cases compare the status and verify that rejected operations retain the output sentinel.

## Results

The experiment compares two operations, 25 ordered view/expected pairs and both operands from a set of 18 values. Both modules match all 16,200 observations, or 32,400 comparisons total. The set includes signed i64 overflow boundaries, logical view boundaries, offsets at ±2³² and empty views. The final input slab remains equal to its original bytes.

| Artifact | SHA-256 |
|---|---|
| Input LLVM IR after triple change | `69d4184e269ac2b350ed0d8aa65d27a9faca1dd9ac590bf1a3259eff82a3ac6b` |
| Wasm O0 | `e8161a3549e7fbadfd8acaa1d308693bcdd8e5f1b72a150812390ef596ca1467` |
| Wasm O3 | `b9609fba032fa20224a64f64d256ae4b43bd51ded38c2d1c83fea23972113e3f` |

The result supports LLVM as one candidate generation route for this view fragment. Valid descriptors and output locations are supplied by the harness. The observation does not prove general pointer provenance, validate arbitrary descriptors, establish defenses for shared linear memory, or compare performance or interoperability with other Wasm tools or engines. The host inspects addresses as integers for testing and does not reconstruct a source pointer from the result.

## Reproduction

From the repository root use CPython 3.12.14, Node v24.22.1 and Debian LLVM/lld 19.1.7. The recorded lld amd64 package SHA-256 is `756a805e8811d527dd2b5417f016c9342b8631fa9c1ddcd56265c13ae33bf3a4`.

```sh
python -B research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01/llvm_wasm_view_probe.py \
  --opt /path/to/opt --llc /path/to/llc --wasm-ld /path/to/wasm-ld
```

[Compiler probe](../PROTOTYPES/LLVM-PRESERVATION-01/llvm_wasm_view_probe.py) · [Engine harness](../PROTOTYPES/LLVM-PRESERVATION-01/wasm_view_host.mjs)
