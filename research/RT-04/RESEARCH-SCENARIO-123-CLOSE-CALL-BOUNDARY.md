# Research Scenario 123 — Close Policies at a Shared Call Boundary

**Status:** bounded comparison with native SQLite observations

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

What must a caller preserve when it forwards the result of cleanup? Compare static admission, a checked snapshot, ordinary close with recoverable busy, and deferred destruction on the same source fragment and dependency configurations. Prior scenarios compare each component in isolation. [Result matching](RESEARCH-SCENARIO-119-OWNED-RESULT-MATCHING.md) · [Close recovery](RESEARCH-SCENARIO-121-SQLITE-LOCAL-CLOSE-RECOVERY.md) · [Evidence freshness](RESEARCH-SCENARIO-122-CLOSE-EVIDENCE-FRESHNESS.md)

## Shared workload

```python
db = connect()
inspect(db)
if registered_owner:
    registered = prepare(db)
if opaque_call:
    foreign(db)
if run_local:
    local = prepare(db)
    finalize(local)
if refresh:
    inspect(db)
close(db)
```

The source adapter tracks `registered` as a known live dependency. The fixture assigns its capability to a separate owner. A restricted foreign call preserves the connection and may leave one more statement with a separate owner. The local query is absent, finalizes successfully, or finalizes with an error from its prior step. When the local query runs, it finalizes before the close decision. The initial observation is empty. `refresh` replaces it at the boundary. The guarded case assumes sequential access from inspection through close. [Source and model](../PROTOTYPES/RT-04-01/rt04_close_call_boundary.py)

The four source flags give 16 paths. Varying the local and foreign outcomes gives 36 inputs for each policy. The static row counts paths whose Boolean facts are available to the caller before any effects. The unspecialized function would need proof on every feasible path to use an unconditional close.

## Results

| Rule | Declined before execution | Returned open | Returned logically closed, destruction pending | Destroyed at return |
|---|---:|---:|---:|---:|
| Require complete source proof | 30 | 0 | 0 | 6 |
| Require a current empty snapshot | 0 | 29 | 0 | 7 |
| Use ordinary close and return busy | 0 | 24 | 0 | 12 |
| Use deferred close | 0 | 0 | 24 | 12 |

Source proof declines 18 inputs with a known outside dependent and 12 with incomplete coverage. The snapshot guard refuses 17 stale observations and 12 current observations of a nonempty set. Five stale observations occur with an empty live set. A fresh observation admits a path with opaque effects when the actual dependent set is empty. All 29 guard refusals happen after the local cleanup would have run and retain the connection. Starting the whole call again would repeat any prefix effects that already ran. [Policy checks](../PROTOTYPES/RT-04-01/test_rt04_close_call_boundary.py)

The native harness ran the wrapper operations for all 114 admitted policy/input pairs on SQLite 3.46.1. It agreed with the model on the ordered finalization and close return codes, remaining statements, and connection state at return. The harness issues its own SQLite calls from the fixture. An open connection stays usable and requires a later close. A pending connection is released on the last outside finalization, as observed by a registered destructor callback. [Native harness](../PROTOTYPES/RT-04-01/sqlite_close_call_probe.py) · [SQLite close](https://www.sqlite.org/c3ref/close.html) · [SQLite finalize](https://www.sqlite.org/c3ref/finalize.html)

## Caller contract

The same local finalization error occurs on inputs that return open, pending, and destroyed connections. The local statement has been consumed in all three. On busy or guard refusal, forwarding needs a typed slot for the retained connection. The exact match checker detects both guard error shapes and the busy error shape when the caller's error carrier has room only for diagnostics. It also flags a missing pending arm when the callee exposes pending and destroyed as distinct outcomes. A pending outcome carries the state of destruction, while the outside owners retain their statements. A caller that requires physical destruction needs a way to wait for its completion. [Forwarding checks](../PROTOTYPES/RT-04-01/test_rt04_close_call_boundary.py) · [Result matcher](../PROTOTYPES/RT-04-01/rt04_owned_call_match.py)

For candidate comparison, keep three contract properties visible: which calls are admitted before effects, which returns still carry authority over the connection, and which returns attest destruction. An interface change can alter one of these while preserving the diagnostic type.

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_close_call_boundary.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_close_call_probe.py
```

The run used Python 3.12.14 and SQLite source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1` on in-memory databases. The corpus has one connection, a bounded set of statements, and sequential execution. Ownership of outside statements comes from fixture contracts. General symbolic caller analysis, source-derived transfer, other SQLite dependent kinds, and synchronization with concurrent or reentrant FFI producers remain open.
