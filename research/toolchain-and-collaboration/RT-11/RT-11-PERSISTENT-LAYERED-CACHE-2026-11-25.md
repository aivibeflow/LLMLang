# RT-11 persistent cache layers and artifact eviction

**Date** 2026-11-25 · **Plan** §3.3 · **Issue** [#300](https://github.com/aivibeflow/LLMLang/issues/300)

The fixture gives local, workspace, remote and global roles separate SQLite files. The local and workspace layers can mirror exact records and keep checked content for restart and disconnected reads. The remote cache supplies shared original records and may supply artifacts. Global storage serves content by digest and contributes no receipts. An externally checked view identifies the exact required records and the request applies its current scope. Every record and payload is checked by hashing the bytes returned from the layer.

| Control | Checked result |
| --- | --- |
| Initial connected lookup and promotion | Remote records and a global artifact make an exact hit. A single workspace transaction persists the original records and verified bytes. |
| Offline restart | Reopened workspace storage can populate local storage. A fresh process finds the exact hit using the persisted local mirror. A policy that recognizes only the workspace as issuer refuses the same copied receipts. |
| Corrupt local bytes | The lookup skips the corrupt copy and reads the exact bytes from workspace storage. Verified promotion repairs the local copy. |
| Workspace eviction while a reader holds a WAL snapshot | The old reader sees exact bytes, the fresh reader sees no artifact, and the original attestation remains. Offline lookup misses once local content is also evicted. Connected lookup can rematerialize from global bytes using retained local records. |
| Original view changes to include an authorized alternative | Connected lookup signals a conflict despite missing alternative bytes. Offline lookup sees the view gap and declines to choose the earlier local candidate. |
| Promotion process exits after writing but before committing | Neither the new record nor its payload is visible on reopen. The old committed pair remains and the workspace database passes the integrity check. |

The ledger contains 13 lookup controls, a two-reader eviction schedule and one interrupted SQLite publication. Use the near layers to optimize placement and reduce restoration cost. Evaluate applicability and current authority from immutable original receipts. Require all records for the exact view before taking a local hit. Publish promotions atomically with their checked payloads, and give active consumers snapshot or lease semantics. Evict payloads independently of records when the cache permits rematerialization.

The global and remote roles run as local SQLite files, with availability supplied by the request. The inputs include an externally trusted exact view. Authentication is separately checked in the [signed admission fixture](RT-11-SIGNED-REBUILD-ADMISSION-2026-11-25.md). Network failure, signed view distribution, power-loss durability, storage quotas, multi-host leases, and a production store remain open. The snapshot guarantee is local to one SQLite database.

Reproduce with Python 3.12.14 and SQLite 3.53.1 from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-11/PERSISTENT-LAYERED-CACHE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh database sets and independently spawned readers and writers reproduce the archived ledger byte for byte.
