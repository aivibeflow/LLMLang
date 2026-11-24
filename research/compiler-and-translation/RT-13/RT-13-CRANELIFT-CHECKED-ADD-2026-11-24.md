# RT-13 Cranelift JIT and LLVM checked-add comparison

Cranelift JIT and LLVM produced the same status, ordered callbacks and output-slot contents as the source evaluator in 4,596 cases at each of four optimization settings. In this fixture Cranelift emitted the same 174 bytes with and without its speed optimization profile. LLVM reduced the function from 108 bytes at O0 to 57 at O3. These observations provide a bounded JIT candidate and a code-size comparison on x86-64.

## Shared workload and ABI

The study reuses the independent evaluator and LLVM lowering for [Scenario 96A checked addition](RT-13-LLVM-CHECKED-ADD-OBSERVATIONS-2026-11-24.md). The function takes two 32-bit arguments, a 32-bit enable value, a returning callback and an aligned writable output slot. It records the first argument with the callback. When disabled, it returns the second argument after emitting it and storing it. When enabled, a valid signed sum is emitted and stored. Overflow returns status 1 after the first callback and preserves the output slot.

The Cranelift implementation uses an explicit control-flow graph and `sadd_overflow`. Calls are indirect through the same callback ABI as the LLVM fixture. The runner uses generic x86-64 features for both paths. It retains the CLIF and native hashes, verifies that the readable finalized JIT bytes equal the compilation buffer, and invokes the actual function address. The LLVM side compiles and links the exact IR with no unresolved object symbols and measures the emitted function extent. Input coverage comprises 500 combinations of boundary operands and five ABI enable bit patterns, plus 4,096 deterministic generated triples.

| Pipeline | Observations checked | Function bytes |
| --- | ---: | ---: |
| LLVM 19.1.7 O0, shared object | 4,596 | 108 |
| LLVM 19.1.7 O3, shared object | 4,596 | 57 |
| Cranelift 0.116.1 `none`, in-process JIT | 4,596 | 174 |
| Cranelift 0.116.1 `speed`, in-process JIT | 4,596 | 174 |

All four pipelines matched the independent evaluator. For each Cranelift mode, the dropped overflow branch changed status, callbacks and output. A second control reversed the callbacks while preserving status and output. A third wrote zero on overflow while preserving status and callback. The scoped ABI checker distinguished all six negative runs.

## Scope for backend selection

The JIT result supports a bounded host execution path without a separately linked object for this function. Machine construction and execution depend on the Cranelift frontend lowering, JIT memory lifecycle, native ABI and callback contract. The LLVM reference has a separate whole-domain IR proof for checked addition; the finite JIT observations leave whole-domain CLIF and machine correspondence open. The single function neither measures compilation latency, debug information quality or runtime throughput nor establishes comparative target coverage.

The Cranelift crates are locked to 0.116.1, whose codegen crate records upstream commit `58282df898d79a787a726d829b166272dde155b9`. Use Rust 1.85.1, LLVM 19.1.7 and GCC 14.2.0 for the recorded manifest. [Exact functions, input hashes and control observations](cranelift-checked-add/results.json).

```sh
fixture=research/compiler-and-translation/RT-13/cranelift-checked-add
CARGO_BUILD_JOBS=1 CARGO_PROFILE_RELEASE_OPT_LEVEL=1 cargo build --release --locked --manifest-path "$fixture/Cargo.toml"
python3 -B "$fixture/run.py" --probe "$fixture/target/release/llmlang-rt13-cranelift-probe" \
  --output /tmp/llmlang-cranelift-add.json
cmp /tmp/llmlang-cranelift-add.json "$fixture/results.json"
```
