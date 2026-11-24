# Research Scenario 120 — Cleanup Dependencies in SQLite

**Status:** executable probe of three versioned SQLite API paths

**Research areas:** RT-03 resource outcomes · RT-04 ownership and typestate · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

When a close operation returns, what can the caller infer from its result about the handle and the objects that depend on it? Scenario 119 compares consumed, retained, and indeterminate cleanup errors. SQLite gives concrete examples of the first two and a success path where destruction is deferred to the lifetime of dependent objects. [Ownership in matched call results](RESEARCH-SCENARIO-119-OWNED-RESULT-MATCHING.md)

## Contracts and observations

`sqlite3_close` leaves a connection open when dependent objects still exist. The probe keeps a statement prepared and sees `SQLITE_BUSY` (`5`). Preparing another statement on the same connection succeeds. After finalizing both statements, a second close returns `SQLITE_OK` (`0`). The recovery changes the resource graph by removing the dependencies first. [SQLite close and close_v2](https://www.sqlite.org/c3ref/close.html)

`sqlite3_finalize` destroys the statement and can report its last evaluation error. The probe steps a statement that computes `abs` of the smallest 64-bit integer and obtains `SQLITE_ERROR` (`1`). Finalizing it returns the same error. Closing the connection then succeeds, showing that the statement no longer blocks close. [SQLite finalize](https://www.sqlite.org/c3ref/finalize.html) · [SQLite abs](https://www.sqlite.org/lang_corefunc.html#abs)

`sqlite3_close_v2` can succeed while a dependent remains. In this case the documented contract invalidates the connection for callers and schedules destruction when its dependents finish. The probe registers an application function with a destructor callback. It observes zero destructor calls after `close_v2` returns success and one after finalizing the remaining statement. The callback is an observable marker for connection destruction in this fixture. The probe finalizes the statement and makes no further calls through the invalidated connection. [SQLite close and close_v2](https://www.sqlite.org/c3ref/close.html) · [SQLite function destructor contract](https://www.sqlite.org/c3ref/create_function.html)

| Operation and precondition | Result | Capability and remaining work |
|---|---|---|
| `sqlite3_close` with a prepared statement | `SQLITE_BUSY` | The connection stays usable. Finalize its dependents before closing it again. |
| `sqlite3_finalize` after an execution error | `SQLITE_ERROR` | The statement is consumed. Preserve the diagnostic. The statement no longer blocks closing the connection. |
| `sqlite3_close_v2` with a prepared statement | `SQLITE_OK` | The caller loses the connection capability. Destruction follows finalization of its last dependent in the probe. |

## Implication for candidate comparison

A result contract can describe three separate facts: the diagnostic, the availability of the capability, and where any remaining cleanup work lives. Scenario 119's plain diagnostic can accompany consumption with error. When `sqlite3_close` leaves a live connection, local recovery requires information about its outstanding statements or other dependents. If those are unavailable to the caller, immediate retry alone cannot satisfy the precondition. With `close_v2`, a type can mark the connection capability as consumed while the runtime preserves the dependency on each remaining object.

The next comparison can use the same API to test static prevention of close with live dependents, explicit recovery from `SQLITE_BUSY`, and deferring release to dependents. The second option needs a way to preserve cleanup errors from finalization even when a later close succeeds. The third needs an observation boundary that distinguishes logical close from physical release when that distinction matters to the caller.

## Reproduction and scope

Run the probe with Python and a system SQLite shared library. It opens only in-memory databases. The observed run used Python 3.12.14 and SQLite 3.46.1, source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`, at base `3f44045` with this probe. The probe checks return codes and callback counts. The experiment covers prepared statements in one thread. Backup objects, BLOB handles, transaction rollback, competing users, and allocator behavior remain outside this evidence. [Probe](../PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py)

```sh
python -B research/PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py
```
