# Research Scenario 125 — Callback Reentry and Dependency Coverage at Close

**Status:** bounded model and native SQLite comparison

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

Scenario 124 orders a producer on another thread with close under a shared guard. This scenario checks synchronous reentry under that same guard and tests which native dependents a fresh statement observation covers. These issues constrain different parts of the close contract. [Close synchronization](RESEARCH-SCENARIO-124-CLOSE-SYNCHRONIZATION.md)

## Reentrant producer

The closer holds a recursive wrapper lock, observes the statement set, and invokes a user-defined scalar SQL function when the set is empty. Its callback may use the same locked wrapper to prepare and retain another statement. The outer SQL statement is finalized before close. SQLite allows this callback to call other APIs while the executing statement and its connection are kept alive. In the fixture the callback returns SQL `NULL` after recording whether it could prepare. [Callback API contract](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/sqlite.h.in#L5469) · [Native harness](../../PROTOTYPES/RT-04-01/sqlite_close_reentry_probe.py)

| Policy | Callback requests a statement after an empty observation | Outer result |
|---|---|---|
| Hold the recursive lock | Reentry acquires the same lock and retains a statement | `SQLITE_BUSY` with an open connection |
| Reserve close before observation | The wrapper refuses new dependents while closing | `SQLITE_OK` and destruction at return |
| Inspect again after the callback | Reentry retains a statement and the refreshed observation sees it | Close is declined with an open connection |

The model varies the three policies, whether a statement is live initially, and whether the callback requests a statement. SQLite agrees on all 12 cases. An initially live statement blocks the outer operation before the callback. A preserving callback permits close in all three policies. The native harness also attempts another prepare through the wrapper after return. It confirms that the connection remains usable after refusal or busy and that the wrapper refuses post-destruction use before entering SQLite. [Model](../../PROTOTYPES/RT-04-01/rt04_close_reentry.py) · [Focused checks](../../PROTOTYPES/RT-04-01/test_rt04_close_reentry.py)

The reservation makes refusal of the nested operation part of the public contract. In this experiment the callback handles refusal and lets the outer operation continue. The reinspection policy permits the nested operation and may decline the outer close after those effects have run. It requires a region from the final observation through retirement that excludes further dependency-creating reentry.

## Native dependency coverage

On a separate connection for each case, the harness observes the statement set with `sqlite3_next_stmt`, then calls ordinary close or `close_v2`. There are four inputs. The backup case targets the source connection after `backup_init`; the destination stays reserved for the backup until `backup_finish`. The BLOB is released through `blob_close` and its backing statement is observed through enumeration. [SQLite close contract](https://www.sqlite.org/c3ref/close.html) · [Statement enumeration](https://www.sqlite.org/c3ref/next_stmt.html) · [Backup API](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/sqlite.h.in#L9306)

| Live dependent | Statements observed | Ordinary `close` | `close_v2` |
|---|---:|---|---|
| None | 0 | `SQLITE_OK`, destroyed at return | `SQLITE_OK`, destroyed at return |
| Prepared statement | 1 | `SQLITE_BUSY`, retains connection | `SQLITE_OK`, destruction on `finalize` |
| Incremental BLOB | 1 | `SQLITE_BUSY`, retains connection | `SQLITE_OK`, destruction on `blob_close` |
| Unfinished backup | 0 | `SQLITE_BUSY`, retains source | `SQLITE_OK`, source destruction on `backup_finish` |

All eight calls match this projection on SQLite 3.46.1. The implementation checks the connection's statement list and B-tree backup state. The tested BLOB creates an internal statement, which explains its visibility in this version. The backup occupies a different path in the close predicate. A complete observation for this API needs to cover backup state even when the statement list is observed under an exclusive guard. [Close implementation](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/main.c) · [BLOB implementation](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/vdbeblob.c) · [Backup implementation](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/backup.c)

## Implications for candidate comparison

A proof or runtime guard needs coverage of the producer operations, dependent kinds, and resource roles that can affect close. A backup involves both source and destination with distinct obligations. For mediated FFI calls, a reservation can deny conflicting entry, or a final guarded observation can account for effects that the wrapper deliberately permits. When lifetime is controlled but dependency coverage is unknown, ordinary close exposes busy and retains the capability. Deferred close instead needs the caller contract to distinguish retirement from completed destruction. [Result forwarding](RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md)

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_close_reentry.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_close_reentry_probe.py
```

The runs used Python 3.12.14 and SQLite source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1` on in-memory databases. The corpus covers one scalar callback, one retained dependent per case, and one version of SQLite. General source-derived authority, effects of callbacks during destruction, multi-resource lock ordering, and incomplete or indeterminate foreign contracts remain open.
