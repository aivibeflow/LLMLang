# RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit

**Status:** Research proposal; not an accepted language or Toolchain architecture decision  
**Date:** 2026-11-18  
**Priority:** P0  
**Related research:** RT-02, identity Studies 05–08 (formerly grouped under the RT-05 research area), RT-06, RT-08, RT-14, RT-15, RT-19  
**Related documents:** [Development Engine RFC](RFC-DEVELOPMENT-ENGINE.md), [RT-19 — Toolchain Server and Semantic Development API](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [ADR-015](../docs/adr/015-toolchain-server-semantic-api.md), [Research dependency map](RESEARCH-DEPENDENCY-MAP.md)

> This document records workflow requirements and a candidate algorithm derived from the RT-20 design discussion. It is a research proposal. It does not settle the canonical SPG schema, hash envelope, call-graph semantics, or commit policy, and it does not change the Proposed status of ADR-015.

**Terminology dependency:** Consult the [Draft Glossary](../draft/GLOSSARY.md) whenever changing `hashId`, operation/callee identity, implementation selection, or conformance-based substitution. Keep `OpHash`, `ImplHash`, `CCHash`, optional `CandidateSetHash`, and conformance-evidence identity distinct. RT-20's current function `hashId` is a workflow-level assumption and must be reconciled with the selected typed identity model; it must not silently redefine any glossary term. The glossary is proposed terminology, not an accepted hash schema.

## 1. Summary

An LLM patch workflow must determine the complete set of function versions that will change **before implementation begins**.

The working identity assumption is that a function version is addressed by a content-derived hash ID (hashId), and that the hash-relevant content of a caller includes the hashId of each callee it references. A function version is immutable: changing its semantic content or a hash-relevant reference creates a new function version and therefore a new hashId. If a changed version is selected by a caller, that caller's content changes and it also receives a new hashId. This propagation can continue through callers to one or more program entry points.

The workflow must not blindly migrate every caller to the newest callee. Different callers may require different behavior:
- one caller may migrate to the new callee version;
- another may preserve its reference to the old immutable version;
- another may require an adaptation or a separate caller/callee variant;
- a decision that cannot be justified must remain unresolved and block plan approval.

The central artifact is a **Change Impact Plan (CIP)**: a versioned, validated graph describing all affected call sites, caller compatibility decisions, required semantic modifications, reference rewrites, expected new function versions, verification obligations, and entry-point hash propagation.

Implementation is permitted only after the plan is complete and approved. A single authorized completion operation then runs all required checks and creates a Git commit only if every gate succeeds. A failed attempt leaves the candidate workspace available for correction but creates no commit.

## 2. Goals and non-goals

### 2.1 Goals

- Determine the full planned change set before modifying program entities.
- Discover callers from a complete, typed reverse-reference index rather than relying on LLM recall.
- Decide independently for each relevant call site whether to preserve or migrate the callee version.
- Propagate changed contracts upward through callers until affected entry points or an explicit compatibility boundary is reached.
- Propagate hash changes through exactly those references selected for migration or semantic modification.
- Detect when one shared caller needs multiple versions to serve consumers that require different behavior.
- Require every planned function-version change and reference rewrite to be implemented and verified.
- Bind plans, implementation results, validation evidence, and commits to exact immutable snapshots and hashes.
- Make successful verification a mandatory precondition of Git commit.

### 2.2 Non-goals

- Selecting the final canonical function identity or hash envelope; this remains part of RT-05.
- Assuming that every caller must migrate whenever a callee changes.
- Requiring meaningless semantic edits merely to force a new hash.
- Treating an LLM's explanation or self-reported completion as verification evidence.
- Guaranteeing defect-free programs.
- Automatically pushing commits to a remote repository.
- Defining every MCP tool schema before the domain workflow and state machine are validated.

## 3. Identity and graph assumptions

### 3.1 Immutable function versions

For this research, a function hashId identifies one exact immutable function version. Its hash-relevant content may include:
- the function's own semantic definition and contract;
- typed references to callee versions;
- other explicitly hash-relevant semantic inputs.

Changing a function in place is prohibited. A change creates a new version. An old version remains available to callers that intentionally preserve its behavior, subject to the eventual retention and reachability policy.

The exact hash envelope, canonical serialization, and distinction between logical lineage IDs and version hash IDs remain open RT-05 questions. The workflow must not silently decide those questions.

### 3.2 Two different propagation relations

The workflow must distinguish two related but non-identical analyses.

**Contract propagation** asks whether a caller's own contract or implementation must change because the behavior or contract of the callee it uses has changed. This is a semantic question. If a caller's contract changes, the analysis recursively examines that caller's callers.

**Hash/reference propagation** asks which caller contents change because a selected call-site reference must point to a different callee hashId, or because the caller itself is semantically modified. This is an identity question. It follows only the reference edges selected by the approved migration plan, not every incoming edge indiscriminately.

A caller may therefore have:
- no semantic change, but a reference-only change and a new hashId;
- a semantic change and a new hashId;
- no change at all because it deliberately retains the old callee version;
- multiple new versions if different consumers require different caller behavior.

An unchanged contract does **not** imply an unchanged caller hash when one of its hash-relevant references changes.

### 3.3 Call-site granularity

Compatibility decisions must be recorded per call site or typed reference edge, not merely per caller function. A single caller may invoke the same callee more than once, and different call sites may require different versions or adapters.

Where call sites cannot be identified unambiguously, the plan is incomplete.

## 4. Change Impact Plan

A CIP is an immutable, versioned planning artifact rooted in a specific base Snapshot and a specific set of requirements.

It contains two complementary views:

1. **Dependency Analysis:** all relevant functions, call sites, callers, dependency evidence, and analysis coverage, including functions that will not change.
2. **Change Implementation Plan:** the exact function versions, call-site rewrites, semantic modifications, and verification obligations that must be produced.

The dependency analysis proves that the candidate plan considered the relevant graph. The implementation plan is the mandatory execution contract for the agent.

### 4.1 Required plan records

Each affected function/version record should contain:

| Field | Meaning |
|---|---|
| Function hashId | Exact source version inspected |
| Logical lineage ID | Optional logical identity, if the eventual model defines one |
| Base Snapshot | Snapshot in which the function was observed |
| Change disposition | Semantic modification, reference-only rehash, preserve, fork/adapt, or no change |
| Reason | Requirement and dependency path explaining the disposition |
| Caller/callee edges | Exact typed references and call-site identities |
| Old callee hashId | Version currently referenced |
| Target callee hashId | Planned version, or preserve-old decision |
| Contract delta | Relevant old/new contract facts and compatibility analysis |
| Expected output | Required semantic content/reference result |
| Verification obligations | Checks that must be run for this record |
| Status | Planned, in progress, implemented, verified, blocked, or waived |

A target hashId may be unknown before implementation because it depends on final canonical content. The plan must still identify the exact function-version slot and all references that must target the resulting version. Once computed, the actual hashId is attached to the record and checked against the planned graph.

### 4.2 Caller migration decisions

For every relevant caller edge, the plan must record one explicit decision:

| Decision | Meaning |
|---|---|
| migrate | Rewrite this call site to the new callee version |
| preserve | Keep the existing reference to the old immutable callee version |
| adapt | Modify the caller or introduce an adapter to preserve its required contract while using the new version |
| fork | Create a separate caller or callee version for a distinct behavior path |
| unresolved | Evidence is insufficient to decide |

An unresolved decision blocks plan approval. Preserve, adapt, and fork require explicit contract/requirement rationale. A bare assertion from the implementing LLM is not sufficient evidence.

The decision is edge-specific. If two call sites in one function need different behavior, the plan must describe the resulting function version or versions explicitly.

## 5. Required planning workflow

No program mutation is allowed before stages 1–8 produce an approved CIP.

### Stage 1 — Establish the baseline and requirements

- Resolve the user request into explicit requirements, assumptions, and open questions.
- Pin the base Snapshot, entry points, relevant toolchain/language version, and dependency-index version.
- Identify the functions directly implicated by the requirements.
- Record the exact hashes and evidence supplied to the planning agent.

### Stage 2 — Identify initial changed callees

For each directly affected function, determine whether the requested change modifies its contract, implementation, or both. Create a new-version candidate in the plan; do not mutate the existing version.

### Stage 3 — Discover all callers

For every changed callee version, enumerate all incoming call/reference edges from the base Snapshot, including transitive and indirect forms represented by the language's dependency model.

The server, not the LLM, must query and audit the reverse-reference index. The result must include call-site identity, caller hashId, edge kind, exact base Snapshot root, index/extractor identity, deterministic digest of the returned edge set, and evidence/provenance.

The reverse-query result has an explicit completeness status: `GAP_FOUND`, `SUPPORTED_WITHIN_SCOPE`, `UNKNOWN`, or `NOT_CHECKED`. A no-caller result is not evidence that no callers exist. Missing evidence is `NOT_CHECKED`; stale or mismatched evidence is `UNKNOWN`. Only matching independent evidence may support a `SUPPORTED_WITHIN_SCOPE` conclusion, and that conclusion is limited to its declared scope, observation model, assumptions, and exclusions. It is not a global completeness proof.

The reverse-query result must be adapted into the CIP through the shared completeness-status type; the adapter must preserve the exact Snapshot root, target hash, scope, evidence ID, index schema version, extractor identity, and edge-set digest. The CIP validator must compare the bound Snapshot root to its pinned baseline and the target hash to the affected artifact. Missing evidence is `NOT_CHECKED`; a mismatched binding is `UNKNOWN`. Both block optimized planning and require human review plus full revalidation. Every binding field is part of the immutable plan identity, so replacing evidence, changing the extractor/schema, or changing the discovered edge set necessarily produces a different plan. A compatibility path for legacy unbound audits may exist for isolated tests, but it must never be used for CIP approval.

If dependency completeness cannot be established for the relevant scope—for example because of dynamic dispatch, unresolved external references, reflection, generated code, or an incomplete index—the plan must mark the affected region unknown and fail closed or require an explicit, policy-authorized boundary.

### Stage 4 — Analyze caller compatibility per edge

For every exact incoming `calls` edge, record a `CallSiteDecision` keyed by caller hash, call-site ID, and target ID. The decision also binds the exact base callee hash; call-site identity alone is insufficient when a call site has conditional/multiple targets.

The edge must also bind the caller's exact `required_contract_hash` for this call-site/target alternative and the base callee's exact `provided_contract_hash`. A resolved `CallSiteDecision` repeats both values, selects the exact provided-contract hash of the proposed callee, and includes a compatibility status plus evidence ID. The plan validator rejects a missing or mismatched required/base-provided contract binding. `preserve` must retain both the exact old callee hash and its exact provided-contract hash. A resolved decision is accepted by this prototype only when its compatibility status is `PROVEN`; the current code checks that status and binds the evidence ID into the plan identity, but does not authenticate or independently validate the evidence.

The semantic declaration prototype represents the call-site requirement as a mandatory `required_contract_hash` in schema v2 and requires each callable callee declaration to expose exactly one `provides_contract` reference. The two hashes remain distinct. They are generic exact Contract Content Hashes in this candidate model and are not yet normatively equated with glossary `CCHash`; that mapping is an open identity decision.

Allowed dispositions are `migrate`, `preserve`, `adapt`, `fork`, and `unresolved`. Every resolved decision records a selected exact callee hash, resulting exact caller hash, rationale, and compatibility evidence ID. `preserve` must retain the exact base callee hash. `migrate` must select a different callee hash and produce a different caller hash. `adapt` and `fork` likewise require an explicit resulting caller version. Unresolved decisions cannot claim output hashes or evidence and block approval.

The prototype's independent payload-scan audit is a second traversal over the selected Snapshot declarations. It differentially checks the reverse index's exact incoming edge set and emits Snapshot/target/scope/schema/extractor/digest-bound evidence. It shares the same Content Store and source payloads, so it is a differential implementation check, not an independent trust domain or proof that runtime/dynamic dispatch has been observed.

For each discovered caller edge:
1. Resolve the exact required contract hash stored on this call-site/target alternative, and the exact contract hash provided by the old callee.
2. Compare the old callee's provided contract with the proposed new callee's provided contract against that same call-site requirement.
3. Decide whether the caller must preserve the old callee, migrate, adapt, or fork.
4. Record the rationale and supporting evidence.
5. Leave the decision unresolved if compatibility cannot be established.

A new callee version must not silently replace an old one merely because it is newer or has a different hashId.

### Stage 5 — Propagate contract changes upward

For each caller whose selected callee version changes in a way that affects the caller's obligations or behavior:
- determine whether the caller's contract must change;
- determine whether its implementation must change;
- identify the exact requirement/contract delta;
- if the caller changes semantically, treat its new version as another changed callee for the next level up;
- repeat caller discovery and compatibility analysis.

Stop only when reaching an entry point, a justified compatibility boundary, or a caller whose contract and implementation are proven unaffected. The stopping decision and evidence must be recorded.

### Stage 6 — Compute reference and hash propagation

Independently compute the transitive set of function versions whose hash-relevant content must change.

Start with:
- functions that require semantic modification;
- functions containing call sites selected for migration;
- functions requiring adapters or forks.

For each such function, compute the resulting reference/content changes. Then inspect its callers and apply their already-recorded migration decisions. A caller that preserves the old function version remains unchanged along that edge. A caller that migrates to the new version receives a planned new version, which may cause further propagation.

Continue until the affected entry points are reached or a justified branch is deliberately left on an older version.

The result must explicitly state which entry-point hash(es) are expected to change and which entry points are expected to remain unchanged. The expected hashes can be unknown before implementation, but the complete set of hash-changing function slots and reference edges must be known.

### Stage 7 — Detect shared-caller version splits

A caller may be shared by upstream consumers with incompatible requirements. If one upstream path must use new behavior and another must retain old behavior, changing the shared caller in place is not an option.

The plan must then:
- preserve the old caller version for consumers requiring old behavior;
- create a new caller version (or explicit adapter) for consumers migrating to new behavior;
- assign each upstream call site to the intended caller version;
- continue contract and hash propagation independently along each path.

The plan must detect this case before implementation. It must not silently break a consumer to avoid creating a version split.

### Candidate Snapshot materialization gate (prototype)

The focused prototype in [RT-20 Candidate Call-Site Validation](RT-20-CANDIDATE-CALL-SITE-VALIDATION.md) checks planned decisions against the exact materialized candidate Snapshot. It verifies Snapshot-root binding, selected caller/callee membership, canonical stored-object hashes, and the actual candidate declaration's call-site/target reference. `PRESERVE` must retain the exact old callee hash at that call site; the caller may still receive a new version because another planned call-site or semantic change modifies it. Changed dispositions must materialize a new caller version. This is a reference-consistency gate only: it does not establish behavioral compatibility, complete dynamic dispatch discovery, or commit readiness. CI coverage for this narrow gate is included in the semantic dependency workflow.

### Stage 8 — Validate and approve the complete plan

The Toolchain Server independently checks:
- reverse-reference discovery completeness for the declared scope;
- an explicit disposition for every relevant call site;
- no unresolved compatibility decision;
- all contract changes propagated to affected callers;
- all required hash/reference changes included;
- all affected entry points accounted for;
- all forks/adapters and shared-caller splits represented;
- each planned change has a reason, expected result, and verification obligation;
- no unapproved mutation has already occurred.

Only then can the CIP be approved and frozen as an immutable plan version. A plan revision invalidates approval and requires the completeness checks to run again.

## 6. Example: mixed old/new caller requirements

Suppose the base graph is:

~~~text
                 EntryPoint
                 /        \
          Caller_New     Caller_Old
                 \        /
                 Algorithm_v1
~~~

A request introduces Algorithm_v2.

The compatibility analysis concludes:
- Caller_New must migrate to Algorithm_v2.
- Caller_Old must preserve Algorithm_v1.

The resulting graph is:

~~~text
                 EntryPoint_v2
                 /           \
          Caller_New_v2    Caller_Old_v1
                 |              |
             Algorithm_v2   Algorithm_v1
~~~

Caller_New receives a new hashId because its call-site reference changes. Caller_Old retains its existing version and hashId because its reference and semantics do not change. The entry point receives a new hashId if its content references Caller_New_v2. The old entry-point version remains available if required by existing consumers or history.

If both branches originally shared the same caller version, and that caller must behave differently for the two upstream consumers, the plan must create a new caller version for the migrating path while retaining the old caller version for the preserving path.

This example is illustrative. Actual graph and entry-point semantics must follow the eventual LLMLang call/dependency model.

## 7. Implementation workflow after plan approval

Implementation follows the approved plan, not a newly improvised scope.

1. Create an isolated Workspace rooted at the exact base Snapshot and bind it to the approved CIP version.
2. Implement semantic changes at the callee level.
3. Compute each new function hashId from canonical content.
4. Apply planned call-site rewrites to caller versions.
5. Recompute caller hashes in dependency order.
6. Continue until all planned entry-point versions are materialized.
7. Do not modify old immutable function versions.
8. Do not change functions or call-site targets outside the approved plan. If new evidence requires scope expansion, stop and submit a CIP revision.
9. Mark a plan record implemented only when the resulting semantic object/reference matches its expected result.
10. Mark it verified only after the required evidence is bound to the exact resulting hashes.

Independent branches may be implemented in parallel when their dependencies and Workspace isolation permit it. Hash-dependent caller construction must wait until the target callee hashId is final.

## 8. Mandatory completion and verified Git commit

The agent must not have a normal direct Git-commit capability. It requests completion through one authorized operation, provisionally named change_set.commit.

That operation is an orchestrated transaction:

1. **Freeze candidate:** capture the exact candidate Snapshot and prevent further mutation of the candidate being checked.
2. **Check plan completeness:** every mandatory function/version and call-site rewrite is implemented; no planned item is omitted; no unplanned semantic mutation is present; no unresolved decision remains.
3. **Check graph and hashes:** all references resolve to the planned immutable versions; caller hashes are recomputed from final content; expected entry-point roots match the resulting graph.
4. **Run deterministic validation:** structural/reference checks, type/effect checks, contracts, invariants, and language-specific validation.
5. **Run required verification:** affected tests, regression tests, property/stateful tests, formal proofs where required, and other plan-specific checks.
6. **Run independent audit:** verify the plan-to-diff mapping, caller migration decisions, hash propagation, and evidence bindings. The proposing LLM's self-report is not an audit.
7. **Check concurrency and repository state:** confirm the base revision and target branch are still valid; reject stale or conflicting publication.
8. **Prepare exact Git tree:** stage only the validated candidate export, not arbitrary files from a mutable working directory.
9. **Create Git commit:** create the commit only if every required preceding gate succeeded.

If any mandatory gate fails:
- no Git commit is created;
- the candidate Workspace and diagnostics remain available for correction;
- the operation returns failed/blocked status and machine-readable reasons;
- the agent may revise the implementation and retry;
- previous evidence may be reused only if its exact semantic inputs, dependency closure, toolchain version, and configuration remain unchanged.

The commit operation must be idempotent or use a durable request/idempotency identity so retries cannot create duplicate commits for the same validated candidate.

Semantic acceptance, filesystem export, Git commit, and remote push remain distinct state transitions even if the user-facing completion operation orchestrates them. Remote push is not implied by commit and is not automatic by default.

## 9. Candidate state model

| State | Meaning |
|---|---|
| draft | Requirements and initial targets are being clarified |
| analyzing | Caller discovery, compatibility, contract, and hash propagation are being computed |
| plan_blocked | Completeness or compatibility evidence is insufficient |
| plan_ready | Complete plan passed server-side validation |
| plan_approved | Immutable plan version is authorized for implementation |
| implementing | Workspace changes are being produced |
| candidate_frozen | Exact candidate Snapshot is frozen for completion checks |
| validating | Deterministic validation and required verification are running |
| auditing | Independent audit is running |
| commit_ready | All required checks passed and repository concurrency checks succeeded |
| committed | Git commit was created for the exact validated tree |
| failed | A required check failed; no commit was created |
| conflicted | Base/branch changed or a concurrent conflict prevents commit |
| abandoned | The proposal was intentionally discarded |

A failed validation does not erase the Workspace. A changed candidate invalidates evidence whose inputs no longer match.

## 10. Core invariants

| ID | Invariant |
|---|---|
| RT20-INV-01 | A complete, server-validated CIP must exist before implementation mutations begin. |
| RT20-INV-02 | Every relevant caller/call-site edge must have an explicit compatibility disposition. |
| RT20-INV-03 | No caller is migrated to a new callee version without an approved edge-specific decision. |
| RT20-INV-04 | Old content-addressed function versions are immutable and remain referenceable. |
| RT20-INV-05 | Contract propagation and hash/reference propagation are analyzed separately. |
| RT20-INV-06 | Every caller whose selected hash-relevant reference changes must have a planned new function version and hashId. |
| RT20-INV-07 | A shared caller requiring incompatible behavior for different consumers must be split, adapted, or explicitly blocked in the plan. |
| RT20-INV-08 | Every semantic modification must trace to a requirement or approved design obligation. |
| RT20-INV-09 | Every planned function version and reference rewrite must be implemented and verified before completion. |
| RT20-INV-10 | Plan changes invalidate prior approval and require a new completeness audit. |
| RT20-INV-11 | Incomplete dependency evidence or unresolved compatibility decisions block plan approval. |
| RT20-INV-12 | Verification evidence is valid only for the exact hashes, dependency closure, toolchain version, and configuration it checked. |
| RT20-INV-13 | No Git commit is created unless all mandatory planning, implementation, validation, audit, and concurrency gates pass. |
| RT20-INV-14 | The commit contains only the exact validated candidate tree. |
| RT20-INV-15 | A failed completion attempt preserves the Workspace for correction and creates no commit. |
| RT20-INV-16 | Commit does not imply remote push. |

## 11. Candidate MCP/domain operations

These names are illustrative. The domain API remains transport-neutral; MCP is an adapter.

| Area | Candidate operation | Responsibility |
|---|---|---|
| Context | project.get_context | Pin project, Snapshot, entry points, and toolchain context |
| Discovery | dependency.callers | Enumerate incoming call/reference edges |
| Discovery | dependency.audit_completeness | Check reverse-reference coverage and unknown edges |
| Compatibility | compatibility.analyze_call_site | Compare old/new callee contracts for one call site |
| Planning | change_plan.create | Create a draft CIP |
| Planning | change_plan.propagate_contracts | Recursively analyze caller contract effects |
| Planning | change_plan.compute_hash_closure | Compute planned reference/hash propagation |
| Planning | change_plan.validate | Server-side completeness and consistency checks |
| Planning | change_plan.approve | Freeze an approved plan version |
| Implementation | change_set.apply | Apply a typed mutation within the approved plan |
| Implementation | change_set.diff | Return semantic diff and plan coverage |
| Verification | change_set.verify | Run required checks against the frozen candidate |
| Completion | change_set.commit | Orchestrate all gates and create a Git commit only on success |
| Repository | repository.push | Separate, explicitly authorized remote publication |

The server should expose coarse-grained operations where possible. A large set of tiny MCP tools is not itself a design goal.

## 12. Failure handling and security considerations

- Reverse-reference indexes must be rebuildable from authoritative semantic data and auditable against it.
- Unknown dynamic or external call targets must not be treated as absent callers.
- An agent must not be able to omit a caller, alter the approved plan silently, forge verification status, or invoke a lower-level commit bypass.
- Toolchain and language versions must be pinned in the plan and verification evidence.
- Long-running validation must be cancellable and recoverable; completion retries must be idempotent.
- The exact candidate tree must be isolated from concurrent edits and unrelated user changes.
- Authorization must distinguish plan creation, plan approval, semantic acceptance, commit, and push.
- A policy may permit an automated agent to approve a mechanically complete plan, but this authority must be explicit and external to model-generated text.

## 13. Open research questions

1. What exactly constitutes a call site and a hash-relevant reference in the canonical SPG?
2. How are dynamic dispatch, function values, callbacks, reflection, generated code, and external calls represented in reverse-reference completeness?
3. Does hashId identify the complete function version, an implementation artifact, or a particular SPG node? How does this relate to stable logical identity?
4. What contract compatibility/refinement evidence is sufficient to justify preserve, migrate, or adapt?
5. When is a function-version fork preferable to an adapter or explicit wrapper?
6. How are recursive and mutually dependent functions handled if the hash-dependency graph is not acyclic?
7. Which entry points are authoritative for a package, executable, test target, or deployment profile?
8. Which checks are mandatory for every patch, and which are selected from the impact plan?
9. Which actors may approve a plan and authorize a commit?
10. How should a commit be coordinated with deterministic multi-file export and crash recovery under RT-19?
11. How should the system handle a branch moving after validation but before commit?
12. What retention/garbage-collection rules preserve old function versions still referenced by accepted roots, branches, or audit records?

## 14. Proposed experiments and exit criteria

### Experiments

1. **Single-chain propagation:** modify a leaf callee and demonstrate contract propagation, reference rewriting, and hash changes through a caller chain to an entry point.
2. **Mixed caller behavior:** one caller migrates to the new callee while another preserves the old version; verify that only the intended branch changes.
3. **Shared-caller split:** two upstream consumers require different behaviors from a shared caller; verify that planning detects and represents the required version split.
4. **Multiple call sites:** one caller invokes the same callee at distinct call sites with different migration decisions.
5. **Branching and convergence:** multiple changed callees share callers and entry points; verify deterministic closure and no duplicate/conflicting plan records.
6. **Incomplete dependency graph:** hide or introduce an unresolved caller edge; verify that plan approval fails closed.
7. **Plan drift:** add a required function during implementation; verify that implementation pauses and plan approval must be renewed.
8. **Commit gate failure:** force each validation/audit/concurrency gate to fail; verify that no Git commit is created.
9. **Evidence invalidation:** mutate one checked object or change the toolchain version; verify that stale evidence cannot authorize commit.
10. **Commit retry:** repeat the same completion request; verify idempotent outcome and no duplicate commit.

### Exit criteria

RT-20 can support a scoped architectural decision when:
- the identity and call-reference assumptions are reconciled with Studies 05–08 and the RT-24 Identity and SPG Reconciliation report;
- caller discovery completeness is demonstrable for a declared language subset;
- edge-specific compatibility decisions are represented and differentially checked against a second Snapshot payload traversal;
- contract propagation and hash propagation are separately specified and tested;
- mixed old/new behavior and shared-caller version splitting work in prototypes with exact per-call-site output hashes and evidence bindings;
- the complete plan is validated before implementation;
- every planned version/reference change is enforced during implementation;
- validation evidence is bound to exact candidate hashes and toolchain configuration;
- a failed completion attempt demonstrably creates no commit;
- a successful completion attempt commits only the exact validated export, including the canonical LLMLang semantic representation and the selected regular-file changes in one Git commit;
- concurrency, crash recovery, authorization, and limitations are documented.

Passing these criteria supports a scoped RT-20/RT-19 design decision. It does not prove whole-program correctness or establish the final LLMLang identity model.


## 15. Related Git merge and Toolchain documents

Study RT-20 together with:

- [Git Representation and Semantic Merge](GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) — defines semantic three-way merge, conflict handling, repository-wide graph validation, and Git integration. RT-20's caller-impact and hash-propagation rules remain mandatory inside merge/reconciliation.
- [ADR-014](../docs/adr/014-git-semantic-merge.md) — proposed repository representation and semantic merge direction.
- [RT-22](RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md) — repository/worktree operations, commit preparation, merge reconciliation, and recovery.
- [RT-23](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) — shared semantic snapshots, mapping revisions, and synchronized commit protocol.
- [RT-19](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) — semantic API and Change Set/Snapshot lifecycle.

Boundary: RT-20 does not define Git's repository-level merge algorithm or worktree runtime. Conversely, a successful semantic merge must not bypass RT-20's complete caller impact plan, per-call-site decisions, hash propagation, validation evidence, and commit gates.


## RT-24 relationship

RT-20 owns caller-impact completeness and per-call-site decisions; RT-24 consumes its complete CIP as a mandatory gate and must not independently decide that all callers migrate to the newest callee.
