# LLMLang Research Taxonomy

**Status:** Working research-management document; not a language specification or an architecture decision  
**Updated:** 2026-11-17

## 1. Purpose

This taxonomy defines the research space that must be explored before selecting an integrated LLMLang specification. It is deliberately broader than the current prototype or the next implementation milestone.

A research topic is an area of uncertainty, not necessarily one decision. Each topic may produce several viable development vectors. A vector is a coherent approach or family of choices, with explicit assumptions, evidence, constraints, trade-offs, and relationships to vectors in other topics.

The taxonomy is a living index. It must be revised when research reveals new aspects, splits an area into independent questions, or shows that two apparently separate topics are inseparable.

## 2. Research-area inventory

| ID | Research area | Scope / questions | Existing material | Priority / status |
|---|---|---|---|---|
| RT-01 | Product goals and design constraints | Intended users, workloads, AI-native goals, correctness expectations, human authority, non-goals, portability and complexity constraints | [LLMLang concept](LLMLang-CONCEPT.md), [Development Engine RFC](RFC-DEVELOPMENT-ENGINE.md) | P0; consolidate and validate |
| RT-02 | Intent, requirements, and specification model | From human intent to clarified requirements, typed requirement representations, contracts, invariants, provenance, ambiguity and change | [Scenario 15](RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md), [Scenario 17](RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md), [Scenario 18](RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md) | P0; active research line |
| RT-03 | Core language semantics | Values, expressions, control flow, evaluation, errors, state, determinism, recursion, modules, observable behavior and semantic boundaries | [LLMLang concept](LLMLang-CONCEPT.md), [Formal verification architecture](LLMLANG-FORMAL-VERIFICATION.md), [Scenario 34](RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md) | P0; foundational gaps remain |
| RT-04 | Type system, effects, ownership, and capabilities | Static typing, refinement, subtyping/coercions, effects, resource ownership/lifetimes, aliasing, capabilities, concurrency and memory model | [LLMLang concept](LLMLang-CONCEPT.md), [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md) | P0; needs dedicated alternatives research |
| RT-05 | Canonical program representation and semantic identity | Specification/Design/Implementation graphs, typed IR, canonicalization, stable IDs, content hashes, artifact granularity, cycles and versioning | [Global semantic artifact store](GLOBAL-SEMANTIC-ARTIFACT-STORE.md), [Git semantic repository](GIT-SEMANTIC-REPOSITORY.md), [Draft glossary](../draft/GLOSSARY.md) | P0; multiple proposals, unresolved questions |
| RT-06 | Dependency semantics and impact analysis | Semantic vs control/configuration/provenance edges, dependency completeness, sound may-depend analysis, discovery, impact closure and evidence | [Scenarios 18–28](RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md), [Scenario 25](RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md) through [Scenario 28](RESEARCH-SCENARIO-28-TYPED-IR-AND-PROOF-BOUNDARY.md) | P0; extensive research, formal foundations need completion |
| RT-07 | Formal semantics and verification architecture | One canonical semantics, executable/formal projections, proof obligations, soundness boundaries, trusted computing base, proof formats and independent checking | [Formal verification architecture](LLMLANG-FORMAL-VERIFICATION.md), [Scenarios 25–34](RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md) | P0; active Lean/Logos/QF_LIA line |
| RT-08 | Testing, validation, and evidence model | Test generation, property/stateful testing, model checking, proof evidence, conformance, coverage, evidence provenance and reuse | [Scenarios 15–24](RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md), [Scenarios 26–34](RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md) | P0; partial, tightly coupled to semantics |
| RT-09 | Compiler architecture and intermediate representations | Front end, semantic analysis, IR boundaries, lowering, optimization, diagnostics, compilation phases and trusted transformations | [Translation and target backends](TRANSLATION-AND-TARGET-BACKENDS.md), [LLVM backend](LLVM-BACKEND-ARCHITECTURE.md), [Formal verification architecture](LLMLANG-FORMAL-VERIFICATION.md) | P1; alternatives need comparison |
| RT-10 | Runtime and execution model | Interpreter/VM/native execution, runtime services, ABI, OS boundary, resource and error behavior, sandboxing and target-specific semantics | [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md) | P1; proposal exists, depends on RT-03/04/07 |
| RT-11 | Build, incremental computation, and caching | Action graph, cache keys, semantic hashes vs action keys, dependency closure, invalidation, reproducibility and cache trust | [Semantic compilation cache](SEMANTIC-COMPILATION-CACHE.md), [speedup estimate](COMPILATION-CACHE-SPEEDUP-ESTIMATE.md) | P1; proposal exists, foundational assumptions unresolved |
| RT-12 | Libraries, packages, templates, and artifact reuse | Package/library boundaries, public contracts, templates, dependency resolution, registries, target profiles, provenance and compatibility evidence | [Libraries and templates](LIBRARIES-AND-TEMPLATES.md), [Global semantic artifact store](GLOBAL-SEMANTIC-ARTIFACT-STORE.md) | P1; proposal exists |
| RT-13 | Target backends and interoperability | Multiple target languages, semantic preservation, FFI, LLVM or alternative backends, target profiles and portability limits | [Translation and target backends](TRANSLATION-AND-TARGET-BACKENDS.md), [LLVM backend](LLVM-BACKEND-ARCHITECTURE.md), [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md) | P1; proposals exist |
| RT-14 | AI-native authoring and change protocol | LLM-facing APIs, structured changes, request/change lifecycle, context planning, provenance, approvals, model neutrality and failure containment | [Development Engine RFC](RFC-DEVELOPMENT-ENGINE.md) | P0; needs cross-check against language semantics |
| RT-15 | Collaboration, version control, and semantic merge | Canonical Git representation, reviewable diffs, stable identity, merge base/ours/theirs, conflict policy, branches and concurrent edits | [Git semantic repository](GIT-SEMANTIC-REPOSITORY.md), [ADR-014](../docs/adr/014-git-semantic-merge.md) | P1; research completed, implementation deferred |
| RT-16 | Security, isolation, trust, and governance | Capability security, sandboxing, trusted computing base, artifact attestations, supply chain, permissions, reproducibility and human decision boundaries | [Development Engine RFC](RFC-DEVELOPMENT-ENGINE.md), [Global semantic artifact store](GLOBAL-SEMANTIC-ARTIFACT-STORE.md), [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md) | P1; substantial research gap |
| RT-17 | Developer experience and diagnostics | IDE/CLI/CI interaction, error localization, explainability, debugging, observability, performance feedback and human review | [Development Engine RFC](RFC-DEVELOPMENT-ENGINE.md) | P2; can be explored alongside RT-14 |
| RT-18 | Conformance, evolution, and ecosystem | Versioning, compatibility, migration, language profiles, standard library evolution, conformance suites and long-term governance | [Libraries and templates](LIBRARIES-AND-TEMPLATES.md), [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md) | P2; depends on core semantics |

Priority is provisional and indicates dependency leverage, not importance to users. Research may be split into smaller topics where separate vectors can be evaluated independently.

## 3. Required research artifact

Every research report should identify:

1. Scope, motivating questions, and explicit non-goals.
2. Relevant existing LLMLang assumptions and source documents.
3. Viable development vectors; do not force alternatives where evidence supports only one.
4. For each vector: semantics, assumptions, evidence, benefits, costs, risks, limitations, and open questions.
5. Compatibility conditions and cross-aspect dependencies, linked to stable IDs in [the dependency map](RESEARCH-DEPENDENCY-MAP.md).
6. What would falsify or materially weaken the vector.
7. Follow-up experiments or research needed to raise confidence.
8. A concise machine-readable or tabular option summary suitable for later synthesis.

Research status must distinguish at least: not started, in progress, evidence collected, proposal drafted, independently reviewed, and completed for current scope. “Completed” means the stated research questions have been investigated to the declared scope; it does not mean a vector has been accepted.

## 4. Research coverage gaps

The current repository has substantial work on requirement evolution, dependency analysis, proof boundaries, artifact storage, compilation caching, runtime, backends, and Git. It does not yet constitute a complete exploration of the language design space.

The highest-leverage gaps to address explicitly are:

- A coherent operational and denotational semantic core covering the language constructs beyond the narrow relational-verification fragment.
- A comparative type/effect/ownership/capability-system study.
- A unified model for state, errors, effects, concurrency, and observable behavior.
- A comparison of alternative SPG/IR decompositions and canonical identity boundaries.
- A security and trusted-computing-base model.
- A unified evidence/conformance model spanning tests, proofs, runtime checks, and external components.
- A cross-aspect comparison of interpreter, VM, LLVM, and source-to-source backend strategies.

These are gaps to research, not predetermined design requirements.

## 5. Relationship to the specification space

The taxonomy defines dimensions of research, not a checklist of independent toggles. The eventual option space is constructed from the vectors actually supported by research. The dependency map identifies conditional choices and incompatibilities; the synthesis process then generates valid integrated candidate specifications and compares them as wholes.

See [Research Dependency Map](RESEARCH-DEPENDENCY-MAP.md) for sequencing and cross-aspect relationships.
