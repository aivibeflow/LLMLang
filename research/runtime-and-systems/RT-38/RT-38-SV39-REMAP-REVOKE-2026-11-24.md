# RT-38 Sv39 remap, revocation and local translation visibility

The same RV64 U-mode load continued to read the old frame after a remap and again after revocation when the kernel executed only `fence rw,rw`. Full local `sfence.vma` and correctly addressed `sfence.vma` both exposed the replacement frame and then caused a load page fault. The wrong-address fence produced the same trace as the correct-address fence in this QEMU build, so a UART-only test would accept the wrong operand.

## Exact fixture

This experiment extends the [RV64 isolation fixture](RT-38-RV64-PMP-SV39-TRAP-ISOLATION-2026-11-24.md). Four images start with the same user-readable Sv39 leaf at VA `0x40400000` backed by frame A at PA `0x80400000`. A syscall updates the leaf to frame B at PA `0x80401000`; a second syscall clears the leaf. Before returning to the user, M-mode reads back each PTE and checks its value. Each image executes the same U-mode doubleword load at VA `0x40000050` before the update, after the remap, and after the revoke. The handler checks `mcause`, `mepc` and `mtval` on the revoked load and supplies a zero fallback.

| Linked synchronization after each PTE write | Initial, remapped, revoked observations | UART trace |
| --- | --- | --- |
| `fence rw,rw`, full `sfence.vma` | A → B → load page fault and zero | `BEISRAMBDPZ!` |
| `fence rw,rw`, `sfence.vma` for `0x40400000`, all ASIDs | A → B → load page fault and zero | `BEISRAMBDPZ!` |
| `fence rw,rw`, `sfence.vma` for `0x40401000`, all ASIDs | A → B → load page fault and zero | `BEISRAMBDPZ!` |
| `fence rw,rw` alone | A → A → A | `BEISRAMADA!` |

`BEISR` is the shared boot, user syscall, invalid syscall, text-store page fault and recovery prefix. `M` and `D` indicate successful PTE readback after remapping and revocation. `A` and `B` indicate distinct loaded values; `PZ` records a checked load page fault and zero fallback. The runner verifies the freestanding ELF, the linked fence sequence and address materialization, both frame positions, the shared user bytes, and the exact UART trace.

## Interpretation for implementation

A kernel must account for local translation visibility separately from successful PTE stores and ordinary memory ordering. The linked disassembly distinguishes the correct and unrelated addresses. The pinned QEMU TCG translator passes neither fence register to its helper, and the helper calls `tlb_flush(cs)` for the complete local CPU. The wrong-address control therefore limits what the dynamic replay can establish. For a selective implementation, verify that the linked instruction uses the intended VA and ASID under the target's architectural premises. [RISC-V privileged architecture](https://docs.riscv.org/reference/isa/priv/supervisor.html) · [Pinned QEMU translator](https://github.com/qemu/qemu/blob/98f88efe8f07067667b8d9b1a5ce9551d34036c1/target/riscv/insn_trans/trans_privileged.c.inc#L154-L162) · [Pinned QEMU helper](https://github.com/qemu/qemu/blob/98f88efe8f07067667b8d9b1a5ce9551d34036c1/target/riscv/op_helper.c#L580-L593).

This evidence covers the pinned QEMU TCG `virt` machine, RV64, one hart and ASID zero. It checks stale reads and link-time fence operands. Selective invalidation costs and actual selectivity, ASID reuse, remote shootdown, physical targets, and interaction with DMA/IOMMU remain open.

## Reproduction

Use LLVM and LLD 19.1.7 and QEMU 10.0.13. The experiment used Debian package version `1:10.0.13+ds-0+deb13u1` and QEMU binary SHA-256 `5f8ec06281e48c4155a8646aa65959e0d9adc8b915c146b93cc0419b6576ba5f`. Check out QEMU source at `98f88efe8f07067667b8d9b1a5ce9551d34036c1`. The replay verifies both cited source files by digest. [Recorded input hashes, linked instructions, and observations](riscv-sv39-remap/results.json).

```sh
python3 -B research/runtime-and-systems/RT-38/riscv-sv39-remap/run.py \
  --qemu-source /path/to/pinned/qemu \
  --output /tmp/rt38-sv39-remap.json
cmp /tmp/rt38-sv39-remap.json research/runtime-and-systems/RT-38/riscv-sv39-remap/results.json
```
