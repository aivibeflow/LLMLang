# RT-26 — Cooperative reservation of a cumulative task budget

- **Status** · Bounded model of hierarchical admission and settlement
- **Date** · 2026-11-21
- **Baseline** · `f09047a65bc77e8756d9d36def836c193a500dfa`

Can sibling tasks share one cumulative budget without overshoot when reservation, settlement, and retry interleave? The fixture compares a split check and charge with a single transition that checks and reserves across the complete ancestor path. [Execution and runtime plan](../../../PLAN.md#52-execution-semantics-and-runtime-architecture) · [RT-26 research requirements](RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md)

## Model

The root has a five-unit cumulative budget. One child belongs to a nested group and the other is a direct child of the root. Each asks for three units. Admission checks the leaf and every ancestor before recording one reservation. Each accepted unit is attributed once to its originating task and appears in each ancestor's inclusive view. Summing inclusive views would double count the units. The admitted operation may commit its units or cancel its pending reservation. Committed units remain spent. The operation ID is bound to the exact task and amount, and terminal outcomes are stable across retry. A denied request can try again under a fresh operation ID.

This model assumes a fixed, acyclic hierarchy and a single serialized admission transition. An unknown settlement request creates no record. Task-wide cancellation that happens before admission needs a separate task lifetime check. The experiment models cumulative usage and makes no assumption about instantaneous live resources or resource use outside cooperative admission.

## Results

| Claim | Evidence and observation |
|---|---|
| BUDGET-01 | Bounded model result. Keeping each task's check before its charge gives six schedules. Four let both checks pass and spend six units against the limit of five. |
| BUDGET-02 | Bounded model result. Across 720 orders of two reservations and four settlement attempts, the incremental ledger matches direct summation over independently listed subtree memberships after all 4,320 transitions. No scope exceeds its limit. The direct sum uses the recorded outcomes, so this check establishes accounting consistency. |
| BUDGET-03 | Fixture result. A local refusal or sibling refusal adds no charge. Cancelling a pending reservation releases capacity at the leaf and ancestors. Cancelling a committed reservation preserves the spent units. Duplicate requests and settlements do not add or refund units twice. |

The split schedule gives a counterexample to separate unsynchronized checks. An implementation with one serialized ledger would match the model assumptions. An implementation with finer-grained locks or a transactional mechanism would need evidence that observers see an equivalent transition under its target memory model. Reservation is viable when the cooperating runtime knows the units before admitting work. Sampling CPU or I/O counters after work occurs would require an explicit overshoot and attribution model. These fixtures do not measure timing, operating-system enforcement, fairness, or throughput. [Evidence and exact schedules](../PROTOTYPES/BUDGET-RESERVATION-01/test_budget_reservation.py)

## Reproduction

From the repository root, run with CPython 3.12.14 and the standard library. Expect four passing tests.

```sh
python -B -m unittest discover -s research/runtime-and-systems/PROTOTYPES/BUDGET-RESERVATION-01 -v
```
