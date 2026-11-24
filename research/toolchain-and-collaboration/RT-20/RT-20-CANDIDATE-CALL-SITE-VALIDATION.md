# RT-20 — Candidate call-site validation

**Status:** Narrow prototype implemented; the candidate graph audit is tracked separately in [RT-20 Candidate Graph Audit](RT-20-CANDIDATE-GRAPH-AUDIT.md).  
**Date:** 2026-11-18  
**Parent:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)

## Purpose

**Contract terminology:** The call-site's `required_contract_hash` and the callee-owned `provides_contract` are generic exact Contract-object hashes. They are not `CCHash` values. This validator checks their structural bindings only; it does not prove compatibility between distinct Contract values. See [RT-20 Contract Identity and Compatibility](RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md).

The per-call-site planner records intended callee and caller hashes. That record alone does not establish that those objects exist in the candidate Snapshot or that the resulting caller actually contains the selected reference. This prototype adds a materialization gate between planning and later semantic validation.

## Implemented check

`src/candidate_validation.py` provides `validate_candidate_call_site_decisions`. It receives the Content Store, exact baseline and candidate Snapshots, and an `ImpactPlan`. It returns a structured result bound to both Snapshot roots and the plan ID.

For each planned call-site decision it checks:

1. The plan's baseline and candidate roots match the supplied Snapshots.
2. The original caller and callee are selected by the baseline Snapshot.
3. The selected callee and resulting caller are selected by the candidate Snapshot.
4. The stored caller and callee hashes recompute from their canonical semantic-value envelope.
5. The baseline caller declaration contains the exact call-site and target IDs and the decision preserves that site's exact required Contract hash.
6. The baseline callee resolves to exactly one provided Contract through its own declaration; the decision does not duplicate that Contract reference.
7. The candidate caller declaration retains the same required Contract hash at that call site.
8. The target at that call site points to the exact selected callee hash; the validator resolves and validates the selected callee's own provided-Contract reference.
9. `PRESERVE` retains the exact original callee hash and caller-required Contract hash; the caller may still receive a new version because of other planned changes.
10. `MIGRATE`, `ADAPT`, and `FORK` materialize a new caller version.
11. Resolved decisions carry a recorded compatibility status and evidence ID; this validator checks the recorded bindings but does not authenticate or prove the evidence. A `PROVEN` value is therefore an untrusted assertion, not a conclusion of this validator.
12. An unresolved decision cannot validate a candidate.

The check accumulates deterministic diagnostics and fails closed. It verifies the decision against the actual baseline call-site/target as well as the candidate reference. The focused tests cover successful migration, adapt/fork dispositions, wrong baseline/candidate target bindings, callee absent from candidate selection, preservation across caller re-versioning, unresolved decisions, and candidate-root mismatch. The last confirmed CI run passed all 57 tests and module compilation; the subsequent preserve-semantics refinement and added adapt/fork test still require a fresh confirmed run. The semantic dependency CI workflow now runs these tests and compiles the new module.

## Scope and limitations

This is a materialized-reference and caller-requirement consistency check for the current explicit declaration subset. The provided Contract is reached only through the selected callee's own declaration (`caller -> callee -> contract`); the plan and call edge do not store a second provided-Contract reference. It does **not** prove behavioral compatibility, authenticate or independently validate compatibility evidence, prove that an adapter or fork implements its rationale, validate upward contract propagation, discover omitted or dynamic call sites, establish global dependency completeness, or authorize a commit. A valid result means only that the supplied decisions agree with the exact stored objects and explicit references in the supplied candidate Snapshot.

This validator also assumes one resulting caller version per base caller hash across its decisions. It does not yet represent a single shared caller being forked into multiple context-specific versions for distinct upstream consumers. That requires an explicit consumer/path identity in the plan model; the existing shared-caller examples use distinct caller objects and do not prove this harder split case.

The candidate Snapshot is assumed to be immutable for the duration of this check. A production implementation must bind the validation result to the frozen candidate root and invalidate it on any candidate change. The current in-memory Content Store prototype does not provide a transaction or concurrency lease.

## Next gate

1. Bind validation to the complete CIP and require exact decision coverage from the baseline reverse-index audit, not merely the decision rows supplied to this validator.
2. [Implemented as a separate prototype] Verify all candidate Snapshot references resolve and recompute the full dependency index from candidate payloads; see [RT-20 Candidate Graph Audit](RT-20-CANDIDATE-GRAPH-AUDIT.md).
3. Compare the actual candidate semantic diff against the approved plan and reject unplanned changes or omitted planned changes.
4. Add mixed old/new, shared-caller split, multi-call-site, and branching/converging graph end-to-end scenarios.
5. Only after these checks, design the frozen-candidate verification and commit gate with RT-19/RT-22/RT-23 concurrency and recovery semantics.

This prototype is not a canonical SPG schema, production Toolchain implementation, or proof of program correctness.

## Public-interface integration (2026-11-24; proposed)

A future public-operation mode must resolve an exact operation and provider binding, preserve the existing direct-call mode, check the single callee-owned provided Contract and validate exact body/refinement evidence plus target/profile constraints. Add negative cases for missing, stale or wrong-kind catalog/provider/evidence references, signature-only matching and an invalid stronger precondition. The current structural validator does not implement these obligations.

Related: [Public interfaces and verified contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This follow-up does not change earlier results or accepted rules.
