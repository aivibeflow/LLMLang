# RT-19 Process crash recovery across SQLite acceptance and Git publication

The bounded coordinator recovered the same Git commit, tree and semantic root after abrupt process exit at each of eight boundaries. SQLite retained accepted work while Git still pointed to the previous commit. Once Git published, the receipt ref recovered the exact operation even when the branch was later moved to a divergent commit.

## Exact experiment

The fixture gives immutable object rows and the workspace journal separate contracts in one SQLite database. A transaction compares the expected generation and root, writes the immutable snapshot and advances the accepted head together with the request and pending outbox. The operation key binds the canonical bytes of the entire request. SQLite runs in WAL mode with full synchronous writes and foreign keys enabled.

Publication materializes the accepted bytes in a private Git index rooted at the pinned base. It includes two source files and their manifest, one approved regular file and one recorded deletion. The runner reuses the closed-inventory importer to reconstruct the expected semantic root from the exact tree. It records the prepared commit in SQLite, publishes the branch and Git operation receipt through one `git update-ref --stdin` transaction, and records the outcome in SQLite. The authoritative Git tree is reconstructible without the local journal. [Exact-tree recovery fixture](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_commit_recovery.py) · [Prior protocol comparison](RT-19-TRANSACTION-RECOVERY-PROTOCOL-COMPARISON-2026-11-24.md).

A separate Python process exits abruptly at each failpoint via `os._exit(74)`, before any cleanup or reply. A fresh reader checks the database and Git refs. Two new processes retry with the same request and must report the same commit, tree, root and generation. Every replay also checks that the live index and unrelated worktree bytes are unchanged, including an independently staged file and a later edit to an approved path.

| Injected process exit | Durable SQLite state | Branch | Receipt ref |
| --- | --- | --- | --- |
| After beginning acceptance | Original head, no accepted operation | Original | Absent |
| After inserting the immutable row, before commit | Original head, no accepted operation | Original | Absent |
| After accepting and writing the outbox | New head, pending | Original | Absent |
| After staging the first private-file entry | New head, pending | Original | Absent |
| After validating the private tree and writing the candidate commit | New head, pending | Original | Absent |
| After recording the prepared candidate | New head, prepared | Original | Absent |
| After the Git ref transaction | New head, prepared | Published | Present |
| After storing the operation outcome | New head, recorded | Published | Present |

Two different requests competing for the same base result in one acceptance and one stale-generation rejection. Two processes submitting the same key and bytes receive the same outcome. Reusing the key with altered approved bytes is rejected, as is an incomplete source inventory. When Git advances before publication, the exact accepted outbox remains pending and the new branch head is preserved. When it advances divergently after publication but before SQLite records the outcome, the receipt still returns the original publication. A fresh Git clone reproduces the final semantic root with no copy of the journal.

## Implementation implications

A Git-only acceptance design would have no published record in the reachable branch during the tested accepted-pending window. A journal that identifies completion from the current branch tip would lose the historical outcome after divergence. The tested split lets SQLite linearize local acceptance and the Git receipt identify publication separately. The study uses a single head and one closed source profile. It leaves branch-based acceptance, authorization, MCP behavior and complete merge discovery to their own gates.

The failpoints bracket the Git transaction and exercise process restart on one filesystem. Mid-transaction Git termination, abrupt machine or storage loss, network filesystems, repository maintenance, production recovery policy and performance under representative load remain open.

## Reproduction

The manifest was generated with Git 2.52.0, CPython 3.12.14 and SQLite 3.53.1. [Recorded crash states, exact commit and root IDs, and input digests](sqlite-git-crash-recovery/results.json).

```sh
python3 -B research/toolchain-and-collaboration/RT-19/sqlite-git-crash-recovery/run.py \
  --output /tmp/llmlang-rt19-crash-recovery.json
cmp /tmp/llmlang-rt19-crash-recovery.json \
  research/toolchain-and-collaboration/RT-19/sqlite-git-crash-recovery/results.json
```
