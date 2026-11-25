# RT-12 leased external CAS collection and process recovery

**Date** 2026-11-25 · **Plan** §4.1 · **Issue** [#319](https://github.com/aivibeflow/LLMLang/issues/319)

The fixture stores graph objects in a filesystem CAS. A SQLite WAL catalog serializes mutations of branch heads and durable reader leases. A catalog epoch qualifies each mark result. Protected objects are the exact reachable closure of all heads and leases. The sweeper compares the epoch and checks the complete current closure while holding the mutation lock, then moves eligible files into quarantine. Recovery validates the reachable closure before removing quarantined bytes.

| Control | Checked result |
| --- | --- |
| A head changes or a lease is added after marking | A stale plan is refused. A proposed plan at the current epoch also fails if it names a protected object. |
| Child exits after its first quarantine move | Both the newest graph and the leased old graph remain exact. Reopening the store validates the reachability set and collection resumes for the two orphan objects. |
| Two readers lease the old revision | Releasing either single lease leaves the old graph protected. Releasing both makes the old root and private implementation collectable. The shared contract survives with the current graph. |
| A live file is found only in quarantine | Normal marking stops on the missing live dependency. Recovery restores exact checked bytes to the active store before disposing of the quarantined copy. |
| Quarantined live bytes are corrupted | Recovery refuses, keeps the suspect bytes for inspection, and leaves the affected root ineligible for a new lease. |

Twelve controls passed in two independent runs. The process-exit test performs actual filesystem renames and SQLite transactions. The design relies on cooperating writers using the catalog lock and on readers acquiring leases before opening a snapshot. The diagnostic salvage cases deliberately move a protected blob to exercise recovery. Lease expiry, automatic recovery across distributed stores, power loss, quota management and production retention rules remain open.

Reproduce with Python 3.12.14 and SQLite 3.53.1 from the repository root.

```bash
study=research/packages-and-ecosystem/RT-12/EXTERNAL-CAS-COLLECTION-01
python "$study/run.py" | cmp "$study/evidence.json" -
```
