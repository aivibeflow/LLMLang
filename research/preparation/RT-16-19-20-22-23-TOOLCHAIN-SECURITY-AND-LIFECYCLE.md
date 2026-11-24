# Research Preparation — RT-16/19/20/22/23 Toolchain Security and Lifecycle

**Status:** Prepared; not executed.  
**Priority:** P0 — parallel work where independent of the semantic gate.  
**Related open questions:** LL-023, LL-024; RT-14, RT-16, RT-17, RT-19, RT-20, RT-22 and RT-23.

## 1. Objective

Prepare an end-to-end lifecycle study for a persistent Toolchain Server and external workflow clients. Validate plan-before-mutation, durable workspaces/change sets, authorization, concurrency, recovery, worktree isolation and exact-tree Git commit behavior under adversarial and interrupted operations.

The LLMLang Toolchain owns the transport-neutral semantic/workspace contract. An external orchestrator may request operations but must not become the source of semantic truth or bypass the authorization and validation gates.

## 2. Required documents

Read as one cluster:
- [RT-19 Toolchain Server and semantic development API](../toolchain-and-collaboration/RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md)
- [RT-20 LLM patch planning and hash propagation](../toolchain-and-collaboration/RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)
- [RT-22 Git repository/worktree MCP surface](../toolchain-and-collaboration/RT-22/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md)
- [RT-23 single-instance and multi-worktree model](../toolchain-and-collaboration/RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md)
- [RT-24 semantic merge and identity reconciliation](../toolchain-and-collaboration/RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md)
- [RT-16 threat model](../security/RT-16/RT-16-THREAT-MODEL-01.md)
- [Draft Glossary](../../draft/GLOSSARY.md) before altering identity-bearing operation or evidence records.

## 3. Questions

### API and durable state
- Which operations are read-only, transactional, durable, cancellable or idempotent?
- What are the exact state machines for Snapshot, Workspace, Change Set, Change Impact Plan, candidate and commit?
- Which operations use optimistic concurrency/CAS and what is the conflict behavior?
- How are requests deduplicated after timeout/retry?
- Which state survives restart, restore and failover?

### Authorization and trust
- Who may inspect, plan, mutate, approve, accept, commit, push, publish and revoke?
- Are authority grants scoped by repository, worktree, path, operation and time?
- Can an agent alter an approved plan, forge evidence or bypass server-side completeness?
- How are credentials isolated from builds and untrusted code?
- How are evidence producer, checker, reviewer and policy identities authenticated?

### Multi-worktree behavior
- Which state is shared across worktrees and which is worktree-local?
- How are File Views and Mapping Revisions versioned?
- How do event journals detect gaps and trigger bounded reconciliation?
- Can one worktree's file event or authorization grant affect another?
- What happens under simultaneous edits, stale mappings, restore and concurrent commits?

### Git completion
- Is the committed tree exactly the tree whose validation passed?
- Are semantic snapshot and mapping revision pinned with the regular-file tree?
- How are concurrent HEAD/ref changes detected?
- Can retry after crash create duplicate or partially staged commits?
- Is remote push always separate from local commit authorization?

## 4. Adversarial and failure-injection scenarios

Prepare deterministic scenarios for:
1. unauthorized read, plan, mutation, approval, accept, commit, push and publication;
2. path traversal, symlink escape, cross-worktree access and credential leakage;
3. a stale Change Impact Plan after source, dependency or mapping change;
4. incomplete reverse references and an omitted caller;
5. concurrent mutation after approval but before validation;
6. crash before/after durable mutation, validation, commit object creation and ref update;
7. timeout followed by retry with the same idempotency key;
8. two clients modifying the same workspace or mapping key;
9. file watcher event loss, duplicate and reordering;
10. restore from a stale snapshot while newer durable operations exist;
11. malicious build worker attempting network, filesystem or process escape;
12. policy revocation during a long-running operation;
13. merge conflict resolution that attempts to drop an unresolved semantic conflict.

For every scenario record actor, grant, resource scope, pre-state, injected failure point, expected state, observable response and recovery procedure.

## 5. Proposed method

- Define state machines and API invariants before building the fault harness.
- Test authorization at the server boundary, not only in client wrappers.
- Use multiple persistent clients and independent worktrees.
- Inject process termination and storage faults around every durable transition.
- Compare recovered state with an independent event-log oracle.
- Test idempotency and concurrency separately from semantic correctness.
- Run hostile workers in the declared sandbox and inspect actual OS-level enforcement.
- Verify that no commit can be produced from a tree other than the exact validated candidate.

## 6. Exit criteria

- All state-changing operations have explicit authorization, durability, idempotency and concurrency semantics.
- A retry or restore cannot duplicate, lose or misapply a completed operation.
- Cross-worktree isolation is demonstrated under concurrent clients and event loss.
- Incomplete semantic impact or untrusted evidence blocks approval/commit.
- Crash/fault injection covers all durable boundaries.
- Sandbox claims are backed by hostile-worker tests on named operating systems.
- Commit identity binds the exact semantic snapshot, mapping revision, regular-file tree and validation evidence.
- Push and publication require separate explicit authority.

This study validates only the declared API/OS profile. It does not authorize automatic agent acceptance or define the final external MCP transport schema.
