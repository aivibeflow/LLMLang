# RT-04 durable typed transitions and exact retry receipts

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

A seal request identifies the storage scope, slot, owner, incarnation, generation, phase and bounded result value. The SQLite prototype serializes competing writers and publishes the typed state and immutable result receipt in one WAL transaction. A retry uses the same request identity. Changed contents under the same nonce are refused. When the live state has advanced or been replaced, the exact old request can retrieve only historical evidence.

| Control | Checked result |
| --- | --- |
| Wrong storage scope, owner, phase or result value | The transition is refused before publication. |
| Process exits after applying changes and before commit | The old open state remains and the receipt is absent. |
| Process exits immediately after commit | Both the sealed result and the receipt persist. Repeating that request returns the same accepted state. |
| A slot is recreated with the same displayed phase and generation | The older incarnation is refused for a new transition. Its old receipt remains historical. |
| Actual competing writer | The second process observes a SQLite writer lock and then sees the changed generation. Only the first request publishes. |
| Generation reaches the largest representable integer | The prototype refuses advancement and preserves the exact state. |

Fifteen controls passed on independent SQLite databases. Static state and value construction can reduce the number of admissible requests at a typed API. Persisted handles still need current owner, incarnation and generation checks while publishing state. Exact historic acceptance stays separately retrievable and conveys no current state authority.

The fixture uses a supplied owner identity and modeled administrative replacement. Production authorization, distributed transactions, full language typestate and ownership reflection, runtime durability under power loss, and liveness remain open.

Reproduce with CPython 3.12.14 and SQLite 3.53.1 from the repository root.

```bash
study=research/language-design/RT-04/DURABLE-TYPED-STATE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent process schedules reproduce the exact results.
