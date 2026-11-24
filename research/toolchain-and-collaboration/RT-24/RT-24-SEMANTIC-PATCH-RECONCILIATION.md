# RT-24 — Compare a Git replay with an independently composed semantic patch

**Date** · 2026-11-21

**Baseline** · `4396691`

**Status** · Bounded experiment for [Plan §4.5](../../../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question

A replayed commit can have the correct parent and a closed source inventory while omitting the change it was meant to apply. Does the existing three-way merge policy give an independent semantic expectation that detects such substitutions? [Closed-inventory merge](RT-24-CLOSED-THREE-WAY-MERGE.md) · [Exact-tree publication](../RT-23/RT-23-EXACT-TREE-COMMIT-RECOVERY.md)

The fixture pins the source patch parent, patch commit and destination commit. It imports their inventories and independently applies the structural three-way policy to the base, destination and patch source. It then imports the actual replay tree, verifies the destination parent and compares exact semantic selections. The evidence captures both semantic roots and the physical tree used for the observation.

| Check | Finding |
|---|---|
| Git closure and ancestry alone | A same-parent replacement can omit the caller and still satisfy both checks. |
| Compare to the composed semantic patch | Detects a missing caller or a conflicting provider edit even if the observed tree independently imports. |
| Bind the resulting physical tree during publication | Needed in addition when ordinary file contents are part of the reviewed change. The fixture records their tree effect and leaves publication to RT-23. |

## Results

A true one-commit cherry-pick and rebase both match the independently composed semantics when the target retains the old provider needed by the patch. A same-parent substitute with a closed tree and no caller fails the semantic comparison. A substitute with the correct declarations and changed ordinary file bytes passes the semantic comparison and produces different physical evidence. A competing provider change produces a structural conflict before result comparison.

The experiment uses a restricted exact declaration inventory and the whole-slot structural merge policy. It does not implement arbitrary replay, resolve conflicts, approve compatibility, or prove ordinary file changes correspond to the original patch. It isolates that source closure, semantic patch correspondence, and physical approval answer different questions. [RT-20 candidate semantic diff](../RT-20/RT-20-CANDIDATE-SEMANTIC-DIFF.md)

## Reproduction

Run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` on CPython 3.12.14 and Git 2.52.0. Ten tests passed. [Experiment](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_replay_patch_correspondence.py)

```sh
python -B -m unittest -v tests.test_rt24_replay_patch_correspondence tests.test_rt24_semantic_merge_core
```