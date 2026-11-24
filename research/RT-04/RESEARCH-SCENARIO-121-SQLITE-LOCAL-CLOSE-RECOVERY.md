# Research Scenario 121 — Local Close Recovery and Resource Dependencies

**Status:** bounded policy comparison with SQLite execution traces

**Research areas:** RT-03 execution · RT-04 ownership and typestate · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

Can a caller finish closing a connection after `SQLITE_BUSY`? The answer depends on who can finalize the outstanding statements. This experiment uses the same connection and statement graph to compare a close precondition, explicit recovery from busy, and deferred destruction. It follows the C API behavior measured in Scenario 120. [SQLite probe baseline](RESEARCH-SCENARIO-120-SQLITE-CLEANUP-DEPENDENCIES.md) · [SQLite close contract](https://www.sqlite.org/c3ref/close.html)

## Candidate rules

The input is a complete list of zero to three prepared statements. Each statement belongs to the caller or an outside owner. Each either has an earlier step error or can finalize successfully. The caller requests close and finalizes all statements it owns in the listed order. We compare making the first request before or after local finalization. Outsiders perform no steps during this part of the run.

| Candidate | At the close request | When outside statements remain at return |
|---|---|---|
| Require no live statements | Check the live set at the requested close. Reject the whole plan before execution if the set is nonempty. | The precondition cannot be established by local finalization alone. |
| Recover from `SQLITE_BUSY` | Use ordinary `close`. If a close before local finalization is busy, retry once after local finalization if all statements are gone. | Forward the still open connection and the outstanding dependency information. The outside owners keep their statements. |
| Defer destruction | Use `close_v2`. Consume the connection capability when the call succeeds. Preserve the dependencies until the last statement is finalized. | The caller has no connection capability to forward. The resource remains pending destruction while outside statements exist. |

Finalize consumes the statement even when returning its earlier execution error. Every policy that executes retains those error observations in order. The busy result remains visible in the trace even if a later retry succeeds. The model compares operation results and destruction observations. Policy for presenting or aggregating diagnostics remains open. [SQLite finalize contract](https://www.sqlite.org/c3ref/finalize.html)

## Results

The four possibilities at each statement slot give 85 input graphs: `1 + 4 + 16 + 64`. With two request orders and three policies the corpus has 510 plans. The table counts the 85 graphs separately for each order within each row.

| Candidate | Admitted, close first / finalize first | Busy observed | Connection state at return |
|---|---:|---|---|
| Require no live statements | 1 / 15 | None in the admitted plans | Destroyed in every admitted plan. The other 154 plans are rejected before any calls. |
| Recover from busy | 85 / 85 | 84 close first, 70 finalize first | In each order 15 destroyed, 70 open and forwarded. Close first recovers with a retry in 14 plans. |
| Defer destruction | 85 / 85 | None | In each order 15 destroyed, 70 pending. The connection capability is consumed in all 85. |

For all 356 admitted plans the harness replayed the predicted call sequence against SQLite 3.46.1. It checked each return code and whether the destruction callback had run at each call return. While the connection was still open, it also compared the live statement set with `sqlite3_next_stmt`. After the caller boundary, the fixture finalized outside statements and checked that a pending connection's callback ran with the last finalization. An open connection instead required a successful later close. The 154 plans rejected by the precondition were excluded from the native run. The probe uses the model's sequence of calls and checks their observed effects against SQLite. [Model](PROTOTYPES/RT-04-01/rt04_sqlite_recovery.py) · [Model tests](PROTOTYPES/RT-04-01/test_rt04_sqlite_recovery.py) · [SQLite harness](PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py) · [SQLite statement enumeration](https://www.sqlite.org/c3ref/next_stmt.html)

One trace has a failed step in the last statement. `close_v2` returns success with no destruction callback yet. `finalize` returns the step error and the callback has run by the time `finalize` returns. This separates a consumed capability, a reported error, and the completion of destruction.

## Consequences for design selection

The precondition trades runtime branching for a proof that all relevant dependents have been accounted for. A type that tracks only resources owned by the caller cannot supply this proof for an open foreign connection. Busy recovery keeps the capability available but must return it with the remaining obligation when the local caller cannot make progress. Deferred close can return promptly without transferring a reusable connection, with physical completion dependent on outside owners. Those are distinct guarantees for a caller that needs destruction before continuing.

An existing wrapper combines static dependency information with an explicit failure result. In rusqlite 0.43.0, `prepare(&self, …)` returns a `Statement<'_>` tied to the connection lifetime. `Connection::close(self)` returns the connection and error on failure, while `Statement::finalize(self)` consumes the statement and returns a normal result. These signatures offer a comparison point for retaining the `Err` payload from Scenario 119. This study reads the wrapper's API documentation and executes the C API. [rusqlite prepare](https://docs.rs/rusqlite/0.43.0/rusqlite/struct.Connection.html#method.prepare) · [rusqlite close](https://docs.rs/rusqlite/0.43.0/rusqlite/struct.Connection.html#method.close) · [rusqlite finalize](https://docs.rs/rusqlite/0.43.0/rusqlite/struct.Statement.html#method.finalize)

## Reproduction and scope

The model and probe ran with Python 3.12.14 at base `42a43c5` plus this experiment. The native run loaded SQLite 3.46.1 with source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1` and used in-memory databases.

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_sqlite_recovery.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py --recovery-matrix
```

The graphs are complete by construction. The fragment has no ongoing statement creation, concurrent use, unidentified foreign dependents, unknown close dispositions, or closure over other SQLite dependent types. The order of finalization follows the input list. The probe uses the callback as its observation of destruction. It does not measure reclamation of every allocation or exercise statement operations other than finalization after `close_v2`. A subsequent language experiment needs source and FFI rules for establishing completeness and preserving it across calls.
