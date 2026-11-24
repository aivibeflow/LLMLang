# RT-19 — Concurrent workspace CAS and retry boundary recheck

**Research item:** `PLAN.md` §7.6 — Toolchain Server and semantic development API  
**Date:** 2026-11-24  
**Baseline main:** `af1f0cfe121a8ee8ff0a42fe15aa9f4bf3c967f4`  
**Evidence type:** source-bound review plus executable two-workspace checks against Prototype 01  
**Status:** bounded concurrency/idempotency recheck; no persistent coordinator selected  
**Question:** Does the current workspace revision CAS detect concurrent acceptance from a shared base, and does a Change Set identifier make retries idempotent?

## Method and result

I reviewed `InMemoryToolchain.apply`, `accept`, the RT-19 proposal, and the RT-23 concurrency model. I ran a deterministic script using Prototype 01's current source at the pinned main commit. Two workspaces opened from one snapshot, both made changes and both accepted at revision 1. This held both when they added different Stable IDs and when they updated the same Stable ID from the same expected object hash. The resulting accepted snapshot roots differed. The per-workspace revision CAS did not coordinate these separate workspaces.

The prototype accepts a `changeset_id` parameter when proposing, but does not persist a map from that ID to request content or outcome. Reapplying the same Change Set at its original expected revision returns `StaleRevision` after the first apply advances the workspace revision. Thus retry is refused as stale; the prototype does not replay a stored result or distinguish same-key/same-request from same-key/different-request.

The current focused test suite passes 9/9. Its isolation and stale-revision tests confirm those local behaviors, but it contains no durable shared-head or same-base competing-acceptance transaction. The observed result is a limitation of the current in-memory model, not evidence of a defect in any production coordinator.

## Compared concurrency boundaries

| Candidate | Conflict scope | Retry behavior | Fit and limitation |
|---|---|---|---|
| **C-A Per-workspace revision CAS only** | Serializes mutations within one workspace; independent workspaces never contend | Stale revision rejects reapplication; no stored operation result | Useful for isolated Change Set editing and is what Prototype 01 exercises. It cannot alone arbitrate a shared repository head or same-base acceptances. |
| **C-B Shared accepted-head CAS at acceptance** | All acceptances for one repository/snapshot lineage compare the exact expected parent/root; exactly one head advance wins | A durable operation-key table can return the original committed outcome for same-key/same-payload retries and reject key reuse with a different payload | Supplies a narrow acceptance linearization point. It rejects even disjoint concurrent edits until the loser rebases or merges. Persistence and multi-process atomicity are required. |
| **C-C Branch acceptance plus semantic merge** | Each workspace can accept an immutable branch root; conflict is decided when advancing/merging a shared target | Operation result is recorded per branch and merge attempt; retries resolve to the same branch/merge receipt | Preserves parallel work and can merge disjoint changes, consistent with RT-23. Same-object changes require semantic conflict handling; merge completeness and authorization remain separate obligations. |

C-B can be a simple initial policy but trades concurrency for a clear winner. C-C permits more parallel progress but moves correctness into semantic merge, source completeness, and conflict resolution. A practical design can combine them: immutable branch snapshots, exact parent/root CAS for each branch, and a separate CAS-protected merge into the repository target. An actor-scoped operation key should bind repository, workspace/branch, expected revision or parent, operation kind, and canonical request digest; its retention and recovery contract must be durable.

## Decision-relevant conclusion

Do not treat workspace-local revision CAS as global acceptance conflict control, and do not treat an identifier field as idempotency without durable request/outcome binding. For an initial persistent coordinator, compare a strict shared-head CAS against branch acceptance plus merge. Keep the current per-workspace CAS for local mutation ordering. Require stable retry outcomes and reject operation-key reuse with changed request content.

This is a bounded discriminator, not a production architecture selection. RT-23's shared immutable object space and concurrent semantic Change Sets make branch-based work plausible, but those statements are proposal-level. The current prototype result cannot decide whether repository acceptance should be global-head CAS, a branch receipt, or merge-first.

## Reproduction

Run the focused prototype suite:

```sh
python3 -B -m unittest discover \
  -s research/toolchain-and-collaboration/PROTOTYPES/TOOLCHAIN-SERVER-01 \
  -p 'test_toolchain.py' -v
```

Additional same-base check, using `PYTHONPATH=research/toolchain-and-collaboration/PROTOTYPES/TOOLCHAIN-SERVER-01`:

```python
from toolchain import Change, Entity, InMemoryToolchain

tc = InMemoryToolchain()
base = tc.create_snapshot([Entity("x", "value", {"n": 0})])
a, b = tc.open_workspace(base), tc.open_workspace(base)
ca = tc.propose(a.workspace_id, 0, [Change("update", "x", tc.get_entity(base, "x").content_hash, "value", {"n": 1})], changeset_id="op-x")
cb = tc.propose(b.workspace_id, 0, [Change("update", "x", tc.get_entity(base, "x").content_hash, "value", {"n": 2})], changeset_id="op-x")
ra, rb = tc.apply(ca, 0), tc.apply(cb, 0)
assert tc.accept(a.workspace_id, 1) == ra
assert tc.accept(b.workspace_id, 1) == rb
assert ra != rb
```

Observed: both same-base roots are accepted; `ra != rb`. A repeat of `tc.apply(ca, 0)` after its first success raises `StaleRevision` because that workspace is at revision 1.

## Remaining dependencies

- Persistent journal/transaction implementing shared-head CAS or explicit branch receipts and merge CAS.
- Durable idempotency-key scope, canonical request digest, retention, and same/different-payload retry rules.
- Crash/restart and multi-process concurrency tests; deterministic race schedules for two writers.
- Semantic merge contract and complete conflict discovery for disjoint and same-object edits.
- Authorization, provenance, repository scope, and policy for who may accept/merge a branch.
- Maintainer decision on whether acceptance denotes a workspace branch or only advancement of the synchronized repository target.

**Conclusion:** local revision CAS, shared-head acceptance, branch acceptance, and retry idempotency are distinct contracts. The next persistent slice should make those boundaries explicit and test competing writers and retry recovery together.
