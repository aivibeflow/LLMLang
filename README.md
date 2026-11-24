# LLMLang — an AI-native programming language for LLMs and coding agents

LLMLang is a research project designing a programming language and development toolchain for software written and maintained by large language models (LLMs). Its core idea is to let coding agents propose **structured changes to a typed semantic program graph** and let independent tools check those changes against requirements and contracts. People define intent, resolve ambiguities, and approve changes.

LLMLang — исследовательский проект языка программирования для ИИ-агентов и больших языковых моделей. Модель предлагает изменения в типизированном графе программы, человек утверждает требования и решения, а инструменты независимо проверяют результат.

**Project status:** Research prototypes and a candidate specification in progress. The `.llmlang` examples illustrate the proposed language. A complete compiler and runtime are still future work. [Candidate specification](draft/README.md) · [Example implementations](draft/examples/README.md) · [Feature registry](FEATURE-REGISTRY.md)

## How the language is designed

The design explores a **Semantic Program Graph (SPG)** as the canonical representation, with human-readable code as a view of the graph. The model connects three independently maintained, optional layers:

- **Specification** records required behavior, constraints, and contracts.
- **Design** records architectural decisions, interfaces, and their rationale.
- **Implementation** records the concrete program and its dependencies.

Agents propose changes to named graph objects against an exact baseline. One candidate uses stable IDs across revisions and renames, content hashes for immutable semantic revisions, and a Merkle DAG of hash-relevant dependencies to trace affected objects and checks. The project is evaluating identity alternatives. [Language concept](research/RT-01/LLMLang-CONCEPT.md) · [Development Engine RFC](research/RT-14/RFC-DEVELOPMENT-ENGINE.md)

A proposed public-interface model separates stable qualified names, exact immutable operation contracts, implementation contracts and provider bindings. Independent checks establish body correctness and public-contract refinement; name resolution and provider selection remain separate from exact call identity. [Public interfaces research](research/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md) (candidate, not adopted).

## What this enables

- **Trace a requirement change through the program.** If a caller's tax policy changes, the graph can identify the affected bindings and checks while preserving the shared contract and other callers' policies. The dependency graph prototype exercises this case and models how requirement revisions affect verification keys. [Business intent prototype](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-16-RESULTS.md) · [Requirement evolution prototype](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-18-RESULTS.md)
- **Review the exact change an agent proposes.** The proposed workflow lets reviewers inspect a semantic diff and its impact, then bind approval to the specific change set and baseline. The context planner is designed to supply the agent with the relevant graph objects, contracts, and diagnostics for that task. [Development Engine RFC](research/RT-14/RFC-DEVELOPMENT-ENGINE.md)
- **Know which revision a check covers.** The verification design ties evidence to input hashes, dependencies, checker configuration, and assumptions. This gives the toolchain a basis for invalidating stale evidence and reusing results whose inputs still match. Tests and formal proof outcomes carry distinct guarantees. [Formal verification research](research/RT-07/LLMLang-FORMAL-VERIFICATION.md) · [Proof-checking prototype scenario](research/RT-07/RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md)

## How LLMLang compares with related projects

| Project | Published approach | What LLMLang aims to add |
| --- | --- | --- |
| linkly | LLM-native language with a semantic IR, interpreter, and native compilation through MLIR. | Independent specification, design, and implementation layers with explicit links so that impact analysis can follow a change from a requirement through an architectural decision to code. [linkly](https://github.com/choiyounggi/linkly) |
| Edict | Agent-first language with a JSON AST, effect checking, SMT-backed contracts, and WASM compilation. | A project-wide model that binds approvals and verification evidence to exact semantic revisions across requirements, design, and code. [Edict](https://github.com/Sowiedu/Edict) |
| DSP CodeGen | Graph-based IR for impact analysis and deterministic polyglot code generation. | A canonical graph that models required behavior, design decisions, and implementation semantics, with revision-bound verification evidence. [DSP CodeGen](https://github.com/Loqira-Labs/dsp-codegen) |
| agent-spec | AI-native specification and task verification using governed requirements and task contracts. | A programming-language design that gives architectural decisions their own lifecycle and links them to both requirements and executable behavior. [agent-spec](https://github.com/ZhangHanDong/agent-spec) |

These are architectural comparisons. The repository documents prototype results for specific mechanisms. [Detailed comparison](research/RT-01/RESEARCH-DEEP-COMPARISON.md) · [Related projects survey](research/RT-01/RESEARCH-RELATED-PROJECTS.md)

## Explore the research

- **Read a program sketch.** Start with the Hello World example, which declares its output effect and handles success and failure explicitly. [Task](examples/0001-hello-world.md) · [LLMLang sketch](draft/examples/0001-hello-world/main.llmlang) · [Task catalog](examples/README.md)
- **Run the dependency graph prototype.** The Python prototype covers content-addressed graph storage, requirement evolution, and verification experiments. [Prototype setup and tests](research/PROTOTYPES/DEPENDENCY-GRAPH-01/README.md)
- **Follow the language design.** Start with the [current research state](research/RESEARCH-STATE-2026-11-19.md) for open design choices. The `draft/` directory holds candidate specification material. The `research/` directory holds exploratory RFCs, alternatives, prototypes, and results, including work on [CPC assumption binding](research/RT-07/RESEARCH-SCENARIO-30-CPC-ASSUMPTION-BINDING.md) and the [strict QF_LIA profile](research/RT-07/RESEARCH-SCENARIO-31-STRICT-QF-LIA-PROFILE.md). [Candidate specification](draft/README.md) · [Research overview](research/README.md) · [Open design questions](TODO.md)

If you're building an LLM-native programming language, a semantic IR for coding agents, or a formal verification workflow for AI-generated code, we welcome comparisons and concrete examples from your project. [Open an issue](https://github.com/aivibeflow/LLMLang/issues/new)

<details>
<summary>Detailed research catalog</summary>

- [Research State 2026-11-19](research/RESEARCH-STATE-2026-11-19.md) — current evidence map, open candidate vectors, synthesis gates, and next steps; no language design selected.
- [COR-13 Typed Ownership Across Calls](research/RT-04/RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md) — proposed discriminator for owned-resource results, cleanup failure, and caller obligations.

- [Research Option Matrix 01 — Language and Execution Foundations](research/RESEARCH-OPTION-MATRIX-01.md) — initial evidence-linked comparison of integrated semantics, type/resource, identity, verification, runtime/backend, and security vectors; no candidate is selected.
- [RT-01 Reference Workloads](research/RT-01/RT-01-REFERENCE-WORKLOADS.md) — common workload acceptance criteria and an executable CLI corpus calibrated with C and Python host references.
- [RT-16 Threat Model 01](research/RT-16/RT-16-THREAT-MODEL-01.md) — initial threat actors, boundaries, abuse cases, and a tested authorization-policy model.
- [RT-03/04 Shared Semantics Corpus v1](research/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md) — inventory of executable scenario families, profile coverage, limits, and gap-ordered comparisons for RT-03/04.
- COR-12 in the shared corpus adds a finite buffered-versus-rendezvous blocking/progress experiment for two actor protocols.
- [Research Scenario 35](research/RT-04/RESEARCH-SCENARIO-35-RESOURCE-RETURN-AND-CLEANUP.md) compares ownership-transfer and cleanup ordering when returning a resource; the branch, caller, and RT-04 type-envelope probes expose a value-versus-error-with-value distinction, but no rule is selected.
- [Research Scenario 77](research/RT-03/RESEARCH-SCENARIO-77-CALL-ARGUMENT-EVALUATION-ORDER.md) compares call/operand sequencing and abrupt completion in Rust, Go, Java, and C++; no LLMLang evaluation order is selected.
- [Research Scenario 78](research/RT-03/RESEARCH-SCENARIO-78-FLOATING-POINT-REPRODUCIBILITY-AND-IEEE-EDGES.md) expands floating-point edge behavior, NaN bits, FMA, and strict/optimized profiles; no LLMLang floating-point profile is selected.
- [Research Scenario 79](research/RT-03/RESEARCH-SCENARIO-79-STRING-LITERAL-SYNTAX-AND-INTERPOLATION.md) compares escaped/raw/multiline literals, byte escapes, and interpolation in Rust, Go, Swift, and Zig; no syntax is selected.
- [Research Scenario 80](research/RT-31/RESEARCH-SCENARIO-80-COMMENTS-DOCS-AND-LEXICAL-TRIVIA.md) compares comment nesting, documentation attachment, directives, and lexical trivia across Rust, Go, Swift, and Zig; no syntax is selected.
- [Research Scenario 81](research/RT-31/RESEARCH-SCENARIO-81-IMPORT-BINDING-SYNTAX-AND-NAMESPACE-POLLUTION.md) compares qualified, selective, wildcard, aliased, relative, and re-exporting imports across Rust, Go, Swift, Java, and Python; no syntax is selected.
- [Research Scenario 82](research/RT-31/RESEARCH-SCENARIO-82-SOURCE-FILE-STRUCTURE-AND-TOP-LEVEL-CODE.md) compares source-file organization, compilation units, top-level declarations, and executable entry forms across Go, Rust, Java, Swift, and Kotlin; no grammar is selected.
- [Research Scenario 83](research/RT-31/RESEARCH-SCENARIO-83-NUMERIC-LITERAL-LEXICAL-SYNTAX.md) compares radix, separators, exponents, suffixes, signs, and token boundaries across Rust, Go, Swift, and Zig; no numeric grammar is selected.
- [Research Scenario 84](research/RT-31/RESEARCH-SCENARIO-84-FUNCTION-SIGNATURE-AND-CALL-SURFACE.md) compares parameter names/labels, returns, defaults, variadics, and method receivers across Rust, Go, Swift, and Java; no signature syntax is selected.
- [Research Scenario 85](research/RT-31/RESEARCH-SCENARIO-85-LOCAL-BINDING-DECLARATION-SYNTAX.md) compares local binding forms, mutability markers, inference, destructuring, initialization, and redeclaration across Rust, Go, Swift, and Zig; no syntax is selected.
- [Research Scenario 86](research/RT-31/RESEARCH-SCENARIO-86-ASYNC-AWAIT-SYNTAX-AND-CONTEXTS.md) compares async declaration markers, await placement, closure/context rules, and top-level await across Rust, Swift, C#, and ECMAScript; no syntax is selected.
- [Research Scenario 87](research/RT-31/RESEARCH-SCENARIO-87-ASYNC-AWAIT-PARSER-DIAGNOSTIC-CORPUS.md) specifies 18 proposed acceptance, context, precedence, module-goal, recovery, and diagnostic fixtures grounded in official language references; the corpus is designed but not yet run.

- [Language Versioning](research/RT-18/LANGUAGE-VERSIONING.md) — composite language versions and the append-only component registry.

## Research planning

- [RT-34 — Automatic Complexity Inference and Resource Verification](research/RT-34/RT-34-AUTOMATIC-COMPLEXITY-INFERENCE.md) — proposed research on model-scoped resource contracts, automatic inference and proof of SPG implementation complexity, problem lower bounds and optimality; [benchmark plan](research/RT-34/RT-34-COMPLEXITY-BENCHMARK.md). No analyzer or normative design selected.
- [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](research/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md) — explicit external-contract premises, conditional proof closure, trust policy and revocation (P0 research).
- [RT-37 — Freestanding, embedded and real-time firmware](research/RT-37/README.md) — proposed shared OS-independent execution profile, peripheral contracts, real-time/resource bounds and firmware pilot.
- [RT-38 — Operating-system kernels and verified microkernel feasibility](research/RT-38/README.md) — proposed privileged runtime, memory isolation, IPC, capabilities and microkernel pilot after RT-37.

- [Research taxonomy](research/RESEARCH-TAXONOMY.md) — research areas, current coverage, and required outputs for each research.
- [RT-03 — Core Language Semantics](research/RT-03/CORE-LANGUAGE-SEMANTICS.md) — candidate semantic vectors and four profiles (pure functional, imperative/linear, actor/concurrent, effectful functional), compatibility tensions, downstream dependencies, and experiments. No profile is selected.
- [RT-04 — Type, Effect, Ownership, and Capability-System Alternatives](research/RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) — comparative alternatives for static/refinement types, effects/handlers, ownership/borrowing/lifetimes, capabilities, concurrency/memory models, error-state composition, and candidate hash boundaries. No architecture is selected; a first limited checker prototype exists, while broader scenarios remain open.
- [RT-04 Prototype 01](research/PROTOTYPES/RT-04-01/README.md) — executable comparison of two candidate checker vectors, with focused unit tests.
- [RT-04 Prototype 01 Results](research/RT-04/RT-04-PROTOTYPE-01-RESULTS.md) — findings, limits, and next experiments.
- [RT-04 Prototype 01 Scenarios](research/RT-04/RT-04-PROTOTYPE-01-SCENARIOS.md) — executable scenario-to-profile outcome matrix.
- [Cross-aspect dependency map](research/RESEARCH-DEPENDENCY-MAP.md) — dependency relationships, research waves, and parallelism guidance.

## Documents

- [LLMLang-CONCEPT.md](research/RT-01/LLMLang-CONCEPT.md) — full concept, architecture, design principles, proposed toolchain, development stages, and open questions.
- [REPOSITORY-AUDIT-2026-11-17.md](research/REPOSITORY-AUDIT-2026-11-17.md) — repository-wide documentation consistency audit, fixes, and validation scope.
- [LLMLang-FORMAL-VERIFICATION.md](research/RT-07/LLMLang-FORMAL-VERIFICATION.md) — architectural requirement for one canonical semantics and generated formal/executable representations.
- [POSIX-RUNTIME-ARCHITECTURE.md](research/RT-10/POSIX-RUNTIME-ARCHITECTURE.md) — proposed standard POSIX library with portable and native Linux runtimes, one shared contract, conformance/differential testing, and progressive formal verification.
- [TRANSLATION-AND-TARGET-BACKENDS.md](research/RT-13/TRANSLATION-AND-TARGET-BACKENDS.md) — translation pipeline, backend architecture, semantic portability, and target-language research.
- [LLVM-BACKEND-ARCHITECTURE.md](research/RT-13/LLVM-BACKEND-ARCHITECTURE.md) — proposed LLVM IR/bitcode and native-code generation backend, semantic boundary, LLVM-specific hazards, and verification limits.
- [LIBRARIES-AND-TEMPLATES.md](research/RT-12/LIBRARIES-AND-TEMPLATES.md) — package/library dependencies, public contracts, templates, and reproducible reuse.
- [GLOBAL-SEMANTIC-ARTIFACT-STORE.md](research/RT-12/GLOBAL-SEMANTIC-ARTIFACT-STORE.md) — proposed global content-addressed store, reusable wrapper implementations, library manifests, contracts, target profiles, and compatibility evidence.
- [PACKAGE-SYSTEM.md](research/RT-12/PACKAGE-SYSTEM.md) — static and dynamic packages, compact binary indexes, compression/sparse lookup, provider resolution, and optional cache indexes.
- [PACKAGE-MANIFEST-AND-IDENTITY.md](research/RT-12/PACKAGE-MANIFEST-AND-IDENTITY.md) — candidate TOML manifest schema, Package Content Root Hash construction, identity boundaries, and validation invariants; includes an [illustrative manifest fixture](research/examples/package/manifest.toml).
- [Package Identity Prototype 01](research/PROTOTYPES/PACKAGE-IDENTITY-01/README.md) — exploratory Python model and focused tests for PMI-001–PMI-014; not a normative implementation.
- [Package Index Logical Schema](research/RT-12/PACKAGE-INDEX-LOGICAL-SCHEMA.md) — candidate logical tables, primary keys, cross-table invariants, canonical ordering, and deterministic merge contract.
- [Package Index Logical Model Prototype 01](research/PROTOTYPES/PACKAGE-INDEX-01/README.md) — executable in-memory validation, digest, and merge experiment; not a binary wire format.
- [RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md](research/RT-02/RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md) — research on transforming contextual business intent into traceable, reviewable formal contracts.
- [RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md](research/RT-02/RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md) — research on a typed, provenance-carrying Requirement IR, finite-domain consistency checks, and scenario generation.\n- [RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md](research/RT-02/RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md) — worked end-to-end order-confirmation example and research plan for reconstructing formal requirements into human-readable rules for stakeholder validation.
- [Prototype 16 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-16-RESULTS.md) — end-to-end experiment for caller-scoped business-rule evolution and contract acceptance.
- [Prototype 17 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-17-RESULTS.md) — typed Requirement IR experiment with provenance, contradiction/underdetermination checks, and finite scenarios.

- [SEMANTIC-COMPILATION-CACHE.md](research/RT-11/SEMANTIC-COMPILATION-CACHE.md) — content-addressed action graphs, incremental compilation, dependency-aware invalidation, cached analysis/tests/proofs, and cache soundness.
- [COMPILATION-CACHE-SPEEDUP-ESTIMATE.md](research/RT-11/COMPILATION-CACHE-SPEEDUP-ESTIMATE.md) — analytical speedup model, illustrative local/component/warm-build scenarios, sensitivity, and benchmark plan.

## Guiding boundary

Formal verification can establish that an implementation satisfies a formal specification under stated assumptions. It cannot, by itself, establish that the specification fully captures the human's actual intent.

- [RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md](research/RT-02/RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md) — immutable Requirement IR evolution, typed semantic impact, provenance-only changes, split/merge, and concurrent edits.
- [Prototype 18 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-18-RESULTS.md) — experiment for requirement revisions and impact propagation over hash-relevant dependencies.
- [RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md](research/RT-06/RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md) — typed impact actions, scoped dependency-completeness evidence, non-interference gates, and fail-closed incremental planning.
- [Prototype 19 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-19-RESULTS.md) — prototype for completeness audits and conservative action planning.

- [RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md](research/RT-06/RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md) — multi-source dependency discovery, explicit semantic classification, and separation of semantic dependencies from audit observations.
- [Prototype 20 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-20-RESULTS.md) — evidence-preserving dependency candidate classification prototype.

- [RESEARCH-SCENARIO-21-COUNTERFACTUAL-DEPENDENCY-DETECTION.md](research/RT-06/RESEARCH-SCENARIO-21-COUNTERFACTUAL-DEPENDENCY-DETECTION.md) — controlled interventions, repeated paired execution, observable-vs-trace comparison, and limits of negative evidence.
- [Prototype 21 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-21-RESULTS.md) — counterfactual dependency analysis prototype.

- [RESEARCH-SCENARIO-22-COVERAGE-GUIDED-DEPENDENCY-DISCOVERY.md](research/RT-06/RESEARCH-SCENARIO-22-COVERAGE-GUIDED-DEPENDENCY-DISCOVERY.md) — typed coverage-guided intervention planning, boundary and interaction coverage, budget scheduling, and coverage/evidence separation.
- [Prototype 22 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-22-RESULTS.md) — finite-domain candidate generation and deterministic coverage-ledger scheduler prototype.

- [RESEARCH-SCENARIO-23-MULTI-FACTOR-COUNTERFACTUAL-ANALYSIS.md](research/RT-06/RESEARCH-SCENARIO-23-MULTI-FACTOR-COUNTERFACTUAL-ANALYSIS.md) — joint interventions and repeated 2×2 factorial analysis for conditional semantic dependencies.
- [Prototype 23 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-23-RESULTS.md) — multi-factor evidence analysis prototype and focused test results.

- [RESEARCH-SCENARIO-24-ADAPTIVE-INTERACTION-DISCOVERY.md](research/RT-06/RESEARCH-SCENARIO-24-ADAPTIVE-INTERACTION-DISCOVERY.md) — evidence-triggered adaptive scheduling, repeated factorial blocks, higher-order escalation, and exploration/exploitation budgeting.
- [Prototype 24 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-24-RESULTS.md) — adaptive interaction-discovery planner and focused test results.

- [RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md](research/RT-06/RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md) — formal semantic dependency analysis, relational independence, sound may-depend graphs, and the role of experimental discovery.
- [RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md](research/RT-07/RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md) — a finite operational core and exhaustive relational dependency prototype.
- [Prototype 26 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-26-RESULTS.md) — finite-model analyzer, tests, and limitations.

- [RESEARCH-SCENARIO-27-SYMBOLIC-RELATIONAL-VERIFICATION.md](research/RT-07/RESEARCH-SCENARIO-27-SYMBOLIC-RELATIONAL-VERIFICATION.md) — product-program encoding and symbolic SAT/UNSAT/UNKNOWN dependency decisions.
- [Prototype 27 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-27-RESULTS.md) — SMT-LIB backend, protocol tests, and solver integration limitations.

- [RESEARCH-SCENARIO-28-TYPED-IR-AND-PROOF-BOUNDARY.md](research/RT-07/RESEARCH-SCENARIO-28-TYPED-IR-AND-PROOF-BOUNDARY.md) — type-safe symbolic IR and explicit proof-evidence boundary.
- [Prototype 28 Results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-28-RESULTS.md) — validator, evidence envelope, and solver protocol correction.


## Latest research

- [Package System: Static and Dynamic Packages](research/RT-12/PACKAGE-SYSTEM.md) — human-readable TOML manifest candidate, compact binary indexes, block compression, optional sparse lookup, exact-hash dependency closure, provider-built dynamic packages, and optional derived-result cache indexes.

- [Scenario 29 — Verified SMT Proof Checking and Encoder Validation](research/RT-07/RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md) — Logos/Lean proof checking, exact assumption binding, QF_LIA semantic profile, and encoder proof obligations.
- [Prototype 29 results](research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-29-RESULTS.md) — current tool availability and implementation acceptance gate.


- [Scenario 30 — CPC Assumption Binding](research/RT-07/RESEARCH-SCENARIO-30-CPC-ASSUMPTION-BINDING.md) — source-level audit of Logos's parser and soundness API; exact structural binding of the parsed CPC assumption list to the canonical LLMLang relational query; adversarial mismatch tests and the conservative MVP boundary.

- [Scenario 31 — Strict QF_LIA Relational Query Profile](research/RT-07/RESEARCH-SCENARIO-31-STRICT-QF-LIA-PROFILE.md) — a separate conservative proof-eligible subset; rejects strings and nonlinear arithmetic, emits QF_LIA only, and removes the constant outcome string from the observation query.


- [Scenario 32 — Canonical Typed Relational Query IR](research/RT-07/RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md) — immutable typed relational query representation, separate QF_LIA rendering, pinned Logos-Term API audit, and strict versioned JSON wire-format design.
- [Scenario 33 — CPC Parser State and Exact Symbol Binding](research/RT-07/RESEARCH-SCENARIO-33-CPC-PARSER-STATE-BINDING.md) — preserving Logos parser state to recover exact UConst identities without writing a second CPC parser.
- [Scenario 34 — Source-to-Query Semantic Correspondence](research/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md) — formal source fragment, operational and relational semantics, correspondence theorem ladder, and Lean proof plan.
- [Prototype QF_LIA profile](research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/qf_lia_profile.py) and [typed query IR](research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/qf_lia_ir.py) — strict relational query builder and typed SMT-LIB renderer.
- [QF_LIA CI workflow](research/../.github/workflows/qf-lia-profile.yml) — Python compile check and focused tests for the strict profile and deterministic canonical JSON exporter.
- [QF_LIA focused tests](research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_qf_lia_profile.py) — accepted/rejected constructs, canonical IR, and renderer checks.


- [Lean CPC parser-state binding prototype](research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding) — pinned Lean/Lake package retaining Logos parser state, binding Bool/Int declarations to exact UConst nodes, independently rendering typed query ASTs, and decoding a strict versioned JSON query envelope; CI validates the parser bridge, exact AST fixtures, and adversarial strict-decoder fixtures (successful run 44095462826).


- [Git Representation and Semantic Merge](research/RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) — proposed textual Git representation, separation of Git/semantic/action identities, automatic custom merge driver, interactive mergetool, and repository-level SPG merge architecture.
- [Semantic Dependency Index — Research Design](research/RT-06/SEMANTIC-DEPENDENCY-INDEX.md) — candidate separation of canonical typed semantic edges, call-site references, discovery evidence, completeness claims, reverse indexes, and consumer-specific projections; does not define the final SPG schema.
- [RT-19 — Toolchain Server and Semantic Development API](research/RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) — research proposal for a transport-neutral semantic API, MCP adapter, durable workspaces and Change Sets, in-memory/persistent SPG storage, optimistic concurrency, deterministic text import/export, Git coordination, recovery, and authorization. No architecture decision or implementation is accepted yet.
- [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](research/RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) — proposed workflow that plans all affected function versions before mutation, analyzes caller compatibility per call site, separates contract propagation from hash/reference propagation, detects shared-caller version splits, and gates Git commit on successful validation and audit.
- [RT-20 — CIP Action Execution Audit](research/RT-20/RT-20-CIP-ACTION-EXECUTION-AUDIT.md) — decomposes the next fail-closed gate into action identity/DAG validation, action-kind policy, execution records, evidence-envelope validation, and deterministic execution receipts; no commit authorization is implied.
- [ADR-015 — Toolchain Server and semantic development API](research/../docs/adr/015-toolchain-server-semantic-api.md) — proposed architectural direction; remains Proposed pending RT-19 validation.
- [Toolchain Server Prototype 01](research/PROTOTYPES/TOOLCHAIN-SERVER-01/README.md) — executable in-memory lifecycle experiment with immutable objects/snapshots, isolated workspaces, typed changes, optimistic checks, and canonical single-file import/export; not a production Toolchain or MCP server.

- [Package Index Logical Model Prototype 01](research/PROTOTYPES/PACKAGE-INDEX-01/README.md) now includes a lazy k-way merge over sorted table streams, with regression tests for laziness, large generated streams, deduplication, conflicts, and invalid input ordering.


- [RT-21 — LLMLang Self-Development: Feasibility, Bootstrap, and Migration Roadmap](research/RT-21/RT-21-LLMLANG-SELF-DEVELOPMENT-AND-BOOTSTRAP-ROADMAP.md) — preliminary implementation-scope analysis, bootstrap architecture, staged migration, first-milestone acceptance criteria, and coarse effort estimates. This is a research recommendation, not an accepted architecture.


- [RT-22 — LLMLang Git Repository and Worktree MCP Surface](research/RT-22/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md) — LLMLang-owned repository/worktree Toolchain operations exposed through MCP, semantic synchronization, scoped authorization, recovery, and the AIVibeFlow integration boundary.

- [RT-23 — Single-Instance Toolchain with Shared Semantic State and Incremental Multi-Worktree File Views](research/RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) — one Toolchain Server serving multiple regular-file worktrees, shared immutable semantic objects/snapshots, separately versioned interface mappings, per-worktree incremental file tracking, bounded reconciliation, concurrency, and recovery.

- [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](research/RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) — candidate technical contract for deterministic textual import/export, typed semantic diff, repository-level base/ours/theirs merge, conflict/provenance model, separate mapping-revision merge, RT-20 CIP integration, and scoped prototype gates. It does not settle the SPG schema or hash envelope and does not accept ADR-014.
- [RT-24 Identity and SPG Reconciliation](research/RT-24/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md) — reconciles RT-24 with identity Studies 05–08, RT-03, the semantic dependency index, package identity, and current executable prototypes. It records unresolved identity alternatives and the safe first-prototype boundary; it does not select a normative model.
- [RT-24 Identity Architecture Decision Matrix](research/RT-24/RT-24-IDENTITY-DECISION-MATRIX.md) — compares Stable Entity ID, content-only value identity, and optional occurrence/slot models against rename, duplication, move, split/merge, call-site, branch, and semantic-profile scenarios; records decision gates without selecting a normative model.
- [RT-05 Identity Lifecycle Experiment](research/RT-05/RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) — executable comparison of global IDs, explicit lineage, and scoped slots, including failure cases for reuse and ordinal matching.
- [RT-05 / RT-20 Call Site Refactoring Experiment](research/RT-05/RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md) — exact call binding transfer and a finite inline counterexample that distinguishes Contract conformance from behavior preservation.
- [RT-05 Recursive Identity Experiment](research/RT-05/RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md) — executable comparison of DAG-only, keyed group, and structural group addressing, including symmetry and invalidation.
- [RT-11 Binding Invalidation Benchmark](research/RT-11/RT-11-BINDING-INVALIDATION-BENCHMARK.md) — measured compiler, linker, and verification action counts for exact and separate linkage across implementation, contract, history, and flag changes.
- [ADR-014 — Git repository representation and semantic merge](research/../docs/adr/014-git-semantic-merge.md) — proposed architecture direction; read together with the detailed merge, patch-planning, repository/worktree, and runtime documents below.
- [Git semantic repository research (background)](research/RT-15/GIT-SEMANTIC-REPOSITORY.md) — earlier research report covering Git object storage, semantic identity, and merge prior art; background rather than the current focused design.
- **Identity prerequisites:** read the [Draft Glossary](research/../draft/GLOSSARY.md) as well as [Study 05](research/RT-05/RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md), [Study 06](research/RT-05/RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md), [Study 07](research/RT-05/RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md), [Study 08](research/RT-05/RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md), [RT-03](research/RT-03/CORE-LANGUAGE-SEMANTICS.md), and [Semantic Dependency Index](research/RT-06/SEMANTIC-DEPENDENCY-INDEX.md) before changing the identity, hash, occurrence, or SPG assumptions used by RT-24. These are research candidates, not accepted language rules.

**Related study set:** [Git Representation and Semantic Merge](research/RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md), [RT-24](research/RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md), [RT-24 Identity and SPG Reconciliation](research/RT-24/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md), [RT-20](research/RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [RT-22](research/RT-22/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md), and [RT-23](research/RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) must be reviewed together when changing semantic merge, Git integration, or commit behavior. The identity prerequisites are Studies 05–08, [RT-03](research/RT-03/CORE-LANGUAGE-SEMANTICS.md), and [Semantic Dependency Index](research/RT-06/SEMANTIC-DEPENDENCY-INDEX.md). [RT-19](research/RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) supplies the shared semantic API/Change Set context. The detailed documents define ownership boundaries and cross-link one another. The [Draft Glossary](research/../draft/GLOSSARY.md) is a shared terminology dependency for identity/hash work: review it whenever changing RT-20, RT-24, semantic dependency/hash roles, or package identity. Its terms are proposals until explicitly adopted.

- [Research Scenario 88](research/RT-18/RESEARCH-SCENARIO-88-DEFAULT-ARGUMENT-EVALUATION-AND-API-COMPATIBILITY.md) compares definition-time, per-call, omitted-argument ordering, source binding, and API-evolution behavior in Swift, Kotlin, Python, and C++; no LLMLang default policy is selected.
- [Research Scenario 89](research/RT-31/RESEARCH-SCENARIO-89-ECMASCRIPT-AUTOMATIC-SEMICOLON-INSERTION.md) extends the Go/Rust/Swift separator comparison with ECMAScript's parser-state and restricted-production ASI rules; no LLMLang policy is selected.
- [Research Scenario 90](research/RT-05/RESEARCH-SCENARIO-90-RUNTIME-HASHING-DETERMINISM-AND-PERSISTENT-IDENTITY.md) separates runtime map hashing, iteration order, stable fingerprints, and cryptographic digests; no LLMLang policy is selected.
- [Research Scenario 91](research/RT-05/RESEARCH-SCENARIO-91-VERSIONED-CONTENT-ADDRESSES-AND-DIGEST-MIGRATION.md) compares Git transition mappings, OCI algorithm-tagged descriptors, and versioned typed CIDs; no LLMLang encoding or migration policy is selected.
- [Research Scenario 92](research/RT-05/RESEARCH-SCENARIO-92-OPERATION-IDENTITY-AND-IMPLEMENTATION-BINDING.md) compares operation contracts, implementation bindings, action-cache keys and content artifacts; no OpHash envelope is selected.
- [Research Scenario 93](research/RT-11/RESEARCH-SCENARIO-93-CACHE-SOUNDNESS-RESULT-ENVELOPES-AND-TRUST.md) studies cache soundness, result envelopes, approximate dependency-cache restores, and trust boundaries; no cache policy is selected.
- [Open Questions Research Program](research/RESEARCH-PROGRAM-OPEN-QUESTIONS-2026-11-19.md) inventories LL design TODOs and taxonomy-wide gates, records the LL-022 ID collision correction, and sequences the remaining research; no design is selected.

</details>
