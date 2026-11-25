# RT-10 reference continuations and resumable VM execution

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

The reference interpreter directly evaluates an expression and suspends when it requests an effect. A separately lowered bytecode machine publishes the same request with an explicit stack checkpoint. Each effect identifies its exact source occurrence, operation, instance, sequence and runtime policy. An effect receipt supplies a value, failure or cancellation. Source evaluation spends one unit of fuel per expression entry. The machine preserves those source charges across a checkpoint.

| Comparison | Checks |
| --- | ---: |
| Completed reference versus resumed VM cases | 14,580 |
| Checkpoints restored and resumed | 13,319 |
| Existing nonresumable reference agreements under default replies | 3,645 |
| Previous receipts refused at later requests | 4,023 |
| Those refused receipts with the same operation name as the new request | 1,385 |

Every case matches the result, terminal state, ordered committed-effect prefix and remaining fuel. The corpus includes 5,198 returns, 5,885 exhaustions, 2,324 cancellations and 1,173 failures. A mismatch in execution instance, policy epoch, bytecode, stored fuel or response shape is refused without advancing the pending continuation. Two new VM objects restored from the same exact checkpoint with the same synthetic receipt agree.

A candidate VM needs a defined source-level observation boundary and exact checkpoint identity. Bytecode representation and VM instruction costs can vary within that boundary. The fixture uses an in-memory synthetic effect service and a stipulated trusted checkpoint identity. Duplicate physical effects, durable external-effect settlement, concurrent scheduling, generalized continuations, optimizer interaction and production VM selection remain open.

Reproduce with CPython 3.12.14 from the repository root.

```bash
study=research/runtime-and-systems/RT-10/RESUMABLE-EXECUTION-01
PYTHONHASHSEED=2 python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent replays produce the same archived counters and refusal outcomes.
