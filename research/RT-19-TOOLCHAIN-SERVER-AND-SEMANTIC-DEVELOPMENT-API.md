# RT-19 — Toolchain Server and Semantic Development API

**Status:** Research proposal; no implementation architecture or wire contract is accepted  
**Date:** 2026-11-18  
**Research area:** Development tooling, semantic editing, storage, collaboration, and AI integration  
**Related:** [RFC — LLMLang Development Engine](RFC-DEVELOPMENT-ENGINE.md), [Git Semantic Repository](GIT-SEMANTIC-REPOSITORY.md), [ADR-014](../docs/adr/014-git-semantic-merge.md), [Semantic Compilation Cache](SEMANTIC-COMPILATION-CACHE.md), [Package System](PACKAGE-SYSTEM.md), [ADR-015](../docs/adr/015-toolchain-server-semantic-api.md), [Prototype 01](PROTOTYPES/TOOLCHAIN-SERVER-01/README.md)

> This research investigates making structured Toolchain API operations—not direct source-file editing—the primary way for agents and automation to inspect and change LLMLang programs. It does not amend the candidate language specification or silently turn the proposed architecture into an accepted decision.

## 1. Research question

Can LLMLang provide a Toolchain Server that exposes a stable semantic development API (including an MCP adapter), maintains isolated working program states in memory and/or persistent storage, and deterministically synchronizes accepted states to the repository's human-readable textual representation?

The intended workflow is:

1. An agent inspects a bounded semantic context.
2. It proposes typed semantic changes against explicit object hashes.
3. The Toolchain applies proposals to an isolated working state.
4. Deterministic engines validate, analyze, and verify the proposed state.
5. An authorized operation accepts a new immutable snapshot.
6. The repository adapter exports that snapshot to canonical text files and coordinates Git operations.

The agent should not need to locate, open, patch, or format source files to perform ordinary program construction. Direct text editing remains a supported interoperability path, not the primary machine-authoring interface.

## 2. Relationship to existing architecture

The proposal is a concrete interface and runtime direction for the existing LLMLang Development Engine (LDE), not a replacement for it.

The RFC already proposes:
- SPG as the semantic representation for supported operations;
- a structured Change API and isolated proposals;
- expected-hash preconditions, semantic diff, impact analysis, and independent verification;
- a model-agnostic Machine API;
- CLI, IDE, CI, and agent clients over shared semantics;
- MCP as a possible adapter rather than a dependency of the semantic core.

RT-19 should resolve the operational details that the RFC leaves open: workspace lifecycle, transaction boundaries, storage abstraction, typed mutation envelopes, concurrency, synchronization, MCP surface, and recovery.

### 2.1 Architectural invariants to preserve

1. **Git portability:** a clean checkout must contain sufficient authoritative, declared inputs to reconstruct the program, subject to pinned external dependencies.
2. **Semantic identity is separate:** Git blob/tree/commit IDs, semantic Content Hashes, Action Keys, and Artifact Hashes remain distinct.
3. **Derived storage is reconstructible:** local SPG databases, indexes, and caches must not become the only copy of source meaning.
4. **No mutation of accepted snapshots:** proposals are isolated until an authorized acceptance operation creates a new immutable snapshot.
5. **Deterministic import/export:** equivalent semantic states produce the same canonical textual repository representation under the same format/toolchain contract.
6. **Independent checking:** model claims are not evidence; validators and verification engines determine their own results.
7. **Protocol independence:** MCP is an adapter over a transport-neutral domain API, not the domain model itself.

These invariants are consistent with ADR-014's proposed Git-authoritative repository direction. ADR-014 remains Proposed and is not changed by this research.

## 3. Proposed logical architecture

The initial deployment should be a modular monolith unless measurements or operational requirements justify process separation.

```text
 Human / Agent / IDE / CLI / CI
              |
       Client-facing adapters
       + MCP + CLI + IDE API
              |
        Toolchain API
     (typed domain operations)
              |
       Workspace / Change
        orchestration layer
              |
   +----------+-----------+----------------+
   |                      |                |
 Context & Query       Change Engine   Repository Manager
   |                      |                |
   +----------+-----------+                |
              |                            |
       Semantic Engine                     |
       Verification Engine                |
              |                            |
        SPG Store / Workflow Store         |
       + indexes + disposable caches      |
              |                            |
              +------ Import / Export -----+
                           |
                    Textual Git repository
```

The diagram is logical, not a mandatory process topology. Components may initially share one executable and one database transaction manager.

### 3.1 Toolchain API (domain boundary)

The Toolchain API owns typed operations and domain-level error semantics. It should not expose MCP-specific JSON-RPC types, transport sessions, or protocol lifecycle objects.

Candidate operation families:

| Family | Candidate operations | Responsibility |
|---|---|---|
| Workspace | open, inspect, status, checkpoint, rebase, close | Isolated working view and lifecycle |
| Query | inspect, search, resolve, dependencies, callers | Semantic reads and bounded context |
| Context | assemble, explain omissions, retrieve continuation | Minimal sufficient context with exact input hashes |
| Change | create, add, update, remove, rename, move, apply, discard | Typed proposals against exact baselines |
| Diff | semantic diff, compare snapshots, summarize | Reviewable graph-level changes |
| Analysis | validate structure, type/effect check, impact | Deterministic semantic analysis |
| Verification | select checks, run tests, prove, inspect evidence | Independent checks and evidence |
| Review | request review, record decision, policy check | Human/policy governance |
| Snapshot | accept, inspect, compare, restore | Immutable accepted states |
| Repository | import, export, status, prepare commit, commit | Text synchronization and Git coordination |
| Package | inspect, resolve, build, publish | Package operations, when supported |

Names are illustrative. Operations must be specified by typed schemas, preconditions, postconditions, authorization, idempotency, failure modes, and version compatibility before implementation.

### 3.2 MCP adapter

The MCP adapter maps the domain API to MCP primitives:

- **Tools:** bounded actions such as `workspace.open`, `program.inspect`, `change.propose`, `change.validate`, `verification.run`, and `repository.export`.
- **Resources:** read-only views such as a workspace summary, object description, diagnostics, semantic diff, or verification report. Resource URIs should be opaque, scoped handles rather than arbitrary filesystem paths.
- **Prompts:** optional task templates such as implementation planning or change review. Prompts are convenience, not policy or authority.

The MCP server advertises only capabilities it actually implements. Long-running operations should expose progress/cancellation where supported. Tool results should be concise and structured, with stable diagnostic codes and handles for retrieving large results.

The adapter must not treat MCP connection identity as durable workspace identity. Every stateful operation carries explicit identifiers and authorization context. Reconnection or a new client process must not silently select another workspace.

### 3.3 Other adapters

CLI, IDE, CI, REST/gRPC (if later justified), and MCP should call the same domain operations. No adapter may bypass validation, policy, transaction, or audit rules.

## 4. Workspace, Change Set, and snapshot model

The API needs explicit lifecycle objects.

### 4.1 Workspace

A Workspace is an isolated mutable view rooted at an immutable base snapshot and a repository revision.

Candidate fields:

| Field | Meaning |
|---|---|
| `workspace_id` | Opaque durable identifier |
| `repository_id` | Repository identity |
| `base_git_revision` | Git commit or equivalent imported revision |
| `base_snapshot_id` | Semantic snapshot identity |
| `working_snapshot_id` | Current proposed graph root |
| `language_version` | Composite LLMLang language version |
| `toolchain_identity` | Exact toolchain identity |
| `state` | Open, stale, conflicted, accepted, discarded, or closed |
| `owner/principal` | Authorized actor or service principal |
| `created_at / updated_at` | Operational metadata, not semantic identity |

A workspace may be persisted or in-memory. An in-memory workspace still needs an explicit lifetime and a recoverable policy: it must either be checkpointed or clearly disposable.

### 4.2 Change Set

A Change Set groups proposed mutations and records:
- the base snapshot and expected hashes;
- typed operations and their order/dependency constraints;
- author/provenance and idempotency keys;
- semantic diff and impact summary;
- validation/verification evidence bound to exact inputs;
- status and review/approval decisions.

A Change Set is not itself an accepted program snapshot. Applying operations creates a new isolated working snapshot. Acceptance publishes a new immutable snapshot; it does not mutate the base.

### 4.3 Snapshot

A snapshot identifies an immutable semantic state, preferably by a defined root hash or set of layer roots. It must be possible to reconstruct its authoritative semantic content from repository inputs and pinned dependencies.

Do not conflate:
- Workspace ID (a mutable work area);
- Change Set ID (a proposal/history unit);
- Stable ID (logical entity lineage);
- Content Hash (immutable semantic object state);
- Snapshot ID/root (a complete semantic state);
- Git commit (repository history state);
- Action Key (a computation over exact inputs and tool configuration).

## 5. Structured change contract

Ordinary agent mutations should be typed semantic operations, not arbitrary source patches.

A mutation envelope should include at least:

- operation kind and schema version;
- target Stable ID or creation scope;
- expected target Content Hash (absent only for explicit creation);
- referenced object hashes and expected versions;
- typed payload;
- declared preconditions;
- actor/provenance and idempotency key;
- optional rationale or links to requirements/decisions.

The Change Engine validates the envelope before applying it. It must reject unknown required operation kinds, malformed payloads, unauthorized targets, missing references, and stale expected hashes.

### 5.1 Granularity

The API should expose domain-meaningful operations (for example, add an operation declaration, attach a contract, replace an implementation body, add a test scenario, or update a module export), not arbitrary mutation of internal graph storage records.

A lower-level graph transaction API may exist for trusted compiler components, migrations, or advanced tooling, but should not be the default agent interface.

### 5.2 Text and escape hatches

Text may be used inside a typed payload where the language defines text-bearing fields (for example, a documentation string or a source snippet in an explicitly syntax-oriented import operation). Such text must be parsed, typed, and validated before it affects SPG.

A compatibility API may accept a complete source file or patch, but it must:
1. bind the request to a repository/workspace baseline;
2. parse and import it into a candidate graph;
3. produce a semantic diff;
4. run the required validators;
5. reject conflicts or incomplete imports;
6. preserve provenance and diagnostics.

It must not bypass the Change Engine or directly overwrite accepted state.

## 6. Storage architecture

The Toolchain Server must depend on a storage interface, not a specific database.

### 6.1 Logical stores

Separate the following logical responsibilities even if they initially share one physical database:

1. **Immutable SPG object store:** content-addressed semantic objects and snapshot roots.
2. **Workspace/Change store:** mutable workspace heads, proposals, operation logs, checkpoints, leases, and state transitions.
3. **Evidence store:** verification records, diagnostics, provenance, and audit events, with explicit retention/integrity policy.
4. **Indexes:** reverse dependencies, symbol/name lookup, graph traversal accelerators.
5. **Cache store:** disposable derived computations keyed by exact Action Keys.

The authoritative repository representation remains Git-visible text and declared metadata under ADR-014's proposed direction. The object store and indexes are reconstructible derived state; accepted snapshot metadata must map deterministically to repository revisions.

### 6.2 In-memory and persistent backends

Support at least two conceptual profiles:

- **In-memory backend:** useful for tests, short-lived tasks, local development, and ephemeral agent sessions. It is not durable across process loss unless explicitly checkpointed.
- **Persistent embedded backend:** suitable for local toolchain operation, durable workspaces, restart recovery, and concurrent local clients.

A remote/shared backend is a later option, not an MVP prerequisite.

The API and semantics must be identical across backends. Backend differences may affect performance and durability guarantees, but not object identity, transaction results, validation, or observable API behavior.

### 6.3 Transaction and recovery requirements

- Publishing a new immutable object is idempotent by content identity.
- Updating a workspace head uses compare-and-swap against the expected prior head.
- Applying a Change Set either produces a complete new working root or leaves the previous root intact.
- Acceptance atomically records the accepted snapshot and its relationship to the Change Set.
- Repository export writes a complete consistent file set; interruption must not leave a mixed generation presented as current.
- A crash between semantic acceptance and Git commit must be recoverable and visible as a pending export/commit, not silently treated as synchronized.
- Cache corruption or absence causes recomputation, not loss of authoritative state.
- Recovery must distinguish accepted, proposed, exported, committed, and pushed states.

The exact cross-store transaction strategy (single DB transaction, write-ahead log, outbox/reconciliation, or staged filesystem publication) is an experiment target.

## 7. Concurrency and multi-agent operation

Use optimistic concurrency as the default, with explicit expected hashes and workspace-head compare-and-swap.

- Two workspaces may branch from the same base snapshot.
- Independent changes may be merged by semantic three-way merge.
- Concurrent updates to the same entity must not use last-writer-wins.
- Conflicts must preserve both alternatives and identify the semantic overlap.
- A rebase must replay or re-evaluate changes against a new base; it must not blindly rewrite expected hashes.
- A Change Set should be immutable once accepted; later changes create a new Change Set.
- Workspace leases/locks may be used for resource coordination, but correctness must not depend solely on lease expiry.
- Actor identity, authorization, and provenance are checked on each operation, not inferred from an MCP connection.

The first prototype should test two independent workspaces, stale writes, same-entity conflicts, and crash/restart recovery.

## 8. Filesystem and Git synchronization

Textual repository files remain the portable, reviewable representation. They are not the primary mutation interface for agents.

### 8.1 Export: semantic state to files

Export should:
1. choose an exact accepted or explicitly exportable working snapshot;
2. verify its language/toolchain compatibility and repository baseline;
3. serialize all affected declarations and metadata canonically;
4. update only files whose canonical bytes changed;
5. stage a complete consistent generation;
6. validate by re-importing or checking exported hashes;
7. atomically publish the generated file set where filesystem guarantees permit;
8. report the exact files, Git tree, snapshot root, and export diagnostics.

The exporter must not create nondeterministic output from timestamps, map iteration order, local paths, or machine-specific formatting.

### 8.2 Import: files to semantic state

Import should:
1. identify the exact Git tree/worktree baseline;
2. parse all required project files and declared dependencies;
3. construct a candidate SPG without modifying the accepted snapshot;
4. validate references, identities, language version, and cross-file invariants;
5. compare the candidate with the workspace/base snapshot;
6. produce semantic diff and conflict diagnostics;
7. publish a new workspace root only after successful validation.

A partial parse or missing required file must not be mistaken for deletion of semantic entities.

### 8.3 External edits and conflict policy

The toolchain must detect edits made outside its API. It should track a repository tree or file-set fingerprint and the baseline used for export. If files changed since the workspace was opened or since the last import/export, export must stop and reconcile the external changes.

Never silently overwrite a developer's IDE edits. A conflict should offer semantic comparison or an explicit import/rebase path.

### 8.4 Git commit boundary

Repository export and Git commit are distinct operations. The API may prepare a tree/index for commit, but commit/push must be separately authorized according to policy. A successful semantic acceptance does not imply that files were exported, committed, or pushed.

The state machine must represent these facts separately, for example:
`accepted -> export-pending -> exported -> commit-pending -> committed -> pushed`.
Failures retain enough metadata to retry safely.

## 9. Context and result design

The Toolchain should return semantic handles and bounded projections, not dump the entire graph.

A context package should record:
- operation/task profile and budget;
- exact object hashes and snapshot root;
- included dependency edges and why they were selected;
- omitted optional context and reasons;
- continuation handles for further retrieval;
- language version and toolchain identity.

Large diagnostics, diffs, and verification reports should be retrievable through handles/resources. Tool outputs should include stable codes, severity, affected Stable IDs, relevant hashes, and actionable next steps.

## 10. Security and authority

All model-originated payloads are untrusted.

Minimum requirements:
- authenticate the principal and authorize each operation;
- scope workspace and object handles to repository and principal permissions;
- enforce path and repository boundaries in import/export;
- apply least-privilege capabilities for reading, proposing, validating, accepting, committing, and publishing;
- prevent prompt/resource content from becoming executable policy;
- treat MCP tool arguments and returned external content as untrusted data;
- redact secrets from context and diagnostics;
- audit reads of sensitive data and all state-changing operations;
- rate-limit and bound expensive analysis/verification operations;
- sandbox compilation and execution independently of the MCP server;
- never infer user approval from an LLM-generated statement.

Acceptance, Git commit, push, package publish, and destructive workspace actions require explicit policy authorization. The model may request them but cannot grant itself authority.

## 11. Failure semantics

Use explicit machine-readable outcomes. At minimum distinguish:
- invalid request;
- unsupported operation/schema version;
- not found / inaccessible;
- stale baseline;
- semantic conflict;
- validation failed;
- verification failed;
- verification unknown / timed out;
- policy denied;
- backend unavailable;
- partial repository synchronization;
- recovery required.

Do not report a timeout or unavailable verifier as success. A failed export must not roll back an already accepted semantic snapshot without an explicit compensating operation; instead record a recoverable pending synchronization state.

## 12. Research hypotheses and alternatives

### H1 — Semantic API as primary agent interface

A typed semantic API will reduce malformed edits, unnecessary context transfer, and formatting churn compared with direct text-file patching, without preventing human-readable source review.

### H2 — Adapter separation

A transport-neutral domain API with MCP/CLI adapters will remain easier to test and evolve than embedding MCP request/session semantics into the compiler or SPG.

### H3 — Reconstructible persistent store

A local persistent SPG/workspace store will improve responsiveness and restart recovery while Git-visible inputs remain sufficient to reconstruct accepted program state.

### H4 — Explicit workspace and Change Set handles

Durable explicit IDs and optimistic concurrency will support reconnects and parallel agents more safely than implicit per-connection state.

### Alternatives to compare

1. Direct source-file editing with compiler/IDE validation.
2. Structured API backed by in-memory graph only.
3. Structured API backed by a persistent embedded store.
4. Structured API backed by an external shared service.
5. MCP-native implementation versus a domain API with MCP adapter.

Do not assume the proposed design wins. Measure complexity, latency, recovery, correctness, and usability.

## 13. Prototype plan

Build a small vertical slice before implementing the complete API.

### Prototype A — In-memory semantic workspace

- Import a minimal valid repository fixture into a typed in-memory SPG.
- Open two workspaces from the same base snapshot.
- Inspect a bounded operation/contract/type context.
- Propose a typed addition or implementation update with expected-hash preconditions.
- Reject malformed and stale proposals.
- Compute semantic diff and run structural/type validation.
- Accept one workspace snapshot and export canonical text.
- Re-import the export and verify semantic round-trip identity.

### Prototype B — Persistent workspace and recovery

- Replace the in-memory store with a persistent embedded backend behind the same interfaces.
- Restart the server and recover workspace heads, Change Sets, and pending export state.
- Inject failures at object write, workspace-head update, acceptance, export staging, and Git commit boundaries.
- Verify atomicity or explicit recoverable state at every boundary.
- Confirm cache/index loss does not lose accepted semantic content.

### Prototype C — MCP adapter

- Expose a small set of read and write Tools plus read-only Resources.
- Verify discovery and schema validation from at least one independent MCP client.
- Reconnect/restart the client and server while preserving explicit workspace handles.
- Verify authorization and error mapping.
- Compare tool payload sizes and task completion against direct source-file editing.

### Required fixtures and tests

- deterministic import/export round trip;
- same semantic graph with formatting-only differences;
- stale expected hash;
- duplicate/idempotent request;
- two independent concurrent workspaces;
- same-entity conflicting updates;
- interrupted multi-file export;
- external IDE edit after workspace open;
- process crash and restart;
- missing/corrupt derived index and cache;
- unauthorized accept/commit;
- MCP disconnect and reconnect.

## 14. Initial prototype evidence

An initial in-memory lifecycle prototype is available at [Toolchain Server Prototype 01](PROTOTYPES/TOOLCHAIN-SERVER-01/README.md). It implements a generic immutable Entity envelope, content-addressed snapshots, isolated workspaces, typed add/update/remove Change operations, expected-hash and workspace-revision checks, acceptance, and single-file canonical JSON import/export with external-edit detection.

This prototype deliberately does not define the canonical SPG schema or public wire format. It does not yet implement persistence, crash recovery, multi-file export, Git coordination, MCP, authentication, or a production authorization model. Its tests and CI workflow are intended to validate only the narrow lifecycle model.

## 15. Evaluation criteria

The prototype should report:
- semantic correctness and round-trip identity;
- number of malformed changes rejected before mutation;
- conflict detection precision and false-negative risk;
- export determinism and changed-file count;
- crash recovery outcomes at each injected failure point;
- workspace open/query/change latency and memory;
- persistent-store size and reconstruction time;
- MCP payload size, tool-call count, and end-to-end latency;
- context tokens and repeated-context ratio;
- developer review effort and clarity of semantic diffs.

Compare against a baseline in which the same tasks are performed by editing textual files and invoking the existing compiler/checker workflow. No single performance result establishes correctness.

## 16. Open questions

1. Which exact SPG entity kinds and semantic mutation operations belong in the first vertical slice?
2. Is an embedded database needed for the first prototype, or is an in-memory implementation plus persistence interface sufficient?
3. Which workflow/audit records belong in the SPG store versus a separate event/workflow store?
4. What is the canonical identity and retention policy for Workspace and Change Set records?
5. Which operations are idempotent, and how are idempotency keys scoped and retained?
6. What consistency model is required when multiple clients share a persistent workspace?
7. How should accepted snapshot publication coordinate with filesystem export and Git commit?
8. Which MCP capabilities/transports are required for the first adapter, and which are deferred?
9. How should large graph results, diagnostics, and long-running verification jobs be paged or referenced?
10. Which permissions may be delegated to an agent, and which always require a human or external policy decision?
11. What is the minimum supported behavior for direct source edits from an IDE?
12. Which toolchain/language version compatibility rules govern reopening old workspaces?

## 17. Provisional recommendations (not accepted decisions)

1. Keep the Toolchain API transport-neutral and expose MCP as an adapter.
2. Start with a modular monolith and an in-memory backend; define a persistent storage interface from day one.
3. Add a persistent embedded backend only after the in-memory transaction and identity model is tested.
4. Make semantic Change Sets and immutable snapshots the only route to accepted program state.
5. Use optimistic concurrency and expected-hash preconditions by default.
6. Keep Git-visible text authoritative and sufficient for reconstruction; treat local SPG databases, indexes, and caches as derived.
7. Separate semantic acceptance, filesystem export, Git commit, and push into observable, recoverable states.
8. Preserve direct text import as an interoperability path, never as an unvalidated bypass.
9. Implement one end-to-end operation before expanding the MCP surface.
10. Do not create a distributed Toolchain Server until a measured need exists.

## 18. Exit criteria

RT-19 is ready for an architectural decision only when:
- the domain API and mutation envelope are specified for a small supported SPG subset;
- import/export round trips deterministically;
- stale and conflicting mutations are rejected;
- accepted snapshots remain immutable;
- two workspaces can safely evolve from one base;
- restart/failure injection demonstrates recoverable persistence semantics;
- external file edits are detected and not overwritten;
- the MCP adapter is independently exercised;
- security and authorization boundaries are tested;
- benchmark and usability comparisons are documented;
- remaining limitations and deferred features are explicit.

Passing these criteria supports a scoped ADR. It does not by itself establish that the entire LLMLang architecture is complete or defect-free.
