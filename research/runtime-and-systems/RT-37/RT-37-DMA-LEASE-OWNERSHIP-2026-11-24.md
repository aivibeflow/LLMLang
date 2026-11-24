# DMA buffer ownership under delayed completion and generation reuse

- **Date:** 2026-11-24
- **Research:** RT-37 EMB-11, RT-04, RT-36 and DEP-246
- **Baseline:** `11f469cae4ea87a5fef572c7036bb35c56c6dfdc`
- **Evidence:** Twelve Lean theorems, 5,628 cross-checked transitions and four policy comparisons

A matching channel and buffer can still identify the wrong DMA operation. Matching a generation rejects an ordinary delayed completion. If a finite generation wraps while an old event remains possible, the full visible key can repeat and the stale event can again give the CPU premature access.

## Candidate protocol

A CPU-owned buffer is submitted with a lease that binds channel, buffer and generation. A running lease admits device writes only in its bounded byte range. Requesting cancellation keeps the buffer unavailable to the CPU and leaves the device's bounded access live. A matching quiescence event leads to a ready cancelled lease. For a normal run, a matching completion leads to a ready completed lease. In both cases, an explicit acquire operation with confirmed cache synchronization returns ownership to the CPU. The candidate increments the generation or retires the endpoint at the configured maximum.

The [Lean model](dma-lease/DmaLease.lean) proves that unrelated completion and quiescence events do not advance the phase, an earlier generation cannot finish a newer lease, CPU access and device-write admission are disjoint, device writes require the exact lease and in-range extent, and handback requires the ready lease plus synchronization. It also proves that acquire advances the generation or retires the endpoint and that retirement keeps submission closed. The axiom output uses `propext` and `Quot.sound`.

The independent Python transition implementation agrees with Lean for 21 phases and 134 events under both the finite retirement and natural-number profiles. The corpus includes wrong channels, wrong buffers, stale generations, missing synchronization and ranges at or beyond the end of an eight-byte buffer. The range control includes a large offset to exercise the use of mathematical bounds.

| Admission policy | Earlier completion after the next submit | Delayed first completion after four handbacks with a two-bit tag |
| --- | --- | --- |
| Channel and buffer only, with retirement | Accepted. A subsequent acquire permits premature CPU access. | Retirement denies a fifth submission. |
| Exact key with wrapping generation | Rejected before wrap. | The fifth submission repeats generation zero and the delayed event is accepted. |
| Exact key with retirement | Rejected. | Retirement denies a fifth submission. CPU ownership remains available. |
| Exact key with natural-number generation | Rejected. | The fifth submission has generation four and the delayed event is rejected. |

The named cancellation trace checks the intermediate states. CPU use remains denied after the request, after a completion delivered while cancelling, and after quiescence until synchronized acquire. A device write ending at the bound is admitted while cancelling and a write crossing the bound is denied.

## Reproduce and scope

Use Lean 4.36.0 (`611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`) and Python 3.12.14. The [ledger](dma-lease/results.json) carries the exact model hashes, normalized transition digest, axiom output and policy traces. Two independent replays reproduced it byte for byte.

```sh
fixture=research/runtime-and-systems/RT-37/dma-lease
output=$(mktemp)
python3 -B "$fixture/run.py" --output "$output"
cmp "$fixture/results.json" "$output"
```

The model receives typed completion and quiescence events and an explicit synchronization observation. A concrete device profile must establish how those events bind to the active descriptor and when a reset or queue drain eliminates pending events. It must also establish memory-range enforcement, cache maintenance and ordering. Retirement and natural-number keys illustrate two responses to delayed events. A fixed-width implementation that reuses tags needs evidence that prior events can no longer arrive.
