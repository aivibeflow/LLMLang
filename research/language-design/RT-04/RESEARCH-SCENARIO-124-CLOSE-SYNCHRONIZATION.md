# Research Scenario 124 — Synchronizing Close with Foreign Producers

**Status:** bounded interleaving comparison with a two-thread SQLite probe

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

When can an observation of zero dependents authorize an ordinary close while another thread can create a prepared statement? Scenario 123 assumes sequential access through close. This experiment varies the scope of the lock and whether another producer uses it. [Shared close workload](RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md)

## Policies and schedule space

One thread observes a fresh connection's statement set and requests ordinary `close` if its evidence allows. A second thread attempts one `prepare` and retains its statement through the boundary. The probe uses an in-memory connection opened with `SQLITE_OPEN_FULLMUTEX` and checks that SQLite supplies a connection mutex. The wrapper uses its own lock for compound operations and stores retirement of the connection under that lock. [SQLite threading modes](https://www.sqlite.org/threadsafe.html) · [Open flags](https://www.sqlite.org/c3ref/open.html) · [Connection mutex](https://www.sqlite.org/c3ref/db_mutex.html)

| Policy | Where the producer can run |
|---|---|
| Separate observation and close | Before observation, between observation and close, or after close. Each wrapper operation takes and releases the lock. |
| Separate version validation and close | Both gaps around validation, as well as before observation and after close. Preparing a statement advances the wrapper version. |
| Shared guard across observation and close | Before the closer acquires the lock or after it releases it. The worker checks retirement before calling SQLite. |
| Guard on the closer, another lock on an alias | Before observation or between observation and close. The experiment schedules the alias only while the connection is live. |

The four policies give 11 schedules for the sole producer in this fixture. The native harness orders the threads with rendezvous and checks statement count, version match where used, the close return code, and whether the producer actually called `prepare`. It checks destruction with a registered callback. In the shared-guard contention case the producer confirms that it cannot acquire the lock while the closer holds it, then waits and observes retirement. [Model](../../PROTOTYPES/RT-04-01/rt04_close_interleavings.py) · [Native harness](../../PROTOTYPES/RT-04-01/sqlite_close_interleavings_probe.py)

## Results

| Policy | Nonempty at observation | Version mismatch | `SQLITE_BUSY` | `SQLITE_OK` |
|---|---:|---:|---:|---:|
| Separate observation and close | 1 | 0 | 1 | 1 |
| Separate version validation and close | 1 | 1 | 1 | 1 |
| Shared guard across observation and close | 1 | 0 | 0 | 1 |
| Guard on the closer, another lock on an alias | 1 | 0 | 1 | 0 |

All 11 schedules on SQLite 3.46.1 match the model. When `prepare` runs before version validation, the version mismatch prevents the call to `close`. When it runs after validation, that check has already returned a match and `close` returns `SQLITE_BUSY`. A producer that uses a different wrapper lock can also prepare while the closer holds its own lock. The busy path leaves the connection and the statement available for cleanup. [Schedule checks](../../PROTOTYPES/RT-04-01/test_rt04_close_interleavings.py) · [SQLite close](https://www.sqlite.org/c3ref/close.html)

With the shared guard, an early producer makes the set visibly nonempty. The contending producer sees a retired connection after successful close and returns without issuing a native call. These two orders account for every schedule in the shared-guard row. Internal SQLite serialization orders individual API calls. The extension across observation, the close decision, and retirement comes from the shared wrapper guard.

## Implications for LLMLang

A dynamic authorization to close needs a scope tied to the underlying resource identity. A generation comparison can detect a change before validation. Keeping the observation usable through close also requires excluding mutations between validation and use. An exclusive capability or a common guard can supply this if every dependency producer participates and retirement is visible before later uses. With a controlled lifetime and incomplete guard coverage, ordinary close remains fallible and can return the retained capability. Foreign aliases also need a lifetime contract that prevents calls after retirement. [Evidence freshness](RESEARCH-SCENARIO-122-CLOSE-EVIDENCE-FRESHNESS.md) · [Result forwarding](RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md)

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_close_interleavings.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_close_interleavings_probe.py
```

The native run used Python 3.12.14 on Linux x86-64 and SQLite source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`. The fixture covers one connection, two threads, and one statement producer with a persistent dependent. Reentrant producers, further dependent kinds, multi-resource lock ordering, and enforcement across general FFI aliases remain open.
