# LLMLang

**LLMLang** is an experimental concept for an AI-native programming language and development environment designed around large language models as primary program authors, with independent machine validation of their output.

> **Core principle:** Don't make the LLM remember the rules. Make the language and its tooling enforce them.

- [Language Versioning](LANGUAGE-VERSIONING.md) — composite language versions and the append-only component registry.

## Concept

LLMLang explores a programming model in which a program is represented as a typed **Semantic Program Graph (SPG)** rather than only as source text or a conventional AST.

The concept is organized around three connected, independently optional layers:

- **Specification Graph** — what the program must do: requirements, contracts, invariants, states, and constraints.
- **Design Graph** — how the program is structured: components, interfaces, dependencies, algorithms, and data structures.
- **Implementation Graph** — how the program is implemented: expressions, instructions, control flow, memory operations, and runtime calls.

Key areas include:

- First-class preconditions, postconditions, invariants, effects, and errors.
- Static strict typing, algebraic data types, refinement types, and typed states.
- Explicit ownership, resource management, concurrency, and capabilities.
- Traceability between requirements, implementation, tests, and proofs.
- Deterministic compiler validation independent of the LLM.
- Interpreter/VM execution during development and a possible native-code backend.

The LLM proposes structured program changes; the compiler and verification tools independently validate them. An LLM response is never treated as proof of correctness.

## Status

This repository contains a **conceptual research document**, not a production-ready language implementation. Syntax, formal semantics, type-system details, verification strategy, and implementation architecture remain subjects for research and prototyping.

## Research planning

- [Research taxonomy](RESEARCH-TAXONOMY.md) — research areas, current coverage, and required outputs for each research.
- [RT-03 — Core Language Semantics](CORE-LANGUAGE-SEMANTICS.md) — candidate semantic vectors and four profiles (pure functional, imperative/linear, actor/concurrent, effectful functional), compatibility tensions, downstream dependencies, and experiments. No profile is selected.
- [RT-04 — Type, Effect, Ownership, and Capability-System Alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) — comparative alternatives for static/refinement types, effects/handlers, ownership/borrowing/lifetimes, capabilities, concurrency/memory models, error-state composition, and candidate hash boundaries. No architecture is selected; executable scenarios remain open.
- [Cross-aspect dependency map](RESEARCH-DEPENDENCY-MAP.md) — dependency relationships, research waves, and parallelism guidance.

## Documents

- [LLMLang-CONCEPT.md](LLMLang-CONCEPT.md) — full concept, architecture, design principles, proposed toolchain, development stages, and open questions.
- [REPOSITORY-AUDIT-2026-11-17.md](REPOSITORY-AUDIT-2026-11-17.md) — repository-wide documentation consistency audit, fixes, and validation scope.
- [LLMLang-FORMAL-VERIFICATION.md](LLMLang-FORMAL-VERIFICATION.md) — architectural requirement for one canonical semantics and generated formal/executable representations.
- [POSIX-RUNTIME-ARCHITECTURE.md](POSIX-RUNTIME-ARCHITECTURE.md) — proposed standard POSIX library with portable and native Linux runtimes, one shared contract, conformance/differential testing, and progressive formal verification.
- [TRANSLATION-AND-TARGET-BACKENDS.md](TRANSLATION-AND-TARGET-BACKENDS.md) — translation pipeline, backend architecture, semantic portability, and target-language research.\n- [LLVM-BACKEND-ARCHITECTURE.md](LLVM-BACKEND-ARCHITECTURE.md) — proposed LLVM IR/bitcode and native-code generation backend, semantic boundary, LLVM-specific hazards, and verification limits.
- [LIBRARIES-AND-TEMPLATES.md](LIBRARIES-AND-TEMPLATES.md) — package/library dependencies, public contracts, templates, and reproducible reuse.
- [GLOBAL-SEMANTIC-ARTIFACT-STORE.md](GLOBAL-SEMANTIC-ARTIFACT-STORE.md) — proposed global content-addressed store, reusable wrapper implementations, library manifests, contracts, target profiles, and compatibility evidence.
- [PACKAGE-SYSTEM.md](PACKAGE-SYSTEM.md) — static and dynamic packages, compact binary indexes, compression/sparse lookup, provider resolution, and optional cache indexes.
- [PACKAGE-MANIFEST-AND-IDENTITY.md](PACKAGE-MANIFEST-AND-IDENTITY.md) — candidate TOML manifest schema, Package Content Root Hash construction, identity boundaries, and validation invariants; includes an [illustrative manifest fixture](examples/package/manifest.toml).
- [Package Identity Prototype 01](PROTOTYPES/PACKAGE-IDENTITY-01/README.md) — exploratory Python model and focused tests for PMI-001–PMI-014; not a normative implementation.
- [Package Index Logical Schema](PACKAGE-INDEX-LOGICAL-SCHEMA.md) — candidate logical tables, primary keys, cross-table invariants, canonical ordering, and deterministic merge contract.
- [Package Index Logical Model Prototype 01](PROTOTYPES/PACKAGE-INDEX-01/README.md) — executable in-memory validation, digest, and merge experiment; not a binary wire format.
- [RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md](RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md) — research on transforming contextual business intent into traceable, reviewable formal contracts.
- [RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md](RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md) — research on a typed, provenance-carrying Requirement IR, finite-domain consistency checks, and scenario generation.
- [Prototype 16 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-16-RESULTS.md) — end-to-end experiment for caller-scoped business-rule evolution and contract acceptance.
- [Prototype 17 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-17-RESULTS.md) — typed Requirement IR experiment with provenance, contradiction/underdetermination checks, and finite scenarios.

- [SEMANTIC-COMPILATION-CACHE.md](SEMANTIC-COMPILATION-CACHE.md) — content-addressed action graphs, incremental compilation, dependency-aware invalidation, cached analysis/tests/proofs, and cache soundness.
- [COMPILATION-CACHE-SPEEDUP-ESTIMATE.md](COMPILATION-CACHE-SPEEDUP-ESTIMATE.md) — analytical speedup model, illustrative local/component/warm-build scenarios, sensitivity, and benchmark plan.

## Guiding boundary

Formal verification can establish that an implementation satisfies a formal specification under stated assumptions. It cannot, by itself, establish that the specification fully captures the human's actual intent.

- [RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md](RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md) — immutable Requirement IR evolution, typed semantic impact, provenance-only changes, split/merge, and concurrent edits.
- [Prototype 18 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-18-RESULTS.md) — experiment for requirement revisions and impact propagation over hash-relevant dependencies.
- [RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md](RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md) — typed impact actions, scoped dependency-completeness evidence, non-interference gates, and fail-closed incremental planning.
- [Prototype 19 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-19-RESULTS.md) — prototype for completeness audits and conservative action planning.

- [RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md](RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md) — multi-source dependency discovery, explicit semantic classification, and separation of semantic dependencies from audit observations.
- [Prototype 20 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-20-RESULTS.md) — evidence-preserving dependency candidate classification prototype.

- [RESEARCH-SCENARIO-21-COUNTERFACTUAL-DEPENDENCY-DETECTION.md](RESEARCH-SCENARIO-21-COUNTERFACTUAL-DEPENDENCY-DETECTION.md) — controlled interventions, repeated paired execution, observable-vs-trace comparison, and limits of negative evidence.
- [Prototype 21 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-21-RESULTS.md) — counterfactual dependency analysis prototype.

- [RESEARCH-SCENARIO-22-COVERAGE-GUIDED-DEPENDENCY-DISCOVERY.md](RESEARCH-SCENARIO-22-COVERAGE-GUIDED-DEPENDENCY-DISCOVERY.md) — typed coverage-guided intervention planning, boundary and interaction coverage, budget scheduling, and coverage/evidence separation.
- [Prototype 22 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-22-RESULTS.md) — finite-domain candidate generation and deterministic coverage-ledger scheduler prototype.

- [RESEARCH-SCENARIO-23-MULTI-FACTOR-COUNTERFACTUAL-ANALYSIS.md](RESEARCH-SCENARIO-23-MULTI-FACTOR-COUNTERFACTUAL-ANALYSIS.md) — joint interventions and repeated 2×2 factorial analysis for conditional semantic dependencies.
- [Prototype 23 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-23-RESULTS.md) — multi-factor evidence analysis prototype and focused test results.

- [RESEARCH-SCENARIO-24-ADAPTIVE-INTERACTION-DISCOVERY.md](RESEARCH-SCENARIO-24-ADAPTIVE-INTERACTION-DISCOVERY.md) — evidence-triggered adaptive scheduling, repeated factorial blocks, higher-order escalation, and exploration/exploitation budgeting.
- [Prototype 24 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-24-RESULTS.md) — adaptive interaction-discovery planner and focused test results.

- [RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md](RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md) — formal semantic dependency analysis, relational independence, sound may-depend graphs, and the role of experimental discovery.
- [RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md](RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md) — a finite operational core and exhaustive relational dependency prototype.
- [Prototype 26 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-26-RESULTS.md) — finite-model analyzer, tests, and limitations.

- [RESEARCH-SCENARIO-27-SYMBOLIC-RELATIONAL-VERIFICATION.md](RESEARCH-SCENARIO-27-SYMBOLIC-RELATIONAL-VERIFICATION.md) — product-program encoding and symbolic SAT/UNSAT/UNKNOWN dependency decisions.
- [Prototype 27 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-27-RESULTS.md) — SMT-LIB backend, protocol tests, and solver integration limitations.

- [RESEARCH-SCENARIO-28-TYPED-IR-AND-PROOF-BOUNDARY.md](RESEARCH-SCENARIO-28-TYPED-IR-AND-PROOF-BOUNDARY.md) — type-safe symbolic IR and explicit proof-evidence boundary.
- [Prototype 28 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-28-RESULTS.md) — validator, evidence envelope, and solver protocol correction.


## Latest research

- [Package System: Static and Dynamic Packages](PACKAGE-SYSTEM.md) — human-readable TOML manifest candidate, compact binary indexes, block compression, optional sparse lookup, exact-hash dependency closure, provider-built dynamic packages, and optional derived-result cache indexes.

- [Scenario 29 — Verified SMT Proof Checking and Encoder Validation](RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md) — Logos/Lean proof checking, exact assumption binding, QF_LIA semantic profile, and encoder proof obligations.
- [Prototype 29 results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-29-RESULTS.md) — current tool availability and implementation acceptance gate.


- [Scenario 30 — CPC Assumption Binding](RESEARCH-SCENARIO-30-CPC-ASSUMPTION-BINDING.md) — source-level audit of Logos's parser and soundness API; exact structural binding of the parsed CPC assumption list to the canonical LLMLang relational query; adversarial mismatch tests and the conservative MVP boundary.

- [Scenario 31 — Strict QF_LIA Relational Query Profile](RESEARCH-SCENARIO-31-STRICT-QF-LIA-PROFILE.md) — a separate conservative proof-eligible subset; rejects strings and nonlinear arithmetic, emits QF_LIA only, and removes the constant outcome string from the observation query.


- [Scenario 32 — Canonical Typed Relational Query IR](RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md) — immutable typed relational query representation, separate QF_LIA rendering, pinned Logos-Term API audit, and strict versioned JSON wire-format design.
- [Scenario 33 — CPC Parser State and Exact Symbol Binding](RESEARCH-SCENARIO-33-CPC-PARSER-STATE-BINDING.md) — preserving Logos parser state to recover exact UConst identities without writing a second CPC parser.
- [Scenario 34 — Source-to-Query Semantic Correspondence](RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md) — formal source fragment, operational and relational semantics, correspondence theorem ladder, and Lean proof plan.
- [Prototype QF_LIA profile](PROTOTYPES/DEPENDENCY-GRAPH-01/src/qf_lia_profile.py) and [typed query IR](PROTOTYPES/DEPENDENCY-GRAPH-01/src/qf_lia_ir.py) — strict relational query builder and typed SMT-LIB renderer.
- [QF_LIA CI workflow](../.github/workflows/qf-lia-profile.yml) — Python compile check and focused tests for the strict profile and deterministic canonical JSON exporter.
- [QF_LIA focused tests](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_qf_lia_profile.py) — accepted/rejected constructs, canonical IR, and renderer checks.


- [Lean CPC parser-state binding prototype](PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/) — pinned Lean/Lake package retaining Logos parser state, binding Bool/Int declarations to exact UConst nodes, independently rendering typed query ASTs, and decoding a strict versioned JSON query envelope; CI validates the parser bridge, exact AST fixtures, and adversarial strict-decoder fixtures (successful run 44095462826).


- [Git Representation and Semantic Merge](GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) — proposed textual Git representation, separation of Git/semantic/action identities, automatic custom merge driver, interactive mergetool, and repository-level SPG merge architecture.
- [Semantic Dependency Index — Research Design](SEMANTIC-DEPENDENCY-INDEX.md) — candidate separation of canonical typed semantic edges, call-site references, discovery evidence, completeness claims, reverse indexes, and consumer-specific projections; does not define the final SPG schema.
- [RT-19 — Toolchain Server and Semantic Development API](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) — research proposal for a transport-neutral semantic API, MCP adapter, durable workspaces and Change Sets, in-memory/persistent SPG storage, optimistic concurrency, deterministic text import/export, Git coordination, recovery, and authorization. No architecture decision or implementation is accepted yet.
- [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) — proposed workflow that plans all affected function versions before mutation, analyzes caller compatibility per call site, separates contract propagation from hash/reference propagation, detects shared-caller version splits, and gates Git commit on successful validation and audit.
- [ADR-015 — Toolchain Server and semantic development API](../docs/adr/015-toolchain-server-semantic-api.md) — proposed architectural direction; remains Proposed pending RT-19 validation.
- [Toolchain Server Prototype 01](PROTOTYPES/TOOLCHAIN-SERVER-01/README.md) — executable in-memory lifecycle experiment with immutable objects/snapshots, isolated workspaces, typed changes, optimistic checks, and canonical single-file import/export; not a production Toolchain or MCP server.

- [Package Index Logical Model Prototype 01](PROTOTYPES/PACKAGE-INDEX-01/README.md) now includes a lazy k-way merge over sorted table streams, with regression tests for laziness, large generated streams, deduplication, conflicts, and invalid input ordering.


- [RT-21 — LLMLang Self-Development: Feasibility, Bootstrap, and Migration Roadmap](RT-21-LLMLANG-SELF-DEVELOPMENT-AND-BOOTSTRAP-ROADMAP.md) — preliminary implementation-scope analysis, bootstrap architecture, staged migration, first-milestone acceptance criteria, and coarse effort estimates. This is a research recommendation, not an accepted architecture.


- [RT-22 — LLMLang Git Repository and Worktree MCP Surface](RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md) — LLMLang-owned repository/worktree Toolchain operations exposed through MCP, semantic synchronization, scoped authorization, recovery, and the AIVibeFlow integration boundary.

- [RT-23 — Single-Instance Toolchain with Shared Semantic State and Incremental Multi-Worktree File Views](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) — one Toolchain Server serving multiple regular-file worktrees, shared immutable semantic objects/snapshots, separately versioned interface mappings, per-worktree incremental file tracking, bounded reconciliation, concurrency, and recovery.

- [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) — candidate technical contract for deterministic textual import/export, typed semantic diff, repository-level base/ours/theirs merge, conflict/provenance model, separate mapping-revision merge, RT-20 CIP integration, and scoped prototype gates. It does not settle the SPG schema or hash envelope and does not accept ADR-014.
- [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md) — reconciles RT-24 with identity Studies 05–08, RT-03, the semantic dependency index, package identity, and current executable prototypes. It records unresolved identity alternatives and the safe first-prototype boundary; it does not select a normative model.
- [RT-24 Identity Architecture Decision Matrix](RT-24-IDENTITY-DECISION-MATRIX.md) — compares Stable Entity ID, content-only value identity, and optional occurrence/slot models against rename, duplication, move, split/merge, call-site, branch, and semantic-profile scenarios; records decision gates without selecting a normative model.
- [ADR-014 — Git repository representation and semantic merge](../docs/adr/014-git-semantic-merge.md) — proposed architecture direction; read together with the detailed merge, patch-planning, repository/worktree, and runtime documents below.
- [Git semantic repository research (background)](GIT-SEMANTIC-REPOSITORY.md) — earlier research report covering Git object storage, semantic identity, and merge prior art; background rather than the current focused design.
- **Identity prerequisites:** read the [Draft Glossary](../draft/GLOSSARY.md) as well as [Study 05](RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md), [Study 06](RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md), [Study 07](RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md), [Study 08](RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md), [RT-03](CORE-LANGUAGE-SEMANTICS.md), and [Semantic Dependency Index](SEMANTIC-DEPENDENCY-INDEX.md) before changing the identity, hash, occurrence, or SPG assumptions used by RT-24. These are research candidates, not accepted language rules.

**Related study set:** [Git Representation and Semantic Merge](GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md), [RT-24](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md), [RT-24 Identity and SPG Reconciliation](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md), [RT-20](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [RT-22](RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md), and [RT-23](RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) must be reviewed together when changing semantic merge, Git integration, or commit behavior. The identity prerequisites are Studies 05–08, [RT-03](CORE-LANGUAGE-SEMANTICS.md), and [Semantic Dependency Index](SEMANTIC-DEPENDENCY-INDEX.md). [RT-19](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) supplies the shared semantic API/Change Set context. The detailed documents define ownership boundaries and cross-link one another. The [Draft Glossary](../draft/GLOSSARY.md) is a shared terminology dependency for identity/hash work: review it whenever changing RT-20, RT-24, semantic dependency/hash roles, or package identity. Its terms are proposals until explicitly adopted.

