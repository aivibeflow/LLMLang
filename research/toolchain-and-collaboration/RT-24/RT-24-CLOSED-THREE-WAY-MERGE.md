# RT-24 — Three-way merge of closed semantic inventories

**Date** · 2026-11-21  
**Baseline** · `017e64b87c87371309197a392165258b8b088dd1`  
**Status** · Structural experiment for [Plan §4.5](../../../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question and alternatives

Can a selection-key merge combine independent semantic changes in the existing source importer, while detecting exact references broken by apparently disjoint edits?

| Approach | Cost and evidence |
|---|---|
| Git text merge followed by import | Gives conventional review and history. The previous experiment found a text-clean result with a missing exact callee. Import detects that case, but it cannot turn a plain text conflict into a structural candidate. |
| Compose semantic slots, then reconstruct the entire graph | Can combine independently edited slots within the same file. Requires complete inventories and needs an exact graph check after composition, including declarations that came from just one branch. This study exercises this approach. |
| Compose typed fields or call sites within a slot | Could recover additional valid results when two branches update one declaration. Requires semantics-specific merge laws, occurrence correspondence, and RT-20 disposition evidence. |

[Three-way contract and conflict matrix](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md#7-three-way-semantic-merge-contract) · [Previous source-completeness study](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md) · [Git three-way file merge](https://git-scm.com/docs/git-merge-file)

## Model

Read three committed inventories with the existing importer. Import each independently and record the ordered tuple of Git tree, inventory digest, and semantic snapshot ID for each. An incomplete inventory fails at the input reader. An independently invalid graph returns an input failure even if the other branches are valid.

Compare slots by explicit key and values by exact address. Adopt a one-sided change or coalesce equal outcomes relative to an existing base slot. Two additions at the same new key require a decision even if their value addresses agree. In the absence of declared continuity, equal addresses alone cannot establish the same managed occurrence. Competing updates and delete/update produce structured records carrying the exact input addresses.

Rebuild the selected rows in a fresh store and run the existing whole-graph audit. Check that the rebuild yields the selected addresses. Export only structural candidates as sorted canonical declaration rows and re-import the export in a temporary Git tree. The policy compares exact selections within this fixture. Lineage, arbitrary replacement under a continuing key, call-site reconciliation, mappings, and repository acceptance require wider context.

## Results

| Experiment | Observation |
|---|---|
| All 64 triples over absence and three possible exact values | 37 resolve, nine report add/add, six update/update, and 12 delete/update. Swapping branches preserves the selected value or conflict kind, with role labels swapped in conflict records. |
| Two changes to one JSON line | Ordinary Git merge reports a conflict. The semantic core combines a callee edit with an independent declaration addition, exports the same bytes with either branch ordering, and reconstructs the same selections from the exported tree. |
| New cross-slot caller combined with a replaced callee | Each input imports independently. Fresh reconstruction of the composed rows reports a graph conflict at the former callee address and emits no candidate. |
| Explicit retention of the old callee under its own slot | Reconstruction succeeds. The exact caller hash is preserved while the main callee slot gets a new address. |
| Invalid input or incomplete manifest | An invalid graph returns an input error. The inventory mismatch stops at the reader, before any slot deletion can be inferred. |

The first two cross-slot cases distinguish three concepts that the coordinator needs to report independently: textual merge, local semantic composition, and graph reconstruction. The successful exact-pin case is a structural witness for RT-20's preserve action. It carries no compatibility or review judgment. Automatic merging of unchanged-base updates in the scoped slot model still relies on the slot correspondence assumption. In production, RT-24 must validate that correspondence against the selected identity policy.

The evidence supports a pure composition stage followed by fresh reconstruction. Wider acceptance requires the RT-20 call-site impact plan, independent reverse-reference evidence for the applicable scope, separate mapping reconciliation, and RT-23 publication of the exact validated tree. The study deliberately emits `structural-candidate`, a result before those gates. [RT-20 candidate gate](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md#candidate-snapshot-materialization-gate-prototype) · [RT-23 commit boundary](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md#91-commit-is-a-synchronized-semantic-and-filesystem-operation)

## Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`, run the following. The recorded run on CPython 3.12.14 and Git 2.52.0 passed all 13 tests, including seven from the original importer study.

```sh
python -B -m unittest -v tests.test_rt24_semantic_merge_core tests.test_rt24_merge_tree_gate
```

[Experiment and fixtures](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_semantic_merge_core.py) · [Dependency map](../../research-management/RESEARCH-DEPENDENCY-MAP.md)
