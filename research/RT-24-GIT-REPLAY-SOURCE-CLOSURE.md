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

## Exact reproduction (2026-11-22)

The dedicated Git replay reproduction workflow completed successfully on the exact PR revision below:

| Field | Observed value |
|---|---|
| Workflow | [RT-24 Git replay exact reproduction #45071845516](https://github.com/aivibeflow/LLMLang/actions/runs/45071845516) |
| Tested commit | `e3b42d8bd8729b7471bbe62b5ce76d2635f5c726` |
| Runner | Ubuntu 24.04 |
| Python | CPython 3.12.14 |
| Git used for the experiment | `git version 2.52.0` |
| Upstream Git v2.52.0 source archive SHA-256 | `da8be57afb73a2370a5a891405b5e5624562f07a5c041f9e827e75320dc61114` |
| Focused tests | 11 passed, 0 failed, 0.557 s |
| Test log SHA-256 | `0a909a8b157f38b5a3d3aebccdf93a9b19eb2889bdf9417b8e0df0240ebd648a` |
| Reproduction artifact | [Artifact #14773368755](https://github.com/aivibeflow/LLMLang/actions/runs/45071845516/artifacts/14773368755) |
| Artifact size / digest | 1,617 bytes / `sha256:12f6ee9d7ffc2982b62c277d015c2905de65a259726cc65de691879b184379e0` |

The workflow also recorded the tested report hash `7ea388ec5a26e63cb28af76bc5632fd567b135aa3b17278e029da9facb45c8b6`, `test_rt24_git_replay.py` hash `12752b90605a57bdc0921b70de87ccf4ede5c6aeadf047f834d178ae02e367c0`, and `test_rt24_merge_tree_gate.py` hash `aa6aa6f76cb0632160bcc06bfd42cb2b640171a554e484c0b2ad90c2fc617cba`.

**Disposition:** the previously documented 11-test RT-24 source-closure/merge-tree fixture is now independently reproduced with the declared Git 2.52.0 and CPython 3.12.14 versions. This closes only that bounded reproduction item. It does not establish a general replay coordinator, multi-commit conflict handling, concurrent publication safety, or RT-20/RT-23 integration.

## Reproduction

Run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` on CPython 3.12.14 and Git 2.52.0. Eleven tests passed. [Fixture and controls](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_git_replay.py)

```sh
python -B -m unittest -v tests.test_rt24_git_replay tests.test_rt24_merge_tree_gate
```
