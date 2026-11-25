# RT-22 — LLMLang Git Repository and Worktree MCP Surface

**Status:** Research proposal; not an accepted architecture decision  
**Date:** 2026-11-18

## 1. Purpose and scope

Define the LLMLang side of an integration in which AIVibeFlow delegates repository and worktree mechanics for LLMLang projects to the LLMLang Toolchain through MCP, while using its native Git tools for other programming languages.

This document is the sole source of truth in LLMLang for the LLMLang-owned Git/MCP contract. AIVibeFlow's provider selection, orchestration, platform policy, and native Git path are specified only in the AIVibeFlow integration document. That document references this one for LLMLang-side behavior.

## 2. Relationship to existing work

This proposal extends, but does not replace:

- [RT-19 — Toolchain Server and Semantic Development API](../RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md): transport-neutral Toolchain API, MCP adapter, Workspace/Change Set/Snapshot lifecycle, authorization, recovery, and repository synchronization.
- [RT-20 — LLM Patch Planning and Hash Propagation](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md): complete impact planning and validation-gated semantic changes.
- [RT-21 — LLMLang Self-Development](../RT-21/RT-21-LLMLANG-SELF-DEVELOPMENT-AND-BOOTSTRAP-ROADMAP.md): use of AIVibeFlow as a development environment for LLMLang.

RT-19 remains the broader Toolchain architecture proposal. RT-22 narrows the repository integration question and adds an explicit external-orchestrator boundary. [RT-23 — Single-Instance Toolchain with Shared Semantic State and Incremental Multi-Worktree File Views](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) is authoritative for the detailed runtime model: shared immutable semantic objects, versioned interface mappings, one server instance, and incremental per-worktree file views. ADR-015 remains Proposed; neither research document accepts it.

## 3. Design goals

1. Make LLMLang repository operations semantically observable rather than opaque shell/Git side effects.
2. Let the Toolchain inspect and validate repository state alongside SPG changes, dependency analysis, and verification.
3. Support isolated worktrees and concurrent jobs without mixing state.
4. Preserve ordinary Git interoperability and a reconstructible textual repository.
5. Permit bounded delegation without transferring unrestricted host or credential access.
6. Keep MCP as a thin adapter over the transport-neutral Toolchain API.
7. Fail closed when repository identity, baseline, ownership, or semantic correspondence is uncertain.

## 4. Responsibility boundary

LLMLang owns the semantics and execution of its repository/worktree capability surface inside an explicitly granted repository scope. This includes repository inspection, local worktree lifecycle, branch/worktree-local operations, semantic import/export, reconciliation, and preparation of verifiable local changes.

The external orchestrator owns provider selection, workflow/job integration, platform authorization, and the decision to grant the scope. Those responsibilities are specified only in the AIVibeFlow integration document.

Remote credentials, provider-account policy, and actions outside the granted local scope must not be inferred from MCP connectivity. Remote publication and other externally privileged actions require explicit delegated authority.

## 5. Repository and worktree model

The Toolchain API should expose durable opaque handles rather than arbitrary filesystem paths. Importantly, a worktree is a regular-file/Git isolation boundary, not a semantic-store isolation boundary. One Toolchain Server instance serves multiple worktrees; semantic objects/snapshots are shared and immutable, while interface mappings are separately versioned. A job that only changes LLMLang semantic objects does not need a Git worktree. See RT-23 for the normative research model and incremental synchronization requirements.

The Toolchain API should expose durable opaque handles rather than arbitrary filesystem paths:

- Repository handle: registered repository identity and configured remote identities.
- Worktree handle: isolated working tree bound to a repository and immutable base commit.
- Semantic Change Set ID: proposed semantic graph transition anchored to an explicit immutable snapshot; it does not require a worktree.
- Change Set ID and Snapshot ID: references to proposed and immutable semantic state.
- Operation ID: durable handle for a long-running operation.

A worktree record retains repository identity, base commit, branch or detached-HEAD state, owning external scope, File View identity/generation, creation provenance, lifecycle state, and cleanup status. Semantic snapshot and interface mapping revision are bound explicitly to operations that need them, not implicitly owned by a worktree.

Paths are private implementation details. A scoped display path may be returned only when required by an explicitly supported filesystem integration; it is never an authorization token.

Repository/worktree lifecycle and semantic Workspace lifecycle are related but distinct. A worktree may contain external edits not yet imported into the semantic model; a semantic Workspace may have accepted changes not yet exported. The API exposes this divergence.

## 5.1 Single-server and incremental worktree requirement

RT-22 MUST NOT be interpreted as requiring one Toolchain Server process or semantic database per worktree. A single long-lived server instance must serve multiple independently authorized worktree handles. Worktree selection is request-scoped and must not change a server-global current directory/worktree. Selecting a healthy registered worktree must reuse its persisted File View and must not trigger a full tree content read, semantic import, or cache rebuild. File change tracking is incremental and per-worktree; a lost event cursor triggers reconciliation of only the affected worktree. Shared immutable semantic objects and snapshots are independent of the selected worktree; interface mappings use explicit versioned revisions and concurrency checks. Detailed design, failure behavior, metrics, and tests are defined by RT-23.

## 6. Candidate MCP capability families

Names are illustrative. Final operation names and schemas must be specified in the Toolchain API before implementation.

| Family | Candidate operations | Purpose |
|---|---|---|
| Repository | repository.register, repository.inspect, repository.fetch, repository.status, repository.unregister | Register and inspect a bounded local repository |
| Worktree | worktree.create, worktree.inspect, worktree.list, worktree.status, worktree.remove | Create and manage isolated worktrees |
| Branch | branch.create, branch.inspect, branch.list, branch.switch | Manage branch state within the granted scope |
| Change inspection | repository.diff, repository.changed_files, repository.untracked_files, repository.base | Inspect local changes and baseline |
| Semantic sync | repository.import, repository.export, repository.reconcile | Synchronize textual files and semantic state |
| Commit preparation | repository.prepare_commit, repository.inspect_commit, repository.commit | Prepare and, when explicitly authorized, create a local commit |
| Recovery | operation.inspect, operation.cancel, worktree.recover | Inspect or resume interrupted operations |

MCP Resources may expose read-only repository/worktree summaries, diffs, synchronization status, and operation reports. Large results use opaque references and bounded retrieval. Prompts are optional conveniences and never grant authority.

The server must not expose a generic shell, arbitrary command execution, arbitrary filesystem access, or unrestricted Git passthrough as a substitute for typed operations.

## 7. Operation contract and consistency

Every state-changing operation defines typed schemas, preconditions, postconditions, authorization, idempotency, concurrency behavior, failure outcomes, and compatibility rules.

At minimum:

- Mutations identify repository and worktree explicitly.
- Operations depending on repository state include expected base commit and/or expected worktree revision.
- Worktree and branch mutations reject stale state through compare-and-swap or equivalent.
- Repeated requests with the same idempotency key and equivalent input return the original result; conflicting reuse is rejected.
- A timeout is not evidence of success or failure. The caller inspects the durable operation ID.
- Reconnection cannot silently select another repository or worktree.
- Removal is refused when ownership is uncertain or protected/unexported changes remain.
- External edits are detected and reconciled explicitly, never silently overwritten.

Long-running fetch, import/export, analysis, and verification use the durable operation model defined by RT-19. RT-22 does not redefine that model.

## 8. Semantic/Git consistency boundary

The implementation represents separately:

1. Filesystem/worktree state.
2. Imported semantic state.
3. Proposed Change Set state.
4. Accepted immutable semantic Snapshot.
5. Exported textual repository state.
6. Prepared local commit.
7. Created local commit.
8. Remote publication state.

These facts must not be collapsed into one clean/committed flag.

A commit candidate associated with a semantic change identifies the exact semantic snapshot, repository baseline, exported tree/content identity, and verification evidence. If any hash-relevant input changes after verification, the candidate is stale and must be revalidated.

RT-20 defines semantic impact planning and validation gates. RT-22 defines the repository/worktree integration surface and does not duplicate caller migration or hash-propagation rules.

## 9. Security and delegated scope

The Toolchain enforces repository-scoped handles and rejects path traversal, symlink escapes, repository substitution, cross-worktree access, and unauthorized cleanup.

An external orchestrator may grant a bounded capability lease containing:

- Principal and originating process/job references.
- Repository and allowed worktree scope.
- Allowed operation set.
- Expiry and revocation information.
- Expected repository identity and baseline constraints.
- Audit and correlation references.

The lease is authorization input, not a replacement for LLMLang's own operation-level checks. It is validated on every operation. Permission is never inferred from an MCP connection, prompt, model output, or guessed handle.

Credentials must not appear in tool results, semantic context, prompts, ordinary logs, or artifacts. Remote authentication requires an explicitly delegated least-privilege mechanism; absence or expiry produces a typed authorization failure.

## 9.1 Commit means synchronized LLMLang and regular-file state

For an LLMLang repository, a successful local commit MUST include a real synchronization of the pinned LLMLang semantic state into the selected Git worktree's canonical repository representation, together with the explicitly selected regular-file changes, and persist both in one Git commit. A Toolchain-local semantic database update without the corresponding Git tree representation is not a commit.

Commit preparation pins the worktree baseline/generation, semantic snapshot, mapping revision, selected regular-file changes, and validation evidence. The Toolchain exports the semantic state into the worktree, verifies a round-trip to the pinned semantic state, validates the combined candidate tree, and only then creates the Git commit. Partial export, stale inputs, or validation failure must not produce a successful commit. Crash recovery must inspect the actual Git commit/tree and durable operation identity before deciding whether to finalize or retry.

Git merge likewise operates on committed LLMLang representations. A merge-generated tree must be semantically imported/reconciled and validated before its merge commit is considered complete. Detailed runtime sequencing and recovery are owned by RT-23; semantic serialization and merge rules are owned by RT-15.

## 10. Failure and recovery

The API distinguishes at least: invalid request, unsupported capability/schema, inaccessible handle, stale baseline, worktree conflict, semantic conflict, policy denied, credential unavailable, remote unavailable, operation timed out/unknown, partial synchronization, recovery required, and cleanup refused.

Recovery inspects actual repository/worktree state before retrying. It does not assume a timed-out Git operation did not happen. Interrupted multi-file export must be detectable and recoverable without presenting a mixed generation as current.

## 11. Required tests

- Two independent worktrees from one base do not interfere.
- Concurrent updates to one worktree reject stale revisions.
- Repeated idempotent requests do not duplicate effects; conflicting idempotency-key reuse is rejected.
- Handles from another repository or external scope are rejected.
- Path traversal, symlink escape, nested repository substitution, and forged handles are rejected.
- External IDE edits are detected before import/export/commit.
- A semantic snapshot and exported tree with mismatched hashes cannot be committed as verified.
- A successful commit contains the exact canonical LLMLang representation and selected regular-file changes in one Git tree.
- A semantic-only Change Set is materialized into a selected worktree and persisted in Git before it is reported as committed.
- A Git merge tree is not finalized as an LLMLang merge until semantic import/reconciliation and validation succeed.
- Crash recovery after Git ref update but before Toolchain finalization recognizes and finalizes the existing matching commit without creating a duplicate.
- Timeout after a successful Git action is reconciled by operation inspection.
- Cleanup refuses to remove an unowned or protected worktree.
- MCP reconnect preserves durable operation and worktree identity.
- Credentials never appear in tool output, prompts, artifacts, or ordinary logs.
- An operation not granted by the capability lease is rejected.

## 12. Implementation sequence

1. Specify transport-neutral Repository/Worktree domain operations and schemas.
2. Implement repository/worktree handles and ownership checks.
3. Add status/diff/base inspection and external-edit detection.
4. Add isolated worktree create/list/remove with stale-state and cleanup protections.
5. Add deterministic semantic import/export and reconciliation.
6. Add commit preparation and explicit authorization for local commit.
7. Expose bounded operations through MCP.
8. Connect RT-20 validation evidence to commit candidates.
9. Add recovery and adversarial contract tests before enabling concurrent AIVibeFlow jobs.

The first vertical slice should support one repository, two isolated worktrees, semantic inspection, diff/status, and safe cleanup. Do not begin with unrestricted remote administration or a generic Git tool.

## 13. Open questions

1. Which local Git implementation/library is acceptable in the trusted Toolchain boundary?
2. Should repository registration be a separate component or part of the initial modular Toolchain?
3. Which remote read operations are required in the first integration slice?
4. Which credential-broker protocol is appropriate when remote authentication is necessary?
5. Which operations may create a local commit, and which require orchestrator authorization?
6. How should submodules, LFS, sparse checkout, and linked worktrees be represented?
7. What retention policy applies to failed, orphaned, and completed worktrees?
8. Which repository identity fields remain stable across URL aliases and remote migrations?

## 14. Research exit criteria

RT-22 is ready for an architectural decision when domain schemas, operation state machine, authorization lease, recovery semantics, and a tested end-to-end LLMLang repository/worktree scenario are specified. A successful MCP demonstration alone is insufficient.

## 15. Cross-project references

AIVibeFlow owns provider selection, language/project routing, process integration, platform-level Git policy, and its native Git tool path for non-LLMLang repositories. See [AIVibeFlow LLMLang MCP Integration](https://github.com/aivibeflow/aivibeflow/blob/main/specs/integrations/LLMLANG-MCP-GIT-WORKSPACE.md).

The shared contract ownership and cross-repository coordination are described there. This document is authoritative only for the LLMLang Toolchain side described above.


## 16. Detailed runtime model

The single-server, shared-semantic-state, versioned-interface-mapping, and incremental multi-worktree model is specified in [RT-23](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md). RT-23 owns those internals; this document owns the external Repository/Worktree/MCP capability contract. In case of overlap, RT-23 refines the internal implementation model while RT-22 remains authoritative for externally observable operation guarantees.


## 17. Related semantic merge and commit documents

Study RT-22 together with:

- [Git Representation and Semantic Merge](../RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) — authoritative research for semantic diff/merge rules, conflict classes, Git driver/mergetool, and repository-level SPG validation.
- [ADR-014](../../../draft/adr/014-git-semantic-merge.md) — proposed architecture for Git-visible source representation and semantic merge.
- [RT-20](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) — caller impact, migration/preservation decisions, hash propagation, and verified completion gates.
- [RT-23](../RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) — single-server runtime, shared semantic state, per-worktree file views, and synchronized commit protocol.
- [RT-19](../RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) — transport-neutral semantic API and snapshot/change-set lifecycle.

Boundary: RT-22 defines how Git/repository/worktree operations are exposed and recovered; it does not redefine semantic merge rules. A Git merge result is not finalized as an LLMLang merge until the repository-wide semantic reconciliation and validation described by the merge document and RT-20 have succeeded. Finalization must use RT-23's synchronized semantic-and-filesystem commit invariant.


## RT-24 relationship

RT-22 owns the externally observable repository/worktree contract. RT-24 owns the candidate semantic representation/diff/merge algorithm; Git operations supply explicit base/ours/theirs trees, and repository-wide semantic validation must precede finalization.


## 18. External orchestrator interoperability contract

This section defines the LLMLang-owned guarantees needed when an external orchestrator such as AIVibeFlow invokes the Toolchain. It refines the Repository/Worktree boundary; it does not redefine the transport-neutral domain API, canonical Tool schemas, or general MCP adapter architecture owned by RT-19.

### 18.1 Capability advertisement and compatibility

The MCP server advertises only capabilities that are implemented and enabled for the connected deployment. Capability discovery must distinguish:

- protocol version from Toolchain API version;
- capability identifier/version from individual input/output schema versions;
- supported behavior from optional behavior;
- configured limits from hard correctness guarantees;
- available operations from operations authorized for the current principal/scope.

The capability descriptor must provide stable identifiers, schema/version references, required scope and authorization class, whether the operation mutates state, idempotency behavior, whether it may be long-running, and the result/recovery mechanism. Exact descriptor and wire schemas remain owned by RT-19.

An orchestrator pins the negotiated capability/schema versions and records the server instance identity with its workflow provenance. An incompatible major version, missing required guarantee, or unknown capability must fail closed. A server upgrade must not silently change the meaning of an already-running operation. Capability refresh affects new bindings; migration of an active binding is explicit.

The server must not advertise a placeholder, experimental, disabled, or unsupported operation as callable. Research candidate names in this document are not evidence of implementation.

### 18.2 Invocation identity and correlation

Every stateful request carries explicit identifiers for all applicable scopes. The logical invocation context includes:

- authenticated principal and delegated capability lease;
- external orchestrator and originating process/Job/Node Execution references;
- repository and worktree handles;
- expected repository baseline and worktree generation;
- semantic snapshot and interface mapping revision when relevant;
- operation ID for continuation/inspection;
- idempotency key for state-changing requests;
- trace/correlation reference.

These fields are typed domain/API inputs or authenticated metadata as defined by RT-19; they must not be smuggled through prompt text or inferred from MCP connection/session identity. The server validates every supplied handle and scope independently. A missing required identity is an invalid request, not permission to use a server-global current repository/worktree.

The server returns stable operation and resource references plus structured status/diagnostic information. Large results are retrieved through bounded reads or Resources. Results identify the exact repository baseline, worktree generation, semantic snapshot, mapping revision, and evidence inputs to which they apply.

### 18.3 Durable operation semantics

For every long-running or externally retriable operation:

1. The server durably records the operation identity, authenticated principal/scope, normalized request identity, idempotency key, preconditions, and initial state before reporting that execution has been accepted.
2. Repeating the same idempotency key with equivalent normalized input returns or references the original operation/result. Reusing the key with different input is rejected.
3. The operation state is queryable independently of the MCP connection and client process.
4. A timeout, transport disconnect, or missing notification means outcome unknown. The caller must inspect the operation before retrying.
5. Cancellation is a request, not proof that side effects have stopped. The final state and any partial effects are reported explicitly.
6. Recovery inspects actual repository refs, worktree generation, exported tree, and semantic state before resuming/finalizing. It must not duplicate an already completed Git effect.
7. Terminal results and evidence remain addressable according to the configured retention policy.

The durable operation state machine and persistence model are owned by RT-19/RT-23. This section defines the externally observable requirements for repository/worktree operations.

### 18.4 State and evidence completeness

The server distinguishes a verified empty result from unavailable, incomplete, stale, or unknown data. In particular:

- An empty dependency/caller set is valid only when the relevant index and analysis coverage are known complete for the exact source snapshot.
- A cached worktree status reports its generation and freshness; stale or unknown freshness is not presented as current.
- A verification result is bound to exact source hashes, mapping revision, toolchain/checker versions, configuration, and relevant environment identity.
- Any change to a hash-relevant input invalidates the affected evidence.
- A partial import/export, interrupted reconciliation, or unknown Git outcome is represented as a recoverable non-success state.
- A Tool/Resource result must not imply semantic acceptance, export, commit, push, or merge merely because an earlier stage succeeded.

The server returns explicit completeness/freshness states (including unknown where appropriate), diagnostics, and continuation/reconciliation handles. It must never convert missing index data, timeout, or unavailable analysis into an empty successful result.

### 18.5 Events and notifications

MCP notifications or progress events may reduce polling latency, but they are hints that an operation or resource may have changed. They are not the durable source of truth and are not proof of successful completion.

The operation record remains authoritative. A client that disconnects, misses notifications, or restarts must recover by inspecting known operation IDs and reconciling the current state. If event sequence/cursor support is implemented, cursors are scoped and replayable; a gap is reported and can be repaired by operation inspection or bounded reconciliation.

The Toolchain does not assume that an orchestrator remains connected or that a notification is delivered exactly once. Event transport details are optional capabilities and must be advertised explicitly.

## 19. Cross-project integration contract tests

These tests validate the LLMLang side of the AIVibeFlow integration. They complement the local repository/worktree tests in Section 11 and the Toolchain lifecycle tests in RT-19/RT-23.

| ID | Scenario | Required LLMLang behavior |
|---|---|---|
| ORCH-01 | Client discovers capabilities | Advertise only enabled/implemented capabilities with stable version/schema identifiers |
| ORCH-02 | Client pins a supported contract | Existing operations retain their negotiated semantics across reconnect |
| ORCH-03 | Client requests unsupported major/schema version | Return a typed compatibility failure without executing the operation |
| ORCH-04 | Two orchestrator Jobs share one server | Enforce independent principals, grants, worktree handles, and operation scopes |
| ORCH-05 | Request omits required repository/worktree identity | Reject; never fall back to implicit server-global selection |
| ORCH-06 | Same idempotency key and equivalent request is repeated | Return the original operation/result without duplicate effects |
| ORCH-07 | Same idempotency key is reused with different input | Reject the conflicting reuse |
| ORCH-08 | Client disconnects after operation acceptance | Operation remains inspectable and recoverable by durable ID |
| ORCH-09 | Notification is lost or duplicated | Operation inspection returns authoritative state; no duplicate side effect |
| ORCH-10 | Dependency/index data is missing | Return incomplete/unknown, never a successful empty dependency result |
| ORCH-11 | Worktree File View is stale or catching up | Expose freshness/generation and do not claim current status |
| ORCH-12 | Verification inputs change after success | Mark affected evidence stale and prevent its use for commit finalization |
| ORCH-13 | Git ref update succeeds but response is lost | Reconcile the actual ref/tree and finalize the existing matching commit without duplication |
| ORCH-14 | Grant expires or is revoked during operation | Enforce the documented authorization boundary and report partial/final outcome accurately |
| ORCH-15 | Cancellation races with completion | Report the actual terminal state and any completed side effects |
| ORCH-16 | Server restarts with pending operations | Recover or expose an explicit recoverable state; never silently drop accepted work |

The tests must run through an independent MCP client as well as direct Toolchain API tests. Passing a transport-level MCP smoke test is insufficient: assertions must cover repository identity, authorization, durable state, semantic/file consistency, and recovery.

The tests are proposed requirements and do not imply that the capabilities or implementation currently exist.
