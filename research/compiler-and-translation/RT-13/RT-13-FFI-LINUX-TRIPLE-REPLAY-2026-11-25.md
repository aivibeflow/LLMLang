# Linux FFI execution on x86-64, AArch64 and RV64

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

An independently built C consumer sends a by-value record, a checked update and a callback to a provider. The provider calls the consumer back with ordered attempt and completion events. The separate source oracle observes the returned generation, state and explicit status, and every callback argument in order. It enumerates 224 inputs including unsigned wraparound, an out-of-range request and terminal-state boundaries.

| Target | Execution evidence | ELF closure |
| --- | --- | --- |
| Linux x86-64 | Native host | Exact host glibc 2.41, x86-64 loader and startup objects |
| Linux AArch64 | QEMU 10.0.13 Linux user | Debian glibc 2.41 cross runtime, AArch64 loader and startup objects |
| Linux RV64 LP64D | QEMU 10.0.13 Linux user | Debian glibc 2.41 cross runtime, RV64 LP64D loader and startup objects |

Each target runs both a statically linked provider archive and a load-time shared provider. Glibc is dynamically linked in both configurations. The runner checks the ELF machine, explicit interpreter, dependencies and selected provider and libc via `dladdr`. It hashes the exact resolved library, loader and startup bytes. Toolchain, source and output identities reproduce in two independent build roots.

All six preserving profiles match all 1,344 observations and produce one full trace digest. A deliberately altered shared provider preserves the ABI and all scalar results but omits the commit callback. Full trace comparison rejects 92 successes per target. The linker separately refuses a shared object constructed from the two incompatible cross-architecture objects.

This is a bounded, bidirectional C ABI observation through a provider and its callback. It covers Linux user-mode execution with the pinned runtimes. Physical AArch64 and RV64 hardware, general C ABI coverage, runtime symbol search variation, OS compatibility beyond the checked Linux interfaces and platform support selection remain open.

## Replay

Use Clang/LLD 19.1.7, LLVM ar, GNU readelf and CPython 3.12.14. The cross profiles use the Debian `libc6` and `libc6-dev` cross packages for each CPU at `2.41-11cross1`. Extracted QEMU Linux-user 10.0.13 comes from Debian `qemu-user_10.0.13+ds-0+deb13u1_amd64.deb`, SHA-256 `ca6ede739327a20ae5a3498230c8a3a9a072c586e131bc6bcc1201eb1725e336`.

```sh
fixture=research/compiler-and-translation/RT-13/FFI-LINUX-TRIPLE-REPLAY-01
python "$fixture/run.py" --clang /path/to/clang19 \
  --arm64-root /path/to/aarch64-linux-gnu --rv64-root /path/to/riscv64-linux-gnu \
  --qemu-aarch64 /path/to/qemu-aarch64 --qemu-riscv64 /path/to/qemu-riscv64 \
  --output /tmp/rt13-ffi-linux-triple.json
cmp "$fixture/evidence.json" /tmp/rt13-ffi-linux-triple.json
```

The [evidence ledger](FFI-LINUX-TRIPLE-REPLAY-01/evidence.json) records cross-target and host-native execution separately.
