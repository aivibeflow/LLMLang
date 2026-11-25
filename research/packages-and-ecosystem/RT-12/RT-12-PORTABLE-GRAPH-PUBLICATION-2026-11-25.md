# RT-12 atomic local graph publication and portable Git recovery

**Date** 2026-11-25 · **Plan** §4.1 · **Issue** [#319](https://github.com/aivibeflow/LLMLang/issues/319)

A writer verifies a graph using repository-local and shared content addresses. It stages every verified object in the repository-local CAS and checks the complete local closure. One SQLite WAL transaction then publishes the exact root, inventory digest and per-occurrence reverse projection. Readers verify the selected local graph and reverse metadata together.

| Control | Checked result |
| --- | --- |
| Child exits after staging local objects | Exact bytes remain staged. The selected root and reverse projection remain at the previous revision. |
| Child exits after writing root and index in the transaction | The previous revision remains selected. The new projection has no visible rows. |
| Child exits immediately after committing | The successor and its complete projection remain selected on reopen. |
| Competing writer pins an earlier root | An actual SQLite writer lock makes the contender wait. Its expected-root check then refuses its stale update. |
| Shared storage becomes unavailable after commit | The selected graph remains readable and its bytes match the exact local closure. |
| Database-free Git archive | A detached restore reconstructs the exact graph, inventory, selected root and reverse index. A wrong-root request or a missing object is refused. |

The portable carrier is an actual Git tree export containing an explicit manifest and all reachable object files. The restore reads members by name, verifies the expected root and complete content, and reconstructs SQLite metadata in a new local store. The shared tier contributes checked immutable content. Repository-local metadata selects a revision only after the corresponding graph is locally complete.

The process exits and writer contention run against local SQLite and filesystem storage. The temporary Git repository uses a branch named `research/all` and has no configured remote. Canonical object schemas, authenticated revision authority, concurrent collection, multi-machine failure, multi-repository retention policy and power-loss durability remain open. The archive format is a fixture.

Reproduce with Python 3.12.14, SQLite 3.53.1 and Git 2.52.0 from the repository root.

```bash
study=research/packages-and-ecosystem/RT-12/PORTABLE-GRAPH-PUBLICATION-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent runs reproduced the archived process outcomes and Git export digest byte for byte.
