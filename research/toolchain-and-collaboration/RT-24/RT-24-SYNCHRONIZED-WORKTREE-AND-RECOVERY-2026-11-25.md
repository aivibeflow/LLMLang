# RT-24 Synchronized worktree publication and exact recovery

## Question and result

A validated semantic candidate can exist in a store even if its Git publication never happened. The local candidate protocol binds the semantic snapshot, mapping, checked evidence, selected regular-file digest, starting worktree generation and expected Git parent to one request. The protocol materializes the scoped files in the actual checkout, prepares a Git tree containing those bytes and the request receipt, then publishes through a compare-and-swap on a single Git ref. Recovery checks the reachable receipt, expected parent and selected content hashes.

Git 2.56.1 reproduced 14 native cases across SHA-1 and SHA-256. Six successful publications recovered from independent clones with the origin removed. Each contained only one publication commit. Eight refusal cases left the ref at its prior value and had no reachable receipt.

| Cut or input | Cases | Observed disposition |
|---|---:|---|
| Normal | 2 | Published staged tree with exact receipt |
| Writer exits immediately before ref update | 2 | Receipt unreachable. Checked retry published once |
| Writer exits after ref update before returning success | 2 | Reachable receipt resolved the unknown outcome without another commit |
| Partial export, already stale ref, already stale worktree, or extra staged path | 8 | Publication withheld |

```mermaid
flowchart LR
  Q[Exact request] --> G[Check ref and checkout generation]
  G --> T[Materialize and verify staged tree]
  T --> C[Prepare one commit with receipt]
  C --> R[Compare and swap branch ref]
  R --> H[Recover exact reachable receipt]
```

## End-to-end evidence

| Plan obligation | Native fixture |
|---|---|
| Reconstruction in an independent clone | [Textual SPG clean clone](RT-24-TEXTUAL-SPG-CLEAN-CLONE-2026-11-25.md) and six clean clones in this report |
| Parallel heads and exact base choice | [Core Git coordinator](RT-24-GIT-CORE-COORDINATOR-2026-11-25.md) and [multiple merge bases](RT-24-MULTIPLE-MERGE-BASES-2026-11-25.md) |
| Merge, rebase, cherry-pick and cross-file semantic conflict | [Native workflow and conflict gate](RT-24-GIT-WORKFLOW-CONFLICT-GATE-2026-11-25.md) |
| Mapping conflict and exact mapping revision | [Mapping coordination](RT-24-GIT-MAPPING-COORDINATION-2026-11-25.md) |
| RT-20 caller splits and clean or failed validation | [CIP coordinator](RT-24-CIP-COORDINATOR-2026-11-25.md) and [whole-graph reverse and CIP gate](RT-24-WHOLE-GRAPH-REVERSE-AND-CIP-GATE-2026-11-25.md) |
| Process interruption and duplicate retry | [CIP recovery](RT-24-CIP-RECOVERY-2026-11-25.md), the current fixture and [prepared ref crash](../RT-23/RT-23-GIT-PREPARED-REF-CRASH-2026-11-24.md) |

A store-only completion flag cannot distinguish the two process exits. A separate receipt ref permits a split visibility interval in the files backend. A single protected journal can carry durable publication decisions across branch projection or rewrite, with additional authorization and fetch requirements. For the fixture, storing the receipt in the single published commit yields ordinary clone recovery while the commit stays reachable. [Ref visibility](../RT-23/RT-23-REF-COMMIT-VISIBILITY-2026-11-24.md) · [Protected journal](../RT-23/RT-23-SINGLE-JOURNAL-REF-2026-11-24.md) · [Git retention](../RT-23/RT-23-PINNED-GIT-RETENTION-2026-11-25.md)

The local checkout and Git ref are separate mutation surfaces. This fixture uses cooperative single-writer sequencing, a fixed four-file baseline and process exit on either side of the Git command. It models a lost reply after publication. It leaves worktree exclusion against ordinary editors, cleanup of a partial export, authority over receipts, arbitrary branch rewrites and storage durability to separate protocols. Existing linked-worktree evidence demonstrates the residual ordinary-editor race. [Linked-worktree publication](../RT-23/RT-23-LINKED-WORKTREE-PUBLICATION-2026-11-24.md)

## Replay

Run from the repository root with CPython 3.12 and Git compiled with SHA-256 support. The runner creates every input repository in a temporary directory. Two hash seeds produce the same [raw ledger](SYNCHRONIZED-WORKTREE-RECOVERY-01/evidence.json).

```sh
LC_ALL=C PYTHONHASHSEED=37 python -B research/toolchain-and-collaboration/RT-24/SYNCHRONIZED-WORKTREE-RECOVERY-01/check.py
```
