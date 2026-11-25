# Timer-driven IPC wakeup under two RV64 address spaces

[GitHub #441](https://github.com/aivibeflow/LLMLang/issues/441) · 2026-11-25

Two user tasks run at the same virtual code and stack addresses under distinct Sv39 roots. The roots share the read-only code and map separate writable stacks. Each resume writes the selected root to `satp`, performs the local translation fence and checks the actual CSR value. The receiver blocks on generation 1. The sender then receives a machine timer credit before delivering a value or revoking the generation. The receiver accepts an exact delivery or cancellation disposition, checks its private stack canary and receives a timer credit after wakeup.

The handler checks endpoint generation before clearing the wait and makes the receiver runnable only on settlement. Revocation advances the generation. A later request from the sender with generation 1 receives the stale result. The source oracle uses an independent runnable-set and generation sequence. Real guest code verifies the returned values and preserves the scheduled order.

| Scenario | UART evidence |
| --- | --- |
| Deliver and wake | `WBDAba!` |
| Revoke, wake and refuse the stale generation | `WBCARba!` |
| Allow the blocked receiver to run after the sender's timer | `WBT` |
| Map both private stack VAs to the same physical frame | `WBDK` |
| Report success for the stale generation after revocation | `WBCART` |

`W` records the blocked wait, `A` and `B` are machine timer deliveries, `D` and `C` settle delivery and cancellation, `R` identifies the stale-request path, and lower-case letters report task completion. The final user checks distinguish the altered stale-request result even when its kernel UART prefix agrees with the intended path.

All five ELF variants preserve the exact user bytes. The runner checks the six page-table pages, two physical stack locations, linked local fences and absence of hosted imports or relocations. Both clean replay runs produce the same complete ledgers on QEMU 10.0.13. The machine profile is one RV64 hart with no firmware image and a fixed virtual instruction clock.

The pilot composes runnable-state admission, timer interruptions, endpoint generation and live address-space selection. Page tables and frames are assigned at boot. The separate composed model adds abstract frame release and reuse. Dynamic allocation with a blocked lease, concurrent mutators, hardware timing, remote invalidation, SMP and DMA remain open. [Frame and IPC composition](RT-38-COMPOSED-MAPPING-AND-IPC-2026-11-25.md) · [Timer delivery model](RT-38-RV64-TIMER-PREEMPTION-2026-11-25.md)

## Replay

Use CPython 3.12.14, LLVM/LLD 19.1.7 and QEMU 10.0.13. Pass `--qemu-data` when QEMU machine data lives outside the default directory.

```sh
fixture=research/runtime-and-systems/RT-38/RV64-PREEMPTIVE-IPC-01
python -B "$fixture/run.py" --qemu /path/to/qemu-system-riscv64 \
  --output /tmp/rt38-preemptive-ipc.json
cmp "$fixture/evidence.json" /tmp/rt38-preemptive-ipc.json
```

The [ledger](RV64-PREEMPTIVE-IPC-01/evidence.json) binds the source inputs, emulator binary, native ELF images and exact outputs.
