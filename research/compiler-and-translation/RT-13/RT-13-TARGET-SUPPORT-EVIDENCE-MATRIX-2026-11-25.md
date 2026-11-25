# RT-13 — Backend target support evidence matrix

The matrix records the architecture and CPU features, OS boundary, ABI, object format, linker, sysroot or libraries, runtime, toolchain and tested operation for each candidate target profile. The branch baseline is `2ca86bf005c6f49ecd49213dfdc4690e642d05a9`. [Machine-readable target matrix](TARGET-SUPPORT-MATRIX-01/matrix.json) · [LLVM backend issue](https://github.com/aivibeflow/LLMLang/issues/330)

| Profile family | Artifact and environment | Scope of checked evidence |
|---|---|---|
| x86-64 Linux raw | Freestanding ELF64, LLD 23.1.1, native Linux | Raw read, write and exit behavior |
| AArch64 Linux raw | Freestanding ELF64, LLD 23.1.1, QEMU Linux user mode | AArch64 syscall entry and byte traces |
| Cortex-M3 Thumb | Freestanding ELF32, LLD 19.1.7, QEMU board model | Startup copying, clearing and retained RAM |
| Wasm32 JavaScript host | LLVM/Wasm LLD 19.1.7 or direct WABT, two Node versions | Checked scalar input and host import effects |
| RV64 with A, with or without Zabha | Freestanding ELF64, LLD 19.1.7, QEMU machine with two harts | Byte and word RMW and a scoped fence fixture |
| RV64 without A, Zaamo and Zalrsc | Freestanding object, no resolved runtime helper closure | Four required atomic helper symbols |
| AArch64 with or without LSE | LLVM 19.1.7 ELF object inspection | Selected exclusive or LSE instruction forms |
| Hosted x86-64 call-convention comparison | Linux ELF64 with System V and explicit Microsoft x64 function conventions | One aggregate return and a pointer bridge |
| Native x86-64 Windows | PE/COFF, Windows SDK and native execution unverified | Coverage remains unknown |

The machine-readable matrix has 11 profiles. The auditor checks the exact hashes of five underlying receipts and reconciles each family with its runtime or object observations. Nine controls test requested evidence scope. Emulated AArch64 does not establish physical execution. An inspected LSE object has no native runtime evidence in this matrix. An unresolved atomic link has no linked execution evidence. The matching Linux calling convention witness leaves Windows system linkage and execution unverified. A broader operation on a tested native profile also remains unverified. [Matrix audit receipt](TARGET-SUPPORT-MATRIX-01/evidence.json)

The matrix covers currently recorded fixtures and selection constraints. A target-wide conformance or supported-product claim requires broader operations, exact toolchain and ABI profiles, runtime availability, and a reviewed acceptance inventory. This work completes a checked candidate matrix and leaves production target selection open. [LLVM backend architecture](LLVM-BACKEND-ARCHITECTURE.md)

## Reproduction

Use CPython 3.12.14. The audit checks existing receipts without rebuilding their artifacts. The linked source studies carry their tool versions and replay commands. Hash seeds 1 and 2 produced identical audit receipts.

```bash
fixture=research/compiler-and-translation/RT-13/TARGET-SUPPORT-MATRIX-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt13-target-matrix.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-target-matrix.json
```
