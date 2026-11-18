# RT-23 — Single-Instance Toolchain with Shared Semantic State and Incremental Multi-Worktree File Views

**Status:** Research proposal; not an accepted architecture decision  
**Date:** 2026-11-18  
**Depends on:** RT-19, RT-20, RT-22

## 1. Problem statement

LLMLang's concurrency model differs from that of conventional source-tree-centric languages. LLMLang semantic objects are immutable/content-addressed; parallel development can create new objects and new graph roots without checking out a different filesystem tree. The principal mutable semantic exception identified by this research is the mapping of LLMLang declarations/objects to external interfaces. That mapping needs explicit versioning and conflict control; it must not be treated as an ordinary immutable object.

Regular repository files still require isolated Git worktrees. Different jobs may concurrently edit tests, build scripts, documentation, configuration, generated non-semantic files, or other conventional files. We therefore need multiple worktrees without multiplying Toolchain Server processes and without re-reading/re-importing every worktree whenever a job changes context.

The target is **one long-lived Toolchain Server instance per registered repository/service scope**, serving multiple worktree file views and multiple semantic change branches. Worktree isolation applies to regular files and Git state; it must not be confused with semantic-object isolation.

## 2. Core design decision under investigation

Separate three dimensions that were previously conflated:

1. **Shared semantic object space:** immutable, content-addressed LLMLang objects and immutable semantic snapshots are shared across jobs. A job creates new objects and references them from its own proposed graph/root; it does not mutate existing objects.
2. **Versioned mutable interface mapping:** mappings from semantic declarations/objects to external interfaces are explicit versioned records, with their own baseline, ownership, concurrency checks, and merge/conflict rules. They are not silently shared mutable global state.
3. **Per-worktree regular-file view:** Git worktrees isolate ordinary files, index, HEAD, and uncommitted changes. Each worktree has a durable identity and incremental file-state journal managed by the single Toolchain Server.

A semantic change branch is not required to have a corresponding Git worktree. A worktree is created only when a job needs an isolated regular-file tree or branch-local Git state.

This document is the source of truth for the single-server/multi-worktree runtime model and incremental filesystem synchronization. RT-22 remains the source of truth for the external repository/worktree MCP contract; it should reference this document rather than duplicate its detailed internals.

## 3. Terminology and identity model

| Entity | Meaning | Mutability |
|---|---|---|
| Repository | Registered Git repository identity and object database | Mutable Git refs/indexes |
| Toolchain Server | One process/service instance managing a repository scope | Long-lived service state |
| Semantic Object | LLMLang declaration/definition addressed by content-derived hashId | Immutable |
| Semantic Snapshot | Immutable graph/root and its exact object references | Immutable |
| Semantic Change Set | Proposed graph transition from an explicit snapshot | Append/proposal lifecycle; accepted result creates a new snapshot |
| Interface Mapping Revision | Versioned mapping between semantic entities and external interfaces | Mutable by creating a new revision |
| Worktree | Git working tree with its own HEAD, index, regular files, and uncommitted changes | Mutable |
| File View | Toolchain's tracked knowledge of one worktree's relevant file state | Incrementally mutable |
| File Observation | Path, file kind, content identity/fingerprint, and observed generation | Immutable observation |
| Worktree Generation | Monotonic revision of observed file/Git state | Advances on detected changes |
| Sync Cursor | Durable position in watcher/event journal and last reconciled Git state | Advances monotonically |

Identifiers must be opaque externally. Internal identities should be repository-scoped and collision-safe. Do not use filesystem paths as authorization identities.

## 4. Logical architecture

```text
                    AIVibeFlow Jobs / MCP clients
                      |       |       |
                      +-------+-------+
                              |
                     ONE Toolchain Server
                              |
          +-------------------+--------------------+
          |                   |                    |
   Shared Semantic       Mapping Revision     Repository Manager
   Object Store          Store                (one repository)
          |                   |                    |
   immutable objects     versioned mappings   Git object DB / refs
   snapshots / roots     CAS + merge rules          |
          |                                      +--+---------+
          |                                      |            |
     semantic branches                       Worktree A   Worktree B ...
     / Change Sets                            File View A  File View B
                                                |            |
                                          incremental   incremental
                                          change feed   change feed
```

This is a logical architecture, not a requirement for separate databases. The initial implementation should be a modular monolith with one process and explicit internal interfaces. Storage may be in-memory for a prototype, but the identity and recovery model must not depend on process-local state.

The server may use multiple worker threads/tasks for independent I/O and analysis. "Single instance" does not mean one execution thread or a global mutex around all jobs.

## 5. Semantic concurrency without worktree switching

### 5.1 Immutable object space

- Existing semantic objects are never edited in place.
- A change creates new object identities only for changed/new objects and the caller/ancestor objects whose content-derived identities change under RT-20.
- Unchanged objects are referenced by hashId and reused.
- A Change Set is anchored to an explicit base Semantic Snapshot and records its proposed graph/root transition.
- Independent Change Sets can be developed concurrently from the same base. Acceptance creates a new immutable snapshot; it does not mutate the base.
- A server-wide content-addressed object store deduplicates identical objects across Change Sets and worktrees.
- Object existence is not equivalent to object reachability or acceptance. Unreferenced objects may be garbage-collected only after retention and active-operation safety checks.

The semantic development context for a job is therefore a tuple such as (repository identity, base snapshot ID, Change Set ID, mapping revision ID), not a checked-out directory.

### 5.2 Interface mappings are a separate concurrency domain

Interface mappings are the mutable exception and require explicit treatment:

- Every mapping revision has an immutable revision ID, parent revision, mapping scope, and content digest.
- A Change Set records the exact mapping revision it read.
- A mapping update uses compare-and-swap against the expected revision; stale writes are rejected.
- Independent mapping edits may be merged only when their affected mapping keys/scopes are disjoint or a deterministic domain-specific merge proves compatibility.
- Two edits to the same mapping key, or edits whose compatibility cannot be established, produce a mapping conflict requiring resolution.
- Mapping conflicts must not invalidate or mutate immutable semantic objects. They may block a deployment/build/acceptance policy that requires a resolved mapping.
- Mapping changes are auditable and included in build/verification provenance whenever they influence the result.

Do not model interface mappings as an unversioned mutable table shared by all jobs. Do not duplicate the entire semantic object graph merely because a mapping revision differs.

### 5.3 Caller migration remains semantic

When an object change requires caller migration, RT-20's complete impact plan and per-call-site decisions apply. A caller can retain an old callee while another caller migrates. New caller versions are new immutable objects. This work occurs in semantic Change Sets and does not require separate Git worktrees.

## 6. Worktree purpose and lifecycle

A worktree exists to isolate ordinary files and Git state, not to isolate the semantic object store.

- One repository registration may own N worktrees.
- Every worktree has its own HEAD/base commit, Git index, branch or detached state, file view, generation, watcher subscription, and capability scope.
- A job receives a worktree handle only if it needs regular-file operations.
- A job doing only semantic LLMLang changes does not need a worktree.
- Multiple jobs may share the Toolchain Server while receiving distinct worktree handles.
- Worktree create/remove operations are explicit and idempotent. Server restart must recover worktree registrations and reconcile their actual Git state.
- A worktree's semantic context is explicitly bound to a Semantic Snapshot and Mapping Revision when an operation needs that relationship. It is not implicitly derived from the currently checked-out branch.

A worktree can contain ordinary files that are not semantic LLMLang objects. The Toolchain must classify file roles rather than assume every file belongs in the SPG. Classification is versioned and explicit; unknown files remain regular files until a supported importer claims them.

## 7. Incremental File View: avoid full worktree rereads

### 7.1 Required behavior

Switching a job from Worktree A to Worktree B must be an O(1)-ish handle/context selection operation, not a recursive content read, parse, or semantic import of B. Re-entering a known worktree must reuse its persisted File View and synchronization cursor, subject to checking whether its change feed is still trustworthy.

The server must never perform a full content read of every file merely to select a worktree or answer a request scoped to a known unchanged path.

### 7.2 Per-worktree state

Persist, at minimum:

- repository and worktree identities;
- canonical worktree root and validated Git common-dir/worktree-dir identities;
- HEAD commit and branch/detached state last observed;
- Git index identity/state last observed;
- per-path file kind and last known content identity (Git blob OID where applicable, otherwise a content digest);
- relevant stat fingerprint (device/inode where available, size, mtime/ctime with platform caveats);
- dirty/untracked/deleted/renamed/conflicted classification;
- watcher generation and durable event cursor;
- last successful reconciliation generation and reason;
- pending import/export operations and their exact input/output generations.

The File View is derived state and must be reconstructible. It is not a new source of truth for file contents.

### 7.3 Change detection layers

Use a layered strategy; no single mechanism is sufficient on every filesystem:

1. **Filesystem notifications:** subscribe to native change notifications per worktree and append normalized path events to a durable journal. Coalesce duplicate events. Treat notifications as hints, not authoritative content.
2. **Git metadata:** use Git index, HEAD/tree OIDs, and bounded Git status/diff operations to identify tracked changes, staged changes, untracked files, renames, and conflicts. Git object IDs avoid reading content for unchanged committed files.
3. **Targeted stat/content verification:** for event paths or paths whose metadata fingerprint changed, inspect only those paths. Hash/read content only when needed to establish a new content identity, parse/import, or defend against unreliable timestamps.
4. **Reconciliation scan:** perform a bounded or full metadata reconciliation only when event continuity is lost, watcher overflow occurs, the worktree was offline, filesystem semantics are unreliable, or an operation explicitly requests a strong whole-tree guarantee. Even then, compare metadata/Git identities first and read content only for changed/unknown paths.

A filesystem watcher event does not prove a file changed; a missing event does not prove it did not. The implementation must expose confidence/freshness and the last reconciliation point.

### 7.4 Avoiding hidden O(N) work

- Worktree selection must not recursively enumerate files.
- Querying one known file must not hash the whole tree.
- Semantic API calls must not implicitly invoke full Git status or full import.
- Full-tree status is an explicit potentially expensive operation and reports scope, duration, and generation.
- Git status may itself perform O(N) metadata work depending on repository/index/filesystem state; benchmark and use FSMonitor/untracked cache where available, without treating them as correctness authorities.
- Large repositories may use sparse checkout or configured path scopes, but sparse visibility must be explicit and must not be mistaken for a complete repository view.

## 8. Consistency, generations, and concurrency

Each worktree has an independent monotonically increasing Worktree Generation. Every operation that reads or mutates regular files declares its expected generation or a weaker documented precondition.

- File events advance the observed generation after durable journaling.
- A multi-file operation captures a start generation and verifies relevant paths/generation before publishing results.
- If relevant paths changed during the operation, it returns stale-input/conflict and does not publish mixed-generation output.
- Different worktrees may progress concurrently.
- Operations against one worktree use path-level conflict detection where possible; serialize only conflicting Git index/ref mutations or operations whose atomicity requires it.
- Never use a single global repository lock for ordinary independent file reads/writes.
- Semantic object insertion is content-addressed and concurrent-safe; Change Set head updates use expected-revision CAS.
- Interface Mapping Revision updates use their own CAS/conflict rules.
- A Git branch/ref is repository-shared mutable state even though a worktree has its own index and files. Concurrent operations that update the same ref must be serialized or rejected using expected-old-OID checks.

The server must distinguish file freshness from semantic snapshot identity. A new file generation does not automatically imply a semantic snapshot change, and a new semantic snapshot does not automatically imply a worktree generation change.

## 9. Semantic/file boundary and explicit synchronization

The Toolchain must not assume all regular files are semantic inputs.

- Semantic object changes are made through typed semantic operations and stored in the shared object store.
- Regular-file changes are made in a selected worktree.
- A supported importer may map selected file types/paths into semantic state; import is explicit or policy-triggered and records the exact file generation and path set consumed.
- A semantic export, if required, targets an explicitly selected worktree and records the exact snapshot/mapping revision and output generation.
- A build/test operation declares both semantic inputs and regular-file inputs. Its provenance pins semantic snapshot ID, mapping revision ID, worktree generation, and per-file content identities for the files actually consumed.
- A result is stale if any declared input identity changes; unrelated changes in another worktree do not stale it.
- No automatic semantic merge is inferred from Git branch merge, and no Git merge is inferred from semantic snapshot acceptance.

This boundary allows semantic development to proceed without worktree churn while still giving regular-file tools familiar branch isolation.

## 10. Single-server process and storage model

## 10.1 Shared immutable object-store read boundary

The shared semantic object store must expose read leases independently of per-worktree File Views and independently of mutable Interface Mapping Revisions. A semantic Change Set or package build identifies the exact semantic root it consumes; it does not select a worktree-local object database.

The minimum object-store read surface is defined in RT-19 §6.3: open a pinned read view, resolve exact Content Hash metadata, enumerate the complete typed outgoing dependency set for an exact source object, and stream the exact payload. The returned handle has a bounded lifetime and a stable opaque store-view token. A backend must provide repeatable reads for that handle while concurrent object insertions continue.

The package-index SQLite prototype demonstrates one possible local implementation using append-only rows and a WAL read transaction. It is a derived-store experiment, not the selected Toolchain backend and not an implementation of the complete RT-23 shared semantic store. In particular:

- object payloads and dependency rows are immutable and content-addressed;
- dependency rows are supplied by the semantic/indexing layer, never guessed from opaque bytes;
- interface mappings remain separately versioned and use their own compare-and-swap rules;
- worktree selection does not open, clone, or switch the semantic store;
- a store snapshot token is not a Semantic Snapshot root and does not replace the exact semantic root recorded by a Change Set or build.

A production implementation still needs to define how semantic roots, object reachability, mapping revisions, retention/garbage collection, repository reconstruction, and active read leases interact. The local SQLite prototype does not establish those policies.



The Toolchain Server should be one service instance per repository registration (or one server managing multiple explicitly registered repositories), not one process per worktree/job.

Recommended initial topology:

- one server process and MCP endpoint;
- repository manager with one Git common-dir registration;
- shared durable semantic object store;
- shared immutable snapshot store;
- versioned mapping store;
- per-worktree metadata, watcher journal, and File View;
- worker pool for I/O, parsing, analysis, and verification;
- durable operation journal and per-scope authorization.

MCP client sessions are not server instances and must not own semantic truth. Disconnecting one job/client must not terminate the server or invalidate another job's worktree. Per-job authorization leases constrain which handles and operations a client can access.

A server restart should recover by loading compact persisted metadata and operation state, reattaching watchers, and reconciling only worktrees whose event continuity/freshness cannot be proven. It must not blindly re-import every worktree.

If the host filesystem cannot provide reliable notifications, use a documented fallback strategy (Git metadata plus periodic/explicit reconciliation). Correctness takes precedence over avoiding scans, but scans must be explicit, observable, and amortized.

## 11. Failure and recovery

Required cases include:

- watcher queue overflow or event-journal gap;
- server crash between event receipt and journal persistence;
- server restart while a worktree was modified offline;
- atomic-save patterns (write-temp-then-rename);
- rename/delete/create bursts and case-folding differences;
- symlink replacement and path escape attempts;
- external Git operations changing HEAD/index/refs;
- concurrent branch/ref mutation;
- interrupted import/export across multiple files;
- stale mapping revision;
- one client disconnecting while other jobs continue.

Recovery procedure:

1. Mark the affected File View freshness as unknown; do not claim it is current.
2. Re-establish repository/worktree identity and inspect HEAD/index identity.
3. Resume the event journal if continuity is provable.
4. Otherwise reconcile metadata/Git state for that worktree only; do not scan unrelated worktrees.
5. Read/hash only paths whose identity cannot be established from trusted Git object IDs or reliable metadata.
6. Publish a new File View generation atomically after reconciliation; retain the previous generation for in-flight readers until they finish or fail stale.
7. Resume/retry durable operations by operation ID and idempotency key.

Never silently serve stale file contents as current. Never invalidate every worktree's File View because one worktree lost its event cursor.

## 12. Security and resource isolation

- Worktree handles are scoped to repository, grant, and allowed path set.
- The server validates canonical roots, Git common-dir/worktree-dir identity, symlink traversal, nested repositories, and path normalization on every operation.
- One job cannot read/write another job's worktree unless an explicit shared grant exists.
- Shared semantic objects may be readable according to semantic authorization policy; write access means proposing new content-addressed objects/Change Sets, not mutating existing objects.
- Mapping writes require mapping-specific permissions and expected revision.
- Watcher events and file paths are untrusted input.
- Resource limits cover number of worktrees, watcher handles, queued events, file sizes, concurrent hashing, and reconciliation load.
- Revoking one job's grant must not stop the shared server or revoke unrelated jobs.

## 13. MCP API implications

The MCP surface should expose stable handles and scoped operations, not server lifecycle controls per job.

Candidate additions/refinements (names illustrative):

| Operation | Purpose |
|---|---|
| `repository.server_info` | Return stable server/repository instance identity and supported multi-worktree capabilities |
| `worktree.create/list/inspect/remove` | Manage isolated regular-file views |
| `worktree.select` | Select a handle in a client request/context; no import or full scan |
| `worktree.status` | Return cached generation/freshness plus optional bounded refresh |
| `worktree.changes` | Return journaled changed paths since a cursor/generation |
| `worktree.reconcile` | Explicitly reconcile one selected worktree, with scope and cost |
| `file.inspect/read/write` | Operate on scoped paths with expected generation/content identity |
| `semantic.snapshot.inspect` | Inspect immutable shared semantic snapshots independent of worktree |
| `semantic.change_set.create` | Create a semantic proposal against a snapshot |
| `mapping.inspect/update/merge` | Versioned mapping operations with expected revision |
| `operation.inspect/resume/cancel` | Durable operation recovery |

`worktree.select` is a client-side context convenience only. It must not mutate a process-global "current worktree" on the server; every operation carries an explicit worktree handle. This prevents concurrent MCP clients from racing over a shared current-directory/current-worktree variable.

The protocol should expose File View freshness (for example: current, catching_up, stale, unknown), generation, last reconciliation time/reason, and whether a result was served from cache. Exact schemas belong in the RT-22 contract refinement.

## 14. Observability and performance acceptance

Measure separately:

- Toolchain process count per repository under N concurrent jobs;
- worktree selection latency;
- server restart recovery time;
- number of directories/stat calls and file-content reads per operation;
- number of unchanged files re-read or re-hashed;
- watcher event loss/overflow and reconciliation frequency;
- Git status latency with and without FSMonitor/untracked cache;
- per-worktree and shared semantic-store memory/disk use;
- lock contention and throughput across independent worktrees;
- stale-result detection precision.

Required performance properties:

1. Adding a worktree does not create another Toolchain Server process.
2. Selecting an already registered, healthy worktree does not trigger recursive content reads or semantic re-import.
3. An edit in Worktree A does not cause Worktree B to be scanned or invalidated.
4. An unchanged committed file can be identified by its Git blob OID without reading its content.
5. A request scoped to a small path set performs work proportional to that path set plus necessary bounded metadata checks, not to total repository content.
6. When a full reconciliation is unavoidable, it is explicit, limited to the affected worktree, and reported.
7. Correctness is maintained after watcher loss, offline edits, and server restart.

## 15. Required test matrix

- One server process serves at least two concurrent worktrees and multiple MCP clients.
- Semantic Change Sets from the same base snapshot can evolve concurrently without worktrees.
- Identical semantic objects proposed by different jobs deduplicate to one content identity.
- A stale Change Set head update is rejected without mutating accepted snapshots.
- Mapping updates from disjoint scopes can merge; same-key concurrent updates conflict.
- Selecting a healthy worktree causes zero file-content reads and no semantic import.
- Editing one file causes only the relevant path(s) to be re-statted/read/hashed.
- Worktree A changes do not invalidate or scan Worktree B.
- Unchanged tracked files use Git object identity without content reread.
- Watcher overflow triggers reconciliation of only the affected worktree.
- Server restart with continuous journal resumes without full content reread.
- Server restart after offline edits detects and imports only changed/unknown paths.
- Atomic-save rename, symlink swap, case-only rename, untracked files, and index-only changes are handled.
- Concurrent writes to the same path or Git ref conflict deterministically.
- One client's disconnect/revocation does not interrupt other clients/jobs.
- A build/test result becomes stale when one of its declared inputs changes, but not when an unrelated worktree changes.

## 16. Implementation phases

1. **Identity and model:** document repository/server/worktree/semantic snapshot/mapping identities; remove any assumption that each worktree owns a separate semantic store.
2. **Single-server registry:** one process registers one repository and creates two worktrees; all operations use explicit handles, never a global current worktree.
3. **Shared semantic store:** concurrent Change Sets, immutable objects/snapshots, mapping revision CAS.
4. **File View prototype:** persisted per-worktree metadata and generations; instrument all file reads/hashes.
5. **Incremental event path:** native watcher + durable journal + targeted path reconciliation.
6. **Git integration:** HEAD/index/ref tracking, status/diff, expected-old-OID updates, FSMonitor/untracked cache where supported.
7. **Recovery:** crash/restart, watcher gap, offline edits, bounded per-worktree reconciliation.
8. **MCP and AIVibeFlow:** expose handles, freshness, durable operation IDs; exercise multiple concurrent Jobs through one server.
9. **Benchmark and decision:** compare against naïve full-tree rescan/re-import and document platform-specific fallbacks.

Do not begin by implementing a distributed service or by spawning a server per worktree. Prove the single-process model first.

## 17. Open questions

1. Which exact semantic entity kinds are immutable, and what is the precise schema/ownership boundary for interface mappings?
2. Are interface mappings global to a repository, scoped by target/environment, or scoped by package/module? The mapping key must include the scope needed to avoid accidental cross-target conflicts.
3. Which files are semantic source inputs versus regular files, and where is the authoritative classification declared?
4. Which filesystem watcher backends are supported on each target OS, and what are their overflow/restart guarantees?
5. Should the first durable File View use SQLite, an append-only journal plus snapshots, or another embedded store?
6. Which Git version/features (FSMonitor, untracked cache, split index) are baseline requirements versus optional accelerators?
7. How are multiple server processes prevented from registering the same repository simultaneously? Is an OS-level repository lock/lease required?
8. What is the policy for worktree branch refs shared by external Git clients?
9. Which operations require strong whole-tree consistency, and which can declare bounded path scopes?
10. How should large generated/vendor trees be excluded or represented without weakening build provenance?

## 18. Research exit criteria

RT-23 is ready for an architectural decision when:
- the immutable semantic/mutable mapping boundary is validated against the language's actual object model;
- a single server serves multiple worktrees with explicit handles;
- selecting a worktree does not read/re-import its contents;
- incremental tracking survives restart and detects watcher gaps;
- independent worktree changes do not cause cross-invalidation;
- build/test provenance pins semantic, mapping, and regular-file inputs;
- concurrency, security, recovery, and performance tests pass on supported filesystems;
- platform-specific limitations and fallback scan costs are measured.

RT-23 is a research proposal, not an accepted architecture decision. It does not change ADR-015 status.
