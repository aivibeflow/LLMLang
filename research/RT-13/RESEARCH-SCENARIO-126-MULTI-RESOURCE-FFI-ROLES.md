# Research Scenario 126 — Multi-Resource FFI Roles and Reservations

**Status:** finite schedule exploration with a native SQLite role probe

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Contract under study

An SQLite backup uses two connections with different roles. Source operations can coexist with a live backup, and the backup keeps the source alive. The destination is reserved for the backup from successful `backup_init` to `backup_finish`. The source and destination must refer to distinct connections. Scenario 125 establishes that the source dependency can exist with an empty statement list. [Backup API](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/sqlite.h.in#L9306) · [Backup implementation](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/backup.c) · [Dependency coverage](RESEARCH-SCENARIO-125-CLOSE-REENTRY-AND-COVERAGE.md)

The model gives the source a shared reservation and the destination an exclusive reservation. Sharing describes which backup roles can coexist. Other kinds of operations need their own declared compatibility. A successful initialization transfers both reservations to the backup handle until finish. An initialization that returns a known failure with no handle releases both. The model assumes all inputs are open and the operation knows the resource identity behind each argument. [Model](PROTOTYPES/RT-04-01/rt04_backup_roles.py)

## Identity and aliasing

The alias fixture gives each of three connections two names. A check using names alone admits six of the 36 argument pairs that resolve both roles to the same connection. For overlap, start with any of the 24 valid named pairs and consider each of the 36 candidates against it. Across these 864 cases, canonical identities admit 96 compatible overlaps. A name-only check admits those 96 and 288 additional cases. Of the additional cases, 72 use the same connection for both roles and 216 conflict with a live reservation on a distinct pair. For example, `A0 → B0` and `C0 → B1` contend for the same exclusive destination even though the destination names differ. [Alias checks](PROTOTYPES/RT-04-01/test_rt04_backup_roles.py)

## Reservation schedules

The scheduler takes two contenders over three known connections. Each chooses one of six ordered role pairs and has an independent initialization result. That gives 144 configurations per policy. It explores every transition order for the declared stages. A configuration counts toward the deadlock column if it has a reachable state where neither contender can proceed and at least one remains unfinished. Each policy has a completing schedule in every configuration.

| Reservation policy | Acquisition rule | Configurations with a reachable deadlock | Visited states across configurations |
|---|---|---:|---:|
| Role order | Shared source first, exclusive destination second | 24 / 144 | 2,502 |
| Identity order | Lower resource identity first, with each role's access mode | 0 / 144 | 2,370 |
| All or none | Grant both reservations together when both are compatible | 0 / 144 | 1,494 |

The role-order cycle is `A → B` holding shared `A` and waiting on exclusive `B`, while `B → A` holds shared `B` and waits on exclusive `A`. It occurs before either initialization can return, including configurations with a planned failure. Ordering by identity removes this cycle in the corpus and still allows partial reservations. The all-or-none policy has no partially held state. Its coordinator must observe and grant both roles as one transition. The model assumes an active backup can finish without acquiring a further resource. [Schedule checks](PROTOTYPES/RT-04-01/test_rt04_backup_roles.py)

## Native observations

SQLite 3.46.1 admits two live backups sharing the same source with distinct destinations. The harness runs all six role placements with both finish orders, for 12 traces. A query on the source still executes while the backups are active. After `close_v2`, the source's destruction callback runs on the second finish in either order. The harness keeps each destination reserved until its own finish. [Native probe](PROTOTYPES/RT-04-01/sqlite_backup_roles_probe.py)

An initialization with identical source and destination returns `NULL` and `SQLITE_ERROR`. Active read and write transactions on the destination produce the same rejection. After rollback of either transaction, the same connections admit a new backup. The source closes normally after the retry finishes, confirming that the failed initialization left no backup dependency in these cases. The probe runs SQLite operations on the destinations only outside their reserved interval. [Native initialization checks](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/backup.c#L125)

## Implications for candidate comparison

An FFI contract needs resource identities, role access modes, the point where obligations transfer to the returned value, and the disposition on initialization error. Borrow compatibility and the order of acquiring live authority are separate properties. A partially acquired pair needs an acquisition discipline, while an all-or-none coordinator needs a common authority that can grant both. Unknown foreign disposition requires a reconciliation path before a caller can release its reservations. [Close result forwarding](RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md)

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_backup_roles.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_backup_roles_probe.py
```

The probe used Python 3.12.14 and SQLite source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1` with in-memory connections. Native traces cover overlapping handle lifetimes, with calls issued in a controlled sequence. The schedule model covers two contenders, fixed identities, and known init outcomes. Source-derived alias proofs, fairness, cancellation, reentry during acquisition, indeterminate outcomes, and parallel native implementations remain open.
