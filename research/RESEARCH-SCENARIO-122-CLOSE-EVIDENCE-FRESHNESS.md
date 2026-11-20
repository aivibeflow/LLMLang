# Research Scenario 122 — Completeness and Freshness of Close Evidence

**Status:** bounded source analysis and SQLite freshness probe

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

When can a compiler prove that a connection has no live dependents at `close`? Scenario 121 assumes the statement set is complete. This scenario compares proof from source, reuse of an earlier observation, and checking the current set at close. [Local close recovery](RESEARCH-SCENARIO-121-SQLITE-LOCAL-CLOSE-RECOVERY.md)

## Source fragment and assumptions

The adapter parses a small Python-shaped fixture with one fresh connection and one terminal `close`. It recognizes statement creation, explicit finalization, inspection, and `if` branches over immutable Boolean inputs. Each use of the same input follows the same branch value. `readonly` means the call preserves the dependency graph. This promise is distinct from data access being read-only. `foreign` preserves the connection and existing statements but may leave a new statement unknown to the wrapper. The concrete model enumerates zero or one new dependent per such call. An arbitrary foreign call that could invalidate a capability needs a separate contract. [Source adapter](PROTOTYPES/RT-04-01/rt04_close_evidence.py)

```python
db = connect()
inspect(db)
if outside:
    foreign(db)
close(db)
```

The source analysis starts with complete information about the new connection. It records known live statement bindings along each path. A foreign call loses completeness. The result is `KNOWN_LIVE` when a tracked statement remains, `PROVEN_EMPTY` when none remain and coverage is complete, and `UNKNOWN` when coverage is incomplete and no tracked statements remain. Unconditional close requires `PROVEN_EMPTY` on every feasible path. Inspection supplies separate runtime evidence and leaves the source fact unchanged.

The runtime comparison treats inspection as a complete enumeration of the fixture's statements. It records the observed emptiness and version for the same connection. Every prepare and finalize advances the version. A foreign call advances it conservatively even on executions with no new statement. The comparison and the ensuing close are one step with respect to changes in that set. This models a guarded boundary. It assumes complete coverage of possible mutations, including foreign ones.

## Results

The corpus varies four positions among no operation, preserving call, foreign call, prepare, prepare then finalize, and inspect. Two positions are the arms of a conditional. A common inspect follows the first position. This yields 1,296 programs, 2,592 Boolean paths, and 4,116 concrete executions after enumerating foreign outcomes. Close would report busy in 2,616 executions in the model. The table counts admissions per execution. A close by static proof is allowed for every path in 256 whole programs. [Generated cases](PROTOTYPES/RT-04-01/test_rt04_close_evidence.py)

| Rule | Admitted executions | Admissions that would encounter busy |
|---|---:|---:|
| Treat an empty local set as sufficient | 2,592 | 1,092 |
| Require complete source proof | 768 | 0 |
| Reuse the last empty observation without checking freshness | 2,820 | 1,320 |
| Require an empty observation at the current version | 660 | 0 |
| Inspect immediately at the guarded close boundary | 1,500 | 0 |

The preserving call keeps source proof and the snapshot valid. A foreign call after inspection can introduce a hidden statement and makes the snapshot stale even on executions where the connection stays empty. A prepare followed by finalize restores emptiness. It still changes the version, so an older snapshot cannot authorize close under this policy. A new guarded observation recovers permission on the empty executions that the static proof or older snapshot could not accept.

The final row is the reference for these execution states. It uses the model's actual live set at the close boundary. The experiment measures neither the cost of the guard nor an implementation of an atomic inspection-and-close operation.

## Native probe and implications

On SQLite 3.46.1, `sqlite3_next_stmt` reports an empty set on a new connection. Closing immediately returns `SQLITE_OK`. In a second run, preparing a single statement after the same observation makes ordinary close return `SQLITE_BUSY`. Finalizing the statement and enumerating again permits a successful close. This tests the effect of an intervening operation. The version and guarded boundary are modeled above. SQLite's serialized mode orders individual calls. A two-call observation and close sequence needs a separate rule to exclude intervening dependency changes. [SQLite harness](PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py) · [SQLite statement enumeration](https://www.sqlite.org/c3ref/next_stmt.html) · [SQLite close](https://www.sqlite.org/c3ref/close.html) · [SQLite serialized mode](https://www.sqlite.org/threadsafe.html)

For a candidate type system, known local ownership and proof of a complete live set carry different information. A snapshot used as a negative fact needs the resource identity, covered kinds of dependents, and evidence that the observation is still current when consumed. The same distinction matters for negative dependency facts used for cache reuse and impact analysis.

## Reproduction and scope

The eight focused tests and the probe ran with Python 3.12.14 at `11b781d` plus this scenario. The native probe used SQLite source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`.

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_close_evidence.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py --snapshot-freshness
```

The research grammar has one connection and a controlled set of statement-producing operations. It excludes loops, ownership transfer, callbacks, and concurrent effects. This experiment tracks statement liveness and leaves finalization diagnostics to Scenario 121. General source binding, other kinds of SQLite dependents, FFI contract validation, and synchronization of the observation with close remain open.
