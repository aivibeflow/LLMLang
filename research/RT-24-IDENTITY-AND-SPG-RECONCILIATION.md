# RT-24 Supplement — Identity and SPG Reconciliation

**Status:** Reconciliation report; no identity, SPG schema, hash envelope, or language-semantics decision is accepted by this document  
**Date:** 2026-11-18  
**Scope:** Reconcile RT-24 with the repository's existing identity, SPG, dependency-index, package-identity, and executable-prototype work  
**Primary document:** [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md)

## 1. Executive result

The repository does not currently contain a single standalone RT-05 specification. The identity work is distributed across Research Studies 05–08, the LLMLang concept, package identity research, semantic dependency-index research, RT-20, and executable prototypes.

The current materials establish useful constraints but do **not** select one canonical entity-identity architecture or define a complete SPG schema.

Two identity models remain in tension:

1. **Stable Entity ID + Content Hash:** a stable opaque ID identifies a logical entity across edits; a content hash identifies one immutable state. This is the direction recommended by Research Study 05 and reflected in the current LLMLang concept.
2. **Content-addressed immutable values + explicit lineage/occurrence selection:** each semantic value is addressed by its canonical content and hash-relevant dependencies; history/continuity is represented by explicit lineage and snapshot-scoped selection. Research Study 06 explores this alternative. Research Study 08 shows that an occurrence-state hash does not itself provide continuity across edits.

RT-24 must therefore remain identity-neutral at its merge-core boundary. It can specify exact immutable state references, typed edges, snapshot-scoped selection, provenance, and fail-closed matching, but it cannot assume that a permanent Stable Entity ID is the selected identity model or that content hashes alone identify logical continuations.

**Recommendation for the first prototype:** use exact immutable content hashes to address stored values; keep selection/slot keys and lineage as separate explicit records; do not infer continuity from equal content, names, paths, source-specification references, or structural similarity. This is a bounded experimental interface, not a final identity decision. It allows the prototype to test value hashing and three-way selection merging without prematurely choosing the permanent logical-identity architecture.

## 2. Source-of-truth map and findings

| Source | Current finding | Consequence for RT-24 |
|---|---|---|
| [LLMLang Concept](LLMLang-CONCEPT.md), §3 | SPG is a typed graph; concept describes Stable ID plus Content Hash, immutable states, provenance, dependencies, and generated human-readable views | Conceptual baseline, not a complete wire schema; its identity model must be reconciled with Studies 06–08 before becoming normative |
| [Research Study 05](RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md) | Recommends name-free core, Stable Entity ID for logical continuity, Content Hash for immutable state, names as aliases | Strong candidate; not accepted |
| [Research Study 06](RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md) | Explores immutable content-addressed values with explicit lineage and specification provenance; recommends testing content-only identity rather than assuming every entity needs permanent Stable ID | Competing candidate; provenance/lineage must not enter semantic value hash unless semantically relevant |
| [Research Study 07](RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md) | Stress-tests content-only identity and its edge cases | Must be reviewed together with Studies 05, 06, and 08 before identity selection |
| [Research Study 08](RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md) | Occurrence-state hash identifies one immutable contextual state, not a timeless occurrence; continuity requires a scoped selector, snapshot mapping, or explicit lineage | Occurrence identity and entity/value identity must remain separate |
| [Core Language Semantics / RT-03](CORE-LANGUAGE-SEMANTICS.md) | No semantic profile selected; full execution/observation semantics remain open | “Semantic equivalence” in RT-24 means canonical structural SPG equivalence for the supported profile, not full behavioral equivalence |
| [Semantic Dependency Index](SEMANTIC-DEPENDENCY-INDEX.md) | Separates may-depend, hash-relevant, call/reference, type/contract/effect, build, test/proof, and provenance relations; completeness is scoped evidence | RT-24 must not collapse all relations into one dependency edge or treat an index query as complete without evidence |
| [Package Manifest and Identity](PACKAGE-MANIFEST-AND-IDENTITY.md) | Separates object hashes, logical index hash, package content root, package archive hash, descriptive package identity, provenance, and optional cache indexes | Package/archive identity is a separate layer; package roots and resolution inputs are not automatically the SPG project snapshot schema |
| [RT-20](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) | Function versions are immutable; hash-relevant references bind exact callee versions; call-site-specific migrate/preserve/adapt/fork/unresolved decisions; hash envelope remains open | Merge must delegate caller-impact decisions to RT-20 and preserve exact call-site identities |
| [RT-23](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) | Shared immutable semantic objects/snapshots; versioned mutable interface mappings; exact snapshot/mapping revision pinned into commit | Mapping revisions are a separate versioned domain and commit must bind exact semantic and mapping roots |

There is no current research/RT-05-... file in the repository tree. References to RT-05 in RT-20/RT-24 are research-area cross-references, not a pointer to a standalone current specification. Until the project consolidates that work, cite the actual studies and documents above.

## 3. Identity model: decisions and non-decisions

### 3.1 Concepts that must remain distinct

| Concept | Meaning | May be mutable? | Current status |
|---|---|---:|---|
| Immutable semantic value | Canonical typed content plus exact hash-relevant outgoing references | No | Supported direction |
| Value/Content Hash | Address of one exact immutable semantic value | No | Exact envelope/encoding/algorithm unresolved |
| Logical entity identity | Continuity of a conceptual entity across versions | No, if adopted | Stable-ID vs content-only alternative unresolved |
| Occurrence state | A value selected in a role/slot/context at one immutable snapshot state | No | Candidate model in Study 08 |
| Current selection | Which value/occurrence occupies a scope/slot in one project snapshot | Only by creating a new snapshot | Required for branch/project state |
| Lineage | Explicit relation between immutable states or occurrences (supersedes, derived_from, split_into, merged_from, moved_from, etc.) | No; append new facts | Required where continuity is asserted |
| Human alias/name/path | Presentation or lookup binding | Yes | Must not be treated as semantic identity by default |
| Provenance/evidence | Origin, authorship, analysis, approval, observation, proof/test evidence | Append-only/separately versioned | Excluded from value hash unless it changes semantics |
| Project/Snapshot root | Immutable selection of current semantic roots and resolution inputs | No | Exact construction unresolved |
| Package Content Root | Identity/integrity of a package's selected contents and logical index | No | Separate package-level candidate |

### 3.2 Stable ID versus content-only identity

Neither model may be silently chosen in RT-24.

If the Stable Entity ID model is selected:
- merge matching may use the same stable ID across base/ours/theirs;
- each side's exact immutable state is still identified by its Content Hash;
- alias/rename operations do not change the Stable Entity ID;
- split/merge operations require explicit lineage and potentially multiple successors.

If content-only values are selected:
- the content hash identifies a value, not a continuing logical entity;
- merge matching cannot infer that two changed values are versions of the same entity from hashes alone;
- a snapshot-scoped slot/selection mapping or explicit lineage must establish the intended continuation;
- equal content hashes permit value deduplication but do not prove equal occurrence, ownership, governance, or logical lineage.

In both models, human names and file paths are not safe identity keys. A call-site ID or local slot key is not automatically stable across arbitrary edits: its scope and lifecycle must be specified.

### 3.3 Occurrence and contextual identity

Study 08's candidate formula H(ValueHash, ContextStateHash, Role, Slot) identifies one immutable occurrence state. It changes when any hash-relevant input changes. It therefore cannot itself select the successor occurrence.

For the prototype:
- represent the current selection as a snapshot-scoped mapping from an explicit slot/selection key to an exact value hash;
- represent lineage as separate explicit records;
- do not use a mutable parent content hash, display name, ordinal, or path as an implicit persistent slot;
- do not hash provenance or lineage into a semantic value unless a reviewed semantic rule says it affects behavior.

Whether slot keys are snapshot-local, scope-stable, or persistent scoped identities remains an explicit design decision.

## 4. Hash and canonicalization reconciliation

### 4.1 Current candidates

The repository contains multiple experimental approaches:

- LLMLang-CONCEPT.md describes a domain-separated semantic hash over entity kind, canonical semantic content, and sorted hash-relevant target hashes; SHA-256 is suggested as an initial algorithm with algorithm agility.
- research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_graph.py uses deterministic compact JSON (sort_keys, UTF-8, no NaN), SHA-256, a llmlang.semantic-value.v1 domain field, object kind, payload, and sorted hash-relevant dependency records.
- research/PROTOTYPES/PACKAGE-IDENTITY-01/package_identity.py uses explicit typed encoding, domain-separated SHA-256, and algorithm-tagged sha256:<hex> values for package/index identity.
- PACKAGE-MANIFEST-AND-IDENTITY.md keeps the final digest algorithm, typed encoding, index schema, and package-root construction open.

These are separate experimental encodings. They are not interchangeable and none is the accepted SPG hash envelope.

### 4.2 Required hash layers

Do not overload one digest for different purposes. The implementation model should distinguish at least:

1. **Semantic Value Hash:** one immutable typed semantic value and only its hash-relevant outgoing references.
2. **Snapshot/Project Root:** exact selected roots and the explicit resolution inputs needed to interpret that snapshot.
3. **Package Content Root:** package roots, dependency-selection policy, resolution inputs, and logical index membership/relationships, according to the package contract.
4. **Action/Verification Key:** exact semantic closure plus tool/verifier identity, configuration, assumptions, target profile, and other action inputs.
5. **Physical Git identity:** Git blob/tree/commit IDs.
6. **Evidence/provenance digest:** integrity of evidence records, without automatically changing semantic value identity.

A Package Content Root is not a Semantic Value Hash. A Git tree hash is not a semantic snapshot identity. A verification/action key is not a semantic identity.

### 4.3 Hash-relevant dependency relation

Only explicitly classified hash-relevant edges participate in a value hash. The dependency-index research distinguishes this from may-depend, call/reference, type/contract/effect, build, proof/test, and provenance relations.

The hash-relevant relation must be acyclic for recursive Merkle hashing. This does **not** imply that every relation in the full SPG is acyclic. Non-hash semantic relations may form cycles if the selected language/schema semantics allow them. The schema must classify relation families and hash roles independently.

Changing a selected exact target hash changes the source value hash. A caller that deliberately preserves an older exact target remains a different, valid immutable value from a caller that migrates to a newer target.

### 4.4 Canonicalization requirements

Before selecting a wire format, the supported profile must define:
- canonical typed values and allowed scalar/container types;
- ordered versus unordered collections;
- normalization of numeric, string, and Unicode values;
- representation of optional, absent, null, and default values;
- typed edge encoding and deterministic edge ordering;
- domain separators and algorithm-tagged digest representation;
- canonicalization/schema versioning and migration rules;
- behavior for unknown fields and unsupported constructs (fail closed or explicit versioned extension).

The prototype's JSON canonicalization and package prototype's typed encoding are useful fixtures, not a basis for declaring one format accepted.

## 5. Reconciliation with the existing executable SPG subset

### 5.1 What the current prototype actually implements

research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_dependency_index.py currently accepts a narrow llmlang.semantic-object envelope, schema version 1:

- object kinds: function, operation, type, contract, implementation, effect;
- typed declaration references: uses_type, uses_contract, extends_type, implements_contract, uses_effect, with restricted target kinds;
- function and operation declarations may contain call_sites;
- each call site has call_site_id and one or more exact targets with target_id, target_hash, and optional condition;
- reference IDs and call-site IDs are checked for duplicates within one declaration;
- publication resolves exact target hashes and validates target kinds;
- the index derives typed outgoing/incoming edges and has a snapshot-scoped builder that excludes historical values not selected by the snapshot.

The current source is an extractor over a supplied versioned declaration envelope. It does not parse LLMLang source or arbitrary SPG payloads. It is not a canonical repository import/export implementation.

### 5.2 Hash behavior in the prototype

ContentStore.put hashes:
- the domain discriminator llmlang.semantic-value.v1;
- object kind;
- the normalized payload;
- sorted explicitly hash-relevant dependency records (relation, exact target_hash, role).

Dependencies marked non-hash-relevant are excluded from the stored semantic value hash. The semantic_dependency_index publisher supplies exact referenced target hashes as dependencies.

Important limitations:
- the declaration envelope's declaration_id is currently part of the normalized payload and therefore affects the value hash; this has not been reconciled with the alternative identity models;
- call_site_id and target_id are explicit fields and contribute through the normalized payload and dependency role, but the prototype does not prove their stability across edits or source transformations;
- the prototype uses an untagged hexadecimal SHA-256 string, unlike the package prototype's algorithm-tagged digest representation;
- its JSON canonicalization is limited to the Python JSON data model and is not the final typed canonical encoding;
- no canonical source-file inventory/import/export or repository-level semantic merge is implemented.

Do not treat these prototype field names or behavior as normative.

### 5.3 Completeness and reverse references

The snapshot-scoped index prevents historical objects retained in the content store from being mistaken for active objects in the selected snapshot. This is useful and should be retained as a prototype property.

However, the current index is built from explicit declarations only. It does not yet carry the dependency-completeness records required by SEMANTIC-DEPENDENCY-INDEX.md and Scenario 19. It cannot prove that every direct, indirect, dynamic, generated, external, or otherwise supported reference has been discovered. An incoming() result is therefore not automatically a complete reverse-reference set.

Until completeness evidence is integrated:
- the index may support fixture-level and explicitly scoped tests;
- it must not authorize a clean repository-wide merge or RT-20 CIP;
- missing/unknown resolution must not be represented as an empty edge set;
- the merge coordinator must return insufficient_context or a corresponding explicit gap status where completeness is required.

### 5.4 Snapshot root and merge prototype limitation

semantic_graph.py computes a snapshot root from the selection mapping and parent roots. This is an experimental snapshot/history identity, not yet the accepted definition of semantic project-state identity. The project must decide whether causal parents belong in the semantic root, in separate history/provenance metadata, or in both distinct digests.

The prototype's merge_snapshots merges only a mapping from logical selection keys to value hashes. It is not a semantic object graph merge: it does not merge typed object fields, references, contracts, call graphs, mapping revisions, or repository files. It is a useful selection-map fixture, not evidence that RT-24's graph-wide merge is implemented.

The current prototype creates a value only after its dependency targets already exist in the content store. This naturally restricts the hash-relevant construction order and is consistent with a Merkle-DAG experiment, but it does not define the full SPG cycle model or a production graph-import algorithm.

## 6. Supported first-prototype boundary

The first semantic merge prototype should be explicitly described as a **snapshot-selected immutable value graph subset**, not as the LLMLang SPG in full.

### 6.1 Minimum supported data

- typed immutable values with kind, canonical payload, and exact hash-relevant outgoing references;
- explicit snapshot selection keys mapping to exact value hashes;
- explicit typed references with target kind and exact target hash;
- explicit call-site records with one or more target alternatives and conditions;
- explicit lineage/provenance side records, kept outside semantic value identity unless proven semantic;
- separate, pinned mapping revision reference, even if mapping merge is initially unsupported.

### 6.2 Required exclusions and fail-closed cases

The prototype must not claim support for:
- arbitrary LLMLang source parsing or full SPG schema;
- unresolved/dynamic/external/generated calls unless their state and completeness evidence are explicitly modeled;
- inferred rename, split, merge, or successor relationships;
- full behavioral equivalence or general language-semantic validation;
- complete repository import/export, Git integration, or crash-safe commit;
- automatic Interface Mapping Revision conflict resolution.

Unknown object kinds, unsupported relation kinds, missing targets, duplicate IDs, incomplete source inventory, stale mapping baselines, and missing completeness evidence must fail closed for any safety-critical merge result.

### 6.3 Prototype merge matching rule

For this first prototype only:
- merge the **snapshot selection map** by its explicit selection keys, using the three-way rule over base/ours/theirs values;
- merge immutable semantic values by exact content hash (deduplicate equal values; never mutate them);
- do not infer that different hashes are versions of one logical entity;
- if two sides change the same selection key to different values, emit a structured selection conflict;
- if selection keys cannot be shown to refer to the same scoped slot, return insufficient context rather than matching by display name/path;
- after combining selections, validate the complete selected dependency closure and all available typed references;
- do not report clean_candidate while completeness, RT-20 CIP, or mapping revision gates are unimplemented or unsatisfied.

This is a safe experimental baseline, not the final semantic merge algorithm. It deliberately avoids resolving the Stable-ID/content-only debate by hiding it inside a heuristic matcher.

## 7. Required amendments to RT-24

RT-24 should be interpreted with these constraints, and its next revision should:
1. replace the unqualified term “semantic entity identity” with explicit immutable value address, optional logical identity, occurrence/selection key, and lineage;
2. state that Studies 05–08 remain unresolved and no single RT-05 spec exists in the current repository;
3. define semantic round-trip equality as canonical structural SPG equality for the supported schema/profile, not full behavioral equivalence;
4. classify the hash-relevant relation as a DAG without imposing a DAG constraint on every SPG relation;
5. specify snapshot selection separately from entity/value identity and keep parent/causal history outside the semantic root unless a later decision explicitly includes it;
6. describe the existing semantic_graph.py/semantic_dependency_index.py implementation as a narrow fixture, including its declaration_id and call-site identity limitations;
7. prohibit clean merge claims until scoped dependency-completeness evidence and RT-20 CIP are available.

## 8. Open decisions that must remain open

1. Stable Entity ID + Content Hash versus content-addressed values with explicit lineage/selection.
2. Whether identical semantic values may be deduplicated across logically distinct occurrences and what governance/ownership state attaches to occurrences.
3. The stable scope and lifecycle rules for declaration IDs, call-site IDs, target IDs, and selection/slot keys.
4. Exact canonical typed encoding, hash algorithm/tag, domain separation, and schema migration.
5. Whether all hash-relevant relations are acyclic by construction and how recursive semantic constructs are represented without cyclic hash preimages.
6. The exact SPG entity kinds, relation families, and semantic/hash roles.
7. Snapshot root composition and whether causal parent roots are separate history metadata.
8. How dependency-completeness evidence covers static, indirect, dynamic, generated, external, and unresolved references.
9. How source import/export maps source declarations to values, occurrences, and lineage without path/name heuristics.
10. Whether and how mapping revisions participate in project-root identity versus a separately pinned root.

## 9. Next research and implementation order

1. Reconcile Studies 05–08 into one explicit decision record; include rename, identical-value/different-occurrence, split/merge, move, call-site stability, and branch-merge scenarios.
2. Reconcile the chosen identity model with RT-03 language semantics and RT-04 type/effect model before freezing canonical semantic fields.
3. Define the minimum SPG declaration and edge schema for the supported prototype, including identity/occurrence/lineage distinctions and hash-role classification.
4. Extend the dependency index with exact scoped completeness records and fail-closed reverse-reference queries.
5. Define canonical encoding/hash envelope as a separately versioned decision, then add adversarial vectors.
6. Define snapshot root independently from Git tree identity and explicitly decide treatment of causal parents and mapping revision.
7. Only then implement canonical repository import/export and semantic diff/merge beyond the current selection-map fixture.

## 10. References

- [LLMLang Concept](LLMLang-CONCEPT.md)
- [RT-03 — Core Language Semantics](CORE-LANGUAGE-SEMANTICS.md)
- [Study 05 — Name-Free Semantic Entities](RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md)
- [Study 06 — Content-Addressed Entity Identity](RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md)
- [Study 07 — Content-Only Identity Stress Tests](RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md)
- [Study 08 — Context-Derived Occurrence Addressing](RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md)
- [Semantic Dependency Index](SEMANTIC-DEPENDENCY-INDEX.md)
- [Package Manifest and Content Identity](PACKAGE-MANIFEST-AND-IDENTITY.md)
- [RT-20 — LLM Patch Planning and Hash Propagation](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)
- [RT-23 — Single-Instance Toolchain and Multi-Worktree](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md)
