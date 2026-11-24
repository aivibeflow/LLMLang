# RT-19 — Transaction and recovery protocol comparison

**Research item:** `PLAN.md` §7.6 — Toolchain Server and semantic development API  
**Date:** 2026-11-24  
**Baseline main:** `4b253db6f1a098d0f249ec6481a7f68a5b0b4dd6`  
**Evidence type:** comparative state-machine analysis plus rerun of the two adjacent prototype suites  
**Status:** bounded protocol comparison; no persistence backend, recovery protocol, or ADR selected  
**Question:** Given Git-visible reconstructibility and distinct immutable-object/workspace contracts, which acceptance/recovery boundary is the best next experiment?

## Findings from the existing prototypes

The in-memory Toolchain prototype atomically applies an entire Change Set in process memory after checking revision and object-hash preconditions. `accept()` records an accepted root only in memory. `export_snapshot()` then writes one canonical file by temporary file, `fsync`, and atomic replace, checking an optional previous-file hash. Its 9 focused tests cover stale revisions, all-or-nothing Change Sets, isolation, export edit detection, and one-file round trip. It does not persist accepted state or exercise restart recovery.

The SQLite Content Store commits one immutable object and its complete dependency rows in one transaction. A read snapshot pins a WAL generation; its 9 focused tests cover idempotent insertion, immutable conflicts, atomic object/edge registration, snapshot visibility, and stream lifetime. It has no workspace head, Change Set, acceptance, or export journal. Both suites passed on CPython 3.12.14 in this recheck (18/18 total). They are adjacent contracts, not interchangeable backend implementations.

The repository boundary in proposed ADR-014/015 requires accepted program meaning to be reconstructible from Git-visible canonical inputs and declared pins. A local database can coordinate acceptance and pending work, but cannot be the only durable authority. A Git commit can make a synchronized tree explicit, but it cannot atomically commit a SQLite transaction or provide a persistent pre-commit workspace by itself.

## Compared transaction boundaries

| Candidate | Atomic unit | Crash recovery shape | Strengths | Costs and unresolved risks |
|---|---|---|---|---|
| **A. Single embedded DB coordinator** | Object rows, workspace CAS/head, Change Set receipt, accepted root, and export outbox in one DB transaction | Reopen the database; accepted-but-unexported state is a durable pending outbox entry; idempotently publish to Git | One local atomic decision; simple rollback boundary; supports a modular monolith | DB schema/WAL durability and migration are contracts; filesystem and Git ref updates remain separate recoverable steps; avoid making DB sole authority |
| **B. Object store + workspace journal/outbox** | Immutable objects are inserted first; journal atomically CASes the workspace head and records acceptance/outbox | Orphan immutable objects are harmless; recover pending export from journal; reconcile Git receipt by idempotency key | Matches the existing logical contract split; clear durable state machine; can colocate both tables in one embedded DB initially | Requires cross-contract ordering, idempotency, garbage collection, and journal/outbox recovery; later split physical stores add distributed failure modes |
| **C. Git commit is acceptance** | Canonical candidate tree validation followed by exact Git commit/ref update | Reconstruct accepted state from commit/tree; rebuild local indexes | Strong Git-visible authority and simple clone recovery after commit | Couples semantic acceptance to publication; no durable accepted-but-uncommitted workspace by itself; worktree/index/ref failures and concurrent editors need Git-specific coordinator state |

**Comparison result:** B is the best *next experiment*, consistent with the previous transaction-boundary recheck. It is a logical decomposition, not a commitment to separate processes or files: begin with one embedded database, keep immutable object insertion and mutable workspace journal operations in separate modules/contracts, and put their coordinated acceptance/outbox update in one SQL transaction. Git remains the reconstructible authority. A is a viable physical deployment of B, not a mutually exclusive alternative. C can serve as the final synchronized-state receipt and recovery oracle, not the sole workspace lifecycle.

## Candidate state machine and invariants

The proposed coordinator slice has these durable workspace/export states:

```text
OPEN(base_snapshot, revision)
  -- CAS + validate + accept/outbox in one DB commit --> ACCEPTED_PENDING_EXPORT(root, operation_id)
  -- canonical export + exact tree validation + Git ref update --> SYNCHRONIZED(root, commit_id)
```

Rejection or a failed CAS leaves the head/revision unchanged. Export failures leave `ACCEPTED_PENDING_EXPORT`; retry uses the same operation ID and must not accept a second semantic revision. A retry after the Git ref update but before the synchronization receipt checks the current tree/commit against the accepted root and records the receipt idempotently. The coordinator must not return successful acceptance before its durable acceptance/outbox transaction commits. Discard and authorization are separate state transitions and are outside this narrow experiment.

| Failure point | Required restart observation | Required retry behavior |
|---|---|---|
| Before immutable object insertion | Base workspace head; no acceptance | Reapply the same request if its base revision still matches |
| After object insertion, before workspace CAS/acceptance | Base head; no acceptance; at most unreachable immutable objects | Same operation may safely reuse identical object hashes |
| During DB transaction before commit | Base head and no outbox after SQLite rollback | Retry with the same operation ID |
| After durable acceptance/outbox commit, before export | Accepted root with pending outbox | Export that exact root; do not revalidate as a new acceptance |
| During temporary export staging | Accepted root with pending outbox; canonical repository tree unchanged | Remove/reuse temporary data and retry |
| After atomic file replacement, before Git ref update | Pending outbox; repository files may be staged or visible but uncommitted | Recheck exact tree and continue; reject unexpected external edits |
| After Git ref update, before receipt update | Git tree contains the accepted root; outbox may still appear pending | Detect commit/tree by operation ID/root and record receipt without duplicate commit |
| Competing workspace accepted against stale revision | Exactly one CAS wins; loser remains unaccepted | Return stale-revision conflict; require rebase/replan rather than silent overwrite |

These are invariants for a future fault-injection test, not tests performed by this report. The present run did not kill processes, manipulate Git refs, or claim crash durability.

## Decision-relevant assessment

The evidence distinguishes the choices at the boundary level:

- **Monolithic broad storage interface:** rejected for the next slice. It obscures that immutable object/edge insertion and mutable workspace acceptance have different atomic units and concurrency policies.
- **One DB for all durable records:** still allowed as the first physical system if the modules retain distinct contracts. This makes the local coordination atomic without violating Git authority.
- **Git-only acceptance:** useful as a synchronization receipt and source of reconstructibility, but insufficient for draft/accepted workspaces that must survive restart before repository publication.

The best discriminator now is failure injection across the eight rows above, checking durable state after process restart, stale-writer CAS, same-operation idempotent retry, and exact Git-tree/root correspondence. A passing state-machine fixture still will not establish production SPG completeness, authorization, MCP behavior, realistic performance, or policy adoption.

## Reproduction

```sh
python3 -B -m unittest discover \
  -s research/toolchain-and-collaboration/PROTOTYPES/TOOLCHAIN-SERVER-01 \
  -p 'test_toolchain.py' -v

PYTHONPATH=research/packages-and-ecosystem/PROTOTYPES/PACKAGE-IDENTITY-01:research/packages-and-ecosystem/PROTOTYPES/PACKAGE-INDEX-01 \
python3 -B -m unittest discover \
  -s research/packages-and-ecosystem/PROTOTYPES/PACKAGE-INDEX-01 \
  -p 'test_content_store.py' -v
```

Result: 9/9 and 9/9 passed on CPython 3.12.14. The only new result here is the protocol/state-machine comparison; these unchanged tests are corroboration of the referenced component contracts, not validation of the candidate coordinator.

## Remaining dependencies

- Implement a persistent workspace journal/coordinator and versioned transaction schema.
- Inject process crashes at the listed boundaries and verify restart, CAS, idempotency, no false acceptance, and exact Git tree/root correspondence.
- Bind source parsing, canonical SPG identity, dependency extraction, and authorization to the lifecycle.
- Define atomic multi-file export and Git ref reconciliation against external edits and concurrent worktrees.
- Independently test MCP schemas and actor authorization across reconnect/restart.
- Compare embedded persistence and Git-authoritative recovery on representative repositories and concurrent client loads; retain storage/latency/recovery distributions.
- Maintainer approval of ADR-015 and the final backend/workflow remains an external decision.

**Conclusion:** use separate immutable-object and workspace-transaction contracts, coordinated in one local DB transaction for the next experiment, with an explicit durable outbox and Git commit receipt. This is the most discriminating bounded path supported by the existing prototypes; production selection remains open.
