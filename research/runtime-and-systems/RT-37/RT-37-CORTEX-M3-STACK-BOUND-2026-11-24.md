# Stack depth of Cortex-M3 polling and SysTick delivery

- **Date:** 2026-11-24
- **Research:** RT-37 EMB-02/07, RT-34 and DEP-250
- **Baseline:** `690ccbbb00ac2a93b5b54871f6d19a2e710eedd6`
- **Evidence:** Twelve exact linked images, a direct-control stack model and independent QEMU measurements

The Cortex-M3 polling workload touches eight bytes of stack. The interrupt workload touches 32 bytes even though the handler has zero software frame bytes. A control shifts the thread stack pointer by four bytes while SysTick is armed. The deepest access moves to 40 bytes, and the stacked xPSR records alignment padding. Direct LLVM and freestanding Rust reach the same depths in this workload.

## Model and observations

The [timer and GPIO result](RT-37-CORTEX-M3-SYSTICK-GPIO-2026-11-24.md) supplies the board, startup, timer driver, step functions and independent controller oracle. The stack experiment uses the same 14 steps and pins the main stack pointer (MSP) at the eight-byte-aligned SRAM top. It verifies that the highest static SRAM load ends below the 128-byte measurement window. The probe explicitly enables `CCR.STKALIGN` at startup and records the minimum MSP and the xPSR alignment bit from the basic exception frame on handler entry.

The [model](cortex-m3-stack/stack_model.py) traverses the linked Thumb disassembly from reset and the ISR. It follows direct branches and calls, checks that saved link registers and restored PCs match, and tracks the byte depth at each reachable instruction. It rejects stack and control-flow instructions outside the supported subset. For SysTick it adds the 32-byte basic Cortex-M3 exception frame and four alignment bytes when the current thread stack is only four-byte aligned. One estimate allows an interrupt at any reachable software depth. The tighter estimate uses the measured configuration and the fixture's armed wait interval, where SysTick can fire before the counter is published.

| Timer profile, both backends | Maximum thread-only depth | Any-phase stack bound | Armed-phase stack bound | QEMU watermark | QEMU handler MSP depth | Stacked xPSR alignment bit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Polling | 8 B | 8 B | 8 B | 8 B | No invocation | No invocation |
| Interrupt, aligned wait | 8 B | 40 B | 32 B | 32 B | 32 B | 0 |
| Interrupt, four-byte thread reservation in the wait | 8 B | 40 B | 40 B | 40 B | 40 B | 1 |

Every image reproduces the controller's duty and GPIO trace. Each profile is linked with both backends and two different stack paint values. Both paints report the same high-water depth as the disassembly model under the armed-phase assumption. The control would fit a 36-byte budget if the model counted four software bytes plus the basic 32-byte frame alone. The measured stack and saved alignment bit reject that budget.

## Reproduce and scope

Use LLVM/LLD 19.1.7, Rust 1.85.1, Python 3.12.14 and QEMU 10.0.13 with the pinned `lm3s6965evb` target. Both backend step functions compile at optimization level 2. The [ledger](cortex-m3-stack/results.json) records exact source and image hashes, ELF resource extents, both static bounds and the UART observations. The final three hex fields are bytes to the first changed paint word, bytes from the initial stack top to the deepest handler entry, and the saved alignment bit. The polling result encodes absence of a handler sample as zero.

The instrumented images have 860–880 bytes of linked flash and 20 bytes of static SRAM. Ten fresh runs rebuilt and booted all twelve images and reproduced the ledger byte for byte.

```sh
fixture=research/runtime-and-systems/RT-37/cortex-m3-stack
output=$(mktemp)
python3 -B "$fixture/run.py" --qemu "$(command -v qemu-system-arm)" --output "$output"
cmp "$fixture/results.json" "$output"
```

The comparison assumes one basic MSP exception frame at a time, no other exceptions in the admitted execution, stable saved return links and disjoint stack and device/data writes. The phase-specific bound further assumes SysTick is pending only inside the admitted armed interval. The software model and QEMU exercise the linked fixture under these assumptions. Nested interrupts, alternate stacks, additional ISR calls, hardware calibration, latency and WCET remain open.
