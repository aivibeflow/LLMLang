# RT-37 — Cortex-M3 stack observations under nested and deferred exceptions

When does a second pending exception extend stack depth? The fixture extends the [single-exception stack study](RT-37-CORTEX-M3-STACK-BOUND-2026-11-24.md) with four combinations of priority and interrupt masking. The branch baseline is `41d8a3e9ea87d07342ca1eaa1307a28c46aeb281`. [Embedded research issue](https://github.com/aivibeflow/LLMLang/issues/440)

The firmware records the thread's main stack pointer before pending PendSV. The PendSV handler records its entry stack pointer and marker `L`, pends SysTick through ICSR, then records marker `l`. SysTick records its entry stack pointer and marker `H`. Both handlers avoid software stack pushes in the measured region. UART reporting runs after both handlers have executed. `PRIMASK` is raised only in the two selected masking controls. [Assembly fixture](cortex-m3-nested-stack/nested.S)

| Priority and mask policy | Marker order | PendSV displacement | SysTick displacement |
|---|---|---:|---:|
| SysTick higher priority, unmasked | `LHl` | 32 B | 64 B |
| Equal priorities | `LlH` | 32 B | 32 B |
| SysTick higher priority, unmasked inside PendSV after its last marker | `LlH` | 32 B | 64 B |
| SysTick higher priority, unmasked after returning to thread mode | `LlH` | 32 B | 32 B |

The higher-priority unmasked case preempts PendSV. The equal-priority case shares the first-level displacement at the observed entry points. Unmasking inside PendSV produces the same marker order as the equal-priority case and twice the observed frame displacement. The order of application markers therefore leaves the underlying nesting ambiguous. [Exact traces, displacements and image identities](cortex-m3-nested-stack/evidence.json)

The measured quantity is exception-entry displacement from the initial aligned main stack pointer. A bound for firmware needs a justified maximum nesting depth, alignment policy, handler frame usage and all additional software stack consumption. QEMU validates these controlled functional observations on `lm3s6965evb`. Physical latency, WCET, other exception sources, RTOS integration and native memory margins remain open. [Firmware research brief](README.md)

## Reproduction

Use QEMU 10.0.13, Clang 23.1.1 at LLVM revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`, Debian LLVM MC and LLD 19.1.7, and CPython 3.12.14. The runner shares the existing UART collector and the retention fixture's linker layout. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-37/cortex-m3-nested-stack
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang > /tmp/llmlang-rt37-nested-stack.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt37-nested-stack.json
```
