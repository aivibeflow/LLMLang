# RT-20 — CIP Action Execution Audit

**Status:** Research design for the next RT-20 prototype slice; not an accepted Toolchain architecture decision  
**Date:** 2026-11-18  
**Depends on:** [RT-20 Candidate Semantic Diff](RT-20-CANDIDATE-SEMANTIC-DIFF.md), [RT-20 Candidate Graph Audit](RT-20-CANDIDATE-GRAPH-AUDIT.md), [Draft Glossary](../draft/GLOSSARY.md)

> This document decomposes the next implementation step. It does not claim that the current prototype executes or verifies planned actions. The existing CIP v2 diff audit proves exact structural output/edge reconciliation for its supported declaration subset; it does not establish that all required work was executed or that its evidence is authentic.

## 1. Problem statement

CIP v2 currently stores `PlannedAction(kind, artifact_hash, reason, prerequisite_hashes)`. The semantic-diff audit checks that changed selection hashes are covered by an action hash and separately requires `REWRITE_CALL_SITE` for changed call targets.

That is insufficient for an execution audit:

- action coverage by hash does not establish that the action kind is appropriate for the change;
- `prerequisite_hashes` identify content, not prerequisite actions, and do not express ordering or completion;
- there is no exact execution record tying an action to its inputs, outputs, tool identity, and evidence;
- non-empty evidence IDs and a `PROVEN` string are bindings, not authenticated evidence;
- an output diff cannot establish that a test, rebuild, derivation, proof, or human review actually ran;
- action-level checks do not yet prove that every planned action completed and that no unplanned action or side effect occurred.

The next gate must therefore be an **execution audit**, separate from the existing semantic-diff audit. It must fail closed and must not authorize a Git commit.

## 2. Terminology and trust boundary

- **Planned action** — an immutable obligation in the approved CIP.
- **Action ID** — stable identity of one planned action, independent of its execution attempt.
- **Prerequisite action** — another planned action that must complete successfully before this action may start.
- **Execution attempt** — one attempt to perform one planned action.
- **Execution record** — immutable report of the attempt, including exact inputs, outputs, tool identity, status, and evidence references.
- **Evidence object** — content-addressed evidence bytes or a resolvable immutable evidence record. An opaque evidence ID alone is not evidence validation.
- **Action audit receipt** — deterministic result of comparing the complete plan with the complete set of execution records and validating supported evidence envelopes.

The audit may validate evidence binding, structure, provenance metadata, and checker results only to the extent that a trusted verifier is actually invoked. It must not treat a self-reported status string as proof. Cryptographic authenticity, signer authorization, and verifier soundness remain explicit trust assumptions until separately implemented.

## 3. Required invariants

### 3.1 Plan identity and action identity

1. Every planned action has a unique, deterministic `action_id`.
2. The action ID commits to action kind, exact subject identity, canonical parameters, rationale/evidence references, and prerequisite action IDs.
3. Prerequisites reference action IDs, not artifact hashes.
4. The prerequisite graph is acyclic; every prerequisite exists exactly once in the same CIP.
5. The CIP identity commits to the canonical action records and their prerequisite edges.
6. Action IDs are not reused for materially different parameters or evidence bindings.

The current `prerequisite_hashes` field is not silently reinterpreted. A schema revision must either replace it or introduce a separately named `prerequisite_action_ids` field. A migration rule must be explicit.

### 3.2 Action-kind compatibility

The audit must validate the action kind against the declared operation and exact target kind. The initial policy must be a closed, versioned table, not permissive string matching.

At minimum, policy rows must cover:

| Change/obligation | Permitted action kinds (initial candidate) |
|---|---|
| Requirement/business-intent change | `HUMAN_REVIEW`; downstream derivation/revalidation as separately planned |
| Formal clause / derived model change | `RE_DERIVE` |
| Test specification change | `REGENERATE_TESTS` |
| Test execution obligation | `RUN_TESTS` |
| Implementation/build/generated artifact change | `REBUILD` |
| Proof/verification record obligation | `REPROVE` |
| Exact call-site rewrite | `REWRITE_CALL_SITE` |
| Unknown or unsupported target kind | `HUMAN_REVIEW` and `FULL_REVALIDATION` |

This table is only a starting policy. It must be refined against the repository's actual artifact-kind taxonomy before implementation. In particular, `RUN_TESTS` must bind the exact test suite and exact candidate subject; a generic action on an arbitrary hash is not sufficient.

A policy mismatch is an audit error. The audit must not infer that one broad `FULL_REVALIDATION` action automatically satisfies every targeted obligation.

### 3.3 Execution records

Each execution record must bind:

- CIP ID and action ID;
- attempt ID and monotonic attempt sequence (or another unambiguous ordering mechanism);
- exact baseline/candidate snapshot roots applicable to the action;
- exact input object hashes and their roles;
- exact output object hashes, if any;
- action status: `SUCCEEDED`, `FAILED`, `BLOCKED`, or `INCOMPLETE`;
- tool/verifier identity and version, execution environment identity, and relevant configuration digest;
- start/end metadata where available (timestamps are descriptive unless trusted time is established);
- evidence object IDs and content digests;
- a structured failure reason for non-success outcomes.

A successful action must not be inferred from an execution record that omits required fields. Retries are separate attempts; the audit policy must state whether only the latest attempt or any successful attempt is eligible, and must prevent a later failed attempt from being hidden by selecting an earlier success without an explicit rule.

### 3.4 Evidence adequacy

Evidence requirements are action-kind-specific and versioned. For example:

- `RUN_TESTS`: exact test selection, test runner identity/version, candidate root, per-test or aggregate results, and exit status;
- `REBUILD`: exact source/input roots, target profile, compiler/toolchain identity, build configuration, and output hashes;
- `REPROVE`: exact theorem/obligation, assumptions, proof artifact, kernel/checker identity, and checker result;
- `RE_DERIVE`: exact derivation inputs, derivation rule-set version, output hashes, and validation result;
- `HUMAN_REVIEW`: reviewer identity/authority evidence, reviewed subject and scope, decision, rationale, and explicit unresolved issues;
- `REWRITE_CALL_SITE`: exact caller output binding, exact edge delta, selected callee output binding, and compatibility evidence binding.

The initial prototype may validate evidence envelopes and bindings without claiming authenticity or proof soundness. Every such limitation must appear in the receipt. Missing, stale, mismatched, unsupported, or unauthenticated evidence must not be reported as verified.

### 3.5 Completeness and non-interference

The audit must establish all of the following within its declared scope:

1. Every planned action has at least one eligible execution attempt.
2. Every action required by policy completed successfully.
3. Every prerequisite completed before its dependent action.
4. Every execution record refers to an action in the exact CIP.
5. No execution record claims an unknown or duplicate action identity.
6. All required outputs are bound to the candidate Snapshot or to an explicitly declared external evidence object.
7. No unplanned semantic output or edge mutation exists; continue to rely on the separate CIP v2 semantic-diff audit for this check.
8. No planned action is silently omitted, waived, or converted into a no-op.
9. A failed or blocked prerequisite blocks all dependent actions.
10. The receipt binds the exact CIP identity, candidate root, execution-record set digest, evidence-set digest, policy version, and audit implementation version.

This gate is not a behavioral-equivalence proof and is not a commit authorization.

## 4. Implementation sequence

The work is deliberately split into small independently testable slices.

### AEA-1 — Action model and canonical identity

- Introduce an explicit action ID and prerequisite action IDs in a versioned CIP schema.
- Define canonical action payload and deterministic action ID.
- Validate uniqueness, exact prerequisite resolution, and acyclicity.
- Keep old CIP v2 parsing isolated; do not silently reinterpret hash prerequisites.
- Add deterministic identity, duplicate-ID, missing-prerequisite, self-cycle, multi-node-cycle, and schema-migration tests.

**Exit:** a plan can be canonicalized and its action DAG validated without executing anything.

### AEA-2 — Action-kind policy

- Define a versioned closed policy table for supported artifact kinds and operations.
- Validate each action against its exact planned output/edge obligation.
- Reject unsupported combinations and ambiguous subject bindings.
- Require exact test-suite/candidate bindings for test actions.
- Add positive and negative matrix tests for every policy row.

**Exit:** every supported obligation has an explicit, tested action-kind rule; unsupported cases fail closed.

### AEA-3 — Execution-record schema

- Define immutable execution attempt and evidence-reference models.
- Validate record-to-plan, snapshot, input, output, and tool identity bindings.
- Define retry/attempt-selection semantics.
- Add malformed, stale, mismatched, duplicate, failed, and incomplete record tests.

**Exit:** execution records can be validated structurally, without yet claiming evidence authenticity.

### AEA-4 — Evidence-envelope validation

- Define per-action evidence requirements.
- Validate evidence digests, exact subject bindings, tool/verifier identity, and required result fields.
- Separate `BOUND`, `AUTHENTICATED`, and `VERIFIED` (or equivalent) states; do not collapse them into a single `PROVEN` string.
- Add tests proving that opaque IDs, self-reported success, stale evidence, and wrong-subject evidence do not pass.

**Exit:** the prototype states precisely which evidence properties it checked and which trust assumptions remain external.

### AEA-5 — Execution audit receipt

- Reconcile all planned actions with eligible execution attempts.
- Validate prerequisite completion ordering and failure propagation.
- Reject missing, extra, duplicate, or contradictory records.
- Bind the receipt to CIP, candidate root, action policy, execution set, evidence set, and audit version.
- Add deterministic receipt and tampering tests.

**Exit:** all supported planned obligations are accounted for, and every unsupported or incomplete obligation blocks the receipt.

### AEA-6 — Integration and independent review

- Integrate the action receipt with the existing candidate semantic diff result, without merging their distinct responsibilities.
- Add end-to-end tests for successful execution, omitted action, extra action, failed prerequisite, retry ambiguity, stale evidence, wrong tool version, and candidate-root drift.
- Run the full dependency-graph prototype suite and repository CI.
- Perform a separate adversarial review of identity binding, DAG validation, policy coverage, and evidence downgrade paths.

**Exit:** structural diff and action execution audit both pass for the supported subset. Commit authorization remains a later, separate design and implementation step.

## 5. Explicit non-goals for this slice

This work does not yet:

- authenticate a publisher or reviewer cryptographically;
- prove that a test suite is adequate or complete;
- prove arbitrary source-code behavior or contract refinement;
- prove runtime/dynamic dependency completeness;
- provide a frozen candidate transaction or prevent concurrent mutation;
- create, sign, or push a Git commit;
- guarantee defect-free output.

## 6. Immediate next implementation task

CIP v5 introduces deterministic, domain-separated identities for planned edge changes and call-site decisions, and commits those identities into the canonical plan payload. This is the first identity prerequisite for exact action-to-obligation bindings. It does **not** yet bind actions to outputs, edge changes, or decisions; it does not close AEA-2.

Detailed requirements are in [CIP Action-to-Obligation Coverage](RT-20-CIP-ACTION-OBLIGATION-COVERAGE.md). Next, add immutable role-labelled action bindings to exact output IDs, edge-change IDs, and path-specific decision IDs; define the closed satisfaction matrix; update planner generation; and enforce complete coverage in the candidate semantic-diff gate. In particular, `RUN_TESTS` must bind both a test-suite output and the candidate-under-test output. AEA-3 must not begin before this is complete.
