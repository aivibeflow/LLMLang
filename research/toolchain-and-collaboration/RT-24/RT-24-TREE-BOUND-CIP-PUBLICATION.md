# RT-24/20/23 — Publishing a tree after exact caller migration review

**Date** · 2026-11-21

**Baseline** · `26ab2be`

**Status** · Bounded executable experiment for [Plan §4.5](../../../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question and boundary

Can an exact caller-migration plan authorize publication of more than one physical tree? The fixture changes one provider, rewrites one guarded call to its exact replacement, and includes an approved ordinary file change. The comparison connects the existing closed-tree importer, source-derived reverse query, Change Impact Plan (CIP) diff validation, and RT-23 Git publication in a disposable repository.

| Gate | Interpretation |
|---|---|
| Semantic roots and CIP only | Can establish matching semantic changes within the supported model. Two trees with identical closed declarations but different ordinary file contents have the same semantic root. |
| Exact Git tree alone | Fixes the published files. It still needs evidence of source coverage and the exact migration required by the plan. |
| Source-bound CIP and exact prepared Git state | Checks both boundaries. Approval must bind physical and semantic evidence, and publication must compare the Git ref and record the receipt. |

[RT-20 materialized semantic diff](../RT-20/RT-20-CANDIDATE-SEMANTIC-DIFF.md) · [RT-24 source-completeness fixture](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md) · [RT-23 exact-tree recovery](../RT-23/RT-23-EXACT-TREE-COMMIT-RECOVERY.md)

## Method and results

The fixture pins the baseline tree and inventory, candidate tree and inventory, prepared commit, and CIP. It reconstructs the two closures in fresh stores, recomputes caller coverage from source, and compares complete audit bindings and the exact set of audited call-site identities. Existing RT-20 validation then compares candidate output, required contract, target and condition with the planned edit. Existing RT-23 code publishes the prepared commit and receipt together.

| Control | Observation |
|---|---|
| Exact candidate with one migrated call and ordinary file update | Publishes the exact commit and receipt. Repeating the gate resolves to the same publication. |
| Substitute ordinary file with a semantically identical tree | Semantic roots match, but publication rejects the different Git tree before ref writes. |
| Remove the source-audit binding and recalculate the plan ID | The gate rejects the missing binding. |
| Remove the migration disposition or change the planned guard and recalculate the ID | The exact site coverage or materialized diff rejects the altered plan. No receipt is created. |

The result shows why a semantic approval and an exact Git tree approval must meet at the same publication boundary. The fixture accepts prepared approval and compatibility evidence as inputs. It verifies neither evidence provenance nor the behavioral compatibility of the replacement. It covers a single explicit call with a fixed inventory. Arbitrary changed-target discovery, full merge ancestry, implicit or dynamic calls, authenticated approvals, interface mapping publication and shared-worktree coordination remain open.

## Reproduction

Run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` on CPython 3.12.14 and Git 2.52.0. All 27 tests passed. [Experiment](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_tree_bound_cip.py)

```sh
python -B -m unittest -v tests.test_rt24_tree_bound_cip tests.test_rt24_merge_tree_gate tests.test_rt23_commit_recovery tests.test_candidate_semantic_diff_cip_v2
```
