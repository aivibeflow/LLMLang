# RT-38 RV64 IPC capability revocation and slot reuse

A handle bound to a slot and generation rejected two stale sends after the slot was granted again. The handle that used slot identity alone admitted both sends, and the receiver read their payloads. An implementation that retires a slot at generation exhaustion rejected the third grant with no remaining guest authority.

## Fixture and comparison

Two U-mode principals take turns making syscalls through the [cooperative context switch](RT-38-RV64-COOPERATIVE-SCHEDULER-2026-11-24.md). The trap handler checks the originating privilege, syscall PC and principal against the active context, and calls a freestanding C endpoint with a dedicated M-mode stack. The privileged endpoint state is outside the user PMP range. The caller's result is returned in its saved `a0`, and the harness records the outcome and payload on UART. All three images have identical U-mode instructions and request data. The request sequences give the guest handles as explicit fixture inputs.

Principal A controls a one-element mailbox and can receive, grant, and revoke. Principal B receives a send-only grant. The oracle uses an independent runnable deque, an optional guest authority and an inbox. It predicts all 25 syscall outcomes and the two exits for each image. The cases include receiving from an empty mailbox, two full-mailbox sends, a receive attempted with send-only authority, a send while the grant is absent, and send attempts against newly issued and revoked handles. A successful revoke preserves the message already queued by a previously authorized send.

| Variant | Old handle after second grant | Current handle after second grant | Third grant | Kernel text |
| --- | --- | --- | --- | ---: |
| Generation checked | Rejected; A observes an empty mailbox | Accepted; A receives `g` | Accepted; old handle rejected again and current handle delivers `k` | 1,248 B |
| Slot identity only | Accepted; A receives the stale request's `f` | Accepted; A receives `g` | Accepted; old handle delivers `j` before the current handle delivers `k` | 1,236 B |
| Generation checked, limit two | Rejected; A observes an empty mailbox | Accepted; A receives `g` | Rejected; sends using either supplied handle leave the mailbox empty | 1,248 B |

The replay checks freestanding ELF closure, linked PMP-region geometry, endpoint placement and the exact UART trace. Sizes include boot, scheduling and instrumentation. This compares local handle admission and slot lifecycle; scope covers one hart, two cooperative principals, common U-mode code and address space, one endpoint and scripted handles. Transfer protocols, restart and persistent handles, multiple endpoints and typed status/payload encoding, blocking IPC, cross-address-space isolation and concurrent revocation need separate contracts and evidence.

## Reproduction

Use Clang, LLVM and LLD 19.1.7 and QEMU 10.0.13. [Exact linked hashes, request events and observations](riscv-ipc/results.json).

```sh
python3 -B research/runtime-and-systems/RT-38/riscv-ipc/run.py \
  --output /tmp/rt38-rv64-ipc.json
cmp /tmp/rt38-rv64-ipc.json research/runtime-and-systems/RT-38/riscv-ipc/results.json
```
