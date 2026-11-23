# RT-28 — Incremental Polyglot Migration and Semantic Mirroring

**Status:** Research proposal and execution brief; no migration architecture, source-import contract, identity model, runtime interoperability model, or equivalence guarantee is accepted  
**Date:** 2026-11-23  
**Priority:** P0  
**Research area:** RT-28 — Incremental polyglot migration and semantic mirroring  
**Related:** RT-02 requirements/contracts; RT-03 language semantics; RT-04 types/effects/ownership/capabilities; RT-05 SPG and identity; RT-06 dependency analysis; RT-07 verification; RT-08 testing/evidence; RT-09 compiler frontends/IR; RT-10 runtime; RT-11 incremental computation; RT-13 interoperability; RT-14 AI change protocol; RT-16 security; RT-18 evolution; RT-19 Toolchain API; RT-20 change-impact planning; RT-22 repository/worktree MCP; RT-23 shared semantic state and incremental File Views; RT-24 semantic diff/merge. Also coordinate with RT-27 SPG repository storage requirements.

## 1. Problem statement

Large, actively developed software systems cannot generally be rewritten in one migration. Their existing implementation must continue to build, ship, receive fixes, and evolve while selected functionality is progressively reimplemented in LLMLang.

The research must establish a deterministic, incremental, evidence-backed process that selects independently migratable parts; imports and analyzes source-language code without assuming a complete LLMLang compiler/runtime already exists; creates and maintains semantic mirrors; preserves source-to-mirror correspondence across edits, moves, renames, splits, merges, and version changes; detects upstream changes and computes impact; supports mixed-language execution; verifies behavioral compatibility to a stated evidence level; discovers and attributes defects; contributes appropriate fixes upstream; and supports shadowing, cutover, rollback, and long-term maintenance.

Upstream change is a normal continuous input, not an exceptional re-import event.

## 2. Goals and non-goals

### 2.1 Goals

1. Incremental migration at function, type, module, package, library, or subsystem granularity.
2. Explicit, versioned source-to-mirror correspondence.
3. Deterministic baseline capture and reproducible migration decisions.
4. Bounded re-analysis and re-verification based on dependency and impact evidence.
5. Mixed-language execution through explicit, safe boundaries.
6. Differential, contract, property-based, fuzz, stateful, and runtime verification where applicable.
7. Defect provenance distinguishing upstream, mirror, adapter, oracle, environment, contract, and unresolved cases.
8. Upstream contribution workflow with regression tests and traceable PR outcomes.
9. Controlled cutover and rollback with state/data compatibility considered.
10. Integration with AIVibeFlow without making LLMLang depend on it.

### 2.2 Non-goals

- Guaranteed automatic translation of arbitrary languages.
- Universal behavioral-equivalence claims from finite tests.
- Mechanical reverse translation of LLMLang changes into the source language.
- Replacing upstream maintainers, review policy, or release process.
- Requiring an entire repository or package to migrate at once.
- Treating Git textual equality, AST similarity, or matching unit-test outcomes as proof of equivalence.
- Silently changing authoritative implementation or production routing.

## 3. Migration-domain model (outside the LLMLang language core)

The concepts in this section describe the migration domain. They are not proposed LLMLang syntax, built-in types, runtime entities, or mandatory language semantics. Their records, lifecycle, persistence, scheduling, and governance may be implemented by AIVibeFlow or another independent migration service. LLMLang participates only through capabilities that are justified by its language and Toolchain responsibilities.

### 3.1 Migration Project

A long-lived Migration Project binds source repositories/providers, tracked refs and baselines, language/toolchain/build configuration, migration policy, Migration Units and dependency graph, verification profiles/evidence, upstream contribution policy, and runtime routing/cutover state. It is not tied to one agent session, Job, worktree, or Workflow execution.

### 3.2 Migration Unit (MU)

A Migration Unit is the smallest independently governed migration scope whose behavior and dependencies can be described and verified sufficiently for its intended use. It may contain one or more source symbols and need not match a file or directory. Candidate granularities include function, method, type, module, package, library, service, and subsystem.

Each MU records:
- stable MU identity and revision;
- exact source entity set and source baseline;
- dependency and caller/callee closure with completeness evidence;
- public and relevant internal interfaces;
- contracts, invariants, effects, errors, and observable side effects;
- tests, fixtures, build targets, and runtime assumptions;
- corresponding LLMLang semantic objects and versions;
- adapters and foreign-language boundaries;
- migration state, verification evidence, and decision provenance.

A unit boundary is acceptable only when dependencies, shared mutable state, initialization/lifecycle, and external effects can be accounted for. Otherwise enlarge, constrain, or block it. Research must define selection criteria, not mandate one universal granularity.

### 3.3 Mirror Binding

A Mirror Binding is a separately versioned relation between source entities and LLMLang semantic entities. It is not the identity of either side; source identity, SPG content identity, and binding identity must remain distinct.

A binding revision should record source repository/entity identity and revision, extractor/toolchain identity, LLMLang repository/snapshot/entity identity, mapping cardinality and role (one-to-one, one-to-many, many-to-one, split, merged, wrapper, adapter, generated), contract revision/compatibility relation, provenance, validity/supersession, confidence, and unresolved questions.

Research stable identity options per language: compiler symbol IDs, AST-derived identities, qualified names plus structural anchors, debug/index metadata, and lineage evidence. Renames, overloads, macros, generated code, templates/generics, dynamic dispatch, reflection, and split/merge are mandatory discriminators. A content hash alone is not stable entity identity.

### 3.4 Source Baseline and evidence envelope

Every analysis, patch, test result, and migration decision is bound to an immutable baseline envelope: source commit/tree; submodules and dependency locks; compiler/interpreter and toolchain versions; build flags, target, features and environment; extractor/frontend/schema versions; test selection and fixture versions; and LLMLang snapshot/Mirror Binding revision where relevant.

Evidence with an incomplete envelope must be explicitly marked partial and cannot authorize automatic advancement.

## 4. Migration lifecycle

Research a per-MU state machine. Candidate states (provisional):
- DISCOVERED — source scope found, not baselined.
- BASELINED — source tree, toolchain, dependencies, reproducible build/test baseline captured.
- ANALYZED — symbols, dependencies, effects, interfaces, analysis limits recorded.
- CONTRACTED — behavioral contract and observation boundary reviewed.
- MIRRORED — LLMLang implementation and Mirror Binding exist.
- VERIFIED — required checks pass for the pinned baseline.
- SHADOW — both implementations evaluated without mirror-controlled authoritative effects.
- CANARY — policy-defined subset of eligible executions uses the mirror.
- LLMLANG_PRIMARY — LLMLang is authoritative for the declared MU scope.
- SOURCE_RETIRED — source implementation no longer required for this scope under explicit policy.

Exception states should include STALE, SOURCE_DRIFT, MIRROR_DRIFT, CONFLICTED, BLOCKED, REGRESSION, QUARANTINED, and CONTRIBUTION_PENDING. Transitions must be explicit, versioned, auditable, and evidence-guarded. One MU must not silently advance dependent MUs. Determine whether SHADOW/CANARY are states or deployment modes orthogonal to implementation authority.

## 5. Source-language analysis and import (Toolchain capability)

Source parsing, compiler integration, semantic extraction, indexing, and import are frontend/Toolchain capabilities, not language-core features. RT-28 must identify stable APIs and semantic guarantees required from those tools; it must not assume that the LLMLang language itself needs migration-specific syntax or concepts.

Study compiler-native frontends/semantic APIs, AST/parser import, compiler IR, language-server indexes/symbol databases, build-system integration/generated-code discovery, runtime instrumentation, and test/trace-derived behavioral constraints.

Separate syntax, resolved symbols/types, control/data/effect dependencies, contracts, and source provenance. Preserve unsupported constructs as explicit opaque/foreign boundaries rather than inventing LLMLang semantics.

For every supported language/profile define supported language/compiler versions, build configurations/features, extraction completeness/blind spots, identity/occurrence rules, macro/template/generic/generated-code behavior, dynamic dispatch/reflection/plugin/runtime-loading limits, external dependency/FFI behavior, and deterministic replay/versioning.

A partial frontend must declare its soundness/completeness envelope. Missing evidence must conservatively enlarge the affected set or block automatic migration; it must not be interpreted as absence of dependencies.

## 6. Upstream change detection and mirror reconciliation

Monitor commits, refs, dependency locks, generated artifacts, build configuration, and relevant release/tag events. For each upstream change:
1. pin old and new source baselines;
2. obtain incremental source diff and changed-entity inventory;
3. resolve entities through the prior Mirror Binding revision;
4. classify trivia/format-only, implementation-only, contract/interface, dependency, build/configuration, add/remove, move/rename, generated-code, and unknown changes;
5. compute affected MUs and dependency/caller closure with completeness evidence;
6. distinguish implementation changes from contract changes;
7. plan preserve/adapt/migrate/fork/retire/unresolved decisions at relevant call sites and boundaries;
8. create a new binding revision only when correspondence changes;
9. update only affected semantic objects and evidence;
10. run required verification against the exact new baseline;
11. publish reconciled state only after all gates pass.

Do not retranslate an unchanged object merely because another object in its file changed. A proven implementation-only change may leave mirror code unchanged but still require regression and differential checks.

Track SOURCE_DRIFT (upstream changed, mirror not reconciled), MIRROR_DRIFT (LLMLang changed independently), BEHAVIOR_DIVERGENCE (observations differ), BINDING_CONFLICT (correspondence ambiguous/incompatible), and BASELINE_STALE (work prepared against superseded inputs).

Git diff is an input, not the semantic reconciliation algorithm. Coordinate with RT-20, RT-22, RT-23, RT-24, and RT-27.

## 7. Contracts and equivalence evidence

Define layered evidence: interface/type compatibility; pre/postconditions and invariants; deterministic unit/integration tests; differential execution; property-based/stateful testing; fuzzing and minimized counterexample replay; ordered-effect/resource-lifecycle trace comparison; formal refinement/equivalence for tractable subsets; and production shadow/canary telemetry under privacy and safety constraints.

The observation model must define return values, errors, state transitions, database/file/network effects, event ordering, cancellation, cleanup/destruction, resource ownership, and externally visible timing/order guarantees.

Do not blindly compare nondeterministic outputs. Define controlled environments, deterministic seeds, virtual clocks, effect capture, admissible result sets, and normalization only for semantically irrelevant fields. Normalization must not hide meaningful behavior.

Classify evidence as proven under a stated formal model; verified for a finite corpus; observed in a specified runtime environment; inferred/assumed; or unknown/not checked. Finite tests are evidence, not universal proof. A divergence does not automatically establish an upstream defect.

## 8. Mixed-language execution and state ownership (runtime/interop boundary)

ABI/FFI, adapters, bindings, process boundaries, and deployment integration are primarily runtime, library, or Toolchain concerns. A language-core change is justified only when a required source-level semantic guarantee cannot be expressed or preserved with existing LLMLang semantics plus runtime/tooling support.

Research ABI/FFI and calling conventions; primitive/aggregate/optional/sum/string/error representation; ownership, borrowing, lifetime, aliasing and cleanup; callbacks/reentrancy; exceptions/panics and error translation; async tasks/cancellation/scheduling/thread affinity; global state and initialization/shutdown; transaction boundaries; generated bindings and version skew.

One mutable state region must have a defined owner and synchronization protocol. Prevent two runtimes from independently believing they own or may mutate the same resource. Adapter behavior is versioned and tested as part of the MU contract.

Compare foreign dependencies, generated shims, process/service boundaries, and direct FFI, including their safety limits and required evidence.

## 9. Defect discovery, attribution, and upstream contribution

### 9.1 Sources

Differential tests, ordinary tests, fuzzing, property/stateful tests, static analysis, sanitizers, formal checks, runtime telemetry, dependency/security scanners, and operator reports.

### 9.2 Classification

- UPSTREAM_DEFECT — source violates the established intended contract.
- MIRROR_DEFECT — LLMLang mirror violates it.
- ADAPTER_DEFECT — interop/marshalling/ownership boundary violates it.
- TEST_OR_ORACLE_DEFECT — test, fixture, or comparison oracle is wrong/incomplete.
- ENVIRONMENT_OR_DEPENDENCY — toolchain, dependency, platform, or configuration caused the observation.
- CONTRACT_GAP — expected behavior is unspecified or contradictory.
- UNRESOLVED — evidence is insufficient.

Differential mismatch alone does not prove UPSTREAM_DEFECT. Preserve competing hypotheses until evidence is sufficient.

### 9.3 Defect record

Bind exact source/mirror/binding baselines; minimized reproducer, inputs, seed, environment and expected/actual traces; affected MU and dependency closure; violated contract/invariant; classification, confidence, severity and security impact; regression tests; fix candidates/review decisions; upstream issue/PR and downstream patch state.

### 9.4 Upstream contribution lifecycle

Candidate workflow:
DETECTED → REPRODUCED → TRIAGED → CONTRACTED → REGRESSION_TESTED → PATCH_PLANNED → PATCH_IMPLEMENTED → SOURCE_TESTED → REVIEWED → SUBMITTED → UPSTREAM_ACCEPTED / UPSTREAM_REJECTED / UPSTREAM_DEFERRED → RECONCILED.

Prepare a native source-language patch using upstream conventions/toolchain; do not mechanically reverse-translate LLMLang. Include a minimal reproducer and regression test, pass relevant upstream checks, and follow upstream contribution policy. Human approval is required for external publication unless a narrowly scoped reviewed policy authorizes it.

If upstream rejects or defers a fix, preserve a downstream-only patch as explicit versioned divergence with rationale, baseline, tests, security/maintenance implications, owner, and revalidation policy. Never mark upstream fixed because the mirror contains a fix. If upstream accepts a modified patch, reconcile against the actual merged commit and rerun checks.

## 10. Rollout, cutover, and rollback

Study shadow execution, canary routing, per-call-site/scenario routing, and full cutover. Define eligibility and verification gates; routing determinism/provenance; metrics/regression thresholds; state/data migration and rollback compatibility; in-flight calls/transactions; deployment/version skew; emergency rollback authority and evidence retention.

Shadow execution must not duplicate irreversible side effects. Use captured inputs, isolated state, effect suppression, transaction snapshots, or safe replay. Canary routing is limited to explicitly eligible operations with deterministic policy.

Cutover is scoped to an MU and declared interfaces; it does not retire the upstream repository. Continue upstream monitoring. Source retirement requires separate review of callers, data, rollback, releases, and maintenance.

## 11. Determinism, concurrency, and recovery across layers

Migration workflow durability, Migration Unit scheduling, event journals, and migration-record recovery belong to the external migration service/AIVibeFlow. LLMLang Toolchain recovery applies only to its own workspaces, semantic state, operations, and repository contracts. SPG object layout and cache-first access are LLMLang infrastructure/storage concerns, not language semantics.

Reproduce from pinned baselines, frontend/toolchain versions, policies, binding revisions, plans, and evidence. Independent MUs may proceed concurrently; conflicting edits to the same binding, shared state, contract, or dependency closure require coordination.

Reuse existing LLMLang boundaries:
- RT-19: Toolchain API, Workspace, Change Set, Snapshot, durable operations.
- RT-20: change-impact plans, call-site decisions, hash propagation, validation-gated completion.
- RT-22: repository/worktree operations and scoped authorization.
- RT-23: shared semantic state, versioned mappings, incremental File Views, event journals, recovery.
- RT-24: semantic import/export, diff, and three-way merge.
- RT-27: SPG repository storage and cache-first metadata requirements.

Do not create a competing Git/worktree manager or second semantic object store. Determine which records belong in SPG, semantic repository, project metadata, or AIVibeFlow durable workflow storage.

## 12. Security, trust, and governance

Treat source repositories, build scripts, dependencies, generated code, fixtures, runtime traces, and patches as untrusted. Research sandboxing/capability grants for builds/tests; credential isolation and least privilege; secret redaction; supply-chain provenance; approval for pushes/PRs/merges/releases; prompt injection through source comments/docs/tests/tool output; reproducible evidence and audit; license/contribution-policy checks; and tenant isolation.

Passing tests or agent assertions cannot grant publication authority.

## 13. Architectural responsibility boundaries

RT-28 studies a system assembled from independently deployable layers. It must not turn every useful migration capability into a requirement on the LLMLang language.

### 13.1 LLMLang language core

The language core owns only source-language semantics: syntax and type rules, evaluation and observable behavior, ownership/lifetime/effect/concurrency guarantees, contracts/invariants, and other guarantees required to express and verify programs.

A core change is a candidate only when evidence shows that:
- a required behavior or contract cannot be expressed with existing LLMLang constructs;
- a required language-level safety or semantic guarantee is missing;
- the source-level semantics of an interoperation boundary cannot be specified without a language change.

Even then, first test whether a library, runtime, adapter, or Toolchain API can provide the capability without changing the language.

Migration Project, Migration Unit, Mirror Binding, upstream repository, contribution, defect ticket, workflow state, approval, and cutover are not language constructs and must not be added to the language core merely to support migration.

### 13.2 LLMLang Toolchain and infrastructure

The Toolchain may provide compiler/frontend APIs, source import and semantic extraction, symbol/dependency indexes, semantic repository operations, impact analysis, diff/merge, verification interfaces, runtime/FFI support, SPG storage, and cache/recovery mechanisms.

These are compiler, tooling, runtime, repository, or storage capabilities. They may be implemented as separate services or modules and should expose stable, versioned interfaces. RT-28 may depend on them, but must not describe them as language syntax or core semantics. The Toolchain need not own migration-specific records or lifecycle.

### 13.3 External migration management

AIVibeFlow or another independent service owns Migration Projects, Migration Unit records/indexes, Mirror Binding lifecycle and persistence, upstream Git monitoring, event ingestion, workflow scheduling, defect/contribution records, approvals, budgets, audit, rollout, cutover, and rollback orchestration.

The migration service stores its own domain records and references LLMLang semantic entities/snapshots through stable Toolchain interfaces. It must not require Migration Units or Mirror Bindings to be first-class SPG objects. A different storage model is acceptable if identity, provenance, versioning, and consistency requirements are met.

### 13.4 Decision test for proposed LLMLang changes

For every proposed capability, classify it as language core, Toolchain/compiler, runtime/library, or external migration service. Prefer the outermost layer that satisfies the requirement. Promote a capability inward only when a concrete semantic limitation demonstrates that the outer layer cannot provide the required guarantee. Record the evidence and compatibility impact; do not infer a core-language requirement from the fact that a migration workflow needs the capability.

AIVibeFlow is one possible orchestrator, not a dependency of the LLMLang language or Toolchain. The same LLMLang capabilities must remain usable by other orchestrators and standalone tooling.

## 14. Required research questions

1. Which source entity identities survive compiler changes, refactoring, generated code, macros, templates, and dynamic dispatch?
2. What is the minimal common semantic model and which facts must remain opaque?
3. How should MU boundaries be selected and dependency completeness measured?
4. How are one-to-many, many-to-one, split, merge, wrapper, and adapter lineages represented?
5. Which frontends provide enough semantics, and how is incompleteness detected?
6. How can incremental analysis avoid full re-import while remaining sound after lost events or build changes?
7. How do source diffs map into RT-20 plans and RT-24 semantic diff/merge?
8. Which contracts can be extracted automatically and how is uncertainty represented?
9. Which differential harnesses are valid for stateful, async, concurrent, effectful programs?
10. What is equivalence at FFI boundaries for ownership, errors, cancellation, and cleanup?
11. How are duplicate side effects prevented in shadow execution?
12. How are defects attributed when behavior differs and the contract is incomplete?
13. What evidence is required before proposing an upstream fix?
14. How are downstream fixes maintained when upstream rejects/delays them?
15. How are accepted changes reconciled when merged patch differs from submitted patch?
16. Which actions require human approval and how is authority enforced?
17. How do cutover/rollback work when persistent schemas or external effects differ?
18. Which capabilities can be prototyped before LLMLang compiler/runtime completion?
21. For every proposed capability, which layer owns it: language core, Toolchain/compiler, runtime/library, or external migration service?
22. Which concrete requirements, if any, cannot be met without changing LLMLang core semantics?
23. Can Migration Unit and Mirror Binding records remain entirely outside SPG and LLMLang semantic storage while preserving stable references and provenance?
19. What are costs of source indexing, mirror maintenance, differential execution, and provenance?
20. How do we prevent partial frontends or incomplete tests from creating false confidence?

## 15. Experimental plan and falsifiers

Use at least two languages with materially different semantics (recommended initial pair: Rust and Go; add Python or C++ as dynamic/template-heavy or ABI-heavy discriminator). Select real, actively maintained repositories with tests, dependencies, module boundaries, and upstream history.

Prototype:
1. import a bounded source subset and produce symbol/dependency inventory;
2. capture reproducible build/test baseline;
3. create MUs and Mirror Bindings;
4. implement a small LLMLang mirror and adapter boundary;
5. introduce upstream implementation-only, API, move/rename, add/remove, dependency, generated-code, and conflicting changes;
6. compare incremental analysis with a clean full-analysis oracle;
7. seed source, mirror, adapter, and oracle defects and test attribution;
8. prepare native upstream patch and simulate accepted/rejected/modified PR outcomes;
9. exercise shadow/canary/cutover/rollback with stateful and side-effecting fixtures;
10. interrupt jobs and event delivery to test recovery/replay.

Mandatory negative controls: incomplete symbol index; missing dependency edge; stale binding revision; lost/duplicated/out-of-order events; same-name collision and rename; source split/merge; nondeterministic oracle; hidden shadow side effect; FFI ownership/error mismatch; rejected/modified upstream fix; baseline changes during patch preparation; tests passing despite seeded semantic defect.

Compare incremental results with fresh analysis of the same pinned baseline. Unexplained under-approximation, silent binding reassignment, untracked downstream patch, or unsafe duplicate side effect falsifies the relevant approach.

## 16. Required deliverables

Layered responsibility map; terminology/domain model; alternatives and decision matrices; source frontend/Toolchain capability matrix; identity and Mirror Binding proposal; MU selection method; lifecycle/state transitions; incremental source-change/reconciliation protocol; contract/equivalence evidence model; ABI/adapter comparison; defect taxonomy and reproducer record; upstream contribution/downstream divergence protocol; external workflow contract; threat model/authorization matrix; executable prototypes, fixtures, tests, benchmarks, negative controls; explicit evidence for any proposed language-core change; traceability from conclusions to sources/experiments/limitations; implementation roadmap with prerequisites and unresolved decisions.

## 17. Acceptance criteria for the research

Ready for integrated review only when every required question has an evidence-backed answer or explicit unresolved decision; alternatives have been compared; incremental analysis is checked against full-analysis oracles; identity/binding covers rename, move, split, merge, ambiguity; differential tests include stateful effects and negative controls; defect attribution distinguishes seeded source/mirror/adapter/oracle defects or records uncertainty; contribution replay covers accepted/rejected/deferred/modified patches; cutover/rollback and shadow safety are prototyped; security/publication authority are explicit; finite tests are not claimed as universal proof; and cross-links/dependencies are reviewed against RT-19/20/22/23/24/27; every capability is assigned to the correct architectural layer; no migration-domain record or workflow is placed in language core without demonstrated semantic necessity.

This is a research brief. It selects no source frontend, identity strategy, SPG schema, migration state machine, equivalence guarantee, interop ABI, rollout policy, or automated contribution authority.
