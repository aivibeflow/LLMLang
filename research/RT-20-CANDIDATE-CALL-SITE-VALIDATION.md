# RT-20 — Candidate call-site validation

**Status:** Narrow prototype implemented; focused CI passed (57 tests).  
**Date:** 2026-11-18  
**Parent:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)

## Purpose

The per-call-site planner records intended callee and caller hashes. That record alone does not establish that those objects exist in the candidate Snapshot or that the resulting caller actually contains the selected reference. This prototype adds a materialization gate between planning and later semantic validation.

## Implemented check

`src/candidate_validation.py` provides `validate_candidate_call_site_decisions`. It receives the Content Store, exact baseline and candidate Snapshots, and an `ImpactPlan`. It returns a structured result bound to both Snapshot roots and the plan ID.

For each planned call-site decision it checks:

1. The plan's baseline and candidate roots match the supplied Snapshots.
2. The original caller and callee are selected by the baseline Snapshot.
3. The selected callee and resulting caller are selected by the candidate Snapshot.
4. The stored caller and callee hashes recompute from their canonical semantic-value envelope.
5. The candidate caller declaration contains the exact call-site and target IDs.
6. The target at that call site points to the exact selected callee hash.
7. `PRESERVE` retains the exact original callee hash at that call site; the caller may still receive a new version because of other planned changes.
8. `MIGRATE`, `ADAPT`, and `FORK` materialize a new caller version.
9. An unresolved decision cannot validate a candidate.

The check accumulates deterministic diagnostics and fails closed. It verifies the decision against the actual baseline call-site/target as well as the candidate reference. The focused tests cover successful migration, wrong baseline/candidate target bindings, callee absent from candidate selection, preservation, unresolved decisions, and candidate-root mismatch. The semantic dependency workflow passed all 57 tests and module compilation. The semantic dependency CI workflow now runs these tests and compiles the new module.

## Scope and limitations

This is a materialized-reference consistency check for the current explicit declaration subset. It does **not** prove behavioral compatibility, prove that an adapter or fork implements its rationale, validate contract propagation, discover omitted or dynamic call sites, establish global dependency completeness, or authorize a commit. A valid result means only that the supplied decisions agree with the exact stored objects and explicit references in the supplied candidate Snapshot.

The candidate Snapshot is assumed to be immutable for the duration of this check. A production implementation must bind the validation result to the frozen candidate root and invalidate it on any candidate change. The current in-memory Content Store prototype does not provide a transaction or concurrency lease.

## Next gate

1. Bind validation to the complete CIP and require exact decision coverage from the baseline reverse-index audit, not merely the decision rows supplied to this validator.
2. Verify all candidate Snapshot references resolve and recompute the full dependency index from candidate payloads.
3. Compare the actual candidate semantic diff against the approved plan and reject unplanned changes or omitted planned changes.
4. Add mixed old/new, shared-caller split, multi-call-site, and branching/converging graph end-to-end scenarios.
5. Only after these checks, design the frozen-candidate verification and commit gate with RT-19/RT-22/RT-23 concurrency and recovery semantics.

This prototype is not a canonical SPG schema, production Toolchain implementation, or proof of program correctness.
