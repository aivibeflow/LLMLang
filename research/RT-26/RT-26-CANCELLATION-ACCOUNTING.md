# RT-26 — Hierarchical admissions under cancellation

**Date** · 2026-11-21

**Baseline** · `3a3f90b`

**Status** · Bounded model for [Plan §5.2](../../PLAN.md#52-execution-semantics-and-runtime-architecture)

## Question

How do cancellation, acknowledgment, and actual completion affect a cumulative budget shared by nested tasks? The baseline reservation model checks every ancestor before issuing capacity. This experiment adds a task-group lifetime boundary while keeping serialized ledger transitions. [Cooperative budget reservation](RT-26-COOPERATIVE-BUDGET-RESERVATION.md) · [Invocation cancellation evidence](../RT-10/RESEARCH-SCENARIO-129-CANCELLATION-AND-INVOCATION-EVIDENCE.md)

The root has five units. A nested worker and an outside sibling each request three. Cancellation closes the nested group. Work may already hold a reservation when cancellation arrives. It may spend as admitted before reaching a terminal stop. An acknowledgment reports receipt of cancellation. Terminal settlement establishes that no more work can spend the reservation and records already spent units.

| Policy | Interpretation |
|---|---|
| Acknowledge and refund | Frees capacity on acknowledgment. Leaves new admissions possible in the cancelled group. |
| Close admissions and refund at acknowledgment | Rejects new descendant work promptly. Assumes acknowledgment is sufficient to release existing capacity. |
| Close admissions and settle at terminal completion | Rejects new descendant work and leaves existing reservations in place pending settlement. Frees unused units and keeps spent units charged. |

## Results

The fixture exhausts 60 legal event schedules for each policy with actual spending, and repeats the schedules with an unused reservation. Completion follows the simulated spending opportunity, and acknowledgment follows cancellation. A separate monitor counts the union of outstanding worker claims and actual spend. The table reports counts per 60 schedules. Both usage variants produce the same counts.

| Policy | Admitted work after group cancellation | Outstanding or spent total exceeded root limit | Ledger undercharged |
|---|---:|---:|---:|
| Acknowledge and refund | 15 | 7 | 23 |
| Close admissions and refund at acknowledgment | 0 | 4 | 15 |
| Close admissions and settle at terminal completion | 0 | 0 | 0 |

Refunding on acknowledgment can admit the sibling while the worker still holds a reservation, resulting in six units against a limit of five. Delaying the refund until termination preserves the reservation invariant. A cancellation recorded before admission rejects a new descendant but permits the outside sibling. Repeated terminal notices do not refund spent units or remove the same reservation twice.

This model assumes one serialized ledger and cooperative enforcement. It does not establish authenticity of termination evidence, consistency across crashes, partial settlement, changing scope ancestry, refunds for instantaneous live memory, or enforcement of external CPU or I/O work. Delayed or absent termination can hold capacity indefinitely. The result supports evaluating task closure and budget settlement as separate transitions.

## Reproduction

From the repository root use CPython 3.12.14. Three cancellation tests and the four baseline reservation tests passed. [Cancellation fixture](../PROTOTYPES/BUDGET-CANCELLATION-01/test_budget_cancellation.py)

```sh
python -B -m unittest discover -s research/PROTOTYPES/BUDGET-CANCELLATION-01 -v
python -B -m unittest discover -s research/PROTOTYPES/BUDGET-RESERVATION-01 -v
```

## Exact retained reproduction (2026-11-21)

The cancellation suite was rerun from exact checkout `00857e7dee48d0026e6d47c776c8792f6f1f245d` under CPython 3.12.14: **3/3 tests passed**. See [workflow run #44949563913](https://github.com/aivibeflow/LLMLang/actions/runs/44949563913) and artifact [14724622101](https://github.com/aivibeflow/LLMLang/actions/runs/44949563913/artifacts/14724622101), digest `sha256:a7c9d8e75c857b59d4827c3cad2aaabe40e0820d13f4f2982fa3db832964b12b`. Test source SHA-256: `7f1380e7abfe4d23c9814098e75bf7fa9cf357f5314280fe22db0e333e136f59`; log digest: `999d093e520cf4008191bcae30fa8acedcf6d50be7b5a9138f5eba19c47e0de9`.
