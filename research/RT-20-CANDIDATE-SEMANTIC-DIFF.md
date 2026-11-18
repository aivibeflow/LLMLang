# RT-20 — Candidate semantic diff and CIP enforcement

**Status:** PR #24 merged. Post-merge workflows on merge commit `cf51c15a34cee14a8b0390322be0a15d9ee85559` passed: semantic dependency 101 tests + `py_compile`; repository structure 6 + 78 tests; strict QF_LIA 30 tests + `compileall`. The subsequent documentation-only `main` commit also passed repository-structure CI.  
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
7. Compare typed references and call-site targets for every changed logical selection, including exact old/new relation, target hash, condition, and call-site required Contract hash. Every observed edge delta must match exactly one typed CIP edge-change record.
8. Require each changed call target or required Contract binding to match a path-bound `CallSiteDecision`, including exact old/new required Contract hashes, old/new provided Contract hashes, `PROVEN` compatibility status, and exact caller/callee output slots. A matching `REWRITE_CALL_SITE` action must name the exact source caller hash.
9. Resolve unknown caller/callee hashes through exact output IDs against the candidate Snapshot. Bind materialized output IDs, logical keys, and exact candidate object hashes into the diff receipt. Reuse candidate call-site materialization validation for exact baseline/candidate membership, stored object hashes, and candidate payload/Contract checks.
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
- typed-reference additions/removals/rewrites with exact CIP records;
- call-site required-contract hash changes are included in the edge identity and deterministic diff;
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
- The semantic diff and plan identity preserve the call site's required Contract hash, the baseline callee's provided Contract hash, the selected callee's provided Contract hash, and the compatibility status/evidence ID. The validator checks these exact bindings but does not authenticate the evidence or prove refinement. These generic Contract Content Hashes are not yet normatively equated with glossary `CCHash`.
- MIGRATE/ADAPT/FORK behavioral compatibility remains a separate contract/test/proof obligation.
- The gate is not commit authorization. Snapshot immutability, transaction/concurrency protection, exact-tree commit, crash recovery, and idempotent retry remain future work.

A successful result means only that the supported explicit selection and edge changes are reconciled with the supplied CIP and both audited graph states. It does not prove behavior or whole-program dependency completeness.


## CIP schema v2 — output slots, edge deltas, and caller forks

The planning model distinguishes the approved plan from exact Content Hashes that may not exist until implementation:

- `PlannedOutput` identifies one logical selection slot and an `ADD`, `REPLACE`, or `REMOVE` operation. It binds the exact base/source hash, output kind, canonical non-edge payload digest, rationale, evidence identity, and optional consumer path.
- The payload digest is SHA-256 over canonical `{declaration_id, content}`. Typed references and call-site alternatives are bound separately as edge records.
- `PlannedEdgeChange` binds one exact typed-reference or call-target `ADD`, `REMOVE`, `REWRITE`, or `CONDITION` operation, including old/new relation, target hash, condition, and call-site required Contract hash where applicable.
- `CallSiteDecision` carries exact selected-callee/resulting-caller hashes when known, or `selected_output_id` / `resulting_output_id` when those hashes are not known at planning time. It also binds required/base-provided/selected-provided Contract hashes and a `PROVEN` compatibility status.
- `consumer_path_id` distinguishes separate versions of one shared caller. Multiple output slots can derive from the same source caller hash while selecting different callee versions for different upstream consumers.
- All these records are included in CIP schema v2's canonical plan identity. The semantic-diff receipt resolves output IDs against the candidate Snapshot and binds the actual Content Hashes to the candidate root.

The payload digest is a planning constraint, not an object Content Hash, OpHash, ImplHash, or glossary `CCHash`. The actual candidate object hash is computed by the semantic object store and appears in the materialization binding only after the candidate exists. Its interpretation remains object-kind-specific; this document does not rename or conflate `OpHash`, `ImplHash`, or `CCHash`. See the [LLMLang Glossary](../draft/GLOSSARY.md).

Focused tests cover declaration add/remove/replace, typed-reference additions and rewrites, call-target additions/removals/rewrites/condition changes, required-Contract migration with compatibility evidence, unknown hash resolution, deleted callers, and a shared-caller fork across two consumer paths.

## Remaining limitations

- Action-kind, prerequisite, and evidence adequacy are not yet reconciled comprehensively against every output/edge operation.
- The explicit declaration projection is not proven complete for runtime dispatch, reflection, callbacks, generated code, or external calls.
- Compatibility evidence is bound by ID and required to state `PROVEN`, but the evidence producer and proof are not authenticated or independently checked here.
- The gate does not execute every planned action, prove behavioral equivalence, freeze a transaction, or authorize a Git commit.


## CIP schema v2 — output slots, edge deltas, and caller forks

The planning model distinguishes the approved plan from exact Content Hashes that may not exist until implementation:

- `PlannedOutput` identifies one logical selection slot and an `ADD`, `REPLACE`, or `REMOVE` operation. It binds the exact base/source hash, output kind, canonical non-edge payload digest, rationale, evidence identity, and optional consumer path.
- The payload digest is SHA-256 over canonical `{declaration_id, content}`. Typed references and call-site alternatives are bound separately as edge records.
- `PlannedEdgeChange` binds one exact typed-reference or call-target `ADD`, `REMOVE`, `REWRITE`, or `CONDITION` operation, including old/new relation, target hash, condition, and call-site required Contract hash where applicable.
- `CallSiteDecision` carries exact selected-callee/resulting-caller hashes when known, or `selected_output_id` / `resulting_output_id` when those hashes are not known at planning time. It also binds required/base-provided/selected-provided Contract hashes and a `PROVEN` compatibility status.
- `consumer_path_id` distinguishes separate versions of one shared caller. Multiple output slots can derive from the same source caller hash while selecting different callee versions for different upstream consumers.
- All these records are included in CIP schema v2's canonical plan identity. The semantic-diff receipt resolves output IDs against the candidate Snapshot and binds the actual Content Hashes to the candidate root.

The payload digest is a planning constraint, not an object Content Hash, OpHash, ImplHash, or glossary `CCHash`. The actual candidate Content Hash is computed by the Content Store and appears in the materialization binding only after the candidate exists. No glossary identity term is redefined here.

Focused tests cover declaration add/remove/replace, typed-reference additions and rewrites, call-target additions/removals/rewrites/condition changes, required-Contract migration with compatibility evidence, unknown hash resolution, deleted callers, and a shared-caller fork across two consumer paths.

## Remaining limitations

- Action-kind, prerequisite, and evidence adequacy are not yet reconciled comprehensively against every output/edge operation.
- The explicit declaration projection is not proven complete for runtime dispatch, reflection, callbacks, generated code, or external calls.
- Compatibility evidence is bound by ID and required to state `PROVEN`, but the evidence producer and proof are not authenticated or independently checked here.
- The gate does not execute every planned action, prove behavioral equivalence, freeze a transaction, or authorize a Git commit.


## CIP schema v3 — planned action identity and prerequisite DAG

AEA-1 is implemented in the dependency-graph prototype. CIP schema v3 adds a deterministic `action_id` to each `PlannedAction` and an explicit `prerequisite_action_ids` relation. The action ID commits to the action kind, exact artifact hash, rationale, legacy content-prerequisite hashes, and prerequisite action IDs. The canonical CIP identity includes these action IDs and prerequisite edges.

The validator rejects missing or duplicate action IDs, unknown or duplicate prerequisite IDs, self-dependencies, cycles, and action IDs that do not match their canonical payload. Plan construction assigns IDs to planner-generated actions. The candidate semantic-diff gate recomputes plan identity through the same validation path, so a forged plan ID cannot bypass an invalid action DAG.

The old `prerequisite_hashes` field is retained as a distinct legacy content binding; it is not reinterpreted as an action dependency. Existing plans generated by the planner now use CIP schema v3. This slice validates only action identity and DAG structure: it does not yet define action-kind policy, record execution attempts, validate evidence adequacy, or prove that actions ran. Those are AEA-2 through AEA-5 in [CIP Action Execution Audit](RT-20-CIP-ACTION-EXECUTION-AUDIT.md).


## CIP schema v4 — versioned action-kind compatibility policy

AEA-2 adds an explicit `subject_kind` to every planned action. The field is included in the canonical action payload and therefore changes both `action_id` and the enclosing `plan_id`. The policy version `cip-action-policy/1` is also committed into the canonical plan identity.

The initial closed policy maps the current prototype artifact-kind vocabulary to permitted action kinds: derivation for formal/derived models; test generation and execution for test suites; rebuild and test execution for implementation/build/generated artifacts; reproving for proof artifacts; human review for requirements and intent; exact call-site rewrite for call-site obligations; and conservative review/full revalidation for candidate-level fallback actions. Unknown or empty subject kinds and unsupported action-kind pairs fail closed.

The planner labels its generated actions with their subject kind. The candidate semantic-diff audit independently revalidates the action-kind policy before accepting plan identity. Tests cover representative accepted pairs, incompatible pairs, unknown kinds, and subject-kind identity binding.

**Scope limitation:** this slice validates action-kind versus subject-kind compatibility. It does not yet bind each action to a complete set of exact output/edge obligation IDs, prove prerequisite execution order, or verify that an action ran. The artifact hash is the exact subject binding available in the current model; action-to-output/edge obligation coverage remains a follow-up refinement before AEA-2 can be considered fully closed.
