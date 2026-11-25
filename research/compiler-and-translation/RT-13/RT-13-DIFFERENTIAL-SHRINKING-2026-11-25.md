# RT-13 — Differential generation and claim-preserving shrinking

The [mutation coverage study](RT-13-STATE-RESULT-MUTATION-COVERAGE-2026-11-25.md) distinguishes six seeded faults with source/reference comparisons. This study adds a reproducible way to find and reduce failures while preserving the observation claim. It applies to [PLAN §2.5](../../../PLAN.md#25-correctness-of-optimization-and-translation) and [#297](https://github.com/aivibeflow/LLMLang/issues/297).

Generate closed, typed source trees by choosing admitted State/Result constructors. Execute both the source and its emitted candidate through the pinned wire reference on both initial cells. Compare the complete result, state and ordered effect trace. The independent small-step evaluator checks the baseline candidates and every accepted shrink step. The seeded faults still use the pinned mutation implementations.

A witness states which property it violates. The complete-observation property accepts any difference. The order-only property requires a difference while tagged result, cell and event multiset agree. For example, swapping two writes can change the final cell, so that small test does not preserve an order-only violation. A third write restoring the original final cell makes the order difference isolatable.

The shrinker deletes a constructor, substitutes a well-typed leaf or subtree, or reduces the initial cell. It takes a smaller witness only if it still violates the same property after the mutant is rerun. A strict order on tree size, initial cell and tree gives reproducible selection and termination. At the final witness none of the smaller candidates in this neighborhood preserve the failure. A separate search finds the smallest witness size in the pinned complete corpus of one-, three- and five-node trees. This checks the greedy result against a bounded exhaustive baseline.

| Result | Count |
| --- | ---: |
| Generated program/cell rows, counting duplicates | 3,072 |
| Distinct trees summed across the four seeds | 992 |
| First witnesses, including order-only variants | 28 |
| Order-only witnesses | 4 |
| Witnesses reduced to the corresponding exhaustive minimum size | 28 |

Each seed finds all six complete-observation defects. A 155-node order-only witness shrinks to five nodes. One five-node result writes `1, 0, 0` while its mutant writes `0, 1, 0`. Both return successful unit, end at cell zero, and have equal event multiplicities. The ordered observation still distinguishes them. The effect-erasure fault for a read shrinks to a single node.

Exhaustive checks give complete results for the fixed small-tree corpus. Seeded checks explore larger trees and report a concrete failure when found. Local shrinking makes those failures reproducible while retaining the diagnostic property. Guided generation for new language constructs still needs coverage controls for error, resource and environment conditions. The current evidence concerns the pinned grammar and six deliberate mutants. General optimizer correctness and production source correspondence remain separate. [DEP-013](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1 and CPython 3.12.14. Run from the repository root with archive commit `409d51c2de9026f12cc42450b29fcbe622a716cd`. The runner verifies the five archived files and their manifest, then regenerates the seeded and exhaustive comparisons. The [ledger](DIFFERENTIAL-SHRINK-01/evidence.json) records digests for the initial trees and each accepted shrink step, the complete minimized witnesses, and exact source and target observations.

```sh
set -eu
fixture=research/compiler-and-translation/RT-13/DIFFERENTIAL-SHRINK-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
