# Static FFI closure on Cortex-M, RISC-V and ESP32 Xtensa

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

A common C consumer calls a separately archived provider and receives ordered callbacks. The provider returns a by-value outcome and calls a separate support object. The independent oracle checks seven requests including state updates, failure with retained state, and callback order. The startup seeds a test word and clears it before entering the consumer, making the initialization step observable.

| Profile | Evidence |
| --- | --- |
| Cortex-M3 Thumb | QEMU Stellaris fixture, exact vector/startup and callback trace |
| Cortex-M4F Thumb with hard-float ABI | QEMU MPS2 AN386, exact vector/startup and callback trace, VFP call ABI tag |
| Freestanding RV32 ILP32 | QEMU `virt`, exact callback trace through a 32-bit ELF |
| Freestanding RV64 LP64 | QEMU `virt`, exact callback trace through a 64-bit ELF using the medium-any code model |
| ESP32 LX6 Xtensa call0 and windowed | Independently compiled vendor objects, archive resolution and exact call instruction evidence |

All four executable profiles match seven preserving rows each. Removing the completion effect changes five rows per profile while retaining all statuses and values. Suppressing the startup probe's zeroing yields the early failure marker. The strict link without the support archive fails for each target. The final ARM and RISC-V images have no undefined symbols, dynamic dependencies or relocations. The ARM emulator output uses semihosting as the observation transport. The RISC-V output uses the QEMU board UART.

The selected upstream Clang driver refuses the generic Xtensa C target, while LLVM MC emits an ELF object for an explicit assembly leaf. The pinned Espressif compiler independently emits `call0`/`callx0` and `call8`/`callx8` object routes. Its consumer introduces a `memcpy` dependency even in the freestanding profile. An explicitly compiled memory routine resolves it, leaving only the expected startup marker. The vendor relocatable linker accepts the deliberately mixed call0 and windowed objects. The scoped ABI gate refuses their differing call conventions before execution. ESP32 evidence from this study is object-level.

The independent RT-37 vendor SDK pilot supplies STM32F103, STM32F407 and ESP32 emulator evidence using their exact startup, archives and drivers. The QEMU ARM boards here are different functional fixtures. Native silicon, floating-point boundary behavior, ESP32 mixed-ABI execution and full toolchain support remain open. [Cross-MCU vendor SDK pilot](../../runtime-and-systems/RT-37/RT-37-CROSS-MCU-GPIO-TIMER-UART-2026-11-25.md)

## Replay

Use CPython 3.12.14, Clang/LLD 19.1.7, the LLVM object tools and QEMU 10.0.13 system emulators. Use Espressif `esp-14.2.0_20251107` for the ESP32 object routes. Its toolchain archive has SHA-256 `b0065b3b28d2b5d3bf4868f2fda6bc95d6081025583d1c17b286884bead0305d`.

```sh
fixture=research/compiler-and-translation/RT-13/FFI-FREESTANDING-ARCHIVE-01
python "$fixture/run.py" --clang /path/to/clang19 --qemu-arm /path/to/qemu-system-arm \
  --qemu-rv32 /path/to/qemu-system-riscv32 --qemu-rv64 /path/to/qemu-system-riscv64 \
  --xtensa-bin /path/to/xtensa-esp-elf/bin --output /tmp/rt13-ffi-freestanding.json
cmp "$fixture/evidence.json" /tmp/rt13-ffi-freestanding.json
```

Two clean runs produced identical [evidence ledgers](FFI-FREESTANDING-ARCHIVE-01/evidence.json).
