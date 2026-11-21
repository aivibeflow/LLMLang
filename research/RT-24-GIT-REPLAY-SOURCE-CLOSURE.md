# RT-24 — Source closure after Git cherry-pick and rebase

**Date** · 2026-11-21

**Baseline** · `11c7f19`

**Status** · Native Git experiment for [Plan §4.5](../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question

Does a successful textual replay preserve exact call bindings when the target branch has changed? The closed-inventory merge study found that a clean merge can omit a required callee version. Replay also changes the parent context and identifies a source patch. Closure, ancestry, and patch correspondence are separate evidence requirements. [Closed-tree merge evidence](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md) · [Git cherry-pick](https://git-scm.com/docs/git-cherry-pick) · [Git rebase](https://git-scm.com/docs/git-rebase)

The fixture starts from a base containing one provider. One commit introduces a caller pinned to that provider, and the target branch selects a newer provider. Both histories import independently. The test applies a real one-commit cherry-pick and an explicit rebase onto the target branch. It records the source parent, source commit, target parent, resulting commit, tree and closed semantic root. An exact parent check rejects altered ancestry. Fresh import checks the result's declared graph.

## Results

| Control | Observation |
|---|---|
| Replace the old provider without retaining it | Both operations finish with clean Git status. Fresh source import rejects both results for the missing exact old provider. |
| Retain the provider under a separate declared slot | Both results import. The caller still pins the old provider. An equal resulting tree and semantic root can carry distinct operation evidence. |
| Substitute the source or target parent | The envelope rejects the changed replay context even when the result tree imports. |
| Substitute a closed tree with the same target parent and no replayed caller | Closure and parent checks both pass. They leave proof of patch correspondence to another gate. |

A coordinator can use Git replay for text and history only if it subsequently checks source closure and reconciles the typed patch with the approved changes. It cannot infer migration to a new version from textual success. The experiment covers one explicitly scoped patch and no concurrent publication. It does not implement an automated replay coordinator, compare multi-commit conflicts, or establish RT-20 approval and RT-23 synchronized publication.

## Reproduction

Run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` on CPython 3.12.14 and Git 2.52.0. Eleven tests passed. [Fixture and controls](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_git_replay.py)

```sh
python -B -m unittest -v tests.test_rt24_git_replay tests.test_rt24_merge_tree_gate
```
