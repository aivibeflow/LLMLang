# Conditional SMP and DMA acknowledgments before frame reuse

[GitHub #441](https://github.com/aivibeflow/LLMLang/issues/441) · 2026-11-25

The model separates removal of a mapping, completion of outstanding access, and reassignment of the underlying frame. Each completion binds a channel, physical frame, old lease generation and detachment epoch. The model accepts a completion only after the matching detachment. Replaying the same completion does not cover another channel.

| Channel | Hardware premise for a future implementation |
| --- | --- |
| Local CPU hart | Relevant cached translations and in-flight accesses are quiescent. |
| Remote CPU hart | Acknowledgment covers the exact remote translation and access scope. |
| DMA drain | New device access is excluded and outstanding transactions have completed. |
| Device visibility | Required cache, IOMMU and ownership synchronization has completed. |

A CPU-only profile requires both CPU receipts. A device-visible profile additionally requires the two device receipts. The selected platform must supply an accurate participant set and sound completion mechanisms. The fixture models two CPU harts and one device path.

## Evidence

Seven Lean theorems check both CPU obligations, both device obligations when needed, rejection of old epochs and generations, the detachment premise, and sufficiency of both CPU receipts in the CPU-only profile. The audit reports no axioms.

An independent enumerator checks 5,184 receipt combinations. It admits 37, including one exact device-visible combination. Matching only the frame number admits 795 invalid combinations. Omitting either CPU channel admits 185 incorrect cases. Omitting either device channel admits five. The receipt rule also matches all 10,080 ordered schedules with two reuse requests, including early completions and a wrong remote epoch. It reassigns once in 480 schedules and retains the frame on the other 19,680 requests.

The fixture checks conditional logical obligations. The channel meanings remain hardware premises. Proving an interrupt protocol, remote invalidation and memory ordering, device shutdown, real IOMMU and cache visibility, or the scheduler and allocator's native correspondence requires the selected platform. [Composed frame and IPC model](RT-38-COMPOSED-MAPPING-AND-IPC-2026-11-25.md) · [Live frame guest experiment](RT-38-RV64-LIVE-FRAME-IPC-2026-11-25.md)

## Replay

Use CPython 3.12.14 and Lean 4.36.0.

```sh
fixture=research/runtime-and-systems/RT-38/SCOPED-SMP-DMA-REUSE-01
python "$fixture/run.py" --output /tmp/rt38-scoped-reuse.json
cmp "$fixture/evidence.json" /tmp/rt38-scoped-reuse.json
```

Two full replays produced identical [evidence ledgers](SCOPED-SMP-DMA-REUSE-01/evidence.json).
