# RV64 boot and trap isolation with PMP and Sv39

- **Date:** 2026-11-24
- **Research:** RT-38 KRN-01/03/04/06/08 and PLAN §6.5
- **Baseline:** `0f22a3499b270113c79cdff38b45be0883a56485`
- **Evidence:** Five exact RV64 ELF images with identical user code and contrasting physical and virtual protections

Split PMP regions and the correctly configured Sv39 pages block both a user store to its code page and a read of a supervisor-protected word. A single writable and executable PMP region protects the private word while permitting the code-page store. Setting the Sv39 user bit on the protected leaf exposes that word while the user code page remains read-only.

## Boot and exception contract

The single-hart QEMU `virt` machine starts the ELF entry at `0x80000000` with `-bios none`. The image checks the protected sentinel in M-mode, sets the direct trap vector, clears delegation and enters U-mode. All five ELFs carry the same user section, including a stack read/write, a valid `ecall`, an invalid request that must return `-38`, and the two memory probes. The user code stores the same marker bytes to test code-page writability without changing the executable instructions.

The handler swaps from the user stack to the machine stack, verifies that every admitted trap came from U-mode and checks `mcause`. It also checks `mtval` and the exact probe PC on a rejected memory access. The fixture advances over the four-byte access and returns an explicit fallback so the user can continue to the next request. Paged profiles execute the user code at `0x40000000` while the ELF stores it at `0x80200000`. The protected physical word at `0x80400000` is mapped at `0x40400000`.

| Protection profile | User store to code bytes | User read of protected word | Machine code | Kernel state |
| --- | --- | --- | ---: | ---: |
| Bare translation, wide PMP | Succeeds | Succeeds | 644 B | 4 KiB |
| Bare translation, one user R/W/X TOR region | Succeeds | Access fault, `mcause=5` | 676 B | 4 KiB |
| Bare translation, separate RX and RW TOR regions | Access fault, `mcause=7` | Access fault, `mcause=5` | 692 B | 4 KiB |
| Sv39 with user RX/RW pages and supervisor-only protected leaf | Page fault, `mcause=15` | Page fault, `mcause=13` | 904 B | 20 KiB |
| Sv39 with `U` set on the protected leaf | Page fault, `mcause=15` | Succeeds | 904 B | 20 KiB |

The two Sv39 images use the same four page-table pages and one machine-stack page. The bare images reserve one machine-stack page. ELF segment flags alone leave the bare wide and single-region stores possible. The `U` control changes the protected leaf permission with the user code and the remaining virtual mappings fixed. [RISC-V privileged architecture](https://riscv.github.io/riscv-isa-manual/snapshot/privileged/)

## Reproduce and scope

Use LLVM/LLD 19.1.7, Python 3.12.14 and QEMU 10.0.13. The Debian `qemu-system-riscv` archive has SHA-256 `80effad6aa07c09a7532e1b731c04ec9a32c545c2b9597320ec16ae59d2f34a2`. The [replay](riscv-trap-isolation/run.py) verifies executable type, entry, absence of hosted imports, disjoint load segments, the exact probe opcodes and identical user section bytes. The [ledger](riscv-trap-isolation/results.json) retains the exact ELF and source hashes, resource extents, symbol locations and UART observations. Twenty fresh replays reproduced it byte for byte.

```sh
fixture=research/runtime-and-systems/RT-38/riscv-trap-isolation
output=$(mktemp)
python3 -B "$fixture/run.py" --output "$output"
cmp "$fixture/results.json" "$output"
```

The result checks selected access and recovery observations under the QEMU reset stub, ELF loader and RV64 model. The current page tables are installed once before entering the single user program. Dynamic mappings, TLB lifetime, frame ownership, context switching, IPC and whole-kernel isolation remain separate obligations.
