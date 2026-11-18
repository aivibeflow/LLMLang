# RT-20 — Candidate Snapshot dependency-closure audit

**Status:** Prototype implemented; PR #16 merged; its PR-head CI checks passed.  
**Date:** 2026-11-18  
**Parent:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)  
**Related gate:** [Candidate call-site validation](RT-20-CANDIDATE-CALL-SITE-VALIDATION.md)

## Purpose

The call-site validator checks decisions supplied by an `ImpactPlan`, but that is not enough to establish that the candidate Snapshot is structurally sound. A candidate may contain unrelated selected objects with broken references, stale dependency metadata, or missing transitive dependencies. The graph audit therefore starts from the complete set of Snapshot selections and reconstructs the reachable dependency closure from stored declaration payloads.

## Implemented interface

`src/candidate_graph_audit.py` exposes:

```python
audit_candidate_snapshot_graph(store, snapshot) -> CandidateGraphAuditResult
```

The result includes:

- `valid`: false if any structural or integrity discrepancy was found;
- exact candidate `snapshot_root`;
- sorted `reachable_hashes`;
- reconstructed `DependencyIndex` scoped to that Snapshot root;
- deterministic `edge_set_digest` and `graph_digest`;
- sorted, deduplicated diagnostics.

## Audit algorithm

1. Recompute the Snapshot root from its selections and parent roots.
2. Initialize traversal from all unique selected object hashes.
3. For every reachable object:
   - require the exact object to exist in the Content Store;
   - recompute its semantic-value content hash;
   - validate its declaration envelope and kind;
   - extract typed references and call-site targets from the payload;
   - resolve every target by exact hash;
   - verify declared reference target kinds and function/operation call-target kinds;
   - compare the multiset of payload-derived dependencies with stored hash-relevant dependency metadata;
   - enqueue every resolved target for recursive inspection.
4. Sort all reachable objects and edges and compute stable digests.

The audit intentionally includes transitive objects that are not direct Snapshot selections. Conversely, historical Content Store objects that are not reachable from any selected root are excluded.

## Test coverage

The focused tests exercise:
- transitive closure through a function, contract, and type;
- exclusion of an unrelated historical object;
- payload dependency missing from stored metadata;
- undeclared dependency present only in stored metadata;
- missing transitive target;
- actual target-kind mismatch;
- forged Snapshot root;
- deterministic graph and edge digests.

The semantic dependency CI workflow includes the new module, tests, and compilation step.

## Scope and limitations

A successful result establishes structural and content-addressed consistency only for the current explicit `llmlang.semantic-object` declaration envelope. It does not establish:

- behavioral or contract compatibility;
- completeness of dynamic dispatch, function values, callbacks, reflection, generated code, runtime or external calls;
- completeness of the declaration envelope relative to arbitrary LLMLang source;
- correspondence between the candidate semantic diff and the approved CIP;
- validity of tests, proofs, or other verification evidence;
- authorization or readiness to create a Git commit.

The audit uses the same Content Store and declaration payloads as the producer. It is a deterministic re-traversal, not an independent trust domain or cryptographic attestation. The current in-memory store also has no immutable snapshot lease or transaction spanning the audit; callers must not mutate it concurrently.

## Next gate

The first narrow selection-level diff/CIP reconciliation slice is implemented in [RT-20 Candidate Semantic Diff](RT-20-CANDIDATE-SEMANTIC-DIFF.md). It derives added/removed/changed logical selections, requires exact-hash CIP action coverage, independently scans baseline-selected explicit call sites for changed callees, checks changed call targets against decisions, and reuses candidate call-site materialization validation.

Remaining work:
1. Strengthen action reconciliation beyond exact old/new hash presence: validate action kind, prerequisites, and evidence against each change class.
2. Reconcile all payload-derived typed reference changes, not only selection hashes and explicit call-site target changes.
3. Define explicit CIP dispositions for added/removed call-site targets rather than treating them as permanently unsupported.
4. Bind both baseline and candidate graph audit digests and extractor/schema identities into the diff result.
5. Add end-to-end branching/converging and consumer-specific shared-caller fork scenarios.
6. Prove that every planned action is realized and no unplanned mutation survives all validation gates.

This still will not prove behavioral compatibility. That remains a separate contract/test/proof obligation. Shared-caller consumer-specific forks also remain unrepresented in the current plan identity and must be solved before claiming complete RT-20 support.

This prototype is not a canonical SPG schema, production Toolchain implementation, or proof of program correctness.
