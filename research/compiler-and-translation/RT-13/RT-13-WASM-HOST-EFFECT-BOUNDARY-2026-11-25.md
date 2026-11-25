# RT-13 — Wasm host effects and integer admission

Can direct Wasm and LLVM-generated Wasm share the same effectful source contract across JavaScript hosts? This fixture compares one module assembled from WAT with two generated from freestanding C through LLVM. The branch baseline is `329787504d3f57a41043977a3bcbad1a688095aa`. [Wasm memory32 validation](RT-13-LLVM-WASM-BYTE-VIEW-LOWERING.md) · [LLVM backend issue](https://github.com/aivibeflow/LLMLang/issues/330)

The source operation receives a signed 64-bit request. It admits byte values 0 through 255, records one commit of the exact byte through a named import, and returns that byte. Other representable requests return refusal 256 without an effect. All modules declare the single required `llmlang.commit` import. Each host oracle supplies either the selected recorder, an implementation that omits the recording, or an implementation that changes its payload. [C source](WASM-HOST-EFFECT-BOUNDARY-01/invoke.c) · [Direct WAT](WASM-HOST-EFFECT-BOUNDARY-01/invoke.wat)

| Host binding | Module instantiation | Return mismatches per run | Effect mismatches per run |
|---|---|---:|---:|
| Selected recorder | Success | 0 | 0 |
| Same import shape, missing effect | Success | 0 | 256 |
| Same import shape, changed payload | Success | 0 | 256 |
| Missing import | LinkError | No calls | No calls |

The three artifacts and two Node versions agree over all 4,698 calls across the three instantiated host profiles. The import shape establishes the binding slot and argument carrier. Independent evidence is needed for the actual host operation and its effect. The engine rejects a JavaScript Number at this `i64` boundary. It converts the BigInt value (2^{64}) to zero before entering raw Wasm, so the raw export emits a commit of zero. A host wrapper that checks the signed range first refuses that value with no effect. [WebAssembly JavaScript value conversion](https://webassembly.github.io/spec/js-api/#towebassemblyvalue) · [Exact artifacts and comparison receipts](WASM-HOST-EFFECT-BOUNDARY-01/evidence.json)

This fixture supports separate profile requirements for the target module, host import behavior, and input transport. It covers one signed scalar argument, one imported effect, and two Node profiles. Browser and WASI environments, host authorization, asynchronous effects, resource lifetimes and a production backend choice remain open. [Translation and target backends](TRANSLATION-AND-TARGET-BACKENDS.md)

## Reproduction

Use Clang 23.1.1 at LLVM revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`, Debian Wasm LLD 19.1.7, WABT 1.0.36, Node v22.23.5 and v24.22.3, and CPython 3.12.14. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/compiler-and-translation/RT-13/WASM-HOST-EFFECT-BOUNDARY-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang --node /path/to/node22 --node /path/to/node24 > /tmp/llmlang-rt13-wasm-host.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-wasm-host.json
```
