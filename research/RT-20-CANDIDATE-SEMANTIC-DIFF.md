# RT-20 — Candidate semantic diff and CIP enforcement

**Status:** Extended narrow prototype implemented; PR #17 merged; 83 semantic-dependency tests and compilation, repository-structure checks, and strict QF_LIA checks passed on the merge commit.  
**Date:** 2026-11-18  
**Parent:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)  
**Related gates:** [Candidate call-site validation](RT-20-CANDIDATE-CALL-SITE-VALIDATION.md), [Candidate graph audit](RT-20-CANDIDATE-GRAPH-AUDIT.md)

## Purpose

The selection-level diff introduced in PR #16 compared logical selections and explicit call-site targets against the supplied CIP. This extension closes several audit-binding gaps: the plan identity is recomputed, both baseline and candidate dependency graphs must pass structural audit, and the resulting diff is bound to both graph and edge-set digests.

## Implemented interface

`src/candidate_semantic_diff.py` exposes:

```python
audit_candidate_semantic_diff(store, baseline, candidate, plan) -> CandidateSemanticDiffResult
```

The result contains exact baseline/candidate roots, plan ID, selection changes, semantic edge changes, both graph digests, both edge-set digests, a deterministic diff digest, and sorted diagnostics.

## Checks

1. Recompute each Snapshot root from its selection rows and parent roots; malformed or duplicate logical keys fail closed.
2. Recompute the canonical `ImpactPlan.plan_id` projection and reject mutated or forged plan contents.
3. Run the candidate graph audit for both baseline and candidate. Both must be valid and bound to the exact supplied Snapshot roots.
4. Derive added, removed, and changed selections by exact logical selection key and Content Hash.
5. Require every changed selection to be covered by a CIP action whose artifact hash is exactly the old or new selected hash.
6. Independently scan baseline-selected explicit declarations for incoming call-site targets to changed old hashes. Every such edge must have a corresponding exact CIP decision, even if its caller is preserved unchanged.
7. Compare typed references and call-site targets for every changed logical selection. Typed-reference changes, call-site additions/removals, and call-site condition changes fail closed because the current CIP schema has no exact output record for them.
8. Require each changed call target's decision to match the observed old target, observed new target, and resulting caller output slot. A matching `REWRITE_CALL_SITE` action must name the exact source caller hash.
9. Resolve unknown caller/callee hashes through exact output IDs against the candidate Snapshot. Bind the resulting output IDs, logical keys, and exact Content Hashes into the diff receipt. Reuse candidate call-site materialization validation for exact baseline/candidate membership, stored object hashes, and candidate payload target checks.
10. Bind both Snapshot roots, plan ID, graph digests, edge-set digests, schema version, selection changes, and edge changes into the deterministic diff digest.

## Tests

The focused suite covers:
- exact-hash action coverage and unplanned selection changes;
- added and removed logical selections;
- changed call target with matching and missing decisions;
- changed callee with an unchanged caller requiring explicit PRESERVE;
- omission of an incoming decision;
- mismatched selected callee;
- malformed Snapshot input;
- typed-reference additions/rewrites with exact CIP records;
- forged plan ID rejection;
- deterministic digest and graph/edge-set bindings.

## Scope and limitations

This remains a narrow explicit-declaration structural audit, not a complete semantic equivalence proof.

- Exact old/new hash presence in an action does not prove that action kind, rationale, prerequisites, or execution evidence are semantically sufficient.
- The independent incoming-call scan uses the same Content Store and declaration payloads; it is not an independent trust domain.
- Dynamic dispatch, reflection, callbacks, generated code, external calls, and omitted declarations remain outside scope.
- Added/removed call-site target identities and condition changes are rejected until the CIP schema can represent them exactly.
- Typed-reference changes are detected and rejected; they are not yet reconciled to typed CIP output records.
- The current plan model still cannot represent one shared caller forked into multiple consumer/path-specific versions.
- MIGRATE/ADAPT/FORK behavioral compatibility remains a separate contract/test/proof obligation.
- The gate is not commit authorization. Snapshot immutability, transaction/concurrency protection, exact-tree commit, crash recovery, and idempotent retry remain future work.

A successful result means only that the supported explicit selection and edge changes are reconciled with the supplied CIP and both audited graph states. It does not prove behavior or whole-program dependency completeness.


## CIP schema v2 — output and edge records (PR #23)

The new planning model distinguishes the immutable approved plan from exact output hashes that may not exist until implementation:

- `PlannedOutput` identifies one logical selection slot and an `ADD`, `REPLACE`, or `REMOVE` operation. It binds the exact base/source hash, output kind, rationale/evidence identity, and a SHA-256 digest of the canonical non-edge declaration payload `{declaration_id, content}`.
- `PlannedEdgeChange` binds a typed-reference or call-target `ADD`, `REMOVE`, `REWRITE`, or `CONDITION` operation, including both old/new relation, target hash, and condition.
- `CallSiteDecision` may bind selected callee and resulting caller hashes directly, or refer to `selected_output_id` / `resulting_output_id` when those hashes are not known at planning time.
- `consumer_path_id` distinguishes separate versions of one shared caller. An output slot records its source hash and consumer path; the corresponding decision binds to that exact slot.
- All records are included in the canonical CIP identity. The semantic-diff receipt binds every materialized output ID to the actual candidate Content Hash and candidate Snapshot root.

The payload digest is a planning constraint, not an object Content Hash, operation hash, or glossary `CCHash`. The actual candidate Content Hash is computed by the Content Store and appears only in the materialization binding after the candidate exists. No identity term in the glossary is redefined here.

The focused tests cover declaration add/remove/replace, typed-reference additions, call-target additions/removals/rewrites/condition changes, hash resolution through output slots, and a shared caller fork where one upstream consumer preserves the old caller while another migrates to a new caller version.

## Remaining limitations

- Action-kind, prerequisite, and evidence adequacy are not yet reconciled comprehensively against every output/edge operation.
- The explicit declaration projection is not proven complete for runtime dispatch, reflection, callbacks, generated code, or external calls.
- Compatibility evidence is bound by ID but not authenticated or independently proven.
- The gate does not execute all planned actions, prove behavioral equivalence, freeze a transaction, or authorize a Git commit.
