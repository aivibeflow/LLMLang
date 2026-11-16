# Scenario Study 02: Concurrent Changes and Conflict Resolution

**Date:** 2026-11-16  
**Status:** Research result / proposed design, not an accepted LLMLang decision  
**Scope:** Concurrent Change Sets, optimistic concurrency, semantic conflicts, merge, approval binding, and atomic acceptance

## 1. Question

Two or more agents or developers work from the same accepted SPG snapshot. They independently propose changes. How can LLMLang accept compatible work without overwriting changes, while preventing semantically incompatible changes from being merged merely because their text or graph locations differ?

This is not only a source-control problem. Two changes can:
- edit the same semantic object;
- edit different objects but violate a shared invariant;
- alter a requirement and its implementation independently;
- change a public interface and a dependent implementation;
- be textually disjoint but semantically incompatible.

The system must distinguish mechanical mergeability from semantic compatibility and authorization.

## 2. Evidence from related projects

### 2.1 linkly: proposals, review, idempotency, and task lifecycle

The inspected accepted Agent Protocol RFC establishes a proposal-only mutation model: `ir.propose` creates a pending proposal and review task; it does not directly mutate the accepted IR. A Reviewer approves or rejects the proposal, after which the server merges the fragment and validates the merged result.

The protocol also requires idempotency keys for side-effecting proposal/dispatch calls. Repeating a request with the same key returns the original logical result; reusing the key with different parameters is an error. This prevents retries from creating duplicate proposals.

RFC-0010 adds explicit proposal intent such as `attach` and `move`, and asks the reviewer to validate invariants on the merged graph rather than infer intent from a surface diff. It is especially relevant to graph changes where removal and relocation can look identical in a naïve diff.

**What it does not fully establish for LLMLang's purposes:** the reviewed material does not show an approval token cryptographically or content-addressably bound to the complete proposal plus exact baseline and transitive semantic dependency closure. The protocol's proposal/review boundary is valuable, but approval freshness and baseline conflict semantics still need to be made explicit.

Sources:
- [linkly RFC-0006 Agent Protocol](https://github.com/choiyounggi/linkly/blob/main/rfcs/0006-agent-protocol.md)
- [linkly RFC-0010 Proposal Intent](https://github.com/choiyounggi/linkly/blob/main/rfcs/0010-proposal-intent.md)

### 2.2 Edict: structured patching and dependency-based invalidation

Edict's patch engine addresses AST nodes by `nodeId`, applies a patch batch to a cloned AST, and reports structured failures rather than exposing a partially mutated successful result. Its structural diff identifies changed definitions and its dependency graph computes transitive dependents for incremental contract verification.

However, the inspected patch API does not require an expected Content Hash for each target or an expected baseline root. Its dependency graph is keyed by definition names, and structural diff compares definitions by name. This supports incremental analysis but is not, by itself, a concurrency-control protocol.

Lesson: a structured patch API is not optimistic concurrency control unless it validates the version/state the author observed.

Sources:
- [Edict patch engine](https://github.com/Sowiedu/Edict/blob/main/src/patch/apply.ts)
- [Edict structural diff](https://github.com/Sowiedu/Edict/blob/main/src/incremental/diff.ts)
- [Edict dependency graph](https://github.com/Sowiedu/Edict/blob/main/src/incremental/dep-graph.ts)

### 2.3 Existing LLMLang proposal

`RFC-REQUEST-CHANGE.md` already proposes:
- Changes against a known graph baseline;
- Change Sets as the default unit of review and atomic acceptance;
- stale-baseline and concurrent conflict detection;
- semantic conflict resolution rather than silent last-writer-wins;
- approvals bound to exact proposal digest and baseline;
- immutable accepted history.

The gap is operational: it does not yet define a sufficiently precise conflict taxonomy, rebase algorithm, conflict-resolution artifact, or the distinction between a merge candidate and an accepted/approved merge.

## 3. Conflict taxonomy

A single boolean `conflict` is too weak. The engine should classify conflicts by the semantic reason they arise.

| Conflict class | Example | Automatic handling |
|---|---|---|
| Same-state write conflict | Two Change Sets modify the same node from the same old hash | Reject direct application; require rebase or explicit resolution |
| Delete/update conflict | One removes a type while another changes its contract | Require explicit resolution |
| Rename/name collision | Two declarations are renamed to the same qualified name | Reject until names/namespace are resolved |
| Structural ownership conflict | Two proposals move one child to different parents | Reject; enforce single-owner invariant |
| Dependency conflict | One changes a provider contract while another relies on the old contract | Revalidate consumer; possibly semantic conflict |
| Invariant conflict | Separate edits jointly violate a global or cross-object invariant | Merged validation must reject |
| Requirement/implementation conflict | One Change Set changes Specification while another implements the old requirement | Rebase and re-evaluate traceability/verification |
| Authorization conflict | A proposal's approval policy or authority assumptions changed | Approval must be reacquired |
| Evidence freshness conflict | Verification evidence was produced against a different graph/toolchain input | Mark stale and rerun or prove reusable |
| Presentation-only overlap | Both change comments or formatting excluded from semantic hash | Merge according to deterministic presentation policy |

Conflict classification is diagnostic. The final decision must be based on graph preconditions, policy, and independent validation—not on an LLM's confidence score.

## 4. Proposed concurrency model

### 4.1 Immutable baseline

Every Change Set records the exact accepted baseline against which it was prepared:

- project snapshot identity;
- relevant layer root hashes;
- target entity Stable IDs and expected Content Hashes;
- any additional semantic dependency pins required by the operation;
- policy/configuration version relevant to validation and approval.

A Change Set must not silently float to the latest head.

### 4.2 Optimistic concurrency at two levels

Use two complementary precondition levels:

1. **Object-level preconditions:** each mutation names the target Stable ID and expected Content Hash (or an explicit expected-absence condition for creation).
2. **Snapshot-level precondition:** the Change Set records the accepted root snapshot from which it was derived.

Object-level checks identify local stale writes. Snapshot-level identity establishes provenance and allows the engine to determine what changed since the proposal was created.

A project may permit safe rebase when unrelated objects changed. That does not erase the original baseline; it creates a new derived proposal/revision with a recorded rebase parent and a new digest.

### 4.3 Proposal is not mutation

The proposal endpoint should be side-effecting only in the sense of creating an immutable proposal record and review task. It must not mutate the accepted graph.

A deterministic merge engine may create a candidate merged graph in an isolated workspace. The candidate remains unaccepted until:
- structural invariants pass;
- semantic validation passes to the policy-required level;
- affected verification obligations are satisfied or explicitly remain UNKNOWN/NOT_CHECKED;
- approvals apply to the exact candidate and baseline;
- the accepted-head compare-and-swap succeeds.

### 4.4 Compare-and-swap at acceptance

Acceptance must be atomic with respect to the current accepted head.

Conceptually:

```text
accept(ChangeSet, expected_head):
    require current_head == expected_head
    require candidate.baseline is valid
    require candidate.validation is current
    require approvals bind to candidate_digest and expected_head
    atomically:
        publish candidate snapshot
        advance accepted_head
        record acceptance event
```

If the accepted head advanced after review, the acceptance attempt fails as stale. The engine must not silently commit the previously reviewed candidate on top of a different head.

A retry requires a new rebase/merge candidate and fresh validation. Approval must be reacquired if the candidate digest, baseline, affected scope, or approval policy changed.

## 5. Rebase and merge procedure

A safe rebase is a derivation, not mutation of the original proposal.

1. Load the original proposal and immutable baseline.
2. Load the current accepted snapshot.
3. Compute the semantic delta from original baseline to current head.
4. Compute the proposal's semantic write set and read/dependency set.
5. Detect overlapping writes, changed read dependencies, structural ownership conflicts, and policy changes.
6. If conflicts are mechanically resolvable under declared rules, produce a candidate merge; otherwise emit typed conflict records.
7. Rebuild the candidate SPG from immutable states; never patch the accepted graph in place.
8. Recompute hashes and dependency closure.
9. Run mandatory structural and semantic checks on the merged candidate.
10. Invalidate/re-evaluate affected verification evidence.
11. Produce a new proposal revision with links to original proposal, rebase base, merge candidate, and conflict resolutions.
12. Review and approve the exact new candidate.
13. Accept only if compare-and-swap against the candidate's expected current head succeeds.

A rebase must preserve the original proposal and approval history. It must not rewrite what the original author proposed or what a reviewer previously approved.

## 6. Read sets, write sets, and semantic dependencies

Object-level write sets alone are insufficient. A proposal can read a constraint or contract without modifying it. If that read dependency changes, the proposal may no longer be valid.

Each Change should declare or allow the engine to derive:

- **Write set:** semantic entities and relations it mutates.
- **Read set:** entities whose current state influenced the proposed operation.
- **Dependency set:** transitive semantic dependencies relevant to validation.
- **Invariant scope:** local or global invariants that must be rechecked.
- **Authority scope:** permissions and policy decisions relied upon.

The engine should distinguish directly edited nodes from read-only dependencies. A changed read dependency does not always make a proposal impossible, but it forces re-evaluation before reuse.

Where dependency discovery is incomplete or conservative, the system should prefer invalidation/revalidation over assuming compatibility.

## 7. Conflict resolution records

A conflict must be an addressable object, not just free-form chat text.

A Conflict Resolution record should include:

- conflict ID and class;
- conflicting Change IDs and exact versions;
- affected Stable IDs and baseline hashes;
- alternatives considered;
- selected resolution or explicit unresolved state;
- author/decision-maker and authority;
- rationale;
- semantic consequences;
- validation obligations;
- links to superseding Change Set revision.

Possible resolutions include:
- accept one side and supersede the other;
- combine both changes into a new Change;
- split a Change Set where atomicity permits;
- alter the design/specification to reconcile both;
- reject both and request clarification;
- defer while keeping the accepted graph unchanged.

An LLM may propose a resolution and explain trade-offs. It cannot manufacture the authority of a human decision or mark an unresolved conflict as resolved.

## 8. Approval binding and idempotency

An approval should bind to a digest that commits to at least:

- exact Change Set revision;
- exact candidate graph/layer root hashes;
- exact baseline/expected accepted head;
- conflict-resolution records;
- validation/evidence summary and relevant tool/policy versions;
- approval scope and required authority.

If any committed field changes, the approval is no longer applicable. The system should request a new approval rather than reinterpret the old one.

Side-effecting API calls that create proposals, reviews, or acceptances should be idempotent. A repeated idempotency key with identical parameters returns the original result; the same key with different parameters is rejected.

## 9. Atomicity and partial progress

The default unit of acceptance remains the Change Set. The engine may perform analysis and prepare candidate artifacts incrementally, but must not publish a partial accepted state unless the Change Set explicitly declares independently acceptable sub-units and project policy permits them.

Atomicity applies to the accepted snapshot pointer and audit record, not necessarily to the internal computation of a candidate. Failed candidate construction or validation leaves the accepted snapshot unchanged.

## 10. Required invariants

Proposed invariants for a future RFC:

1. Every Change Set is bound to an immutable baseline.
2. Every mutation has an explicit target identity and expected prior state or expected absence.
3. The accepted graph is never mutated in place.
4. Two concurrent proposals cannot silently overwrite one another.
5. A merge candidate is not an accepted snapshot.
6. A proposal rebase creates a new immutable revision and preserves its parent history.
7. All semantic conflicts are either resolved by an authorized decision or remain blocking.
8. Merged graph invariants and semantic obligations are checked after merge, not inferred from independently valid branches.
9. Verification evidence is reused only when all declared inputs remain exact or a sound reuse rule proves applicability.
10. Approval is bound to the exact candidate and baseline.
11. Accepted-head advancement is atomic and guarded by compare-and-swap.
12. Stale approval or stale evidence cannot be treated as current success.
13. Idempotent retries cannot create duplicate logical proposals or acceptances.
14. Failed merge/validation/acceptance leaves the prior accepted snapshot unchanged.

## 11. Open questions

1. Should the baseline always be the full project root hash, or can a Change Set pin only a relevant layer/subgraph closure plus a global policy root?
2. How should LLMLang represent read sets for operations whose semantic dependencies are discovered only during validation?
3. Which conflict classes can be auto-resolved deterministically without human approval?
4. Should disjoint Change Sets be batch-accepted in one transaction, or always serialized through accepted-head compare-and-swap?
5. How should global invariants be partitioned for incremental checking without missing cross-module conflicts?
6. Can approval policy be evaluated at proposal time, review time, and acceptance time, and which policy version is authoritative?
7. What is the exact semantics of partial Change Set acceptance, if supported at all?
8. How should long-running verification interact with a head that advances while verification is in progress?

## 12. Preliminary conclusion

The most valuable precedent is linkly's explicit proposal/review boundary, idempotency, and merged-graph invariant checking. Edict demonstrates useful structured patching and dependency invalidation, but its node-targeted patch API is not a concurrency protocol.

LLMLang's existing Request/Change RFC already points in the right direction. The next design increment should make it executable and testable by specifying object/snapshot preconditions, semantic read/write sets, immutable rebase revisions, conflict records, exact approval binding, and accepted-head compare-and-swap.

**Preliminary recommendation:** use optimistic concurrency over immutable graph snapshots, with object-level expected-hash preconditions and atomic accepted-head compare-and-swap. Permit automatic rebase only for provably non-conflicting changes; require fresh validation and approval for every changed candidate. Never use silent last-writer-wins for semantic graph state.

This is a research conclusion, not an accepted change to LLMLang's normative concept or RFCs.

## Sources

- [linkly RFC-0006 Agent Protocol](https://github.com/choiyounggi/linkly/blob/main/rfcs/0006-agent-protocol.md)
- [linkly RFC-0010 Proposal Intent](https://github.com/choiyounggi/linkly/blob/main/rfcs/0010-proposal-intent.md)
- [Edict patch engine](https://github.com/Sowiedu/Edict/blob/main/src/patch/apply.ts)
- [Edict structural diff](https://github.com/Sowiedu/Edict/blob/main/src/incremental/diff.ts)
- [Edict dependency graph](https://github.com/Sowiedu/Edict/blob/main/src/incremental/dep-graph.ts)
- LLMLang internal baseline: `RFC-REQUEST-CHANGE.md`, `RFC-DEVELOPMENT-ENGINE.md`, `LLMLang-CONCEPT.md`, `RESEARCH-DEEP-COMPARISON.md`
