# RT-23 — Recovery after publishing a validated Git tree

- **Status** · Executable study of the local publication and retry boundary
- **Date** · 2026-11-21
- **Baseline** · `ce97b1a`, the RT-24 merged-tree source completeness study
- **Plan** · §4.5, synchronized commit and recovery

## Question

Can a retry identify the exact outcome of a validated Git publication when the caller loses the reply? The study advances the publication phase of RT-23 using the closed source importer from RT-24. Full worktree synchronization also needs a stable worktree generation, the mapping revision, and the complete validation context. [RT-23 synchronization protocol](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md#92-commit-preparation-and-synchronization-protocol) · [RT-24 source completeness](../RT-24/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md)

## Alternatives and fixture

| Recovery rule | Prediction or distinguishing test |
|---|---|
| Rebuild from the current index or worktree | A later edit can change the validated tree. The fixture adds an edit after freezing the tree and keeps a separate user's staged and unstaged changes. |
| Infer completion from the branch tip's tree and parents | Another operation can produce a different commit with the same tree and parents. |
| Write an operation receipt in a separate ref update | The write order leaves a gap between branch publication and recording the receipt, or between recording the receipt and branch publication. |
| Prepare one commit object and use one Git ref transaction | The tested precondition failures must leave both refs intact. After both ref updates succeed, the operation receipt should identify the same commit on every retry. |

The harness constructs a tree with an alternate index seeded from the first parent. It stages a changed semantic declaration and one selected ordinary file there. It reconstructs the semantic snapshot from the frozen tree, then creates a commit object with two ordered parents and an operation-specific message. A JSON preparation record pins the operation, tree, semantic root, parents, and exact commit OID. Tests reload that record across the interruption boundary. The fixture trusts its local preparation record and models loss of an operation reply. [Executable fixture](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_commit_recovery.py)

Publication verifies the prepared metadata and re-imports the exact candidate. An `update-ref --stdin` transaction compares the branch with the first parent and creates a private receipt ref for the operation. The receipt names the exact candidate OID. Recovery checks the receipt, ordered parents, tree and semantic root. With no receipt, the old branch OID makes an attempt eligible for another compare-and-swap. A different branch tip gives a stale result. A valid receipt after a later branch move records historical publication with a distinct result for branch movement. [Git commit-tree](https://git-scm.com/docs/git-commit-tree) · [Git update-ref](https://git-scm.com/docs/git-update-ref)

## Results

The claims below are experimental observations for the local Git files backend and the closed scalar declaration fixture. The tests make concrete predictions about refs, commit identity, semantic reconstruction and worktree bytes. [Reproduction corpus](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_commit_recovery.py)

| Claim | Observation |
|---|---|
| COMMIT-01 | Before the ref update, replay publishes the frozen tree, including the selected file's validated bytes. The unrelated staged and unstaged bytes survive. The late edit survives on disk and is absent from the commit. |
| COMMIT-02 | After the ref transaction succeeds and the reply is discarded, two retries recover the same OID. The first-parent chain contains the base and exactly one published commit. |
| COMMIT-03 | A branch move between inspection and the transaction causes compare-and-swap failure and leaves the receipt absent. A conflicting existing receipt also causes failure and leaves the branch at its old OID. |
| COMMIT-04 | A different operation with an identical tree and ordered parents yields `stale`. A mismatched tree, parent set or semantic root blocks publication. Inspection of an existing receipt also detects reordered parents. |
| COMMIT-05 | A receipt still identifies the published commit after another commit advances the branch. Recovery reports historical publication and leaves the new branch tip in place. |
| COMMIT-06 | If the branch moves away and returns to the original OID before publication, the Git compare-and-swap succeeds. The original OID alone cannot enforce a worktree generation or a monotonic ref revision. |

## Scope and decision boundary

The results support a prepared commit OID plus an operation receipt for retry within the tested boundary. RT-23 still needs a generation check at publication to enforce its policy on concurrent edits and ref movement. A production implementation also needs to protect receipt refs, retain prepared objects across garbage collection, and bind the mapping revision, exact validation evidence, and operation authority. The fixture publishes an already validated tree and deliberately preserves the live index, so success establishes an exact Git commit rather than a synchronized worktree generation. [Plan §4.5](../../../PLAN.md#45-end-to-end-semantic-merge-and-synchronized-commit-lifecycle)

The tests inject interruption before and after the Git ref transaction. They cover precondition failures during normal command operation. The evidence leaves process loss inside the ref transaction, machine power loss, fsync durability, arbitrary concurrent ref readers, remote pushes, and later receipt collection open. In particular, the Git ref transaction and the preparation record are distinct durability domains. A recovery implementation needs an explicit policy for unknown or inconsistent observations. [Git update-ref](https://git-scm.com/docs/git-update-ref) · [RT-23 crash recovery](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md#93-failure-crash-recovery-and-atomicity-boundary)

## Reproduction

Run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` with CPython 3.12.14 and Git 2.52.0 on Linux 6.18.57 x86-64. Fixtures use disposable SHA-1 repositories, pinned Git author and committer dates, and a 30-second command timeout. Expect eight passing tests.

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest -v tests.test_rt23_commit_recovery
```

All 173 tests in the focused semantic dependency and research selection passed. Full discovery ran 412 tests and repeated the baseline `test_analysis_bound_returns_unknown_not_success` failure and the optional Z3 skip.
