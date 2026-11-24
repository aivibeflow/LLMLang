# RT-23 — A Git branch generation alongside exact-tree publication

**Date** · 2026-11-21

**Baseline** · `95f95a7`

**Status** · Bounded native Git experiment for [Plan §4.5](../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

## Question

Can a publisher reject a stale approval after a branch moves away from the expected commit and returns to the same OID? The original exact-tree transaction compares the branch's expected OID. The recovery fixture found movement away and back can pass that comparison. A separate causal generation can distinguish identical branch states reached through different coordinated histories. [Exact-tree recovery](RT-23-EXACT-TREE-COMMIT-RECOVERY.md) · [Git update-ref transactions](https://git-scm.com/docs/git-update-ref)

| Approach | Trade-off |
|---|---|
| Compare only the expected branch OID | Simple and interoperable. A branch can revisit a previous commit. |
| Compare branch and generation together | Detects intervening coordinated updates, including movement back. Requires every writer in the guarantee to update the generation. |
| Inspect refs or reflogs outside the transaction | May provide forensic context. The observation can become stale before ref publication and reflog history can be unavailable. |

## Method and results

A separate Git ref points at a generation token stored as a blob. Every coordinated update derives a new token from the preceding token and new branch OID. The publisher binds the current token when preparing its request. The Git update compares and advances the branch and token in one transaction and creates the operation receipt. For a previous successful operation, recovery checks the existing receipt first.

| Control | Observation |
|---|---|
| Coordinated move away from and back to the original OID | The original OID-only inspection reports retryable. Generation comparison returns stale and creates no receipt. |
| The same move between preflight and the ref transaction | Transactional comparison rejects the stale generation and leaves the original branch and receipt state intact. |
| Subsequent coordinated moves after successful publication | Repeating the original request resolves to the recorded result. |
| Writes that bypass the generation and return to the original OID | The token stays unchanged, so the experiment cannot detect the movement. |

The result separates exact content identity from a coordinated mutation generation. Branch generation is distinct from worktree file generation, mapping revision and semantic snapshot identity. It does not protect operations that bypass the coordinator. Atomic observations across multiple refs, durability under crashes, authentication, externally moved refs and accepted recovery policy remain open. The test concerns the outcome of cooperating Git writers and fixture receipt recovery.

## Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`, run on CPython 3.12.14 and Git 2.52.0. Twelve tests passed. [Experiment](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_ref_generation.py)

```sh
python -B -m unittest -v tests.test_rt23_ref_generation tests.test_rt23_commit_recovery
```