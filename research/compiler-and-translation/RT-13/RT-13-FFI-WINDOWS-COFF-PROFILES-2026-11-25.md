# Windows x64 and ARM64 COFF artifacts and import-library identity

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

The experiment cross-builds an SDK-independent C ABI leaf from Linux for Windows x64 and ARM64. Provider and consumer are separately compiled. The provider exports one by-value record operation. Each target builds a static archive, DLL, import library and independently linked consumers. The runner checks PE machine headers, import and export tables, the COFF short-import record and exact artifact digests.

Both profiles verify LLP64 geometry, including a 16-byte record aligned at eight bytes. Their actual lowered signatures differ. Windows x64 returns through a hidden `sret` pointer and passes the record by address. ARM64 uses a pair of 64-bit words in both positions. Equal layout and symbol spelling do not establish a shared call convention.

| Link evidence | Outcome on each architecture |
| --- | --- |
| Ordinary call plus matching static archive | PE consumer has no DLL imports. |
| Explicit DLL import plus matching import library | PE consumer imports `record_step` from `provider.dll`. |
| Ordinary call plus matching import library | PE consumer still imports from `provider.dll`. |
| Explicit DLL import plus static archive or renamed export | Linker refuses the missing import symbol. |
| Opposite-architecture static archive | Linker refuses the object machine. |
| Opposite-architecture import library with matching symbol and DLL names | Linker accepts it and emits exactly the same consumer bytes as the matching import library. The package gate refuses the supplied import and DLL machine mismatch. |

The last case separates input import records from the output PE metadata. Both directions produce the expected consumer machine in the linked executable, while the opposite-architecture import record and DLL stay mismatched. The candidate package gate checks the exact import record against the chosen DLL machine and exported symbol before relying on the dependency. The experiment does not run either Windows loader.

Clang's default COFF object time changed static archive bytes across runs even with deterministic archive headers. The reproducible profile sets `-mno-incremental-linker-compatible`, verifies zero object timestamps, uses deterministic archive mode and pins the final PE timestamp. Two independent roots then produce identical DLL, EXE and library digests.

These are cross-build observations on Linux. Native execution, the Windows SDK, CRT integration, signing, runtime loader behavior and PE targets beyond these two profiles remain open.

## Replay

Use CPython 3.12.14 and the LLVM 19.1.7 Clang, LLD, archive and readobj tools.

```sh
fixture=research/compiler-and-translation/RT-13/FFI-WINDOWS-COFF-PROFILES-01
python "$fixture/run.py" --clang /path/to/clang19 --output /tmp/rt13-ffi-windows.json
cmp "$fixture/evidence.json" /tmp/rt13-ffi-windows.json
```

The [ledger](FFI-WINDOWS-COFF-PROFILES-01/evidence.json) records both target triples and all artifact hashes.
