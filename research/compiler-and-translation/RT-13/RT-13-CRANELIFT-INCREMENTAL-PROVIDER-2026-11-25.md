# Cranelift JIT provider edits and code lifetime

[GitHub #330](https://github.com/aivibeflow/LLMLang/issues/330) · 2026-11-25

A hosted function calls one provider and adds one to its result modulo 2³². The provider changes from an addend of 13 to 29. Two Cranelift routes exercise the same edit. One emits a direct call within a JIT module. The other compiles an entry with a provider pointer argument and keeps provider code in a separately owned JIT module.

## Executed observations

Cranelift 0.116.1 on x86-64 Linux generates two complete code generations at optimization levels `none` and `speed`. A duplicate definition of a finalized direct provider returns `DuplicateDefinition`. The direct route compiles two functions in a fresh module on the edit. The indirect route retains the entry and compiles one new provider. A Rust wrapper checks the measured ABI before each call and borrows the owning modules throughout execution.

An independent Python oracle checks 260 inputs across both generations, both call routes and both optimization modes. All 2,080 native comparisons agree with their exact binding. Reusing an old binding for the new request changes all 1,040 affected observations. After the old modules are freed, the two new entry paths continue to produce the expected result in each mode. The harness holds no callable reference to freed code.

| Artifact | Pre-relocation bytes in both modes | Recompiled on the edit |
| --- | ---: | --- |
| Direct-call entry plus provider | 17 + 12 | Both functions |
| Indirect entry | 14 | Entry retained |
| Indirect provider | 12 | Provider only |

The direct caller's pre-relocation bytes are identical across the edit, but its module owns a different resolved provider. The indirect caller's bytes are also unchanged. Its runtime dispatch uses the explicitly supplied provider pointer. These byte counts exclude page allocations, relocations, debug data and host support.

## Admission and integration

Eight controls per mode qualify each receipt by call route, generation, caller and provider code digests, optimization profile and live ownership. Stale receipts, released generations and a current generation with the wrong provider or optimization profile are refused. The controls model admission using fixture data. Native execution independently checks the selected code. The isolated result makes provider indirection a candidate for scoped Debug or JIT edits with explicit lifetime and binding responsibilities.

An earlier study compares LLVM ORC and Cranelift unwind registration and source attribution. Together the fixtures cover two native ABI integration choices and an incremental edit case. Production decisions still depend on target coverage, debugger stepping, concurrent code retirement, exact relocation manifests, workload latency and recurring maintenance. [JIT unwind and callback origins](RT-13-JIT-UNWIND-AND-CALLBACK-ORIGINS-2026-11-25.md) · [Cranelift and LLVM checked add](RT-13-CRANELIFT-CHECKED-ADD-2026-11-24.md)

## Replay

Use Rust and Cargo 1.85.1 and CPython 3.12.14. Fetch exact lockfile dependencies before the offline build. The crate pins Cranelift 0.116.1.

```sh
fixture=research/compiler-and-translation/RT-13/CRANELIFT-INCREMENTAL-PROVIDER-01
scratch=$(mktemp -d)
cargo fetch --locked --manifest-path "$fixture/Cargo.toml"
CARGO_BUILD_JOBS=2 CARGO_PROFILE_RELEASE_OPT_LEVEL=1 cargo build --offline \
  --release --locked --manifest-path "$fixture/Cargo.toml" --target-dir "$scratch/target"
python "$fixture/run.py" --probe "$scratch/target/release/llmlang-rt13-jit-provider" \
  --output "$scratch/evidence.json"
cmp "$fixture/evidence.json" "$scratch/evidence.json"
```

Two fresh process executions produced identical [evidence ledgers](CRANELIFT-INCREMENTAL-PROVIDER-01/evidence.json).
