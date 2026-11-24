# RT-13 Byte and word atomic lowering across RV64, AArch64 and x86-64

On the pinned LLVM pipeline, byte-sized fetch-add compiles to a retry loop on base RV64 and baseline AArch64, and to a single atomic instruction with Zabha or LSE. RV64 without the required atomic ISA features introduces four runtime imports even though the input IR passes verification. Two RV64 harts executed the linked byte and word variants and confirmed the observed wraparound, return values, neighboring bytes and publication payload.

## Exact build

The LLVM fixture uses naturally aligned `i8` and `i32`, system-scope atomic operations, monotonic and acquire-release fetch-add, and a release-fence/acquire-fence publication pair. The runner takes the module through LLVM 19.1.7 `default<O0>` or `default<O3>`, verifies its RMW widths and orders and the fence positions, and emits five target profiles with the corresponding `llc` level. It checks closure in all five objects and inspects the actual linked RV64 instructions and freestanding ELF before running them.

| Target profile | Byte acquire-release RMW, O3 | Byte function size O0 / O3 | Word acquire-release RMW, O3 |
| --- | --- | ---: | --- |
| RV64 A without Zabha | Masked `lr.w.aq` / `sc.w.rl` retry loop | 80 / 60 B | `amoadd.w.aqrl` |
| RV64 A with Zabha | `amoadd.b.aqrl` | 8 / 8 B | `amoadd.w.aqrl` |
| AArch64 without LSE | `ldaxrb` / `stlxrb` retry loop | 100 / 24 B | `ldaxr` / `stlxr` |
| AArch64 with LSE | `ldaddalb` | 8 / 8 B | `ldaddal` |
| x86-64 | `lock xaddb` | 8 / 7 B | `lock xaddl` |

RV64 emits `fence rw,w` and `fence r,rw` around the corresponding byte accesses. AArch64 emits `dmb ish` and `dmb ishld`. The x86-64 publication and observation functions contain no hardware fence for this ordering pair. The byte monotonic RMW uses a locked instruction on x86-64 at both levels. Baseline AArch64 O0 uses acquire/release exclusive instructions for the monotonic fixture, while O3 uses the weaker `ldxrb` / `stxrb` pair. These are measured function lengths and selected instructions. Code size and the presence of a retry loop establish neither latency nor a contention bound.

Turning off RV64 A, Zaamo and Zalrsc leaves unresolved `__atomic_fetch_add_1`, `__atomic_fetch_add_4`, `__atomic_load_1` and `__atomic_store_1` at O3. This makes the native target features or a pinned runtime implementation part of freestanding admission.

## Runtime and controls

In four linked RV64 images, two harts rendezvous before fetch-add at byte offset 1 of a seeded aligned word. The fixture checks the old-value set {254, 255}, a final zero counter, and the exact values of the other three bytes. It checks that the word operation returns all ones and leaves zero, and that the observer which reads publication flag 1 obtains payload 42. Both feature profiles pass at both optimization levels. The same native oracle rejects both linked wrong-byte variants.

Moving the release fence after the flag store passes LLVM verification and changes the RV64 O3 instructions. The x86-64 O3 reference and mutant have byte-identical `.text`. The bounded source-level model admits a stale payload for this control, so target text identity on one architecture cannot establish the modeled source contract. [RMW and fence model](../../language-design/RT-04/RT-04-RMW-RELEASE-SEQUENCES-AND-FENCES-2026-11-24.md).

Only RV64 was executed, under QEMU 10.0.13's two-hart `virt` profile. AArch64 and x86-64 findings are exact object observations. Physical weak-order outcomes, the full target memory-model correspondence, synchronization outside ordinary RAM, and comparison with generated Rust remain open.

## Reproduction

Use LLVM and LLD 19.1.7 and QEMU 10.0.13. [Input hashes, normalized LLVM identities, instructions, function extents and target traces](atomic-lowering/results.json).

```sh
python3 -B research/compiler-and-translation/RT-13/atomic-lowering/run.py \
  --output /tmp/llmlang-atomic-lowering.json
cmp /tmp/llmlang-atomic-lowering.json research/compiler-and-translation/RT-13/atomic-lowering/results.json
```
