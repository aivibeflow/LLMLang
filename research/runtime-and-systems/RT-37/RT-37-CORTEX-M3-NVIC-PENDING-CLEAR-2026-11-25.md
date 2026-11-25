# RT-37 — Write-one-to-clear semantics for Cortex-M3 interrupt pending bits

Does a read-modify-write update preserve the nonselected pending interrupt when the register clears one bit for every written one? The fixture checks direct mask writes and three candidate mistakes against Cortex-M3 NVIC pending aliases. The branch baseline is `c736e2c863750509fe65a1defa4fdfa805b27974`. [Cortex-M3 device guide](https://documentation-service.arm.com/static/5ea823e69931941038df1af5?token=) · [CMSIS 5.9.0 NVIC operations](https://arm-software.github.io/CMSIS_5/5.9.0/Core/html/group__NVIC__gr.html)

The firmware masks interrupt delivery and sets both selected pending bits. It reads the pending set through both the set alias and clear alias. Each image then applies its policy to one target and reads the resulting state. The two target masks are 1 and 2. A correct clear replaces the first pending set of 3 with 2 or 1, respectively. [Assembly fixture](cortex-m3-nvic-clear/pending.S)

| Write policy | Remaining pending mask when clearing 1 | Remaining pending mask when clearing 2 |
|---|---:|---:|
| Write the selected mask to the clear alias | 2 | 1 |
| Read clear alias, OR with selected mask, and write back | 0 | 0 |
| Read clear alias, AND with complement of selected mask, and write back | 1 | 2 |
| Write the selected mask to the set alias | 3 | 3 |

Both aliases report 3 before every update. Only the direct clear mask preserves the other pending interrupt in both cases. OR writes both observed bits and consequently clears both. AND with the complement writes only the other pending bit and clears it. The set alias leaves both bits pending. [Exact observations and linked image identities](cortex-m3-nvic-clear/evidence.json)

The fixture supports an MMIO operation contract that names the alias, the write-one-to-clear effect, and the writable selection. Readability and physical register width alone leave the update behavior ambiguous. This tests software-pended bits on QEMU's `lm3s6965evb` target. Physical peripheral behavior, concurrent arrivals, active interrupt state, per-IRQ authority, and LLMLang volatile lowering remain open. [MMIO metadata and capabilities](RT-37-MMIO-METADATA-AND-CAPABILITIES-2026-11-24.md) · [Embedded research issue](https://github.com/aivibeflow/LLMLang/issues/440)

## Reproduction

Use Clang 23.1.1 at LLVM revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`, Debian LLVM MC and LLD 19.1.7, QEMU 10.0.13, and CPython 3.12.14. The runner shares the Cortex-M3 UART collector and linker layout. Two Python hash seeds produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-37/cortex-m3-nvic-clear
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang > /tmp/llmlang-rt37-nvic-clear.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt37-nvic-clear.json
```
