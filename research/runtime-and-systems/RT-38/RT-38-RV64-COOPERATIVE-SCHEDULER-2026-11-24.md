# RT-38 RV64 cooperative scheduling and integer context restoration

With both U-mode contexts runnable, round-robin admitted at most one intervening peer yield across the four workload pairs. Run-to-completion made the second task wait for all of the first task's yields, up to three in the fixture. Both policies completed the same work with identical linked U-mode instructions.

## Exact experiment

Two workers execute the same RV64 code. Each has its own 4 KiB stack, a task ID, and an independently initialized budget of one or three yields. The RV64 image uses bare addressing and TOR PMP, with kernel state inaccessible to U-mode and separate user RX and RW regions. Both workers share the user address space. A U-mode `ecall` traps to M-mode. The handler checks `mcause`, originating privilege, task identity, the exact yield or stop PC and each context's strictly increasing sequence number. A sequence number is advanced by the worker and checked independently by the handler.

Each task has a 256-byte record for x1–x31 and its saved PC. The runner inspects the linked integer save/restore locations and instructions for `mepc` and `mret`. In the dynamic probes, the worker checks its distinct stack canary, a callee-saved register and a temporary register after each return. The trap records provide additional checks on the argument and sequence registers. The replay verifies the ELF's entry, segment permissions, symbol addresses, closure and common worker bytes. Its independent scheduling model uses a runnable deque. Round-robin puts each yielding task at the back, while run-to-completion puts it back at the front.

| Yield budgets (A, B) | Round-robin | Run-to-completion | Maximum intervening yields for B, round-robin / run-to-completion |
| --- | --- | --- | ---: |
| 1, 1 | `ABab!` | `AaBb!` | 1 / 1 |
| 1, 3 | `ABaBBb!` | `AaBBBb!` | 1 / 1 |
| 3, 1 | `ABAbAa!` | `AAAaBb!` | 1 / 3 |
| 3, 3 | `ABABABab!` | `AAAaBBBb!` | 1 / 3 |

Uppercase letters record yields, lowercase letters record validated exit calls, and `!` marks both contexts complete. The wait metric counts successful peer yields while the task is runnable. It measures scheduling order at explicit kernel entries.

| Control | Divergence on the 3, 3 case |
| --- | --- |
| Break restoration of `s0` | `ABS`. The resumed worker reports the altered saved register. |
| Restore the other task's stack pointer | `ABK`. The resumed worker reads the other task's canary. |
| Leave the saved `ecall` PC unchanged | `ABP`. The repeated trap carries the previous sequence number. |

## Bounds and follow-up

The selected policy changes ordering in this fixture. A round-robin timing bound additionally needs a bound on work between yields. The checked experiment uses one hart with interrupts masked, two runnable contexts, common user mappings and integer state. Preemption, blocking and wakeup, address-space switching, floating-point and vector state, and physical interrupt or scheduling latency remain open.

## Reproduction

Use LLVM and LLD 19.1.7 and QEMU 10.0.13 as in the pinned RV64 experiments. [Exact image hashes, U-mode hashes, and schedule traces](riscv-cooperative-scheduler/results.json).

```sh
python3 -B research/runtime-and-systems/RT-38/riscv-cooperative-scheduler/run.py \
  --output /tmp/rt38-rv64-cooperative-scheduler.json
cmp /tmp/rt38-rv64-cooperative-scheduler.json \
  research/runtime-and-systems/RT-38/riscv-cooperative-scheduler/results.json
```
