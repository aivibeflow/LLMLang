# Research Scenario 09: Dependency-Driven Evolution Without Mandatory Occurrence Identity

**Status:** Research / exploratory  
**Date:** 2026-11-16  
**Scope:** LLMLang semantic identity, dependency graphs, version evolution, selective requirement-driven change

**Predecessors:** RESEARCH-SCENARIO-05 through RESEARCH-SCENARIO-08.

---

## 1. Executive Summary

This research revisits the identity problem from a different starting point.

> A content-addressed semantic value, together with explicit directed dependency edges and immutable project snapshots, may be sufficient for ordinary code evolution. A separate persistent identity for every use-site or occurrence may be unnecessary.

Consider a function named calculate_tax used by 100 callers. A new business rule applies only to three callers. Those three callers can be changed to reference a new immutable function value H1; the other 97 callers continue to reference H0. Both values coexist. Each changed caller receives a new content hash because its dependency reference changed. Unchanged callers retain their old hashes.

This is not merely theoretical. Unison documents a closely related content-addressed code model: definitions are hashed from syntax trees, names are separate metadata, and dependencies are represented by hashes. Changing a name binding does not mutate old definitions; callers that reference an old hash continue to do so until explicitly updated. Unison also exposes dependency and dependent queries.

Sources:
- https://www.unison-lang.org/docs/the-big-idea/
- https://www.unison-lang.org/docs/language-reference/hashes/
- https://www.unison-lang.org/docs/usage-topics/general-faqs/
- https://www.unison-lang.org/blog/dependents-release/

**Preliminary recommendation:** prototype a dependency-driven, content-addressed semantic graph before introducing mandatory Occurrence or global stable IDs. Treat those mechanisms as optional extensions whose necessity must be demonstrated by concrete use cases.

This does not establish that every identity-like mechanism can be removed. Stable names, public interfaces, ownership, lifecycle, authorization, and independently managed entities may still require separate metadata or identity mechanisms.

---

## 2. Reframed Problem

Earlier scenarios asked how to preserve the identity of an entity while its content changes. That may assume too early that a function is a persistent mutable entity.

An alternative interpretation is that a function definition is an immutable value. What appears to be the same function changing is a sequence of different values connected by references, requirements, and project snapshots.

Initial state:

    H0 = calculate_tax(old_rule)

    Caller001 -> H0
    Caller002 -> H0
    ...
    Caller100 -> H0

A requirement change affects only callers 001, 002, and 003:

    H1 = calculate_tax(new_rule)

    Caller001-v1 -> H1
    Caller002-v1 -> H1
    Caller003-v1 -> H1

    Caller004-v0 -> H0
    ...
    Caller100-v0 -> H0

No global mutation of calculate_tax is required. No automatic rewrite of every inbound reference is required. Both values remain valid and addressable.

The central question becomes:

> Can the immutable value graph, its dependency edges, and its selected snapshots represent meaningful evolution and branching without mandatory occurrence identity?

The answer appears to be yes for a large class of code evolution, provided the graph model distinguishes semantic dependencies from non-semantic relations and makes selection explicit.

---

## 3. Core Model Under Test

### 3.1 Semantic Value

A semantic value is an immutable, canonical representation of a definition or other semantic object.

Candidate definition hash:

    ValueHash = H(domain_separator, canonical_semantic_form)

For a function, the canonical semantic form should include:
- normalized syntax or canonical semantic IR;
- parameter and binding structure independent of source names where appropriate;
- type and effect information when it affects meaning;
- exact references to hash-relevant dependencies;
- language and semantic-version information needed to interpret the representation.

Names, comments, source locations, author metadata, and provenance should not be included unless the language explicitly defines them as semantically relevant.

Two definitions with the same canonical semantic form have the same ValueHash and can be deduplicated, even if created in different projects or derived from different requirements.

### 3.2 Dependency Edge

A dependency edge is a directed, typed relation from a dependent value to a value it relies on.

Example:

    CallerA1 --calls--> CalculateTaxH1
    CallerD0 --calls--> CalculateTaxH0

An edge should identify:
- source value;
- target value or interface;
- relation kind;
- semantic role (call, type use, constant use, effect capability, etc.);
- whether the edge participates in the source value's semantic hash;
- optional structural locator for diagnostics.

If the exact callee reference is part of a definition's meaning, that reference must be represented in the canonical form that is hashed. It cannot be merely an untracked index generated after hashing.

### 3.3 Project Snapshot

A project snapshot is an immutable selection of semantic values and other graph records.

    ProjectRoot = H(canonical_snapshot_manifest)

The snapshot manifest selects current values of relevant roots, modules, packages, requirements, and other project-level records.

The mutable notion of current project is a reference to a ProjectRoot, not a mutation of the root itself:

    main -> ProjectRootA
    feature-tax -> ProjectRootB

This resembles Git's distinction between immutable objects and mutable references such as branches. See https://git-scm.com/docs/gitdatamodel.

### 3.4 Lineage and Provenance

Lineage records how values were derived. Provenance records why a change was made and which requirements, decisions, or requests motivated it.

These relations should not automatically participate in the semantic ValueHash.

Examples:

    CallerA1 --supersedes--> CallerA0
    CallerA1 --derived_from--> CallerA0
    CallerA1 --implements--> RequirementR17
    CallerA1 --introduced_by--> ChangeSetC42

The same semantic value may be reused in two projects while having different provenance records in each project. Including provenance in the value hash would prevent this reuse.

---

## 4. Stress Test: One Function, 100 Callers, Only Three Change

### 4.1 Initial graph

One immutable function value exists:

    Tax0 = H0

One hundred caller definitions reference it:

    Caller[001] -> H0
    Caller[002] -> H0
    ...
    Caller[100] -> H0

Each caller's canonical semantic representation includes its exact call dependency. Therefore each caller hash commits to the particular callee hash it uses.

### 4.2 Requirement change

A business rule changes in a context that applies only to callers 001, 002, and 003.

A new immutable function value is created:

    Tax1 = H1

Only three caller definitions are updated:

    Caller[001-v1] -> H1
    Caller[002-v1] -> H1
    Caller[003-v1] -> H1

    Caller[004-v0] -> H0
    ...
    Caller[100-v0] -> H0

### 4.3 Expected hash consequences

| Node | Expected result |
|---|---|
| Tax0 | Unchanged; H0 remains addressable |
| Tax1 | New value; H1 |
| Caller 001–003 | New values because dependency references changed |
| Caller 004–100 | Unchanged; exact references still point to H0 |
| Unchanged ancestors of callers 004–100 | Unchanged unless another hash-relevant input changes |
| Ancestors that depend on changed callers 001–003 | New values only if their own semantic dependency closure changes |

The graph does not require global replacement of H0 by H1. It requires an explicit candidate change to the three affected callers.

**Conclusion:** this scenario is representable without a globally mutable identity for calculate_tax, an occurrence record for each call site, or automatic rewriting of every inbound edge.

---

## 5. The Crucial Hashing Boundary

The model works only if the system is precise about what is hashed. Three concepts must not be collapsed.

### 5.1 Local Semantic Value Hash

ValueHash identifies the canonical semantic content of one value, including its direct hash-relevant references.

For a caller that invokes a concrete callee:

    CallerValueHash = H(canonical_body, exact_callee_reference)

Changing the callee reference changes the caller's ValueHash.

### 5.2 Transitive Dependency Closure

The transitive closure describes everything a value depends on, directly or indirectly. It is useful for:
- verification cache keys;
- build and execution reproducibility;
- impact analysis;
- dependency completeness checks;
- deployment closure.

It need not be redundantly folded into every node's local hash if direct references are already committed transitively through the Merkle DAG.

For A -> B -> C, if B's hash commits to C and A's hash commits to B, A indirectly commits to C. Rehashing A from the entire transitive closure at every step is unnecessary.

### 5.3 Project Root

The project root identifies one selected graph state. It changes when selected root values or relevant manifest metadata change. It may change even when many individual semantic values are reused unchanged.

### 5.4 Recommended separation

    ValueHash       = identity of immutable semantic value
    ProjectRoot     = identity of selected project snapshot
    ClosureDigest   = identity of a specified dependency closure

ClosureDigest is useful as a derived query or verification input, not necessarily as the identity of the semantic value itself.

---

## 6. Which Edges Participate in Semantic Hashing?

Not every graph edge should change a value's hash.

| Relation | Usually hash-relevant? | Reason |
|---|---:|---|
| Direct call to concrete function value | Yes | Exact implementation affects semantics |
| Type reference | Yes | Type constrains interpretation and compatibility |
| Constant/value reference | Yes | Referenced value affects computation |
| Effect/capability requirement | Yes | Constrains behavior and execution |
| Exact interface/contract reference | Yes | Contract constrains caller |
| Concrete implementation binding | Depends | Yes for statically bound calls; separate binding record for dynamic dispatch |
| Implements requirement | No | Traceability metadata, not necessarily runtime semantics |
| Derived from previous value | No | Historical lineage |
| Introduced by ChangeSet | No | Change provenance |
| Authored by / owned by | No | Governance metadata |
| Source path / line number | No | Presentation and navigation |
| Human-readable alias | Usually no | Names are bindings, not semantic content |
| Project membership | No for value identity | Snapshot selection metadata |

The system should maintain distinct edge classes, rather than treating every reference as one generic graph relation.

### 6.1 Actual dependencies versus declared dependencies

A declared dependency graph must be a sound over-approximation of actual dependencies. Missing edges can make incremental analysis unsound; redundant edges can cause unnecessary invalidation.

Bazel explicitly distinguishes actual and declared dependencies and states that correct builds require actual dependencies to be covered by declared dependencies:
https://bazel.build/versions/7.3.0/concepts/dependencies

For LLMLang this principle is broader than build correctness: a hidden semantic dependency can invalidate impact analysis, verification reuse, and reproducibility claims.

### 6.2 Avoiding false invalidation

If a requirement merely records that a function was created to satisfy a business rule, changing that requirement's descriptive metadata should not necessarily change the function's ValueHash.

Instead:
- semantic contract changes may change the relevant contract hash;
- provenance records may be updated independently;
- traceability completeness may become stale;
- verification obligations may need re-evaluation.

This permits independent evolution of semantics and evidence.

---

## 7. Caller-to-Implementation Versus Caller-to-Contract

A direct-reference model is not sufficient for every language construct.

A caller may invoke:
1. a concrete immutable implementation;
2. an abstract interface or contract;
3. a virtual method selected by runtime dispatch;
4. a function selected through configuration or dependency injection;
5. an external API or ABI symbol.

These cases require different reference semantics.

### 7.1 Direct concrete call

    Caller -> ImplementationHash

The caller commits to the exact implementation. Updating the implementation requires changing the reference in the caller, which creates a new caller value.

### 7.2 Contract-based call

    Caller -> ContractHash
    ImplementationA --satisfies--> ContractHash
    ImplementationB --satisfies--> ContractHash

The caller commits to the contract, not to one concrete implementation.

A separate resolution or deployment record selects the implementation:

    BindingSnapshot:
      ContractHash -> ImplementationAHash

Changing the selected implementation need not change the caller's semantic value if the language defines the call as contract-based and the contract remains unchanged. However, the executable/deployment closure must include the exact binding selection.

### 7.3 Dynamic dispatch

Dynamic dispatch may select different implementations based on runtime type or environment. The semantic model must represent:
- dispatch rule;
- candidate implementation set or lookup semantics;
- relevant type/class hierarchy;
- runtime environment assumptions.

A simple edge to one implementation hash would be incorrect if program semantics permit multiple implementations.

### 7.4 External interfaces

Public API names, exported symbols, ABI identifiers, routes, command names, environment variables, and serialized field names are externally observable contracts.

These may require stable interface bindings even when internal implementation values are content-addressed.

A useful separation:

    InterfaceHash       = immutable contract shape/semantics
    ImplementationHash  = immutable implementation value
    BindingSnapshot     = selected implementation for an interface
    ExternalName        = stable externally observable name

An external name is not necessarily the identity of the implementation. It is a binding point whose compatibility and evolution need explicit rules.

**Conclusion:** do not universally replace every reference with an implementation hash. Represent binding semantics explicitly. A first prototype can support direct concrete calls and exact type references, while treating dynamic dispatch and external interfaces as explicit extensions.

---

## 8. Requirement Evolution and Selective Impact

A requirement change does not imply that every value with a historical relationship to the requirement must be changed.

The system needs at least three separate operations:

1. **Traceability traversal:** find values linked to the requirement.
2. **Semantic impact analysis:** determine which values may be semantically affected.
3. **Change planning:** decide which values should actually be changed in a candidate.

These sets are not necessarily equal.

Example:

    R17 --implemented_by--> Tax0
    R17 --used_in_context--> Caller001
    R17 --used_in_context--> Caller002
    R17 --used_in_context--> Caller003

A changed requirement R18 may affect only three business contexts. The system should not infer that every historical consumer of Tax0 must migrate.

### 8.1 Many-to-many traceability

Requirement-to-code relations are naturally many-to-many:
- one requirement may be implemented by several values;
- one value may contribute to several requirements;
- one requirement may split into several successor requirements;
- several requirements may merge into one;
- one implementation may remain valid for one requirement while another requirement evolves.

Therefore provenance and traceability cannot be represented by a single source requirement hash embedded as the identity of a function.

A relation record should support:
- source requirement value;
- target semantic value;
- relation kind (implements, refines, constrains, tests, documents, supersedes);
- scope/context;
- evidence and verification status;
- validity within a project snapshot.

### 8.2 Requirement split and merge

A requirement split may produce two successor requirements while implementation values map selectively to either, both, or neither. A merge may combine requirements without requiring implementation values to be merged or reidentified.

The merge changes traceability and potentially verification obligations, not necessarily semantic value hashes.

**Important:** a requirement relation is not automatically a semantic dependency. If a function's runtime behavior does not depend on a requirement record, embedding that record hash into the function hash couples provenance to implementation identity and defeats semantic deduplication. A formal contract derived from a requirement may be a semantic dependency; the historical fact that a human request motivated the code is provenance.

---

## 9. Parallel Branches and Merging

Immutable values naturally support parallel evolution.

Initial snapshot:

    Root0:
      CallerA -> H0
      CallerB -> H0

Two branches independently evolve:

    BranchX:
      CallerA1 -> H1
      CallerB  -> H0

    BranchY:
      CallerA  -> H0
      CallerB1 -> H2

A merge can select both independent changes:

    RootMerged:
      CallerA1 -> H1
      CallerB1 -> H2

The merge creates a new snapshot root. It does not mutate existing values.

If both branches change the same caller differently, the conflict is a semantic selection conflict, not a hash collision:

    BranchX: CallerA -> CallerAX
    BranchY: CallerA -> CallerAY

Resolution creates a new candidate value and snapshot. It should preserve both parent roots, both candidate values, the resolution decision, exact selected result, and required approvals and verification evidence.

A proposal created against Root0 must not silently apply to Root1 if its assumptions are stale. The proposal should carry:
- expected base root;
- expected hashes of directly modified values;
- expected hashes of relevant dependencies;
- read set and write set;
- relevant invariant and authority set.

Rebase creates a new proposal revision. It must not silently change the meaning of an already approved proposal.

---

## 10. Transitive Invalidation and Incremental Verification

If a caller's direct dependency changes, the caller value changes. Its dependents may also change if their own semantic references point to the previous caller value.

For A -> B -> C, if C changes:
- C receives a new ValueHash;
- B receives a new ValueHash if its canonical content references C's new hash;
- A receives a new ValueHash if it references the new B hash.

Only values on hash-relevant dependency paths are affected.

### 10.1 Semantic invalidation versus verification invalidation

These are different.

A value can remain byte-for-byte and semantically identical while a verification result becomes stale because:
- verifier version changed;
- proof configuration changed;
- obligation set changed;
- assumption or environment changed;
- policy changed.

Thus:

    ValueHash != VerificationKey

A verification key should commit to the exact value and all relevant proof inputs, including verifier identity, configuration, assumptions, environment, and obligation identity.

### 10.2 Dependency completeness

Incremental systems are only sound when dependencies are complete enough. Bazel's Skyframe documentation describes dependency registration and how the reverse transitive closure of changed inputs determines which nodes need rebuilding:
https://bazel.googlesource.com/bazel/%2B/d167757e358b239f261afa41c0725ae74e86aee5/site/en/reference/skyframe.md

For LLMLang, hidden inputs are especially dangerous:
- environment variables;
- global mutable state;
- time and randomness;
- network/database state;
- compiler/runtime version;
- target platform;
- dynamically loaded code;
- implicit configuration.

The language and execution model must either represent such inputs as explicit dependencies/effects or weaken reproducibility and verification claims.

---

## 11. Deduplication and Different Business Provenance

Suppose two projects independently create semantically identical functions:

    ProjectA: calculate_tax -> Hx
    ProjectB: calculate_tax -> Hx

If canonical semantic content is identical, both should reuse Hx.

Their provenance may differ:

    ProjectA: Hx --implements--> RequirementA
    ProjectB: Hx --implements--> RequirementB

This is not a contradiction. The semantic value is the same; contextual facts about its use differ.

A project-local relation or traceability record can preserve these differences without changing the value hash.

If two apparently identical values require independent ownership, lifecycle, access control, retention, approval authority, external identity, or audit history, a separate context or governance record may be required.

This does not mean the semantic value itself needs a Stable ID. It means the system needs an identity for the independently governed record.

Do not introduce a context record automatically for every function. That would recreate mandatory Occurrence under another name. Require a concrete lifecycle or governance need.

---

## 12. What the Model Solves and What It Does Not

| Problem | Dependency-driven content addressing |
|---|---|
| Keep old and new function versions | Solves directly |
| Change only three of 100 callers | Solves directly |
| Deduplicate identical definitions | Solves directly |
| Preserve old references | Solves directly |
| Branch and merge immutable code states | Solves with snapshot roots and conflict resolution |
| Compute semantic dependency impact | Solves if edge graph is complete and typed |
| Reuse verification results | Supports it with exact verification keys |
| Requirement split/merge | Requires separate many-to-many traceability relations |
| Different provenance for identical values | Requires separate provenance records |
| Public API/ABI stability | Requires interface and binding model |
| Dynamic dispatch | Requires explicit dispatch semantics |
| Ownership and authorization | Requires governance records/policies |
| Independently managed logical objects | May require a separate identity |
| Hidden environmental dependencies | Requires explicit modeling or weaker guarantees |
| Cyclic definitions | Requires canonical SCC/cycle hashing or another formal strategy |

The hypothesis is strong for semantic values and code evolution, but it is not a universal replacement for every kind of identity in the system.

---

## 13. Cycles and Recursive Definitions

A naïve Merkle DAG cannot directly hash a cyclic dependency graph by recursively hashing every dependency.

Mutually recursive functions introduce cycles:

    f -> g
    g -> f

Possible strategies:
1. hash a strongly connected component (SCC) as one canonical group;
2. assign canonical positions within the SCC and derive member references from the group hash;
3. require recursion to be represented through explicit recursive-group nodes;
4. use a language-level recursion construct with defined hashing semantics.

Unison documents a strategy for mutually recursive definitions: the cycle is treated as a group, recursive references are normalized, members are put in canonical order, and member hashes are derived from the group hash. See https://www.unison-lang.org/docs/usage-topics/general-faqs/.

LLMLang should not assume every semantic graph is a DAG. It should define which subgraph must be acyclic and how recursive semantic groups are canonicalized.

---

## 14. Relevant Existing Systems

### 14.1 Unison — closest precedent

Unison is the most direct precedent for content-addressed definitions:
- hashes identify terms and types;
- names are separate metadata;
- dependency references are represented by hashes;
- immutable definitions coexist across versions;
- dependencies and dependents can be queried;
- changes can be propagated through structured refactoring tools.

Sources:
- https://www.unison-lang.org/docs/the-big-idea/
- https://www.unison-lang.org/docs/language-reference/hashes/
- https://www.unison-lang.org/docs/usage-topics/general-faqs/
- https://www.unison-lang.org/blog/dependents-release/
- https://www.unison-lang.org/docs/ucm-commands/

Important limitation: Unison demonstrates the code-value and dependency model. It does not by itself establish LLMLang's requirements graph, business-context analysis, governance, approval, or formal verification model.

### 14.2 Bazel / Skyframe — dependency precision and incremental evaluation

Bazel distinguishes declared from actual dependencies and uses dependency graphs to determine what must be rebuilt. Skyframe describes incremental evaluation and reverse-transitive invalidation.

Sources:
- https://bazel.build/versions/7.3.0/concepts/dependencies
- https://bazel.googlesource.com/bazel/%2B/d167757e358b239f261afa41c0725ae74e86aee5/site/en/reference/skyframe.md

Relevance: a content-addressed graph is only as useful as its dependency completeness and precision. Over-approximated edges cause unnecessary work; missing edges can make results unsound.

### 14.3 Git — immutable objects and mutable references

Git stores immutable objects identified by hashes and uses mutable refs for branch and tag names.

Source: https://git-scm.com/docs/gitdatamodel

Relevance: LLMLang can use immutable semantic values plus mutable project/branch pointers without assigning a mutable identity to every value.

### 14.4 Nix — content addressing and dependency propagation caveat

Nix documents how input-addressed derivations can cause downstream store paths to change when inputs change, while content-addressed outputs can avoid propagation when output bytes remain the same.

Source: https://github.com/NixOS/nix/blob/master/doc/manual/source/store/derivation/outputs/content-address.md

Relevance: dependency identity and produced-value identity answer different questions. LLMLang should distinguish the identity of a definition from the identity of an execution/build result.

---

## 15. Candidate Minimal Data Model

The following is a research proposal, not an accepted LLMLang specification.

### 15.1 Immutable semantic records

    SemanticValue {
      value_hash
      semantic_kind
      canonical_form
      direct_dependencies[]
    }

A dependency entry:

    Dependency {
      relation_kind
      target_hash
      semantic_role
      hash_relevant
      structural_locator?
    }

The canonical form includes hash-relevant dependency references. Non-hash-relevant graph edges are stored separately.

### 15.2 Snapshot record

    ProjectSnapshot {
      root_hash
      parent_roots[]
      selected_roots[]
      selected_bindings[]
      traceability_root?
      policy_root?
    }

The exact manifest schema remains open.

### 15.3 Separate relations

    TraceabilityRelation {
      source_requirement_hash
      target_value_hash
      relation_kind
      scope
      evidence_refs[]
    }

    LineageRelation {
      source_value_hash
      target_value_hash
      relation_kind
      change_set_ref?
    }

    ExternalBinding {
      interface_or_symbol
      selected_contract_hash
      selected_implementation_hash?
      compatibility_policy
    }

    GovernanceRecord {
      governed_object_ref
      owner_or_scope
      lifecycle_policy
      authorization_policy
    }

A GovernanceRecord may refer to a semantic value or another record. It should only be introduced when independent governance is needed.

### 15.4 No mandatory Occurrence

There is no mandatory Occurrence record in the minimal model.

If experiments demonstrate a need for stable use-site identity (for example, a source-level call site must retain independent identity across arbitrary rewrites), add it as an optional record with a precisely defined lifecycle.

---

## 16. Candidate Evolution Algorithm

Given a requirement change:

1. Pin the current ProjectRoot.
2. Create a requirement-change proposal against that exact root.
3. Traverse typed traceability relations to find potentially relevant semantic values.
4. Compute semantic impact using hash-relevant dependencies, contracts, effects, and context.
5. Separate impacted values from merely traceable values.
6. Propose edits to the exact caller values that need to change.
7. For each changed caller, resolve the intended callee/interface binding and create a new immutable semantic value.
8. Recompute only changed values and their hash-relevant dependents.
9. Create a candidate ProjectSnapshot selecting the intended new values.
10. Check graph integrity, type/effect compatibility, interface compatibility, and requirement coverage.
11. Run or reuse verification only when exact verification keys match.
12. Resolve semantic conflicts and stale preconditions.
13. Obtain approval for the exact candidate root and evidence set where policy requires it.
14. Atomically advance the selected project head from the expected baseline root to the candidate root.

No global replace-all-references operation is implied.

---

## 17. Failure Modes and Falsification Tests

The hypothesis must be rejected or extended if any of the following cannot be modeled without mandatory occurrence identity or another stable logical identity.

### F1. Identical value, independently governed lifecycle

Two semantically identical functions must be independently retired, authorized, or audited in ways that cannot be expressed by separate context/governance records.

**Test:** create identical values in two projects with different ownership, retention, and approval policies. Verify that semantic deduplication remains possible without merging governance.

### F2. Stable call-site identity is required

A call site must preserve an identity across edits even when its enclosing function's canonical semantic value changes.

**Test:** move, split, duplicate, and rewrite call sites. Determine whether structural locators plus lineage and snapshot-local selection are sufficient. If not, define the exact use case that requires a stable slot key.

### F3. Dynamic binding changes behavior without caller hash change

A caller references an interface, while a mutable binding selects an implementation.

**Test:** change the binding while keeping caller and interface unchanged. Ensure executable/deployment snapshot identity changes and verification is invalidated where required.

### F4. Hidden dependency

A function reads a global value or environment input not represented in its dependency graph.

**Test:** change the hidden input and demonstrate that the system either detects it or refuses to claim sound incremental verification/reproducibility.

### F5. Requirement lineage ambiguity

A requirement splits or merges and the same implementation value remains related to multiple successor requirements.

**Test:** preserve traceability and evidence without embedding requirement identity into the semantic value hash.

### F6. Parallel merge ambiguity

Two branches make incompatible changes to the same semantic context.

**Test:** merge must produce an explicit conflict or resolution, never silently select a winner based on write order.

### F7. Recursive dependency hashing

A mutually recursive group changes one member.

**Test:** canonical group hashing must be deterministic and independent of declaration order and source names, while preserving exact semantics.

### F8. External compatibility

An internal implementation hash changes while the public symbol or serialized contract remains stable.

**Test:** prove that implementation evolution does not accidentally change external identity, and that incompatible interface changes are detected.

---

## 18. Prototype Plan

A small prototype can falsify most core assumptions without implementing a language.

### Phase 1 — Value graph

Implement canonical function records, content hashes, direct hash-relevant dependency references, immutable value storage, project snapshot roots, and branch pointers.

Acceptance:
- identical canonical definitions deduplicate;
- changing a direct dependency changes only the dependent value and its hash-relevant ancestors;
- unchanged callers retain their hashes;
- old values remain addressable.

### Phase 2 — 100-caller experiment

Generate one calculate_tax value H0, 100 caller definitions referencing H0, H1 with a changed tax rule, and a change to only three callers.

Acceptance:
- exactly three caller values change at the direct caller layer;
- the other 97 caller values are reused;
- H0 remains available;
- both H0 and H1 can coexist in one snapshot;
- reverse dependency queries identify the 100 callers;
- impact analysis selects only the three intended contexts when supplied with relevant requirement/context relations.

### Phase 3 — Requirements and provenance

Implement separate many-to-many traceability and lineage records.

Acceptance:
- one requirement can map to many values;
- one value can map to multiple requirements;
- requirement split/merge does not force semantic value rehashing;
- provenance differences do not defeat semantic deduplication.

### Phase 4 — Contracts and binding

Implement interface/contract values, implementation values, and explicit binding snapshots.

Acceptance:
- changing an implementation behind a stable interface does not mutate the caller value;
- binding snapshot identity changes;
- incompatible contract changes are detected;
- deployment and verification inputs pin exact bindings.

### Phase 5 — Concurrency and verification

Implement immutable branch roots, expected-root and expected-value preconditions, explicit merge conflicts, and verification records keyed by exact inputs.

Acceptance:
- stale proposals cannot silently apply;
- merge preserves both parent roots and explicit resolution;
- verification evidence is reused only for exact matching keys.

---

## 19. Revised Conclusions

### 19.1 Main conclusion

For ordinary function definitions and statically bound calls, a content-addressed dependency graph appears sufficient to model:
- independent versions;
- selective caller migration;
- parallel development;
- immutable history;
- semantic deduplication;
- transitive dependency impact.

The 100-caller scenario does not require persistent identity for every call site. Changed callers become new immutable values; unchanged callers continue to reference the old value.

### 19.2 What should be reconsidered in earlier scenarios

The earlier Occurrence model may be over-generalized if applied to every semantic entity or call site.

Keep these concepts separate:
- **Semantic value:** what the definition means; content-addressed.
- **Dependency reference:** which exact semantic value or contract is used.
- **Snapshot selection:** which values are current in a project state.
- **Lineage:** how values evolved.
- **Provenance/traceability:** which requirements and decisions relate to values.
- **Binding:** which implementation is selected for an interface or external symbol.
- **Governance identity:** which object is independently owned, authorized, or lifecycle-managed.

Only the first two are necessarily part of ordinary function semantics.

### 19.3 Remaining identity needs

Stable identity may still be justified for:
- externally observable symbols and API contracts;
- independently governed project resources;
- mutable references such as branch heads and aliases;
- long-lived user-facing objects whose identity must survive semantic replacement;
- stable source-level slots if a concrete editing or governance use case requires them.

These are separate problems. They should not force every function definition to carry a global Stable ID or Occurrence.

### 19.4 Recommendation

**Do not make Occurrence mandatory in the LLMLang core at this stage.**

First prototype:
1. content-addressed semantic values;
2. exact hash-relevant dependency references;
3. immutable project snapshots and mutable root references;
4. separate lineage and requirement traceability;
5. explicit interface/implementation binding where required.

Only add an identity layer when a falsification test demonstrates a requirement that cannot be represented by these primitives.

This is a research recommendation, not an accepted language design decision.

---

## 20. Open Questions

1. What canonical semantic representation should be hashed: normalized AST, typed IR, or dedicated semantic IR?
2. Which dependency classes must be hash-relevant in the core language?
3. How should effect dependencies and environmental inputs be represented?
4. Should interface/contract hashes be first-class semantic values from the first prototype?
5. How should overload resolution and dynamic dispatch be pinned?
6. What is the canonical hashing algorithm for recursive SCCs?
7. How should a project snapshot select module-level and package-level roots?
8. Which traceability relations need explicit scope or validity intervals?
9. How should aliases and external names evolve without introducing accidental global identity?
10. What minimum governance record is required for ownership and authorization?
11. Can stable source locations be replaced by snapshot-local structural locators for all editing workflows?
12. How can impact analysis distinguish potentially affected from must change without pretending graph reachability proves business relevance?

---

## 21. References

1. Unison, The big idea: https://www.unison-lang.org/docs/the-big-idea/
2. Unison, Hashes: https://www.unison-lang.org/docs/language-reference/hashes/
3. Unison, General FAQs — propagation and recursive definitions: https://www.unison-lang.org/docs/usage-topics/general-faqs/
4. Unison, Dependents view, 2025-09-26: https://www.unison-lang.org/blog/dependents-release/
5. Unison, UCM command reference — dependencies and dependents: https://www.unison-lang.org/docs/ucm-commands/
6. Bazel, Dependencies: https://bazel.build/versions/7.3.0/concepts/dependencies
7. Bazel, Skyframe: https://bazel.googlesource.com/bazel/%2B/d167757e358b239f261afa41c0725ae74e86aee5/site/en/reference/skyframe.md
8. Git, Git data model: https://git-scm.com/docs/gitdatamodel
9. Nix, Content-addressed derivation outputs: https://github.com/NixOS/nix/blob/master/doc/manual/source/store/derivation/outputs/content-address.md

---

## 22. Status of Findings

| Finding | Status |
|---|---|
| Selective migration of three out of 100 callers is representable with immutable content-addressed values | Strongly supported by the model |
| A caller's exact concrete callee reference should participate in its semantic hash | Strong design consequence for static direct calls |
| A separate mandatory Occurrence is unnecessary for the 100-caller scenario | Supported |
| Requirement provenance should be separate from semantic value identity | Strong design recommendation |
| Project roots should be separate from value hashes | Strong design recommendation |
| Dynamic dispatch requires explicit binding semantics | Open design requirement |
| Stable identity is never needed anywhere in LLMLang | Not established |
| All dependency edges can be represented as one DAG | Not established; recursion and non-semantic relations require distinctions |
| Dependency-driven model is sufficient for the entire LLMLang system | Not yet established; requires prototype and falsification tests |
