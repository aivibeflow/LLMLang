# RT-35 — Semantic Function Discovery and Retrieval

**Status:** Research brief; retrieval architecture, ranking policy, and semantic compatibility rules remain open\
**Priority:** P0\
**Research area:** RT-35 — Semantic Function Discovery and Retrieval\
**Related:** RT-03 core semantics; RT-04 types, effects, ownership, and capabilities; RT-05 SPG and semantic identity; RT-06 dependencies; RT-07 formal verification; RT-08 testing and evidence; RT-09 compiler/frontends/IR; RT-11 incremental computation and caching; RT-12 libraries and artifact reuse; RT-14 AI-native authoring/context; RT-16 security and trust; RT-18 evolution; RT-19 Toolchain Server; RT-20 call-site compatibility and hash propagation; RT-24 canonical semantic representation and identity; RT-31 syntax and Toolchain optimization.

## 1. Goal

Research a Toolchain-level mechanism for discovering callable functions by semantic intent and requirements when source-level name search is unavailable, insufficient, or deliberately not used.

In LLMLang, a call binds to the hash of an exact immutable function/operation version. That hash is the deterministic invocation identity, not a search key. Function discovery therefore needs a separate retrieval representation that can locate candidate functions from a natural-language intent, a structured requirement, or a combination of both.

The central proposal is **Semantic Function Discovery (SFD)**:

- derive one or more semantic fingerprints from a canonical semantic description of each discoverable function;
- index those fingerprints for semantic retrieval, including vector nearest-neighbour search (KNN/ANN);
- combine approximate retrieval with exact structured filtering and compatibility analysis;
- resolve the result to an exact function hash before emitting a call.

SFD is a Toolchain/platform capability. It must not make embedding similarity part of LLMLang program semantics, function identity, or call execution.

## 2. Scope and non-goals

### In scope

- Canonical semantic descriptions and derived, versioned function fingerprints.
- Semantic retrieval from natural-language intent, structured requirements, and hybrid queries.
- Vector KNN/ANN indexes and alternative retrieval/ranking mechanisms.
- Structured candidate filtering by types, contracts, preconditions, effects, capabilities, ownership, errors, and other applicability constraints.
- Compatibility checking, ranking, ambiguity handling, provenance, and exact hash binding.
- Index construction, incremental updates, invalidation, persistence, distribution, access control, and reproducibility.
- Retrieval-quality, safety, latency, and cost benchmarks.
- Toolchain APIs for discovery, explanation, and resolution.

### Out of scope

- Replacing exact hash-based invocation with runtime semantic lookup.
- Treating a nearest-neighbour score as proof of substitutability or compatibility.
- Making function names mandatory or treating names as semantic identity.
- Defining embedding vectors, a specific embedding model, vector database, or ANN algorithm as language requirements.
- Allowing an embedding/index change to alter a function hash or program meaning.
- Silently selecting an arbitrary candidate when several candidates remain materially different or insufficiently distinguished.

## 3. Identity, description, fingerprint, and index

The research must keep four concepts distinct:

1. **Function identity:** the exact immutable semantic/operation version identified by its project-defined hash. This is the value ultimately bound at a call site.
2. **Canonical semantic description:** structured, authoritative information about the function's purpose, signature, contracts, behavior, effects, constraints, and relevant provenance. It must be derived from or validated against the semantic model; a free-form summary alone is not authoritative.
3. **Semantic fingerprint:** one or more derived representations used to retrieve and compare candidates. Fingerprints may include text, structured features, embeddings, or other learned/engineered representations.
4. **Search index:** a rebuildable, versioned, potentially distributed acceleration structure over fingerprints and metadata. It is derived data, not the source of truth.

Changing an embedding model, vector normalization, ANN implementation, ranking weights, or index layout must not change function identity. Fingerprint and index versions must record their derivation inputs and be reproducible or explicitly marked as non-reproducible.

## 4. Candidate fingerprint model

Do not assume that one embedding of source code or one prose description is sufficient. Compare a canonical multi-aspect description and multiple derived fingerprints, including:

| Aspect | Information to represent | Retrieval use |
|---|---|---|
| Intent / purpose | Problem solved, operation goal, domain concepts | Find functions from a task statement |
| Inputs | Parameter roles, semantic types, accepted domains, ownership/borrowing requirements | Match required input data and usage |
| Outputs | Result meaning, shape, ownership, guarantees | Match required result |
| Preconditions | Required state, validity, resource/capability availability | Exclude inapplicable candidates |
| Postconditions / behavior | Observable guarantees, state transitions, failure behavior | Distinguish similar operations |
| Effects / capabilities | I/O, mutation, synchronization, external interaction, authority required | Enforce effect and authority constraints |
| Errors | Error cases, propagation, recoverability, result/error shape | Match caller handling requirements |
| Constraints | Bounds, determinism, ordering, resource limits, environmental assumptions | Filter or rank by applicability |
| Cost characteristics | Complexity and measured resource/performance properties, when available | Optional optimization among compatible candidates |

The study should compare at least: one combined embedding; separate aspect embeddings; text-plus-structured hybrid fingerprints; and non-vector baselines. It must test whether separate vectors improve recall or precision enough to justify indexing and maintenance cost.

## 5. Query and retrieval model

Support three query forms without requiring source-level function names:

- **Intent query:** natural-language task, such as “read the complete contents of a file”.
- **Structured requirement:** explicitly stated input/output types, required guarantees, allowed effects, capabilities, and constraints.
- **Hybrid query:** intent plus hard and soft constraints.

Candidate retrieval should be a staged process:

1. Normalize and validate the query; preserve explicit constraints and provenance.
2. Derive query representations compatible with the selected fingerprint/index versions.
3. Retrieve a bounded candidate set through one or more channels: KNN/ANN over semantic fingerprints, structured indexes, exact metadata/contract lookup, and optionally lexical search over descriptive metadata.
4. Merge and deduplicate candidates while retaining retrieval-channel and score provenance.
5. Apply hard eligibility filters and semantic compatibility checks.
6. Rank only the remaining eligible candidates using documented relevance and preference criteria.
7. Explain the decisive matches, exclusions, unknowns, and trade-offs.
8. Bind the selected exact function hash into the call representation.

The architecture must allow a non-vector implementation or multiple retrieval channels to replace or supplement KNN without changing language semantics or the Toolchain discovery contract.

## 6. Compatibility and selection rules

**Retrieval similarity is candidate-generation evidence only.** It is not a compatibility proof.

The study must distinguish:

- semantic relevance: whether a function appears to address the requested goal;
- type compatibility: whether arguments and results satisfy the caller's explicit requirements;
- contract compatibility: whether preconditions can be established and required postconditions are guaranteed;
- effect/capability compatibility: whether effects and authority are permitted;
- behavioral substitutability: whether observable behavior and failure modes satisfy the requested contract;
- operational suitability: optional preferences such as complexity, latency, allocation, or locality.

Hard constraints must be checked independently of vector similarity. Unknown or incomplete evidence must not be interpreted as compatibility. A candidate that is semantically close but violates a hard constraint must be excluded, not rescued by a high similarity score.

Where several candidates remain compatible, ranking may use soft preferences, but the system must preserve meaningful distinctions. If the evidence does not justify one unique choice, return an explicit ambiguous result with candidate explanations or request clarification. Never silently turn an arbitrary top-1 ANN result into a binding.

## 7. Toolchain boundary and call binding

SFD belongs to Toolchain discovery services and their indexes/adapters. The language's call semantics remain simple and deterministic: a resolved call references the exact function/operation hash and any separately required explicit arguments or bindings.

The research should define transport-neutral operations for:

- submitting an intent/requirements query;
- inspecting candidate summaries and compatibility evidence;
- requesting a detailed explanation or comparison;
- resolving a candidate to an exact immutable hash;
- validating that the selected hash remains available and that the call binding is valid for the current semantic snapshot.

MCP, CLI, IDE, and agent workflows should use the same domain contract. Runtime execution must not repeat KNN search or silently re-resolve an already-bound call.

## 8. Index lifecycle, consistency, and security

Investigate:

- Index build and rebuild from authoritative semantic descriptions.
- Incremental updates when a function, contract, dependency, or discoverability metadata changes.
- Separation of semantic identity changes from fingerprint/index refreshes.
- Cache keys and invalidation for query embeddings, candidate sets, compatibility results, and ranking.
- Version compatibility across function descriptions, fingerprint schemas, embedding models, and index generations.
- Snapshot consistency: a search result must identify the semantic snapshot and exact function versions against which it was computed.
- Deleted, superseded, inaccessible, or stale candidates and race conditions between search and call binding.
- Namespace, package, workspace, visibility, authorization, and tenant isolation; retrieval must not leak inaccessible function metadata.
- Untrusted or misleading descriptions, embedding/index poisoning, adversarial near-neighbours, and provenance validation.
- Reproducible diagnostics and explanations for candidate inclusion, exclusion, and final resolution.

A stale or incomplete index may reduce recall, but it must not authorize an invalid call. Before binding, validate the exact candidate against the current permitted snapshot or require an explicit snapshot-bound workflow.

## 9. Required experiments and metrics

Build a benchmark corpus with functions that are semantically close but not interchangeable, functions with different names but equivalent purposes, overlapping signatures with different behavior, different signatures implementing related goals, explicit hard-constraint violations, missing/unknown contracts, and adversarially misleading descriptions.

Compare lexical/name search, structured-only retrieval, one-vector KNN, multi-aspect KNN, hybrid retrieval, and reranking/compatibility pipelines.

Measure at least:

- Recall@K and candidate-set coverage;
- precision@K, MRR, and nDCG for relevance;
- compatible-candidate recall and false-compatible/unsafe-selection rate;
- hard-constraint violation rate after filtering and at final binding;
- ambiguity detection quality and unjustified top-1 selection rate;
- performance under paraphrase, synonym, multilingual, underspecified, and adversarial queries;
- index freshness and stale-result behavior;
- query latency, indexing/update cost, storage, memory, and embedding/API cost;
- explanation completeness and reproducibility;
- sensitivity to embedding-model and index-version changes.

Report task-level results, confidence/uncertainty, corpus construction, model/index versions, and failure cases. A high Recall@K is not sufficient if false-compatible selection or silent ambiguity remains unsafe.

## 10. Open research questions

1. What is the canonical semantic description schema, and which fields are authoritative versus descriptive metadata?
2. Should the fingerprint be one vector, a set of aspect vectors, a structured feature bundle, or a hybrid?
3. Which embedding models and ANN/index algorithms provide useful retrieval under LLMLang's workload and privacy constraints?
4. Which compatibility checks can be decided statically, which require proofs or runtime evidence, and how are unknowns represented?
5. How should query intent be translated into explicit hard constraints without inventing requirements?
6. How are equivalent implementations distinguished from merely related operations?
7. What ranking policy is explainable and stable enough for agent workflows?
8. When should the system return multiple candidates or ask the caller to clarify?
9. How should index updates interact with immutable semantic snapshots, packages, workspaces, and distributed Toolchain instances?
10. What minimum benchmark and safety thresholds must be met before SFD can be used for automatic candidate resolution?

## 11. Candidate architecture vectors

| Vector | Retrieval strategy | Hypothesis | Main risk |
|---|---|---|---|
| A | Structured-only | Explicit contracts/types provide high precision without embedding uncertainty | Poor discovery from vague natural-language intent |
| B | Single semantic embedding + KNN | A compact vector retrieves useful candidates cheaply | Collapses distinct behavior/effects into one similarity score |
| C | Multi-aspect embeddings + KNN | Separate intent, I/O, behavior, and effect vectors improve recall and explainability | More index complexity and calibration work |
| D | Hybrid retrieval + hard compatibility filters + reranking | Approximate retrieval provides recall while formal checks protect correctness | Higher latency and integration complexity |
| E | Multiple independent retrieval channels with calibrated fusion | Lexical, structured, vector, and graph signals cover complementary query types | Fusion may be difficult to calibrate and reproduce |

These are research alternatives, not selected implementation choices. The preferred candidate must be determined by controlled experiments.

## 12. Exit criteria

- A canonical function-description candidate schema and fingerprint-versioning proposal are documented.
- A benchmark corpus includes close-but-incompatible and differently named equivalent-purpose functions.
- At least structured-only, single-vector, multi-aspect, and hybrid retrieval baselines are compared.
- Candidate retrieval quality and unsafe-selection behavior are measured separately.
- Hard compatibility checks, unknown handling, ambiguity behavior, and exact hash binding are demonstrated in a bounded prototype.
- Index lifecycle, snapshot consistency, privacy/access isolation, and stale-result handling have explicit contracts and tests.
- The recommended architecture is supported by reproducible results and documented limitations; no embedding or ANN choice is promoted to language semantics.

## 13. Relationship to other research

RT-35 builds on RT-03/04 for meaning and compatibility; RT-05/24 for immutable identity and canonical semantic representation; RT-06/11 for dependency and index invalidation; RT-07/08 for soundness and benchmark evidence; RT-09/19 for Toolchain APIs and integration; RT-12 for reusable library/package discovery; RT-14/31 for agent intent, context, and controlled AI evaluation; RT-16 for authorization and index trust; RT-18 for version evolution; and RT-20 for exact call-site binding, caller compatibility, and hash propagation.

RT-35 does not decide LLMLang function syntax, function naming conventions, or call semantics. It researches how the Toolchain helps an author or agent discover the correct exact function hash before constructing a deterministic call.
