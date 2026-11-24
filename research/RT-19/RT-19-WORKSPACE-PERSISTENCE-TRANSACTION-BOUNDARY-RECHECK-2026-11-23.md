# RT-19 — Workspace persistence transaction boundary recheck

**Research item:** `PLAN.md` §7.6 — Toolchain Server and semantic development API  
**Date:** 2026-11-23  
**Current-main baseline:** `8c114817028f98d74c65bfeb723d5d386d1b17d0`  
**Status:** Bounded contract comparison and implementation probe; no production backend selected  
**Question:** Given the Git-authoritative, reconstructible-store boundary proposed by ADR-014/015, what next persistence experiment can safely connect immutable objects to atomic workspace Change Set acceptance?

## Current implementation contracts

Two current-main prototypes exercise adjacent but different boundaries:

| Contract | Toolchain Server 01 (in-memory) | Package Index SQLite Content Store |
|---|---|---|
| State represented | Immutable generic `Entity` objects, semantic snapshot membership, mutable workspace heads/revisions/state | Opaque object bytes, content hashes, typed dependency rows and a generation counter |
| Atomic unit | Whole in-memory Change Set: validate preconditions, build next mapping/root, then advance the workspace revision | One immutable object plus its complete outgoing dependency set, inside one SQLite transaction |
| Concurrency evidence | Workspace lock and expected revision/hash; separate workspaces remain isolated | Pinned read transaction; old readers keep their generation while a writer commits |
| Acceptance/export | `accept()` adds the root to an in-memory accepted set; export writes one canonical file via temp file, `fsync`, and atomic replace | No workspace, Change Set, acceptance, export, or Git commit operation |
| Recovery | Process state is lost; JSON snapshot import/export is not a durable workspace journal | SQLite WAL and reopenable immutable objects, but no Toolchain state machine or crash-injection coverage |
| Semantic completeness | Generic entity envelope; no production SPG/source/dependency extractor | Dependency rows supplied by caller; payloads remain opaque |

The current CI-required focused suites pass **9/9** for each prototype on CPython 3.12.14 in this recheck. Toolchain tests cover atomic rejection of a ChangeSet with a stale later precondition, revision conflicts, isolated workspaces, export external-edit detection, and snapshot round trip. SQLite tests cover object-plus-edge atomic insertion, idempotency/conflict, pinned read visibility, dependency completeness, stream closure, and Provider use. The test suites do **not** share an adapter and do not cover one durable transaction containing object writes, workspace head movement, accepted-state transition, and export intent.

One local schema probe inserted an immutable object, then attempted to write a `workspace_heads` row in SQLite. SQLite returned `OperationalError: no such table: workspace_heads`; the object remained present and no workspace table existed. This confirms the boundary is absent, not a failing supported API. It does not test rollback of a multi-operation transaction because the workspace schema and coordinator have not been implemented.

## Constraint from repository decisions

ADR-014 and Proposed ADR-015 state that Git-visible repository input remains sufficient to reconstruct accepted program meaning; local stores, indexes, and caches are derived/reconstructible. Therefore an external database as the only authority is not a candidate for this comparison. The unresolved choice is the **transaction coordinator and journal** used by a local Toolchain while preserving Git as the reconstruction authority.

## Candidate transaction boundaries

### A — One embedded database transaction coordinator

Keep logical contracts separate but store object rows, workspace heads, immutable ChangeSets, acceptance records, and pending-export metadata in one embedded database. A coordinator performs object insertion, expected-head compare-and-swap, new snapshot publication, accepted-state transition, and outbox/event creation in one SQL transaction. Git export/commit remains a later external step with an explicit pending/synchronized state.

**Strengths:** one local atomic commit for database-owned state; standard transaction rollback; simple crash points inside one engine; supports a modular-monolith MVP.

**Risks:** a database transaction cannot atomically include a filesystem rename and Git ref update. Those remain recoverable multi-step transitions. The schema, migration policy, backup/rebuild, and WAL durability settings become operational contracts. It must not promote the database to sole authority.

### B — Separate immutable object store plus workspace journal/outbox

Retain the append-only object store contract and persist workspace revisions, ChangeSets, acceptance, and pending export in a separate journal. A coordinator writes immutable objects first, then atomically CAS-updates the journal head and acceptance/outbox record. Unreferenced objects from a failed attempt are harmless and can be garbage-collected. A recovery worker reconciles outbox events with a Git-visible export/commit receipt.

**Strengths:** clear immutable-object and mutable-workspace responsibilities; object store can be rebuilt from Git; workspace state machine is explicit; can later replace the object backend without changing lifecycle semantics.

**Risks:** cross-store write ordering and idempotency are mandatory. Failure after object writes but before journal CAS creates garbage; failure after journal acceptance but before Git export leaves pending work; retry and stale-writer handling must be specified. A single embedded database may still be the physical engine, so this is logical separation, not necessarily distributed storage.

### C — Git commit as the acceptance transaction

Stage canonical repository files and the required metadata, validate the exact tree, then create a Git commit; derive or rebuild object/workspace indexes from the committed tree. This keeps accepted durable state directly Git-visible.

**Strengths:** accepted state and recoverability align; a commit provides an exact tree identity and Git's normal history/transport.

**Risks:** semantic acceptance and repository publication become tightly coupled; long-running validation and external edit conflicts need staging/revalidation; concurrent workspace branches and non-commit accepted drafts still need journal state; crash recovery around worktree/index/ref update requires Git-specific tests. Git commit is not an atomic transaction with database rows.

## Comparison result

**B is the best next experiment, with one embedded database allowed as the initial physical implementation.** It preserves the contracts already exercised by both prototypes while exposing the unresolved coordinator semantics: immutable object insertion, workspace-head CAS, accepted snapshot record, pending export/outbox, and idempotent recovery. This is a narrower and more discriminating test than implementing a monolithic `ToolchainStorage` interface (which would hide distinct atomic units) or treating Git commit as the only workspace state machine.

The first vertical slice should inject failures at:

1. before/after immutable object insertion;
2. before/after workspace-head CAS;
3. before/after acceptance plus outbox record;
4. during export staging and after atomic file publication;
5. after Git ref update but before recording the synchronized receipt.

For every restart, assert one of three explicit outcomes: no acceptance and base head intact; accepted state with a recoverable pending export; or synchronized state whose Git tree equals the accepted root. Also test idempotent retry and a competing writer with a stale expected head. The result should not report a successful accept if the only durable copy of accepted meaning is absent from reconstructible Git-visible inputs.

## Reproduction and scope

Run the in-memory lifecycle tests:

```sh
python3 -B -m unittest discover \
  -s research/PROTOTYPES/TOOLCHAIN-SERVER-01 \
  -p 'test_toolchain.py' -v
```

Result: 9/9 passed on CPython 3.12.14.

Run the SQLite Content Store tests from the package-index directory, because sibling package identity modules are imported explicitly:

```sh
cd research/PROTOTYPES/PACKAGE-INDEX-01
PYTHONPATH=../PACKAGE-IDENTITY-01:. python3 -B -m unittest discover \
  -s . -p 'test_content_store.py' -v
```

Result: 9/9 passed on CPython 3.12.14.

This recheck executed no new persistent workspace implementation. The absent-table probe establishes an API/schema gap only. No latency, crash-recovery rate, or production durability claim is made.

## Remaining dependencies

- Implement a persistent workspace journal and a coordinator/outbox with explicit transaction boundaries and versioned schema.
- Inject process termination/crash at all listed boundaries; reopen from disk and verify recovery, CAS, and idempotent retry.
- Prove accepted semantic state is reconstructible from Git-visible canonical inputs and declared pinned dependencies.
- Define atomic multi-file export and Git commit/ref-update reconciliation.
- Bind source parsing, SPG identity, dependency extraction, and authorization to the lifecycle; the current tests use generic entities and opaque objects.
- Compare persistent embedded storage and Git-authoritative workflows under realistic project size and concurrent client load.
- Test MCP schemas with an independent client and preserve actor authorization across reconnect/restart.

**Conclusion:** keep immutable object reads and workspace/acceptance transactions as distinct logical contracts. The lowest-dependency implementation experiment is a single-process coordinator with durable journal/outbox and one embedded database, preserving Git as the reconstructible authority. This is a research recommendation for the next failure-injection slice, not a selected production backend or accepted ADR.
