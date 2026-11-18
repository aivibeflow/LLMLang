# RT-22 — LLMLang Git Repository and Worktree MCP Surface

**Status:** Research proposal; not an accepted architecture decision  
**Date:** 2026-11-18

## 1. Purpose and scope

Define the LLMLang side of an integration in which AIVibeFlow delegates repository and worktree mechanics for LLMLang projects to the LLMLang Toolchain through MCP, while using its native Git tools for other programming languages.

This document is the sole source of truth in LLMLang for the LLMLang-owned Git/MCP contract. AIVibeFlow's provider selection, orchestration, platform policy, and native Git path are specified only in the AIVibeFlow integration document. That document references this one for LLMLang-side behavior.

## 2. Relationship to existing work

This proposal extends, but does not replace:

- [RT-19 — Toolchain Server and Semantic Development API](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md): transport-neutral Toolchain API, MCP adapter, Workspace/Change Set/Snapshot lifecycle, authorization, recovery, and repository synchronization.
- [RT-20 — LLM Patch Planning and Hash Propagation](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md): complete impact planning and validation-gated semantic changes.
- [RT-21 — LLMLang Self-Development](RT-21-LLMLANG-SELF-DEVELOPMENT-AND-BOOTSTRAP-ROADMAP.md): use of AIVibeFlow as a development environment for LLMLang.

RT-19 remains the broader Toolchain architecture proposal. RT-22 narrows the repository integration question and adds an explicit external-orchestrator boundary. [RT-23 — Single-Instance Toolchain with Shared Semantic State and Incremental Multi-Worktree File Views](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) is authoritative for the detailed runtime model: shared immutable semantic objects, versioned interface mappings, one server instance, and incremental per-worktree file views. ADR-015 remains Proposed; neither research document accepts it.

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

The single-server, shared-semantic-state, versioned-interface-mapping, and incremental multi-worktree model is specified in [RT-23](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md). RT-23 owns those internals; this document owns the external Repository/Worktree/MCP capability contract. In case of overlap, RT-23 refines the internal implementation model while RT-22 remains authoritative for externally observable operation guarantees.


## 17. Related semantic merge and commit documents

Study RT-22 together with:

- [Git Representation and Semantic Merge](GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) — authoritative research for semantic diff/merge rules, conflict classes, Git driver/mergetool, and repository-level SPG validation.
- [ADR-014](../docs/adr/014-git-semantic-merge.md) — proposed architecture for Git-visible source representation and semantic merge.
- [RT-20](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) — caller impact, migration/preservation decisions, hash propagation, and verified completion gates.
- [RT-23](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) — single-server runtime, shared semantic state, per-worktree file views, and synchronized commit protocol.
- [RT-19](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) — transport-neutral semantic API and snapshot/change-set lifecycle.

Boundary: RT-22 defines how Git/repository/worktree operations are exposed and recovered; it does not redefine semantic merge rules. A Git merge result is not finalized as an LLMLang merge until the repository-wide semantic reconciliation and validation described by the merge document and RT-20 have succeeded. Finalization must use RT-23's synchronized semantic-and-filesystem commit invariant.
