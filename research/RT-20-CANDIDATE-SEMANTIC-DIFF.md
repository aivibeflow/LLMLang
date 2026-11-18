# RT-20 — Candidate semantic diff and CIP enforcement

**Status:** Narrow prototype implemented; CI validation pending.  
**Date:** 2026-11-18  
**Parent:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)  
**Related gates:** [Candidate call-site validation](RT-20-CANDIDATE-CALL-SITE-VALIDATION.md), [Candidate graph audit](RT-20-CANDIDATE-GRAPH-AUDIT.md)

## Purpose

The candidate graph audit establishes structural consistency of the candidate's explicit dependency closure. The call-site validator checks materialized decision rows. Neither, by itself, compares every logical selection change with the approved Candidate Impact Plan (CIP). This gate derives that diff from the exact baseline and candidate Snapshots and rejects changes that cannot be reconciled with the supplied plan.

## Implemented interface

`src/candidate_semantic_diff.py` exposes:

```python
audit_candidate_semantic_diff(store, baseline, candidate, plan) -> CandidateSemanticDiffResult
```

The result binds the exact baseline root, candidate root, plan ID, sorted selection changes, a deterministic diff digest, and sorted diagnostics.

## Checks

1. Recompute each Snapshot root from its selection rows and parent roots; malformed or duplicate logical keys fail closed.
2. Derive added, removed, and changed selections by exact logical selection key and exact Content Hash.
3. Require every changed selection to be covered by a CIP action whose artifact hash is exactly the old or new selected hash.
4. Independently scan all baseline-selected explicit declarations for incoming call-site targets to changed old hashes. Every such edge must have a corresponding exact CIP decision, even if the caller is preserved unchanged in the candidate.
5. For changed caller selections, compare explicit call-site/target identities and exact target hashes. Changed targets require a matching decision; added/removed call-site target identities fail closed because the current decision model cannot represent their disposition.
6. Require each changed edge's decision to match the observed old target, observed new target, and resulting caller hash.
7. Reuse candidate call-site materialization validation for exact baseline/candidate membership, stored object hashes, and candidate payload target checks.
8. Bind the deterministic diff digest to both Snapshot roots and the plan ID.

## Tests

The focused suite covers:
- changed selection with exact action coverage;
- unplanned selection mutation;
- added and removed logical selections;
- changed call target with a matching decision;
- changed target without a decision;
- changed callee with an unchanged caller requiring an explicit PRESERVE decision;
- omission of that incoming decision;
- mismatch between the planned selected callee and observed candidate target;
- deterministic diff digest and exact root/plan bindings.

## Scope and limitations

This is a selection-level diff and explicit-call-site CIP enforcement prototype, not a complete semantic equivalence proof.

- An action's exact old/new hash binding proves only that the changed selection is named by an action. It does not prove that the action kind, rationale, prerequisites, or execution evidence are semantically sufficient.
- Incoming call-site completeness is independently reconstructed only from the baseline Snapshot's explicit declaration payloads. Dynamic dispatch, reflection, callbacks, generated code, external calls, and omitted declarations remain outside scope.
- Added/removed call-site target identities are rejected rather than guessed. The current CIP model needs an explicit decision representation for those operations.
- The current model still cannot represent one shared caller forked into multiple consumer/path-specific versions.
- The gate does not prove that MIGRATE, ADAPT, or FORK is behaviorally compatible; contracts, tests, proofs, and evidence validity remain separate obligations.
- It is not commit authorization. Snapshot immutability, transaction/concurrency protection, exact-tree commit, crash recovery, and idempotent retry remain future work.

A successful result means only that the explicit selection diff and call-site changes observed within this prototype's scope are reconciled with the supplied CIP records.
