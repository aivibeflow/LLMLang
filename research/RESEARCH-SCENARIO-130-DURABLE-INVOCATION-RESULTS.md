# Research Scenario 130 — Durable Invocation Results After Interruption

**Status:** finite crash-boundary model with a file-backed SQLite process probe

**Research areas:** RT-04 ownership · RT-06 dependencies · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

Can an invocation-specific completion be recovered after the worker exits before delivering it? Scenario 129 binds consumption evidence to the exact invocation. This scenario compares publication boundaries and tests identity allocation across fresh processes. [Invocation-specific cancellation evidence](RESEARCH-SCENARIO-129-CANCELLATION-AND-INVOCATION-EVIDENCE.md)

## Fixture

An invocation reserves a shared source and an exclusive destination. The probe stores its role pair, generation, and journal phase in SQLite. A separate row represents the backend effect's liveness. One child process reserves the pair and returns the generation after commit. Another clears the simulated effect and records completion. The two arrangements put these changes in one transaction or commit the effect first. The interruption uses an immediate process exit at a selected boundary. A fresh connection reads the terminal result, and another process tries to reserve the pair. [Probe](PROTOTYPES/RT-04-01/sqlite_durable_receipts_probe.py) · [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html)

## Recovery results

| Interruption point | Effect and result share a transaction | Effect commits before result |
|---|---|---|
| Before the effect update | Live, pending | Live, pending |
| After the effect update | Live, pending | Released, pending |
| After writing the result, before committing it | Live, pending | Released, pending |
| After the result commit, before reply | Released, consumed | Released, consumed |
| After normal reply | Released, consumed | Released, consumed |

All ten traces match the model. Before commit, the shared transaction rolls both changes back. After commit, the journal recovers completion even when the response is lost. The two-commit arrangement yields two cases in which the effect is gone but the terminal lookup is empty. The same empty lookup occurs in four cases where the effect is still live. Treating the lookup as proof of release would admit reuse in those four cases. Keeping the role footprint holds the two physically released cases until stronger evidence arrives. [Model](PROTOTYPES/RT-04-01/rt04_durable_receipts.py) · [Model and process tests](PROTOTYPES/RT-04-01/test_rt04_durable_receipts.py)

In all four terminal cases, a new process can reserve the same roles and gets a later committed generation. The old terminal result leaves this successor pending. The lookup also checks role identities. With a resettable counter, the pure model produces an equal invocation key for the successor and accepts the old consumption evidence. The probe uses `AUTOINCREMENT` within one continuing database and returns the generation after commit. [SQLite allocation semantics](https://www.sqlite.org/autoinc.html)

## Implications for candidate comparison

A successful reply can reflect a committed terminal record, and a lost reply can be recovered by querying that record with the exact invocation key. This needs stable identity, retention of results through the retry window, and evidence tied to the backend effect. When the effect and publication share a commit boundary, the journal demonstrates both changes. With separate commit boundaries, a pending record leaves two possible outcomes. An external provider needs an authoritative lookup or a reconciliation protocol for that window, with retry safety stated by the API. [Reservation outcomes](RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md)

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_durable_receipts.py' -v
python -B research/PROTOTYPES/RT-04-01/sqlite_durable_receipts_probe.py
```

The probe ran with Python 3.12.14 and its `sqlite3` module linked to SQLite 3.53.1. The backend effect is a modeled row change. The experiment covers abrupt process exits on one local database and an already known invocation key. Crash recovery across independent services, reconciliation under concurrent delivery, loss of the allocated key before the initial reply, restored older snapshots, and terminal-record expiry remain open.


## Reproduction identity baseline — 2026-11-21

The native reproduction run [#44774296240](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240) recorded the separately loaded Python SQLite runtime as version `3.53.1`, source ID:

```text
2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9
```

The original Scenario 130 execution record did not preserve this source ID. Therefore the value above is adopted as an explicit **future reproduction baseline**, not as proof that the original historical run used the same SQLite build. The native runner now requires both version and exact source-ID equality before it executes the durable-receipt probe. A version-only match is no longer reported as reproduction-baseline equivalence.

Before extraction, the workflow also verifies the downloaded SQLite 3.53.1 and Python 3.12.14 source archives against pinned SHA-256 values. The SQLite digest is recorded in Buildroot's package hash update; the Python digest is published on the official Python 3.12.14 release page.
