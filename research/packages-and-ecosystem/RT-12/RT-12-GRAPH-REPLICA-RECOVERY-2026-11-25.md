# RT-12 incremental graph replica recovery

**Date** 2026-11-25 · **Plan** §4.1 · **Issue** [#319](https://github.com/aivibeflow/LLMLang/issues/319)

The follower stores immutable graph objects in a filesystem content store and its selected revision in a SQLite WAL database. A revision binds its predecessor, serial, exact root and the complete reachable inventory. The caller supplies the already authenticated revision identity. The follower verifies each transferred digest, traverses the entire graph over local retained bytes and the incoming delta, and compares the resulting inventory. It stages the verified object files before selecting the exact successor in one SQLite transaction.

| Control | Checked result |
| --- | --- |
| Bootstrap and incremental transfer | The three revisions contain three, four and three reachable objects. After bootstrap, the two updates transfer two and one objects respectively. |
| Incomplete, corrupt or extraneous transfer | Missing closure members, altered bytes, surplus entries and the wrong complete inventory all prevent publication. |
| Child exits after staging and before commit | The new bytes exist, SQLite retains the old selected revision, and the old graph stays readable. Retrying with the exact delta succeeds and subsequent retransmission is idempotent. |
| Corrupt retained dependency | The currently selected graph becomes unreadable. A same-revision repair with exact bytes restores the closure. |
| Lag, fork or replay | A lagging replica is historical only. An alternative root at the same next serial and replay of the predecessor are refused. |
| Failover admission | A complete current replica without writer authority remains read-only. The fixture requires separate authority scoped to the exact current revision before reporting eligibility to take over. |

The local storage writes and process exit are real. The follower uses a controlled filesystem and a local authenticated-tip premise. The external writer fence is supplied by the experiment. Consensus, issuance and revocation of writer authority, actual failover writes, concurrent garbage collection across replicas, power loss and network partitions remain open. Historical reads are available only while the selected closure is retained and verified.

Reproduce with Python 3.12.14 and SQLite 3.53.1 from the repository root.

```bash
study=research/packages-and-ecosystem/RT-12/GRAPH-REPLICA-RECOVERY-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Twenty controls reproduced in two independent runs. The runner reuses the exact closure validator from the [closed backup experiment](RT-12-CLOSED-GRAPH-BACKUP-2026-11-25.md).
