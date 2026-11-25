# RT-14 context fixture readiness and controlled evaluation

The finite context corpus distinguishes complete authorized inputs from stale, missing, inaccessible, conflicting, duplicated, corrupted and over-budget alternatives. The exact gate matches the fixture disposition in all 15 inventories. Presence of ranked required records alone yields one false readiness result and misses one feasible context.

## Scoring

The comparison treats readiness as the binary label. It scores each distinct inventory once. The 164 input orderings check determinism separately. The ranked heuristic is scored by whether both exact required records appear in its delivered prompt. The label also requires valid permissions, conflict-free required inputs and a feasible budget.

| Ranked surrogate outcome | Inventories |
| --- | ---: |
| True positive | 8 |
| False positive | 1 |
| False negative | 1 |
| True negative | 5 |

Precision and recall for the ranked readiness surrogate are both 8/9. The conflicting-required case contains the exact required records alongside a conflicting version, so presence alone marks it ready incorrectly. The optional-before-mandatory budget case misses a required record even though both mandatory records fit. The exact gate refuses the first and successfully renders the second. Duplicate, stale, inaccessible and over-budget controls remain in the original corpus. [Original assembly study](RT-14-KNOWLEDGE-CONTEXT-ASSEMBLY-2026-11-25.md) · [Authorization and minimization](RT-14-CONTEXT-MINIMIZATION-2026-11-25.md)

## Representative evaluation

A separate trial needs independently labeled required and relevant evidence for each task, an exact authorized context, a pinned model and matched instruction and Toolchain versions. Report per-task evidence precision and recall, end-to-end task correctness, scope violations, repair and review effort, and budget. The fixture score characterizes the constructed readiness cases. It supplies no observed participant outcomes or representative retrieval accuracy.

## Reproduce

The checker pins the original corpus ledger and independently enumerates its expected readiness labels. CPython 3.12.14 and hash seeds 37 and 71 produce evidence SHA-256 `21b7cfef0b43f69052a23fa81e0fa004f9d98f5ba1ed2dabc2774912d355b550`. [Evidence ledger](CONTEXT-FIXTURE-SCORING-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/toolchain-and-collaboration/RT-14/CONTEXT-FIXTURE-SCORING-01/check.py > /tmp/rt14-context-scoring.json
```
