# Research Scenario 129 — Cancellation and Invocation-Specific Evidence

**Status:** finite comparison with a scheduled two-thread fixture and primary API evidence

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-06 dependencies · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

What evidence lets a caller release a shared source and exclusive destination after cancellation? Scenario 128 distinguishes a usable retained handle from an indeterminate outcome. This scenario studies cancellation acknowledgment and result delivery when later invocations can use the same resource identities. [Foreign reservation outcomes](../RT-13/RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md) · [Async cancellation and cleanup](../RT-04/RESEARCH-SCENARIO-40-ASYNC-CANCELLATION-AND-CLEANUP.md)

## Boundary and observed messages

The wrapper starts with an unresolved reservation over a known pair of roles. Its invocation key includes the role identities and the generation of the call. The backend can acknowledge cancellation, report a missing result, establish terminal consumption or retention, or leave the state unresolved. In the fixture, terminal evidence for the current invocation is authoritative for its reported disposition. An acknowledgment, a missing result without disposition evidence, or an unresolved result leaves the current disposition unknown. Evidence from an earlier or unrelated invocation gives no information about the current reservation. The bounded role footprint from Scenario 128 still allows operations compatible with the possible live reservation. [Model](../PROTOTYPES/RT-04-01/rt04_cancel_receipts.py)

Microsoft's `CancelIoEx` provides an interface-level example of the signal boundary. It marks outstanding I/O for cancellation and returns without waiting for completion. The target operation may still complete normally, complete as canceled, or fail for another reason. The lifetime of the overlapped record extends until completion. The fixture uses a host thread and explicit barriers to model the two events. [Pinned CancelIoEx contract](https://github.com/MicrosoftDocs/sdk-api/blob/0797841e74f7d55cba99a08948b601604799ef07/sdk-api-src/content/ioapiset/nf-ioapiset-cancelioex.md)

## Compared rules and results

| Rule | Release predicate |
|---|---|
| Acknowledgment by invocation | The current invocation receives either a cancel acknowledgment or a consumed result. |
| Terminal disposition by role pair | A consumed result names the current resource pair. |
| Terminal disposition by invocation | A consumed result names the current pair and invocation generation. |

The corpus uses four resource identities, 12 valid first pairs, and all 16 proposed pairs. It combines five evidence kinds with three subjects and two possible actual states. Two exact terminal messages constrain the actual state, yielding 28 evidence and state combinations and 5,376 inputs per rule. An independent compatibility oracle applies the proposed roles against the actual current reservation. [Generated cases and oracle](../PROTOTYPES/RT-04-01/test_rt04_cancel_receipts.py)

| Rule | Admits | Admits a conflict | Releases a live reservation | Declines a compatible proposal | Claims retention from another invocation |
|---|---:|---:|---:|---:|---:|
| Acknowledgment by invocation | 1,632 | 96 | 192 | 1,152 | 0 |
| Terminal disposition by role pair | 1,632 | 96 | 192 | 1,152 | 384 |
| Terminal disposition by invocation | 1,440 | 0 | 0 | 1,248 | 0 |

The host-thread fixture receives an acknowledgment while cleanup is held at a barrier and the worker is still live. A conflicting operation becomes admissible under the first rule at that point. The invocation-specific terminal rule waits for the worker's consumed result. In the reuse fixture, invocation 1 completes, then invocation 2 reserves the same pair. A delayed copy of invocation 1's consumed result releases invocation 2 under the role-pair rule. Checking the generation preserves the new reservation. After a release, repeated delivery keeps the released state stable, including a delayed retained report. [Thread and reuse checks](../PROTOTYPES/RT-04-01/test_rt04_cancel_receipts.py)

## Implications for design

An operation contract can stay stable across calls. The lifecycle result needs an invocation identity with a lifetime that covers message delivery and resource reuse. The transition also needs evidence of disposition, with cancellation acknowledgment available as its own event. Delayed or missing terminal information can keep a reservation live in the wrapper after the backend has released it. This accounts for the conservative refusals in the table and sets a requirement for the reconciliation protocol. The fixture allows operations that can share a source in either possible state. [Bounded role comparison](../RT-13/RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md)

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_cancel_receipts.py' -v
```

The checks ran on Python 3.12.14. The two-thread fixture uses a cooperative worker and explicit barriers. `CancelIoEx` is specification evidence. The model assumes authoritative receipts within one invocation, stable resource identities, and serialized application of observations to the wrapper record. Lost delivery recovery, persisted identity allocation, races between multiple observers, and authority for same-invocation retained evidence during further cleanup remain open.
