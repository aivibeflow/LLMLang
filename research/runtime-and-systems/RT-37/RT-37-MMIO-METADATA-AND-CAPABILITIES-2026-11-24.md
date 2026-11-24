# Register metadata and MMIO operation admission

- **Date:** 2026-11-24
- **Research:** RT-37 EMB-03/04, RT-04 and DEP-246
- **Baseline:** `5434727fae861c42887419f63c06b22cc6c33807`
- **Evidence:** Exact SVD, header and emulator inputs, 33 admission cases and earlier runtime discriminators

Register width and access direction leave important MMIO behavior unspecified. The Cortex-M3 header describes SysTick `CTRL` and `VAL` as read/write. QEMU clears `COUNTFLAG` when `CTRL` is read, and a write to `VAL` resets the current count instead of storing the supplied value. Ordinary loads and stores inferred from the qualifiers miss both differences.

## Import and applicability

The ARMCM3 SVD has zero peripherals and fails the pinned CMSIS schema because `<peripherals>` is missing. The accompanying Cortex-M3 header supplies core register addresses, directions and bit positions. The TM4C123GH6PM SVD passes that schema check. Its `GPIOF` derives the register declarations from `GPIOA`. Inheritance supplies `read-write` for `DATA` at `0x400253fc`, `read-write` for `DIR` at `0x40025400`, and `write-only` for `ICR` at `0x4002541c`. Its AHB `DATA` alias is at `0x4005d3fc`. None of these entries carries `readAction` or `modifiedWriteValues`, both of which the pinned schema can represent.

The pinned community dataset has no LM3S or Stellaris SVD. Matching GPIO addresses in the related TM4C file supply a comparison for layout extraction. QEMU's `lm3s6965evb` model supplies the separate behavioral authority for this experiment. Requests to physical TM4C hardware remain unresolved in the protocol comparison.

## Admission comparison

| Candidate | Allowed | Denied | Unknown | Allowed outside the scoped protocol |
| --- | ---: | ---: | ---: | ---: |
| Address and register width | 31 | 1 | 1 | 17 |
| Layout and access direction | 28 | 4 | 1 | 14 |
| Device, capability and explicit operation | 14 | 15 | 4 | 0 |

Direction checking distinguishes calibration reads from writes and rejects reads of the write-only GPIO interrupt-clear register. The checked protocol also requires a controller capability and explicit operations with effects. A `consume` on `CTRL` performs one volatile load. Resetting `VAL` writes zero through a reset operation. Pending-set and pending-clear each write a single allowed bit to `ICSR`. Reading and rewriting `ICSR` can echo the set bit alongside the clear bit, and the emulator handles set first. A generic modify operation fails admission.

For GPIO pin 1, the accepted store uses `0x40025008` with the value bounded by mask `0x02`. A request to write both pin values through that capability fails. The earlier QEMU test reads `02` after a full-port write that clears the neighboring pin. It also distinguishes clearing and leaving a forced SysTick pending bit with 14 and 15 handler invocations. Those runtime controls cover the previous binary's masking and pending paths. The clear-on-read and write-any-reset behavior in this study comes from the pinned emulator source. [Timer/GPIO experiment](RT-37-CORTEX-M3-SYSTICK-GPIO-2026-11-24.md)

## Reproduce and scope

Use Python 3.12.14 and lxml 6.1.1. Copy the exact input blobs to a directory under their basenames. The [ledger](mmio-metadata/results.json) records SHA-256 values, derived addresses and widths, schema checks and case outcomes.

| Checkout and revision | Paths |
| --- | --- |
| [ARM-software/CMSIS_5](https://github.com/ARM-software/CMSIS_5/tree/61e36449f53c25ef7825c40f7dd93685736f457f) | `Device/ARM/SVD/ARMCM3.svd`, `CMSIS/Utilities/CMSIS-SVD.xsd`, `CMSIS/Core/Include/core_cm3.h` |
| [cmsis-svd/cmsis-svd-data](https://github.com/cmsis-svd/cmsis-svd-data/blob/c65f8551e57c770344d229dcaa0bf838fa29aff4/data/TexasInstruments/TM4C123GH6PM.svd) | `data/TexasInstruments/TM4C123GH6PM.svd` |
| [QEMU v10.0.13](https://github.com/qemu/qemu/tree/98f88efe8f07067667b8d9b1a5ce9551d34036c1) | `hw/arm/stellaris.c`, `hw/intc/armv7m_nvic.c`, `hw/timer/armv7m_systick.c`, `hw/gpio/pl061.c` |

```sh
fixture=research/runtime-and-systems/RT-37/mmio-metadata
output=$(mktemp)
python3 -B "$fixture/run.py" --inputs /path/to/pinned/blobs --output "$output"
cmp "$fixture/results.json" "$output"
```

This is a scoped admission comparison, with controller authority supplied as an input. Automatic LLMLang capability proof, derived clusters and arrays, verified volatile lowering, DMA ownership and physical board evidence remain separate.
