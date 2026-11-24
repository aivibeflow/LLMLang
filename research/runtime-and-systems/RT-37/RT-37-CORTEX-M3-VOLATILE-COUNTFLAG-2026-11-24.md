# Preserving read-to-clear SysTick loads on Cortex-M3

- **Date:** 2026-11-24
- **Research:** RT-37 EMB-03, RT-13 and DEP-249
- **Baseline:** `0aa0527b0df36b94ba3b4ec4a4bd06aca0db2915`
- **Evidence:** Seven closed ELF images, linked Thumb load observations and exact UART traces

Two volatile word reads of SysTick `CTRL` observe `COUNTFLAG` as `1` and then `0`. LLVM and Rust preserve that pair at O2, and direct LLVM also preserves it at O0. The ordinary-load controls emit `1` twice. In the LLVM O0 control, two loads survive the IR pipeline and a single load reaches the linked image.

## Fixture and controls

The QEMU `lm3s6965evb` fixture enables SysTick without interrupt delivery, lets the timer latch `COUNTFLAG`, and disables counting before the compiled routine reads `CTRL` at `0xe000e010`. The two flag bits are sent over UART in read order. A deterministic instruction-count clock makes it possible to repeat the latch sequence without relying on host scheduling.

The direct LLVM function uses two `load volatile i32` instructions and the Rust function uses two `core::ptr::read_volatile` calls. Each ordinary-load control replaces only the access form. The static check disassembles the exact linked `sample_pair` function and records the word loads through the CSR pointer. The LLVM path also records the load count after the chosen IR passes.

| Backend and access form | Post-pass LLVM IR word loads | Linked word loads | UART trace |
| --- | ---: | ---: | --- |
| LLVM volatile, O0 | 2 | 2 | `B10!` |
| LLVM ordinary, O0 | 2 | 1 | `B11!` |
| LLVM volatile, O2 | 2 | 2 | `B10!` |
| LLVM ordinary, O2 | 1 | 1 | `B11!` |
| Rust volatile, O2 | — | 2 | `B10!` |
| Rust ordinary, O2 | — | 1 | `B11!` |
| Rust volatile, O2, with a nonzero write to `VAL` after latching | — | 2 | `B00!` |

The `VAL` control writes `0x1234`, requires an immediate read of zero from `VAL`, then checks that both volatile reads observe a cleared flag. It exercises the reset effect separately from either optimization path. [RT-37 metadata and capability study](RT-37-MMIO-METADATA-AND-CAPABILITIES-2026-11-24.md)

## Reproduce and scope

Use LLVM/LLD 19.1.7, Rust 1.85.1, Python 3.12.14 and QEMU 10.0.13. The program runs with `-icount shift=0,align=off,sleep=off`. The [ledger](cortex-m3-volatile/results.json) records the exact build inputs, ELF hashes, load observations and UART bytes. The live access images occupy 224–228 bytes in flash and four bytes of static SRAM. The reset control occupies 244 bytes of flash and the same static SRAM.

Twenty fresh runs rebuilt and booted all seven images and reproduced the ledger byte for byte.

```sh
fixture=research/runtime-and-systems/RT-37/cortex-m3-volatile
output=$(mktemp)
python3 -B "$fixture/run.py" --qemu "$(command -v qemu-system-arm)" --output "$output"
cmp "$fixture/results.json" "$output"
```

This result covers the two 32-bit accesses to a modeled read-to-clear register and the selected optimization paths. General MMIO ordering, barriers, interrupt/DMA interleavings and physical board timing require separate evidence.
