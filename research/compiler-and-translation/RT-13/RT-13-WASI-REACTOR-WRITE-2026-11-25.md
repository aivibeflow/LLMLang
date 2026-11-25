# WASI Preview 1 reactor output across direct and LLVM builds

[GitHub #330](https://github.com/aivibeflow/LLMLang/issues/330) · 2026-11-25

The fixture writes two ordered vectors through one WASI Preview 1 reactor export. The source contract checks initialization and each unsigned length before the host call, preserves WASI errors and reports the exact written prefix on success. A returned count above the requested length yields a distinct error. The test includes zero lengths, boundary values, invalid unsigned lengths, a bad descriptor, and byte wrapping.

## Real and modeled host observations

A direct WAT module and two C17 modules lowered through Clang and LLD export memory, `_initialize` and `emit`. The only imported operation is `wasi_snapshot_preview1.fd_write`. WABT validates all three. Node 22.23.5 and Node 24.22.3 instantiate each module with their WASI Preview 1 implementation and a configured output file. Both host versions refuse to run the reactor as a command. An absent write import prevents instantiation, and calling `emit` before initialization returns the fixture's explicit error.

Each module and host profile checks 588 real statuses. The configured output file contains all 1,080 expected bytes in source order. The two additional host fixtures inject short progress and an impossible progress count. Every short-progress case preserves the accepted prefix, which can cross the vector boundary. Every over-report fails admission. The simulated host counts 300 calls per policy and profile, confirming that invalid lengths and uninitialized calls stay outside the import. The experiment totals 3,528 real-host and 7,056 simulated-host observations.

| Lowering | Wasm bytes | Complete matches per host across all three modes |
| --- | ---: | ---: |
| WABT direct WAT | 283 | 1,764 |
| Clang/LLD 19.1.7 O0 | 839 | 1,764 |
| Clang/LLD 19.1.7 O2 | 467 | 1,764 |

The direct module is smaller for this hand-written leaf. The LLVM route provides a compiler-generated lowering of the freestanding C implementation. Both realize the declared import and reactor contract in the tested Node runtimes. The sizes measure emitted module bytes. This experiment leaves independent WASI implementations, Preview 2 components, async I/O, native short writes, broader application footprints and the production toolchain choice open.

## Replay

Use CPython 3.12.14, Clang and wasm-ld 19.1.7, WABT 1.0.36 and the two Node versions above.

```sh
fixture=research/compiler-and-translation/RT-13/WASI-REACTOR-WRITE-01
python "$fixture/run.py" --clang /path/to/clang19 --linker /path/to/wasm-ld19 \
  --node /path/to/node22 --node /path/to/node24 --output /tmp/rt13-wasi-reactor.json
cmp "$fixture/evidence.json" /tmp/rt13-wasi-reactor.json
```

Two full replays produced identical [evidence ledgers](WASI-REACTOR-WRITE-01/evidence.json).
