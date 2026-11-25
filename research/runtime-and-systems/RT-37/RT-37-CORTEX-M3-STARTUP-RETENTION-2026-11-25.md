# RT-37 — Copied, zeroed and retained Cortex-M3 RAM

Can startup re-entry restore initialized RAM and clear BSS while preserving a separate retained word? Four freestanding Cortex-M3 images use the same linker layout and different startup range policies. The branch baseline is `d146c34c79fb69ace99f042e518eed825f0c6e38`. [Cold startup closure](RT-37-CORTEX-M3-FREESTANDING-CLOSURE-2026-11-24.md) · [Embedded research issue](https://github.com/aivibeflow/LLMLang/issues/440)

The image has a flash load value of 2 for its four-byte `.data` word. RAM then places four-byte `.bss` and `.noinit` regions in that order. The two latter sections are NOBITS in every ELF. Linker assertions check the disjoint intervals and reserve headroom below the selected stack top. The program seeds the three words as hexadecimal `a,b,c`, invokes the initialization routine, and reports the three values. It then seeds `5,6,7` and explicitly calls the same routine again. Both calls occur during one emulated boot.

| Startup policy | First observed data, BSS, retained | Second observed data, BSS, retained |
|---|---|---|
| Exact copy and clear ranges | `2,0,c` | `2,0,7` |
| Clear extends through the retained region | `2,0,0` | `2,0,0` |
| Omit flash copy | `a,0,c` | `5,0,7` |
| Omit BSS clear | `2,b,c` | `2,6,7` |

QEMU reports the exact UART trace for each image. All four preserve the same section types, addresses, lengths and alignment. Only the exact-range startup satisfies all three word conditions in both calls. The oversized clear erases the reserved word despite the unchanged NOBITS layout. Startup code therefore needs to implement and preserve the linker-defined ranges. [Assembly and linker script](cortex-m3-startup-retention/) · [ELF identities and UART traces](cortex-m3-startup-retention/evidence.json)

The scope is software re-entry through the initialization routine on QEMU's `lm3s6965evb` machine. It provides a boundary for a candidate linker and startup contract. Physical reset retention, brownouts, bootloader writes, allocator policies and broader device profiles need separate evidence. [Firmware research brief](README.md)

## Reproduction

Use Clang 23.1.1 at revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689` to preprocess, Debian LLVM MC and LLD 19.1.7 to assemble and link, GNU `readelf`, CPython 3.12.14 and QEMU 10.0.13. Hash seeds 1 and 2 produced byte-identical receipts. The runner reuses the existing probe's QEMU UART completion observation.

```bash
fixture=research/runtime-and-systems/RT-37/cortex-m3-startup-retention
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang > /tmp/llmlang-rt37-startup-retention.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt37-startup-retention.json
```
