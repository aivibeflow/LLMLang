# RT-20 — CIP Action-to-Obligation Coverage

**Status:** Design contract; stable obligation IDs implemented in CIP v5, action coverage still open  
**Date:** 2026-11-18  
**Depends on:** [CIP Action Execution Audit](RT-20-CIP-ACTION-EXECUTION-AUDIT.md), [Candidate Semantic Diff](RT-20-CANDIDATE-SEMANTIC-DIFF.md), [Draft Glossary](../../../draft/GLOSSARY.md)

## 1. Problem

CIP v5 commits each action's `subject_kind`, `artifact_hash`, action kind, rationale, and prerequisite action IDs into its identity. The closed action-kind policy rejects unsupported `ActionKind × subject_kind` pairs.

That check is necessary but not sufficient. It does not establish which approved output or semantic-edge obligations an action is responsible for. In particular:

- an action can have a valid subject kind but refer to no planned output;
- an output can exist without any action being accountable for producing or removing it;
- a planned edge delta can be present without an action accountable for that exact edge;
- an action can claim an unrelated output or edge;
- a broad `FULL_REVALIDATION` action can be incorrectly treated as satisfying a specific rebuild, derivation, test, proof, or call-site rewrite;
- `artifact_hash` alone cannot identify an output slot when a candidate object does not exist at planning time, nor distinguish multiple consumer-specific outputs derived from one source object.

Therefore action-kind compatibility must not be described as complete AEA-2. The current implementation is AEA-2 policy compatibility only.

## 2. Normative obligation identities

The action-coverage model must refer to stable identities already committed by the CIP, not to list positions or display strings.

### 2.1 Output obligation

A `PlannedOutput` is one output obligation. Its existing `output_id` is the obligation identity. The ID must be unique within the CIP and all of its existing output fields remain part of canonical plan identity.

### 2.2 Edge-change obligation

CIP v5 now provides a deterministic `edge_change_id` computed from a versioned canonical projection of every semantic field:

- `output_id`;
- edge kind and exact edge ID;
- operation;
- baseline and candidate relation;
- baseline and candidate target hash;
- baseline and candidate condition;
- baseline and candidate caller-required Contract hash;
- rationale and evidence identity.

The implementation uses domain-separated canonical JSON and SHA-256, with the CIP schema version included in the projection. A change to any field changes the ID, and the ID is included in the CIP canonical plan payload. Duplicate semantic edge records are still rejected by planner validation. It must not be confused with an object Content Hash, edge-set digest, or Package/Contract hash; consult the glossary when naming or documenting hash domains.

## 3. Action bindings

Extend each `PlannedAction` with explicit, immutable references:

- `output_ids`: exact output obligations this action is assigned to;
- `edge_change_ids`: exact edge-change obligations this action is assigned to.

Both collections are sorted and duplicate-free in canonical identity. Every reference must resolve exactly once within the same CIP. References to another plan, an unknown ID, a removed/nonexistent output, or a duplicate are invalid.

An edge binding is valid only when the action also binds the edge's owning `output_id`. This prevents a call-site or typed-reference edge from being detached from the exact caller/output slot in which it changes.

The action identity and plan identity must commit to these bindings. Changing only an obligation reference must change the corresponding action ID and enclosing plan ID.

## 4. Coverage semantics

Coverage has two distinct meanings and must not be collapsed:

1. **Accountability binding:** an action names the exact obligation(s) it concerns.
2. **Satisfaction eligibility:** the action kind and subject policy permit it to satisfy that obligation.

A broad action may be bound to an obligation for audit visibility without satisfying it. In particular, `FULL_REVALIDATION` and candidate-level `HUMAN_REVIEW` are not substitutes for targeted actions.

The validator must enforce:

1. Every planned output is bound by at least one action eligible for that output operation and kind.
2. Every planned edge change is bound by at least one action eligible for that edge kind and operation.
3. Every action has at least one exact output or edge obligation, except for a separately enumerated plan-level action class whose scope is explicitly represented in the schema. No implicit "all outputs" interpretation is allowed.
4. An action cannot bind an output or edge outside its exact subject/consumer path.
5. Every edge binding's owning output is also bound by the same action.
6. No duplicate, dangling, foreign, or contradictory obligation binding is accepted.
7. Every required obligation has at least one satisfying action; extra accountability bindings do not increase satisfaction.
8. A candidate-wide fallback action cannot satisfy a targeted obligation merely because it is present in the same plan.

The implementation must return stable, actionable diagnostics identifying the action ID and obligation ID. It must not silently discard malformed references.

## 5. Initial eligibility matrix to validate against actual planner behavior

This is a design matrix, not an assertion that the current planner already emits these bindings. The implementation must reconcile it with all current planner-generated actions and all supported CIP output/edge operations before enabling fail-closed enforcement.

| Action kind | Minimum obligation binding | Satisfaction rule |
|---|---|---|
| `RE_DERIVE` | One or more exact derived/formal output slots; edge changes owned by those slots | Satisfies derivation obligations only for compatible subject kinds |
| `REGENERATE_TESTS` | Exact test-suite output slot | Satisfies generation obligation, not execution |
| `RUN_TESTS` | Exact test-suite output plus explicit candidate output(s) under test | Satisfies test-execution obligation only when both tested suite and tested candidate are bound; current single `artifact_hash` is not enough to infer both |
| `REBUILD` | Exact implementation/build/generated output slot and its owned semantic deltas | Satisfies rebuild obligation for that output |
| `REPROVE` | Exact proof/verification output or proof obligation identity | Satisfies reproving obligation only for the exact theorem/verification target |
| `REWRITE_CALL_SITE` | Exact caller output slot and exact `CALL_TARGET` edge-change ID | Must bind a matching path-specific call-site decision; cannot satisfy a typed-reference delta |
| `HUMAN_REVIEW` | Exact requirement/intent obligation, or explicit candidate-wide review scope | Candidate-wide review does not satisfy implementation/output obligations |
| `FULL_REVALIDATION` | Explicit candidate-wide scope, represented without pretending to be a targeted output | Never substitutes for any targeted action |

The table exposes a model gap: `RUN_TESTS` needs separate typed bindings for the test suite and candidate under test. Do not overload one `artifact_hash` or infer the second binding from proximity. Introduce role-labelled output bindings (for example, `test_subject` and `candidate_under_test`) or an equally explicit typed representation before claiming exact test-action coverage.

Similarly, a call-site rewrite must be linked to the exact path-specific `CallSiteDecision`; matching a free-form rationale string is not an acceptable identity mechanism. Add an explicit decision identity or derive a canonical decision ID and include it in the action binding.

## 6. Validation boundaries

The action-to-obligation validator is a plan-structure check. It does not prove that an action ran, that the resulting output is correct, or that evidence is authentic. Those belong to AEA-3 through AEA-5.

The candidate semantic-diff audit remains responsible for independently deriving observed output and edge deltas from baseline/candidate Snapshots and reconciling them one-to-one with CIP records. The new action coverage validator must consume the exact planned output/edge records and must not replace or weaken that diff audit.

The provided Contract remains owned by the callee. Action/edge bindings must not reintroduce duplicate provided-Contract hashes in caller records, decisions, or dependency edges. Caller-required Contract bindings remain on the call-site edge and relevant decision.

## 7. Required adversarial tests

Before AEA-2 is closed, tests must cover:

- valid exact output and edge bindings;
- missing action binding for an output;
- missing action binding for an edge;
- unknown and duplicate output/edge IDs;
- edge bound without its owning output;
- action bound to an output from a different source hash or consumer path;
- wrong action kind for an otherwise valid obligation;
- one broad fallback action incorrectly offered as the only satisfying action;
- one action bound to multiple outputs where one is incompatible;
- call-site rewrite bound to the wrong caller fork or wrong edge;
- call-site decision omitted or mismatched;
- test execution missing either exact test suite or candidate-under-test binding;
- edge-change ID changes when any canonical edge field changes;
- action and plan identities change when only obligation bindings change;
- duplicate edge IDs and canonicalization/tampering cases.

Every policy row and every supported output/edge operation must have positive and negative coverage. One test may verify multiple requirements, but the test inventory must make the covered rows explicit.

## 8. Implementation sequence

1. Implemented in CIP v5: canonical `edge_change_id` is included in plan identity.
2. Add immutable action-to-output/edge bindings and include them in action/plan identity.
3. Add explicit role-labelled bindings for test suite versus candidate under test, and exact call-site decision binding.
4. Define the closed obligation-satisfaction matrix separately from the existing subject-kind compatibility matrix.
5. Update planner generation to emit complete bindings; do not synthesize bindings from rationale text.
6. Add a validator that rejects missing, extra, duplicate, foreign, incompatible, or path-mismatched bindings.
7. Add adversarial tests and run the full semantic-dependency suite plus repository CI.
8. Update RT-20 design/results docs only after the implementation and tests demonstrate complete supported-subset coverage.

**AEA-2 exit:** every supported output and edge obligation has explicit stable identity, every action is bound to exact obligations, every required obligation has an eligible satisfying action, and unsupported cases fail closed. Stable edge-change and call-site decision IDs are now available in CIP v5; action bindings and complete coverage remain outstanding. AEA-3 execution records must not begin before this exit is met.
