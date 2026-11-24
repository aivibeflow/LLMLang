# RT-38 RV64 isolated IPC pilot and address-space switching

The integrated single-hart prototype completed the same 25-call IPC workload with two Sv39 roots under both a shared ASID with local invalidation and distinct ASIDs with static page tables. Both task contexts used the same stack virtual address with different physical frames. The two mapping controls exposed an aliased stack and an accessible peer frame. A third control omitted the required shared-ASID fence and still passed on QEMU. Linked inspection distinguished it.

## Integrated boundary

The prototype combines the [cooperative context switch](RT-38-RV64-COOPERATIVE-SCHEDULER-2026-11-24.md) and [generation-checked endpoint](RT-38-RV64-IPC-REVOCATION-2026-11-24.md) with two Sv39 page tables. Each root maps the common RX code at VA `0x40000000` and a private RW stack at VA `0x40001000`. M-mode clears and initializes both three-page table trees and orders the new leaves with a full `sfence.vma` before first use. Each context switch installs the selected root and checks the actual `satp` readback. The trap handler checks U-mode origin, the saved PC, and the address of any expected load page fault. The runner verifies identical linked user code and request bytes, linked switch instructions and the six page-table locations.

Each worker places a distinct canary on its own stack and checks it after every IPC return. At startup both try to read a user VA that only the deliberate mapping control aliases onto the peer's physical stack frame. The expected fault returns zero; the exposed-peer control reaches a distinct path and reports the marker that M-mode seeded in the peer frame. All successful IPC paths are compared against the independent endpoint and scheduler oracle used by the earlier endpoint experiment.

| Address-space variant | Observed result | Linked kernel text |
| --- | --- | ---: |
| Shared ASID 0 with full switch-time `sfence.vma` | Both peer loads fault, private canaries survive, IPC matches the oracle | 1,792 B |
| Distinct ASIDs 0/1 with immutable non-global leaves | Both peer loads fault, private canaries survive, IPC matches the oracle | 1,788 B |
| Both roots point their stack VA at the same frame | A detects B's overwritten canary on the first return after B runs | 1,792 B |
| A's probe VA maps B's frame with the user bit set | A reads the exact peer marker `0x3344` before entering IPC | 1,824 B |
| Shared ASID 0 with missing switch-time fence | Matches the valid UART trace; linked inspection finds the missing fence | 1,788 B |

All five images reserve 24 KiB for their page tables and 36 KiB in the linked kernel state segment including alignment. Two 4 KiB user stack frames are backed by RAM. The text measurements include boot, context switching, IPC, probes and UART. The distinct-ASID experiment uses a boot-time global fence and two permanently assigned ASIDs. Dynamic PTE updates, ASID reuse and remote invalidation remain separate obligations.

## QEMU-specific observation

The pinned QEMU `write_satp` calls `legalize_xatp`. For a legal new value, changing the ASID, root PPN or paging mode triggers `tlb_flush(env_cpu(env))`. Changing only the root in the shared-ASID control therefore also invalidates old translations in this emulator. The identical success traces provide no evidence that the omitted fence is valid on other implementations, or that a distinct-ASID switch retains translations or reduces latency. [Pinned QEMU implementation](https://github.com/qemu/qemu/blob/98f88efe8f07067667b8d9b1a5ce9551d34036c1/target/riscv/csr.c#L1929-L1952) · [RISC-V privileged architecture](https://docs.riscv.org/reference/isa/priv/supervisor.html).

This completes the bounded boot, cooperative switch, two-address-space isolation and single-mailbox IPC test on the pinned emulator. Live mapping/allocator composition, preemption, multiple endpoints, DMA/SMP, physical timing, and a proof of linked kernel semantics remain open.

## Reproduction

Use Clang, LLVM and LLD 19.1.7 and QEMU 10.0.13. Point the runner at `target/riscv/csr.c` in QEMU commit `98f88efe8f07067667b8d9b1a5ce9551d34036c1`; it checks the exact digest. [Image hashes, table locations, switch instructions and traces](riscv-address-spaces/results.json).

```sh
python3 -B research/runtime-and-systems/RT-38/riscv-address-spaces/run.py \
  --qemu-csr-source /path/to/qemu/target/riscv/csr.c \
  --output /tmp/rt38-rv64-address-spaces.json
cmp /tmp/rt38-rv64-address-spaces.json \
  research/runtime-and-systems/RT-38/riscv-address-spaces/results.json
```
