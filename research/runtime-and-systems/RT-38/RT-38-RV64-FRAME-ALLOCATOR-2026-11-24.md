# RT-38 RV64 frame ownership, zeroing and rollback

Zero-on-allocation and zero-on-release produced the same ownership, Sv39 leaf mappings and U-mode observations in a three-frame pool. They moved a 512-word scrub to different operations. Zero-on-allocation scrubbed during allocations, including attempts that failed after scrubbing. Zero-on-release scrubbed during initialization and each successful release. The result lets the kernel choose where to account for that work in a single-hart bounded allocator.

## Compared contracts and observations

The RV64 fixture uses three physical 4 KiB frames at `0x80401000`, `0x80402000` and `0x80403000`, and four user virtual slots starting at `0x40400000`. The allocator runs in M-mode before enabling address translation with interrupts masked. It selects the lowest free frame, reserves it, installs a user-readable and writable leaf, and publishes exclusive ownership. Releasing a mapped slot clears the leaf before returning the frame to the pool. The harness dirties the entire frame to represent writes by the previous owner before release. Two fault injections exercise rollback immediately after reservation and after the candidate's scrub point, before the PTE write.

Each of five freestanding images emits 14,746 operation records. The cases cover all triples over 17 commands (four allocations at each of three fault settings, four frees, and one invalid request), followed by a seven-operation exhaustion, abort and reuse sequence. An independent Python model uses a set of free frame IDs and a map of slots to frame IDs instead of the concrete per-frame states and PTE array. It compares each result, all four decoded PTEs, each physical frame's ownership tag, the number of scrub stores and the dirty-publication flag. The target reads all 512 words immediately before each publication. For the final U-mode probe it reads the first and last doubleword of an allocated page, then reads an unmapped slot using the same load instruction. The inherited trap handler checks the cause, linked fault PC and fault address.

| Policy | Initialization scrub stores | Stores per successful allocation | Stores per successful release | Stores before post-scrub allocation abort | Linked kernel text |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero on allocation | 0 | 512 | 0 | 512 | 2,732 B |
| Zero on release | 1,536 | 0 | 512 | 0 | 3,032 B |

These sizes include the harness, boot and traps. The counts measure scrub stores, excluding fixture poisoning, the publication scan and PTE traffic. They do not measure cycles or production allocator size. Both positives matched every abstract record and observed two zero reads followed by a checked page fault with zero fallback (`EISRZZPZ!`). Both could reuse a frame after exhaustion, release and an injected abort.

| Control | Observed violation |
| --- | --- |
| Skip clearing the frame | 3,276 dirty publications. The U-mode probe read the poison in both boundary words (`EISRVVPZ!`). |
| Omit rollback after the late fault | 5,694 returned states retain a reservation. The targeted retry reports exhaustion even after release because the intervening failed call retained the only free frame. |
| Select the first frame regardless of ownership | 702 records alias a frame across slots. In 1,275 records the published-frame set disagrees with the leaf set, including after release of an aliased slot. |

## Proof and execution boundaries

The separate Lean model classifies free, reserved, zeroed and owned frames. Its checked theorems cover counting the complete inventory, the zeroed publication predecessor, release as the only outgoing transition from an owned frame, both rollback cases, and uniqueness of an owner tag. Counting uses `propext` and `Quot.sound`. The other four theorems report no axioms. The concrete traces supply the correspondence evidence at the enumerated inputs. A general source-to-binary refinement theorem and a proof of the actual linked scrub routine remain open.

Both policies assume a single hart, no asynchronous access during the transaction and an initial pool established by the kernel. With a live address space, release also needs the translation maintenance and observation ordering checked separately in the [Sv39 remap and revocation study](RT-38-SV39-REMAP-REVOKE-2026-11-24.md). Faults after publication, concurrent observers, multiple address spaces, live shootdown, DMA and physical timing are outside the allocation replay.

## Reproduction

Build with LLVM, Clang and LLD 19.1.7, QEMU 10.0.13 and Lean 4.36.0. The runner checks exact freestanding ELF closure, matched U-mode bytes and the proof axiom report. [Pinned inputs, all tallies, witnesses and per-image hashes](riscv-frame-allocator/results.json).

```sh
python3 -B research/runtime-and-systems/RT-38/riscv-frame-allocator/run.py \
  --output /tmp/rt38-frame-allocator.json
cmp /tmp/rt38-frame-allocator.json \
  research/runtime-and-systems/RT-38/riscv-frame-allocator/results.json
```
