# RT-26 hierarchical reservations and durable limit-handler outcomes

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

A local WAL ledger tracks one parent hard cap of 10 units and two delegated child caps of seven and six. Each typed event identifies an exact request and logical clock tick. Admission serializes the new hold with its decision receipt. Current held and settled usage both count against the hierarchy. Terminal settlement replaces the original reservation with the actual amount, once. A native write supplies a verified four-byte result under a six-byte reservation.

| Handler choice | Checked transition |
| --- | --- |
| Continue | Rechecks both limits and current scope. A competing six-unit request passes its own child cap and fails the parent cap after the first writer commits. |
| Throttle | Until an explicit logical tick, new admission is refused. Retry at the boundary can resume eligibility. |
| Pause and retry | New reservation remains blocked until an explicit successful resume. |
| Degrade | Uses a separately specified smaller amount and rechecks both caps. |
| Cancel | Prevents new reservations and retains the held amount until terminal partial settlement. |
| Shed | Applies to optional work. Required work remains a distinct refusal. |
| Escalate | Delegates the decision to the parent without assigning extra capacity. |
| Terminate | Closes the scope to retry. |
| Handler failure | Returns a typed failure and acquires no capacity. |

Twenty-six independent controls cover exact retry, changed event scope, a regressed clock, duplicate settlement and transaction interruption. A child process exits after staging a reservation and receipt and before commit. Neither persists. A separate contender observes a real SQLite writer lock and is refused when it rechecks the current parent budget. Candidate hard caps hold throughout the selected schedule.

The controller uses a stipulated event issuer, logical ticks, one metric and local serialized storage. It checks the ordering and accounting of each typed option. A production system still needs approved units, authenticated issuer and escalation authority, real-time service guarantees, external effect atomicity, portable runtime lanes and liveness evidence.

Reproduce with CPython 3.12.14 and SQLite 3.53.1.

```bash
study=research/runtime-and-systems/RT-26/DURABLE-LIMIT-HANDLERS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent process schedules reproduced the ledger byte for byte.
