# Research Scenario 128 — Foreign Errors and the Fate of Reservations

**Status:** finite contract comparison with a native SQLite error probe

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

After an admitted call reserves a shared source and an exclusive destination, what must the caller retain if the foreign operation returns an error? This experiment adds outcome dispositions to the role and source checks in Scenarios 126–127. [Multi-resource roles](RESEARCH-SCENARIO-126-MULTI-RESOURCE-FFI-ROLES.md) · [Source role correlation](../RT-04/RESEARCH-SCENARIO-127-SOURCE-ROLE-CORRELATION.md)

## Outcome contract

Each retained or unresolved result carries the two role identities as one obligation. Initialization can return an owned backup, an error with known absence of a backup, or an indeterminate outcome. A finish on a known backup can succeed, report an error that consumes the backup, report an error that retains it, or leave disposition indeterminate. The latter two finish dispositions supply additional foreign contract alternatives for comparison. The SQLite probe below checks its consuming branch. [Outcome model](../PROTOTYPES/RT-04-01/rt04_backup_outcomes.py) · [Disposition model](../PROTOTYPES/RT-04-01/rt04_return_disposition.py)

An indeterminate outcome has two possible states in the fixture. The backup can be absent or it can hold its original shared and exclusive roles. Both connection identities remain valid, and the API contract bounds the possible foreign effect to that pair of reservations. The caller receives a reconciliation obligation, with insufficient evidence to offer a usable handle. A checked subsequent call can proceed if its roles are compatible with both states. A caller requiring the same exclusive role must resolve the uncertainty first. [Finite forwarding checks](../PROTOTYPES/RT-04-01/test_rt04_backup_outcomes.py)

## Admission comparison

The corpus varies the first pair over 12 distinct pairs of four identities. The proposed pair varies over all 16 pairs, including repeated identities. Seven observed outcomes give nine concrete states after expanding the two uncertain outcomes. This yields 1,728 inputs per policy. The oracle tests the proposed roles against the actual live reservation, while each policy sees only the observed outcome. A compatible refusal counts inputs where the oracle could admit the proposal.

| Policy | Admits | Admits a conflicting proposal | Declines a compatible proposal | Claims a handle without evidence | Drops an obligation |
|---|---:|---:|---:|---:|---:|
| Release on every error | 1,200 | 288 | 0 | 0 | 960 |
| Retain a usable handle on every error | 528 | 0 | 384 | 1,152 | 0 |
| Declared disposition, block both identities while uncertain | 624 | 0 | 288 | 0 | 0 |
| Declared disposition, use the bounded role footprint while uncertain | 720 | 0 | 192 | 0 | 0 |

The last policy recovers 96 compatible proposals compared with blocking both identities. For example, while `a → b` is uncertain, a new `a → c` is compatible whether the first backup exists or has been consumed. A new `b → a` requires reconciliation. The reconciliation obligation remains at both branches. These counts are finite contract checks. [Generated cases](../PROTOTYPES/RT-04-01/test_rt04_backup_outcomes.py)

The existing match checker accepts exact forwarding with tagged payloads. It flags an error carrier with only diagnostics on `InitUncertain`, `FinishErrorRetained`, and `FinishUncertain`. An attempted `finish_first()` in the source fragment only makes a conflicting second call legal when the receipt establishes consumption. This connects source control flow to the foreign contract. [Matcher](../PROTOTYPES/RT-04-01/rt04_owned_call_match.py) · [Source fragment](../RT-04/RESEARCH-SCENARIO-127-SOURCE-ROLE-CORRELATION.md)

## Native SQLite evidence

The probe makes disposable databases in a temporary directory. A writable destination gives `SQLITE_DONE` at `backup_step` and `SQLITE_OK` at `backup_finish`. Reopening a different initialized destination read-only gives `SQLITE_READONLY` at both calls. The source is retired with `close_v2` while the backup exists. In both cases its destruction callback runs during `backup_finish`, and a query on the destination succeeds after finish. The error describes the earlier copy failure, while finish consumes the backup and frees its reservations. [Native probe](../PROTOTYPES/RT-04-01/sqlite_backup_outcomes_probe.py) · [SQLite implementation](https://github.com/sqlite/sqlite/blob/version-3.46.1/src/backup.c) · [Backup result contract](https://www.sqlite.org/c3ref/backup_finish.html)

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_backup_outcomes.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_backup_outcomes_probe.py
```

The runs used Python 3.12.14 and SQLite 3.46.1 with source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`. The finite model assumes declared resource identities and a single admission check with stable authority. It covers synthetic uncertainty bounded by known roles and the consuming native finish case. Reconciliation protocols, alias escape, cancellation races, and contracts with broader unknown effects remain open.
