# Semantic Dependency Index — Research Design

**Status:** Research proposal; not a canonical SPG schema or accepted language rule  
**Date:** 2026-11-18  
**Research area:** Semantic foundation, dependency analysis, incremental computation, Toolchain storage  
**Related:** [LLMLang Concept](LLMLang-CONCEPT.md), [Scenario 19 — Dependency Completeness](RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md), [Scenario 20 — Dependency Discovery and Classification](RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md), [Scenario 25 — Formal Semantic Dependency Analysis](RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md), [RT-19 — Toolchain Server](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [RT-20 — Patch Planning and Hash Propagation](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [RT-23 — Shared Semantic State and Multi-Worktree](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md), [RT-24 — Semantic Merge](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md), [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md), [Package System](PACKAGE-SYSTEM.md), [Draft Glossary](../draft/GLOSSARY.md)

> This document synthesizes existing research into a candidate dependency-index contract. It does not settle the canonical SPG object schema, hash envelope, call-graph semantics, or final Toolchain storage format. Proposed field names and relation families are illustrative until reviewed against the accepted semantic model.

**Terminology dependency:** Consult the [Draft Glossary](../draft/GLOSSARY.md) before changing hash roles or typed reference semantics. `OpHash`, `ImplHash`, and `CCHash` name different semantic object identities; `CandidateSetHash` (if used) identifies a finite discovery result, not a conformance class. Do not treat these as interchangeable with generic Content Hashes or with derived dependency-index/evidence digests. The glossary remains a terminology proposal.

## 1. Problem and design objective

LLMLang needs a trustworthy way to answer two different questions:

1. **Forward dependency:** which exact semantic inputs does an immutable object depend on?
2. **Reverse impact:** which exact objects and call sites refer to a changed object, and therefore may need compatibility analysis, revalidation, or a new immutable version?

The index must support package closure, incremental validation/cache invalidation, formal dependency analysis, and RT-20 Change Impact Planning (CIP). These consumers need related but not identical projections. A single untyped edge list is insufficient.

The index is a derived, versioned projection of semantic facts and analysis evidence. It is not a second source of semantic truth and must not infer authoritative dependencies from opaque serialized payloads.

## 2. Existing findings and boundary

The current research establishes the following:

- The LLMLang concept proposes typed SPG objects, immutable content-addressed states, typed hash-relevant edges, and a Merkle-DAG constraint on the hash-relevant relation. It does not define a complete canonical edge schema.
- Scenario 19 establishes that graph traversal over an incomplete graph is unsafe. Completeness must be evidenced for an exact artifact and scope; `UNKNOWN` and `NOT_CHECKED` cannot mean unaffected.
- Scenario 20 separates dependency discovery from semantic classification. Static analysis, traces, sandbox observations, declarations, and proof extraction produce evidence-bearing candidates; they do not automatically create authoritative semantic edges.
- Scenario 25 proposes a sound conservative may-depend graph as the primary safety mechanism. Its soundness is conditional on the modeled semantics, observation boundary, alias/effect/call resolution, and other assumptions. Unsupported or opaque regions remain `UNKNOWN`.
- RT-20 requires complete reverse-reference discovery and a disposition for every relevant caller edge. Migration decisions are call-site-specific, not merely caller-specific.
- RT-23 requires immutable semantic objects/snapshots to be shared across worktrees. Interface mappings remain separately versioned mutable state.
- RT-19 §6.3 and the Package System prototype require storage to return the complete typed outgoing dependency set for an exact object hash. Storage does not discover or guess those dependencies.

Therefore, a production index cannot be implemented correctly until the language's canonical semantic object and reference schema is defined. This proposal specifies a boundary and candidate contract, not that missing schema.

## 3. Separate relations that must not be conflated

The term *dependency* currently covers several distinct relations. Keep them distinguishable in storage and APIs.

| Relation family | Meaning | Typical consumer |
|---|---|---|
| Semantic may-depend | Changing an input may change a contract-visible observation | Impact analysis, sound invalidation |
| Hash-relevant reference | Exact target identity contributes to source object's Content Hash | Merkle hashing, immutable object identity |
| Call/reference | A caller object has a particular call/reference site targeting a callee or unresolved binding | RT-20 caller migration and reverse lookup |
| Type/contract/effect relation | A declaration relies on a type, contract, effect, capability, or invariant | Type/effect/contract checking |
| Build/toolchain input | A compiler, generator, verifier, target profile, or configuration affects a derived artifact or evidence | Build/proof cache |
| Test/proof premise | A test or proof result is bound to exact semantic inputs and assumptions | Evidence invalidation and provenance |
| Provenance/audit observation | An object was observed, generated, reviewed, accessed, or derived from another fact | Audit and explanation; not automatically semantic closure |

These families are not mutually exclusive. A call-site edge may also be hash-relevant and may-depend. Store the relation kind and its independently determined semantic/hash role rather than encoding several meanings in one overloaded enum.

A relation being present does not by itself prove behavioral influence. Conversely, a conservative may-depend edge may exist without a direct source-level reference.

## 4. Candidate index model

The proposal separates four records. They may be materialized in one database or several derived indexes.

### 4.1 Immutable dependency edge

An edge describes one typed outgoing relation from one exact immutable source object version.

Candidate fields:

| Field | Meaning |
|---|---|
| `source_hash` | Exact Content Hash of the source object version |
| `edge_id` | Unique identity within the source version; stable across index rebuilds for the same canonical source |
| `relation_kind` | Typed semantic relation, such as call, type-use, contract-use, effect-use, or composition |
| `target_hash` | Exact target Content Hash when resolved; never silently replaced by a newer version |
| `target_ref` | Typed unresolved/logical reference when no exact target can yet be resolved |
| `site` | Optional semantic location such as call-site identity, expression/field identity, or declaration slot |
| `hash_role` | `REQUIRED`, `EXCLUDED`, `CONDITIONAL`, or `UNKNOWN` for the source object's identity |
| `dependency_role` | Semantic input, control input, configuration, toolchain, environment, external effect, test/proof premise, or another reviewed role |
| `condition` | Explicit condition/selector for a conditional edge; absent only for unconditional edges |
| `resolution_status` | Resolved, unresolved, ambiguous, external, or unsupported |
| `origin` | Canonical declaration, semantic elaboration, formal analyzer, or another declared producer |
| `schema_version` | Version of the edge/index contract used to interpret the record |

The exact encoding, identifiers, and allowed relation kinds remain open. The index must not synthesize `edge_id` from unstable source locations unless the language explicitly makes those locations stable semantic identities.

### 4.2 Conditional and unresolved references

A conditional relation must preserve the condition and the alternatives it selects. Do not flatten it into an unconditional edge to whichever target happened to be selected in one build or runtime observation.

For example, a call whose target depends on an explicit mapping, dispatch rule, or environment may have:
- a declared selector/condition;
- a finite set of statically known target versions, if available;
- an explicit unresolved/external alternative where static resolution is not possible;
- evidence and scope describing what the analyzer actually resolved.

The selected target set is part of a pinned analysis result, not an implicit mutable lookup at read time. A change to the relevant mapping is handled through the separately versioned Interface Mapping Revision and must be included in the planning/build input identity when it affects the result.

Unknown dynamic dispatch, reflection, generated references, or external calls must remain visible as unresolved/opaque scope. They cannot be represented as an empty dependency set.

### 4.3 Discovery candidate and evidence

Discovery tools produce candidates, not authoritative semantic edges.

A candidate/evidence record should pin:
- exact source object hash and semantic snapshot;
- candidate target or input identity, if known;
- relation hypothesis and proposed dependency role;
- discovery method and tool identity/version;
- exact scope, environment, target profile, and observation model;
- evidence artifact digest and source observations;
- classification decision and reviewer/authority, where applicable.

Multiple independent observations of the same candidate must be retained. Merging candidates must not erase source provenance or make a weak observation look like a proof.

### 4.4 Dependency completeness record

Completeness is a separate scoped claim, not a boolean property inferred from successful index construction.

Candidate statuses follow Scenario 19/20:
- `GAP_FOUND`: a relevant missing dependency or unresolved discrepancy was found;
- `SUPPORTED_WITHIN_SCOPE`: available evidence supports the declared set only within its exact scope and assumptions;
- `UNKNOWN`: evidence is absent, stale, unsupported, or insufficient;
- `NOT_CHECKED`: no completeness audit was run.

A record must pin at least the source object hash, snapshot, dependency-set digest, declared scope, semantic/analyzer model version, tool identity, observation-model hash, assumptions, and evidence digest.

Never label `SUPPORTED_WITHIN_SCOPE` as globally complete. A reverse-reference query may be used for a safety-critical plan only when its scope is covered by matching completeness evidence. Otherwise RT-20 planning must fail closed, require an explicit policy-authorized boundary, or schedule conservative full revalidation.

## 5. Caller/callee requirements from RT-20

Call/reference edges need call-site granularity. The caller object alone is not a sufficient key: one caller can invoke the same callee multiple times, and those sites may require different target versions or adaptations.

For each relevant call site, the index/query layer must expose:
- exact caller Content Hash and semantic snapshot;
- call-site identity;
- exact currently referenced callee Content Hash, or an explicit unresolved target;
- relation kind and resolution status;
- any condition/dispatch selector and applicable Interface Mapping Revision;
- evidence and completeness coverage for the reverse-reference query.

RT-20's planner—not the storage layer—records one disposition per relevant edge:
- `migrate`: rewrite this site to the proposed callee version;
- `preserve`: keep the exact old callee version;
- `adapt`: change the caller or add an adapter;
- `fork`: create a separate caller/callee version for a distinct behavior path;
- `unresolved`: insufficient evidence; plan approval is blocked.

The same callee may therefore remain referenced by one caller while another caller moves to a new version. If one shared caller must serve consumers with incompatible behavior requirements, the plan must create a new caller version (or explicit adapter) for the migrating path and retain the old caller version for the preserving path.

Do not implement a global “replace every reference to latest callee” operation.

## 6. Hashing, storage, and query invariants

Hash terminology in this candidate design remains provisional; see the [draft glossary](../draft/GLOSSARY.md). PLAN.md explicitly leaves the `ImpHash`/`ImplHash` spelling discrepancy unresolved until terminology is reconciled.

1. **Exact source identity.** Every outgoing dependency set is keyed by the exact source Content Hash, never by a mutable Stable ID alone.
2. **Immutable publication.** Once published, an object's canonical dependency set cannot be silently edited. A changed semantic reference creates a new source object version when that reference is hash-relevant.
3. **Explicit empty set.** An explicitly empty dependency set is different from missing/uncomputed dependency metadata.
4. **Typed edges.** Every accepted edge has a relation kind and target interpretation; opaque bytes are not parsed heuristically by the storage adapter.
5. **Deterministic projection.** The same exact semantic input and indexer/model version produce a deterministic canonical edge set and digest.
6. **Reverse index is derived.** Incoming-reference indexes are reproducible from immutable outgoing edges and carry the same source/index generation identity.
7. **No silent target substitution.** A query for an exact target hash returns that exact version or a typed missing/unavailable result.
8. **Hash DAG boundary.** Only the hash-relevant relation must satisfy the acyclicity/grouping rules of the eventual canonical hash model. Ordinary SPG relations may be cyclic.
9. **Unknown is not empty.** Unresolved references, unsupported constructs, missing indexes, and incomplete coverage remain explicit and block unsafe completeness claims.
10. **Store does not infer semantics.** Content Store persists and returns trusted index output; semantic extraction/classification belongs to a versioned semantic/indexing layer.
11. **Snapshot consistency.** Forward and reverse queries used by one CIP must refer to the same pinned semantic snapshot and compatible index generation.
12. **Shared semantic state.** Worktree selection does not create or switch a semantic dependency database. Worktrees are regular-file views; immutable semantic objects and snapshots are shared. Interface Mapping Revisions are separately versioned.

## 7. Consumer-specific projections

The same canonical facts can feed multiple indexes, but consumers must declare which projection they need.

| Consumer | Required projection | Safety condition |
|---|---|---|
| Content Store / Package Provider | Complete typed outgoing edges for exact object hashes | Missing index is an error; explicit empty set is valid |
| RT-20 CIP | Reverse call/reference edges with call-site identity and completeness evidence | Every relevant edge gets a disposition; unresolved scope blocks approval |
| Merkle identity | Only hash-relevant edges and exact target hashes | Canonical encoding and acyclic hash relation must be defined |
| Incremental validation/cache | Conservative may-depend closure from exact action inputs | Unknown dependencies prevent unsafe reuse |
| Type/effect/contract checking | Typed declaration/use relations and exact semantic versions | Checker semantics and supported constructs must be explicit |
| Tests/proofs | Exact semantic inputs, premises, assumptions, toolchain and observation model | Evidence reuse requires matching verification identity |
| Audit/explanation | Discovery candidates, observations, provenance and classification history | Audit observations do not automatically enter semantic closure |

## 8. Candidate API boundary

Names are illustrative; exact wire schemas belong to RT-19/RT-22 refinement.

| Operation | Purpose |
|---|---|
| `dependency.outgoing(source_hash, snapshot)` | Return the complete typed outgoing edge set for one exact object version |
| `dependency.incoming(target_hash, snapshot, scope)` | Return reverse references plus index/completeness identity |
| `dependency.inspect(edge_id, source_hash)` | Inspect one exact edge and its classification/evidence |
| `dependency.completeness.inspect(source_hash, scope)` | Retrieve matching scoped completeness evidence |
| `dependency.candidates(source_hash, snapshot)` | Inspect unclassified discovery candidates separately from accepted edges |
| `dependency.rebuild(source_hash, model_version)` | Recompute a derived index from canonical semantic inputs; publish atomically |

All reads participating in one plan must use a pinned semantic snapshot/read view. A rebuild must not expose a partially published outgoing set or reverse index.

## 9. Failure and conservative behavior

The following conditions must not be silently normalized to “no dependencies”:
- source object absent;
- dependency index absent or built with an incompatible schema/model version;
- target unresolved or ambiguous;
- dynamic dispatch or external behavior outside the declared analyzer model;
- discovery discrepancy not classified;
- stale/mismatched completeness evidence;
- reverse index generation not matching the pinned snapshot;
- interface mapping revision missing or stale where mapping affects resolution.

For RT-20, these conditions make the affected region `UNKNOWN` and block approval unless a policy-authorized boundary explicitly accepts the limitation and prescribes conservative validation. For cache/build consumers, they prevent unsafe reuse. For package closure, missing required dependency metadata is an error, not an empty closure.

## 10. Open decisions before implementation

1. What is the canonical SPG schema, and which object kinds can own outgoing references?
2. Which relation kinds are language-level semantic facts versus derived may-depend relations?
3. What is the canonical call-site identity, including nested, overloaded, generated, and macro-like constructs?
4. How are dynamic dispatch, higher-order calls, callbacks, reflection, and external calls represented?
5. What exact condition language and target-set representation are required for conditional edges?
6. Which relation kinds are hash-relevant for each object kind, and how are cycles/group roots handled?
7. How are Interface Mapping Revision scope and resolution semantics incorporated into edge resolution and CIP inputs?
8. Which analyzers are trusted to emit canonical semantic edges, and how are their soundness assumptions versioned?
9. How are completeness evidence and index generations invalidated after semantic-model, analyzer, environment, or toolchain changes?
10. What retention and garbage-collection policy preserves old exact target versions referenced by accepted snapshots and active plans?
11. How should the index support multiple projections without duplicating or contradicting canonical facts?
12. What migration/versioning policy applies when the edge schema evolves?


## 10.1 First executable subset (prototype; not canonical SPG)

An executable candidate subset now exists at `research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_dependency_index.py`.

The prototype deliberately fixes only a small set of rules so they can be tested:

- Schema envelope: `format = llmlang.semantic-object`, `schema_version = 2` (the candidate schema-v1 call-target shape is not silently reinterpreted).
- Object kinds: `function`, `operation`, `type`, `contract`, `implementation`, `effect`.
- Every declaration has an explicit `declaration_id` and object-valued `content`. The content is opaque to the extractor; only the typed reference fields are interpreted.
- Function and Operation may own `call_sites`. Each call site has a caller-local `call_site_id`; each alternative has a `target_id`, exact `target_hash`, nullable explicit `condition`, and mandatory exact `required_contract_hash` selected by the caller for that specific call-site/target alternative.
- A callable target must expose exactly one typed `provides_contract` reference to a Contract object. The extractor carries both `required_contract_hash` and `provided_contract_hash` on the call edge. A synthetic `requires_contract` dependency edge makes the requirement queryable in reverse and hash-relevant to the caller.
- A call edge ID is `call_site_id/target_id`. It is unique within the source declaration and does not depend on display names or array positions.
- Typed reference relations are constrained by source and target kinds: Function/Operation → Type or Contract; Contract → Type; Type → Type; Implementation → Contract or Effect; Effect → Type.
- Publication resolves every exact target hash and checks its stored object kind. Missing targets and kind mismatches are errors.
- Exact target hashes are passed to the existing ContentStore as hash-relevant dependencies. Call-site/reference identity is carried in the dependency role and declaration payload.
- The derived index exposes deterministic outgoing/incoming edges and retains conditional selectors without choosing a target implicitly.

This is an executable **candidate schema**, not acceptance of the final LLMLang SPG model. It has no source parser, no inference from arbitrary payloads, no completeness proof, and no production snapshot lease. The current `ContentStore` is in-memory; index generation is built as a deterministic projection for tests. The candidate schema does not yet settle recursive types, mutually recursive functions, SCC hashing, generic/higher-order calls, external calls, or Interface Mapping Revision semantics. Unsupported constructs must remain outside this subset rather than being coerced into these records.

The prototype tests cover two different callee revisions in two call sites of one caller, multiple conditional targets at one call site, reverse lookup preserving call-site identity, exact required/provided contract bindings, hash sensitivity to a changed call-site requirement, rejection of missing requirements or provided contracts, typed Implementation→Contract/Effect references, malformed/ambiguous schema rejection, caller hash changes when the exact callee revision changes, and snapshot-scoped reverse lookup that excludes historical caller versions while retaining a preserving caller and a migrating caller. `build_dependency_index` remains an all-store diagnostic projection; planning must use `build_snapshot_dependency_index`, which pins the result to the exact snapshot root and includes only its selected object versions. CI workflow: `.github/workflows/semantic-dependency-index.yml`.

## 10.2 Call-site-specific contract binding (candidate schema v2)

The v2 call-target record carries a mandatory `required_contract_hash`. This is the exact Contract object hash the caller requires at that call site and target alternative; it is not inferred from the caller's function-wide references. The selected callee declaration must expose exactly one `provides_contract` reference. The call edge records both hashes, and a separate `requires_contract` dependency edge makes the caller's requirement visible to reverse lookup and dependency closure.

RT-20's `CallSiteDecision` now binds:
- exact base callee hash;
- exact required contract hash from the caller's call-site alternative;
- exact contract hash provided by the base callee;
- exact selected callee hash and its provided contract hash;
- resulting caller hash, disposition, rationale, compatibility status, and evidence ID.

A `preserve` decision must retain the exact base callee and base provided-contract hashes. Any resolved disposition requires compatibility status `PROVEN` and an evidence ID. The prototype includes all these values in the deterministic plan identity and rejects missing or mismatched contract bindings.

This remains a binding/consistency gate, not a proof checker: it does not authenticate the evidence producer or prove behavioral refinement. The generic Contract Content Hash used here is not yet normatively identified with glossary `CCHash`; reconcile that distinction with the identity model before adoption. The candidate schema is versioned as v2 rather than silently accepting the changed v1 record shape.

## 11. Validation plan and exit criteria

Before implementing a production extractor:

- Define the accepted SPG object and reference schema for a deliberately small supported subset.
- Specify canonical edge encoding, edge identity, relation taxonomy, target resolution, conditional references, and hash-role rules for that subset.
- Build a reference extractor from canonical semantic objects—not generic `Entity` payload guesses.
- Independently validate extracted edges against hand-authored fixtures and a formal or otherwise trusted semantic model.
- Demonstrate sound may-depend over-approximation for the supported subset, or return `UNKNOWN` for unsupported constructs.
- Demonstrate exact forward and reverse queries pinned to one immutable snapshot/index generation.
- Test explicit-empty versus missing index, stale generations, unresolved targets, conditional targets, and duplicate call sites.
- Exercise RT-20 cases: two callers selecting different callee versions; two call sites in one caller selecting different versions; and a shared caller requiring a version split.
- Verify that RT-23's shared semantic store is used across at least two worktrees, with mappings versioned separately.
- Connect the resulting trusted edge set to the Content Store read contract and Package Provider only after the schema/extractor boundary is validated.

Passing these criteria supports a scoped implementation decision for the supported subset. It does not establish a complete dependency model for unrestricted LLMLang programs.

## 12. Current recommendation

Adopt this separation as the next research target:

1. Canonical SPG declarations/references define semantic facts.
2. A versioned semantic/indexing layer derives immutable typed outgoing edges and reproducible reverse indexes.
3. Discovery tools contribute evidence-bearing candidates and completeness audits, not unreviewed authoritative edges.
4. Formal analysis supplies a conservative may-depend relation where its soundness assumptions are met; unsupported regions remain `UNKNOWN`.
5. RT-20 consumes call-site-specific reverse references and makes migration decisions per edge.
6. Content Store persists exact immutable object bytes and the trusted complete dependency projection; it does not invent dependency semantics.

The immediate implementation target should be a **small, explicit SPG subset and its canonical extractor**, not a generic dependency parser or a production database integration.


## 13. Snapshot-scoped reverse-query completeness binding

The extractor prototype exposes `query_snapshot_incoming(store, snapshot, target_hash, scope, evidence)`. It returns incoming typed edges selected by the exact Semantic Snapshot together with an explicit completeness status. The query result is bound to the exact `snapshot_root` and `target_hash`, caller-supplied scope, dependency-index schema version and extractor identity, and a deterministic digest of the exact returned edge set. It also retains an external evidence identifier, observation-model identity, assumptions, exclusions, and discrepancies.

Statuses are `GAP_FOUND`, `SUPPORTED_WITHIN_SCOPE`, `UNKNOWN`, and `NOT_CHECKED`. Missing evidence yields `NOT_CHECKED`. Any mismatch in snapshot, target, scope, index schema, extractor identity, or edge-set digest yields `UNKNOWN`; it must never be treated as an empty caller set. A `GAP_FOUND` record must identify a discrepancy. A `SUPPORTED_WITHIN_SCOPE` record cannot carry unresolved discrepancies and remains limited by its declared assumptions and exclusions.

This adapter validates evidence bindings only. It does not authenticate the producer, establish that the observation model is sound, or prove completeness. The evidence producer must independently audit the declared reverse-reference scope. Production integration must bind evidence to the accepted SPG semantic model, exact Toolchain/Snapshot generation, analyzer and observation-model versions, and authenticated evidence storage.


## 14. RT-24 relationship

RT-24 consumes typed semantic and hash-relevant relations from this research but does not treat the index as the source of semantic truth. In particular, a snapshot-scoped incoming-edge query is not a complete reverse-reference proof unless matching scoped dependency-completeness evidence exists. See [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md) for the current prototype limitations and the required fail-closed boundary.

## Public-interface integration (2026-11-24; proposed)

Candidate edges/projections: scoped name lookup (including absent/ambiguous candidates and aliases), exact operation/public-contract use, implementation-owned provided contract, provider binding selection, external symbol mapping, and claim-specific evidence dependencies. Separate hash-relevant edges from resolution, provenance and proof relations. A caller's abstract proof may read only the public revision while execution, link and whole-system evidence read exact selected providers. Include negative scoped lookups and completeness state so a newly inserted shadowing export cannot escape invalidation. Keep the single provided Contract reference on the provider; do not add a duplicate authoritative edge from each caller.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
