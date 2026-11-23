# RT-19: Storage backend contract recheck

**Date:** 2026-11-23  
**Baseline:** `98dfae6debdc8d5f16deb7a144d27ed77111e3f4` (`main`)  
**Question:** can the in-memory Toolchain Server prototype and the SQLite Content Store be treated as interchangeable backends behind one storage contract?

## Finding

Not as they stand. Their abstraction boundaries differ:

| Concern | Toolchain Server 01 | Package Index SQLite Content Store |
|---|---|---|
| Stored data | Typed prototype `Entity` objects plus snapshot membership and workspace state | Opaque immutable payload bytes plus supplied dependency rows |
| Snapshot API | Creates roots and resolves Stable ID to object hash | Opens a pinned read transaction; gets objects/dependencies by exact hash and streams bytes |
| Mutation semantics | Atomic multi-change validation/application within one in-memory workspace; optimistic revisions; accept/discard | Append-only object insertion and dependency registration; no Change Set, workspace, accept, or multi-file publication API |
| Persistence / recovery | Process memory; export/import one accepted JSON snapshot | SQLite file with WAL transactions; recovery/reopen beyond its tests is not a Toolchain lifecycle contract |
| Dependency interpretation | No canonical SPG schema or dependency extraction | Edge rows supplied externally; store does not infer semantics |

The SQLite prototype's backend-neutral contract currently abstracts **read snapshots only**, not the full Toolchain workspace and acceptance lifecycle. Forcing both behind one broad `ToolchainStorage` interface would either hide these gaps or give the in-memory implementation persistence-shaped behavior it does not have. Keeping one monolithic protocol would also conflate two responsibilities: immutable content storage and transactional workspace coordination.

Candidate direction: define separate contracts for (1) immutable object storage and pinned snapshot reads, and (2) workspace revisions, atomic Change Set validation/publication, acceptance, and export state. Keep the in-memory engine as the lifecycle reference. Evaluate SQLite as a durable object/snapshot adapter only after an integration experiment demonstrates exact root reconstruction and atomic acceptance/export behavior. This is a decomposition recommendation, not a selected production backend.

## Validation

On CPython 3.12.14, the Toolchain Server lifecycle suite passed **9/9** tests. The three relevant suites (cache-version record, package logical index, and SQLite Content Store snapshot) passed **36/36** tests on the same main revision. Together they cover immutable object identities, pinned snapshot reads, concurrent-writer visibility boundaries, stale revision/object rejection, atomic rejection of a Change Set, isolated workspaces, export/import round-trip and tamper detection. They do not test a shared adapter or bridge acceptance to a persistent multi-object transaction.

SHA-256 at the baseline:
- `TOOLCHAIN-SERVER-01/toolchain.py`: `94c6277697f872be4fcfc967f1ca80597027f82853b2ad4e03232ff4a664d167`
- `TOOLCHAIN-SERVER-01/test_toolchain.py`: `7ee891533410acf66316f3c2c72565d8da8754b0c17c29a94ab7f162e45f7ae8`
- `PACKAGE-INDEX-01/content_store.py`: `8f6d7ed6cdae98c752f467accde214e163eb17b0566011be57c941469ff2657c`

## Remaining dependencies

- Persistent workspace/revision records and a durable Change Set transaction spanning object writes plus snapshot publication.
- Crash/failure injection across prepare, accept, export, and external repository commit; recovery and idempotency semantics.
- Canonical semantic import/export and source-derived dependency extraction, rather than opaque caller-provided payloads/edges.
- Multi-agent optimistic concurrency, conflicts, authorization, and independent MCP client tests.
- Comparative latency, storage and recovery measurements under realistic project sizes.

Until those exist, the current implementation choice is limited to a prototype boundary: use the in-memory engine for lifecycle behavior, and treat SQLite as a separate local immutable-store experiment.
