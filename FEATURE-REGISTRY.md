# LLMLang Feature Registry

**Status:** Initial consolidated inventory; not a language specification or an architecture decision  
**Updated:** 2026-11-23  
**Repository baseline:** `1071875edc260287b5d72901b9189fad646cf1b5` (`main`)  
**Scope:** LLMLang language, semantic platform, compiler/runtime, development toolchain, storage/build infrastructure, and external polyglot migration platform.

## 1. Purpose and authority

This registry is the project-wide index of capabilities that LLMLang is intended to support or that must be considered in its architecture. It consolidates the current research taxonomy (RT-01–RT-36), the development plan, open design questions, candidate architecture documents, and explicit requirements.

It is an inventory, **not** a commitment to implement every item, a release roadmap, or a normative specification. A feature's presence here does not make it accepted. Research documents and recommendations do not change the design baseline unless a decision is explicitly accepted in a durable decision/specification document.

The registry intentionally includes capabilities outside the language core when they constrain LLMLang's architecture. In particular, polyglot repository mirroring and incremental migration are external platform capabilities, not LLMLang syntax or built-in language semantics.

### 1.1 Status vocabulary

| Status | Meaning |
|---|---|
| **Accepted** | Explicit project decision recorded in a durable decision document. Scope is limited to that decision. |
| **Candidate** | Direction confirmed in design discussion or a candidate model, but not yet normative or fully specified. |
| **Required (research contract)** | Mandatory requirement inside a research brief; does not by itself mean the overall feature or format is selected. |
| **Proposed** | An architecture or capability is proposed in a research document/ADR, but not accepted. |
| **Researching** | Alternatives, semantics, feasibility, or evidence remain under investigation. |
| **Decision pending** | The question is sufficiently framed to require an explicit decision; see the linked open-question item. |
| **Deferred** | Explicitly postponed; not part of the current implementation commitment. |
| **Not selected** | An alternative or policy was examined but is not part of the current design baseline. |

Where a feature combines sub-capabilities with different maturity, its status is conservative. The source document remains authoritative for detailed evidence and limits.

### 1.2 Priority

- **P0** — foundational or blocks important architecture decisions, as classified by the research taxonomy/plan.
- **P1** — important for a coherent implementation or platform, but can follow foundational decisions.
- **P2** — ecosystem, usability, or governance work that can be sequenced later.
- **Unranked** — no explicit priority is assigned in the source.

Priority is a planning signal, not a quality or value judgment.

### 1.3 Registry record fields

Every feature has a stable registry ID, name, scope, concise capability statement, status, priority, and source references. Dependencies are not duplicated in each row: use the [research dependency map](research/RESEARCH-DEPENDENCY-MAP.md) and the linked primary sources for dependency relationships. IDs identify registry entries, not language symbols, SPG identities, or implementation APIs. Keep IDs stable when wording or status changes; split an entry only when it represents independently trackable capabilities.

## 2. Feature inventory

### 2.1 Product goals, intent, requirements, and contracts

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-PROD-001 | AI-native development workflow | Make structured semantic authoring, inspection, change planning, and verification first-class workflows for humans and coding agents. | Proposed | P0 | [RT-01](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md), [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) |
| F-PROD-002 | Explicit product constraints and workloads | Define intended users, representative workloads, correctness expectations, human authority, portability, and complexity constraints. | Researching | P0 | [RT-01](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [reference workloads](research/RT-01-REFERENCE-WORKLOADS.md) |
| F-PROD-003 | Bidirectional semantic translation across C, C++, Go, Rust, and LLMLang | Provide automated translation from LLMLang to C/C++/Go/Rust and from each of those languages into LLMLang, preserving defined observable semantics; permit target-specific runtime support (including a dedicated C runtime) and report unsupported or unverified cases explicitly. | Proposed (Goal) | P0 | [RT-30](research/RT-30-BIDIRECTIONAL-SEMANTIC-TRANSLATION.md), [RT-13](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [RT-28](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-REQ-001 | Requirements and intent model | Represent human intent as explicit, traceable requirements with ambiguity, provenance, scope, and evolution. | Researching | P0 | [RT-02](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [requirement reconstruction](research/RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md) |
| F-REQ-002 | Typed requirement representation | Represent requirements in a typed intermediate model that can be related to contracts, design, implementation, and evidence. | Researching | P0 | [Scenario 17](research/RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md), [RT-02](research/RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md) |
| F-REQ-003 | Behavioral contracts | Express preconditions, postconditions, effects, permitted transitions, and observable behavior for operations and components. | Candidate | P0 | [contract and invariant model](research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md), [RT-20](research/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md) |
| F-REQ-004 | Structure invariants | Declare invariants over fields, related structures, and domain-wide state; preserve declaration provenance and independent obligations. | Candidate | P0 | [structure contracts](research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md) |
| F-REQ-005 | Invariant composition and compatibility | Require all declared invariants to hold together; check compatibility conservatively and reject proven contradictions. | Candidate | P0 | [structure contracts, §§3–4](research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md) |
| F-REQ-006 | Deferred invariant checks and commit boundary | Permit only contract-authorized temporary invalid states; verify the affected consistency scope before atomic publication. | Candidate | P0 | [structure contracts, §4](research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md) |
| F-REQ-007 | Requirement-to-evidence traceability | Link requirements and contracts to implementations, tests, proofs, and exact verification evidence. | Researching | P0 | [RT-02](research/RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md), [RT-08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-REQ-008 | Public interface contracts and provider refinement | Stable public names and exact immutable operation contracts; independent body correctness and contract refinement with explicit evidence and unknown states. | Proposed | P0 | [Public interfaces](research/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md), [RT-20](research/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md) |

### 2.2 Core language: values, types, structures, ownership, and execution

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-LANG-001 | Core computation and evaluation semantics | Define values, expressions, evaluation order, control flow, state, determinism, and observable behavior. | Researching | P0 | [RT-03](research/CORE-LANGUAGE-SEMANTICS.md) |
| F-LANG-002 | Error and failure semantics | Define recoverable errors, exceptions/fatal failures, propagation, cancellation, cleanup failures, and observable failure traces. | Researching | P0 | [RT-03](research/CORE-LANGUAGE-SEMANTICS.md), [Scenarios 39–41](research/RESEARCH-SCENARIO-39-CLEANUP-FAILURE-AND-OWNERSHIP-TRANSFER.md) |
| F-LANG-003 | Numeric and string semantics | Specify integer overflow, floating-point behavior, conversions, Unicode, indexing, literals, and interpolation. | Researching | P0 | [RT-03](research/CORE-LANGUAGE-SEMANTICS.md), [Scenarios 45–46](research/RESEARCH-SCENARIO-45-NUMERIC-SEMANTICS-AND-OVERFLOW.md) |
| F-LANG-004 | Names, scopes, and source syntax | Define identifiers, scope, imports, statement termination, patterns, operators, and source safety. | Researching | P0 | [RT-03/04 scenario corpus](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-LANG-005 | Static type system | Provide explicit static types and compatibility checks; inference, coercion, subtyping, and conversion boundaries remain separately specified. | Researching | P0 | [RT-04](research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md), [LL-020](TODO.md#ll-020--define-llvm-backend-role-and-semantic-boundary) |
| F-LANG-006 | Structure inheritance | Support multiple inheritance with distinct parent subobjects, preserved parent guarantees, explicit initialization, and reverse-order destruction. | Candidate | P0 | [structure inheritance](research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md) |
| F-LANG-007 | Structure composition | Embed structures as independently identified, owned components with their own invariants, contracts, and lifecycle. | Candidate | P0 | [structure composition](research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md#3-structure-composition) |
| F-LANG-008 | Explicit initialization and destruction | Initialize parent parts and fields in declaration order; destroy in reverse initialization order; handle partial initialization failure correctly. | Candidate | P0 | [initialization and destruction](research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md#23-initialization-and-destruction) |
| F-LANG-009 | Ownership, borrowing, copy, and move | Track ownership and borrowing; distinguish copying references from copying referents; make move an ownership transfer. | Candidate | P0 | [copy and move](research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md#5-copy-and-move), [RT-04](research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) |
| F-LANG-010 | Templates with explicit arguments | Support template structures and functions with explicitly supplied type arguments; no implicit type-argument inference or arbitrary compile-time metaprogramming. | Candidate | P0 | [templates](research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md#6-templates) |
| F-LANG-011 | Template parameter constraints | Express structural, contract, and invariant constraints on template parameters; verify specializations against those constraints. | Candidate | P0 | [template constraints](research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md#62-constraints-on-template-parameters) |
| F-LANG-012 | Full and partial specialization | Support explicitly defined full and partial specializations as distinct concrete types, preserving the template contract. | Candidate | P0 | [template specialization](research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md#6-templates) |
| F-LANG-013 | Effects and capabilities | Describe observable effects and the authority required to perform them; keep effect semantics distinct from capability authorization. | Researching | P0 | [RT-04 alternatives](research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md), [Scenarios 37–38](research/RESEARCH-SCENARIO-37-EFFECT-ROWS-HANDLERS-AND-OBSERVATION.md) |
| F-LANG-014 | Concurrency and memory model | Define tasks, synchronization, atomic operations, memory ordering, fairness/liveness boundaries, and structured concurrency. | Researching | P0 | [RT-04](research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md), [Scenarios 57, 61, 94, 112–118](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-LANG-015 | Async cancellation and cleanup | Specify cancellation requests, terminal task disposition, resource cleanup, and cleanup-error composition. | Researching | P0 | [Scenario 40](research/RESEARCH-SCENARIO-40-ASYNC-CANCELLATION-AND-CLEANUP.md), [Scenario 129](research/RESEARCH-SCENARIO-129-CANCELLATION-AND-INVOCATION-EVIDENCE.md) |
| F-LANG-016 | Modules and initialization | Define module boundaries, imports, initialization order, and composition semantics. | Researching | P1 | [RT-03/04](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [Scenario 43](research/RESEARCH-SCENARIO-43-MODULES-IMPORTS-AND-INITIALIZATION.md) |
| F-LANG-017 | Pattern matching and exhaustiveness | Support typed pattern matching with explicit failure and exhaustiveness semantics. | Researching | P1 | [Scenarios 54 and 74](research/RESEARCH-SCENARIO-54-PATTERN-MATCHING-AND-EXHAUSTIVENESS.md) |

### 2.3 Semantic Program Graph, identity, and dependencies

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-SPG-001 | Typed Semantic Program Graph | Represent supported program meaning as typed immutable values and typed exact relationships. | Candidate | P0 | [RT-05 SPG](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) |
| F-SPG-002 | Specification, Design, and Implementation views | Represent requirements/contracts, design operations/interfaces, and implementations as related but independently optional logical views. | Candidate | P0 | [RT-05 SPG](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md), [concept](research/LLMLang-CONCEPT.md) |
| F-SPG-003 | Typed relationship model | Give each relation an explicit source/target kind, cardinality, ordering, resolution, and hash-relevance policy. | Researching | P0 | [RT-05 SPG](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) |
| F-SPG-004 | Immutable semantic versions | Model semantic values and accepted snapshots as immutable; changes create new versions rather than editing accepted objects in place. | Candidate | P0 | [RT-05 SPG](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md), [ADR-014 proposal](docs/adr/014-git-semantic-merge.md) |
| F-SPG-005 | Stable logical identity and lineage | Track logical entity continuity separately from content identity, including rename, move, split, merge, and replacement. | Researching | P0 | [LL-002](TODO.md#ll-002--define-operation-stable-id-lifecycle), [RT-05](research/RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) |
| F-SPG-006 | Content-addressed identity and canonical encoding | Define canonical semantic bytes, domain separation, digest algorithms, and hash-relevant dependencies. | Decision pending | P0 | [LL-004](TODO.md#ll-004--choose-canonical-encoding-and-hash-algorithm-policy), [LL-005](TODO.md#ll-005--define-hash-relevant-dependency-edges-and-cycles) |
| F-SPG-007 | Operation and implementation identity | Distinguish operation identity, implementation identity, contract identity, and stable logical lineage; bind calls to exact immutable operation versions. | Researching | P0 | [LL-001–003](TODO.md#operation-identity-and-calls), [RT-20 contract identity](research/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md) |
| F-SPG-008 | Occurrence and containment identity | Distinguish reusable immutable values from their managed occurrences/slots in owning scopes. | Researching | P0 | [RT-05 SPG](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md), [Scenario 8](research/RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md) |
| F-SPG-009 | Provenance and evidence relations | Preserve the origin, revision, assumptions, and evidence associated with semantic claims and bindings. | Researching | P1 | [RT-05 SPG](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md), [RT-16](research/RT-16-THREAT-MODEL-01.md) |
| F-SPG-010 | Semantic snapshots and change sets | Isolate candidate changes and publish new immutable semantic snapshots after acceptance. | Proposed | P0 | [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) |
| F-SPG-011 | Semantic diff and three-way merge | Compare typed semantic trees and reconcile base/ours/theirs with explicit conflict and provenance handling. | Researching | P0 | [RT-24](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md), [ADR-014](docs/adr/014-git-semantic-merge.md) |
| F-SPG-012 | Semantic conflict detection and resolution | Detect conflicting changes at typed semantic boundaries and require explicit, auditable resolution. | Researching | P0 | [RT-24](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) |
| F-DEP-001 | Typed semantic dependency graph | Track semantic, call, data, contract, evidence, and other dependency relations with explicit edge meaning. | Researching | P0 | [RT-06](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [semantic dependency index](research/SEMANTIC-DEPENDENCY-INDEX.md) |
| F-DEP-002 | Dependency completeness and conservative unknowns | Distinguish complete dependency knowledge from partial/unknown analysis; do not interpret missing edges as proof of non-dependence. | Researching | P0 | [RT-06](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [Scenarios 19–28](research/RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md) |
| F-DEP-003 | Reverse references and caller discovery | Find all callers and references affected by a changed semantic object. | Proposed | P0 | [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) |
| F-DEP-004 | Change impact analysis and planning | Compute the affected closure and a versioned Change Impact Plan before implementation. | Proposed | P0 | [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) |
| F-DEP-005 | Per-call-site compatibility and version splitting | Independently preserve, migrate, adapt, or fork caller/callee bindings; do not blindly migrate every caller to the newest version. | Proposed | P0 | [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [LL-003](TODO.md#ll-003--specify-contract-based-analogue-discovery-and-substitution) |
| F-DEP-006 | Hash propagation to entry points | Propagate identity changes only through hash-relevant references selected for migration or semantic modification. | Proposed | P0 | [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [LL-005](TODO.md#ll-005--define-hash-relevant-dependency-edges-and-cycles) |
| F-SPG-013 | Public name resolution and exact provider binding | Separate scoped export catalog, exact operation revision, provider selection and external symbol mapping; explicit compatible evolution and deterministic resolution. | Proposed | P0 | [Public interfaces](research/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md), [RT-05](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) |

### 2.4 Formal semantics, verification, tests, and evidence

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-VER-001 | Canonical formal semantics | Establish a reference semantics from which executable and formal interpretations can be related. | Researching | P0 | [RT-07](research/LLMLang-FORMAL-VERIFICATION.md), [RT-03](research/CORE-LANGUAGE-SEMANTICS.md) |
| F-VER-002 | Proof obligations and verification conditions | Derive explicit obligations from requirements, contracts, invariants, and transformations. | Researching | P0 | [RT-07](research/LLMLang-FORMAL-VERIFICATION.md) |
| F-VER-003 | Independent proof checking | Check proof artifacts independently of the component that generated them. | Researching | P0 | [RT-07](research/LLMLang-FORMAL-VERIFICATION.md) |
| F-VER-004 | Solver integration | Use SMT/solver backends with explicit SAT/UNSAT/UNKNOWN/error/timeout semantics and sound trust boundaries. | Researching | P0 | [Scenarios 102–103](research/RESEARCH-SCENARIO-102-SOLVER-UNKNOWN-AND-SOUND-PATH-PRUNING.md) |
| F-VER-005 | Lean and Logos integration | Explore proof-backed semantic models and independent kernel checking. | Researching | P0 | [RT-07](research/LLMLang-FORMAL-VERIFICATION.md), [research prototypes](research/PROTOTYPES) |
| F-VER-006 | Formal model checking | Explore finite-state and temporal model checking for concurrency, protocols, and stateful behavior. | Researching | P1 | [RT-07/08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-VER-007 | Translation and optimization correctness | Require evidence that lowering and optimization preserve the declared source semantics. | Researching | P0 | [RT-07](research/LLMLang-FORMAL-VERIFICATION.md), [Scenario 96](research/RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md) |
| F-VER-008 | Explicit evidence status and provenance | Bind evidence to exact inputs, assumptions, tool versions, and scope; distinguish proved, tested, partial, unknown, and stale results. | Candidate | P0 | [RT-07/08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [RT-28](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-VER-009 | Verified SPG-to-Lean pipeline and compositional proof graph | Derive Lean representations and proof obligations from versioned SPG functions/contracts; verify callers compositionally through explicit callee-contract assumptions; track checked proof dependencies, assumption discharge, transitive proof closure, and incremental invalidation in a typed PDG linked to SPG. | Researching | P0 | [RT-32](research/RT-32-VERIFIED-SPG-TO-LEAN-PIPELINE.md), [RT-07](research/LLMLang-FORMAL-VERIFICATION.md) |
| F-VER-010 | Backend-independent proof planning and orchestration | Classify proof obligations independently of backend syntax; select or combine eligible Lean, SMT, TLA+, and future backends using versioned capability profiles; preserve translation correspondence, trust, partial/unknown outcomes, and evidence provenance. | Researching | P0 | [RT-33](research/RT-33-PROOF-BACKEND-SELECTION-AND-ORCHESTRATION.md), [RT-32](research/RT-32-VERIFIED-SPG-TO-LEAN-PIPELINE.md), [RT-07](research/LLMLang-FORMAL-VERIFICATION.md) |
| F-VER-011 | Automatic resource complexity inference and verification | Infer and independently verify model-scoped resource bounds from SPG, compose typed cost summaries, distinguish functional task lower bounds from implementation upper bounds, prove optimality when justified and detect resource regressions with conservative abstention. | Researching | P0 | [RT-34](research/RT-34-AUTOMATIC-COMPLEXITY-INFERENCE.md), [benchmark plan](research/RT-34-COMPLEXITY-BENCHMARK.md) |
| F-VER-012 | Explicit assumptions and conditional proof management | Typed premise identity, scoped authorization, foreign-provider conformance assumptions, PDG discharge and transitive closure, consistency controls, freshness and separate policy admission. | Researching | P0 | [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](research/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md) |
| F-TEST-001 | Contract- and property-based testing | Generate and execute tests from contracts and properties. | Researching | P0 | [RT-08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-TEST-002 | Stateful and scenario testing | Validate operation sequences, state transitions, and multi-step deterministic scenarios. | Researching | P1 | [RT-08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-TEST-003 | Fuzzing and differential testing | Generate adversarial inputs and compare independent implementations/backends against a shared oracle. | Researching | P1 | [RT-08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [RT-13](research/TRANSLATION-AND-TARGET-BACKENDS.md) |
| F-TEST-004 | Verification impact and evidence reuse | Select affected tests/proofs and reuse evidence only when exact inputs and dependency closure remain valid. | Researching | P0 | [RT-08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [RT-11](research/SEMANTIC-COMPILATION-CACHE.md) |

### 2.5 Compiler, runtime, backends, and system interfaces

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-COMP-001 | Source frontends and semantic analysis | Parse source and construct typed semantic representations with explicit unsupported/opaque boundaries. | Proposed | P1 | [RT-09](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [RT-28 §5](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-COMP-002 | Semantic IR and ordered lowering | Lower semantic objects into an execution-oriented representation without losing ordering or semantic dependencies. | Researching | P1 | [RT-09](research/RT-09-ORDERED-SPG-LOWERING.md), [RT-05 SPG](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) |
| F-COMP-003 | Type, effect, ownership, and contract checking | Run static analyses over types, effects, ownership, contracts, and invariants. | Proposed | P0 | [RT-04](research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md), [RT-07](research/LLMLang-FORMAL-VERIFICATION.md) |
| F-COMP-004 | Structured diagnostics | Produce machine-readable diagnostics with source/semantic locations and human/agent renderings. | Researching | P2 | [Scenario 95](research/RESEARCH-SCENARIO-95-DIAGNOSTICS-FOR-HUMANS-AND-AGENTS.md) |
| F-RUN-001 | Interpreter or graph execution | Execute a supported semantic subset directly as a reference/runtime path. | Proposed | P1 | [RT-10](research/POSIX-RUNTIME-ARCHITECTURE.md), [RT-03](research/CORE-LANGUAGE-SEMANTICS.md) |
| F-RUN-002 | Bytecode VM | Explore a portable VM and its runtime contract. | Researching | P1 | [RT-10](research/POSIX-RUNTIME-ARCHITECTURE.md) |
| F-RUN-003 | Native execution | Compile to native targets with a runtime that preserves source-level behavior. | Proposed | P1 | [RT-10](research/POSIX-RUNTIME-ARCHITECTURE.md), [RT-13](research/TRANSLATION-AND-TARGET-BACKENDS.md) |
| F-RUN-004 | POSIX system interface | Provide a defined LLMLang-facing POSIX API with portable/native runtime implementation options and explicit conformance scope. | Proposed | P1 | [POSIX runtime](research/POSIX-RUNTIME-ARCHITECTURE.md), [LL-013–019](TODO.md#runtime-and-system-interfaces) |
| F-RUN-005 | Resource lifecycle and cleanup | Preserve ownership, close/release obligations, failure behavior, and cleanup ordering across calls and foreign boundaries. | Researching | P0 | [COR-13](research/RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md), [Scenarios 119–133](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-BACK-001 | Replaceable backend interface | Keep target lowering behind a replaceable backend boundary; do not make a backend's IR the canonical semantic representation. | Proposed | P1 | [LL-020](TODO.md#ll-020--define-llvm-backend-role-and-semantic-boundary), [LLVM backend](research/LLVM-BACKEND-ARCHITECTURE.md) |
| F-BACK-002 | Rust, Go, C/C++ and other target interop | Evaluate generation/interop with target languages as implementation choices, not as already committed mandatory backends. | Researching | P1 | [translation and target backends](research/TRANSLATION-AND-TARGET-BACKENDS.md) |
| F-BACK-003 | LLVM backend | Evaluate LLVM as a leading candidate behind a replaceable boundary; its role and preservation contract remain undecided. | Decision pending | P1 | [LL-020](TODO.md#ll-020--define-llvm-backend-role-and-semantic-boundary), [LLVM architecture](research/LLVM-BACKEND-ARCHITECTURE.md) |
| F-BACK-004 | WebAssembly target | Evaluate WASM as a target/runtime profile with explicit memory and ABI constraints. | Researching | P1 | [RT-13](research/TRANSLATION-AND-TARGET-BACKENDS.md), [WASM memory views](research/RT-13-WASM-MEMORY32-VIEWS.md) |
| F-INTEROP-001 | FFI and ABI boundaries | Define typed ownership/effect/resource contracts for calls across foreign ABIs and runtime boundaries. | Researching | P1 | [RT-13](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [Scenarios 126–128](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |

### 2.6 Incremental computation, storage, Git, packages, and artifacts

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-BUILD-001 | Semantic action graph | Represent compilation, analysis, testing, and proof work as a typed dependency graph of actions. | Proposed | P1 | [LL-021](TODO.md#ll-021--define-semantic-action-caching-and-incremental-compilation), [semantic cache](research/SEMANTIC-COMPILATION-CACHE.md) |
| F-BUILD-002 | Action Key and artifact identity | Separate semantic object hash, action key, and output artifact hash; include all result-determining inputs. | Proposed | P0 | [LL-021](TODO.md#ll-021--define-semantic-action-caching-and-incremental-compilation) |
| F-BUILD-003 | Incremental invalidation | Recompute only affected actions when dependency closure proves unaffected results reusable; fail conservatively on incomplete dependencies. | Researching | P0 | [RT-11](research/SEMANTIC-COMPILATION-CACHE.md), [RT-32/33](research/RT-32-INCREMENTAL-INVALIDATION-RECHECK-2026-11-23.md) |
| F-BUILD-004 | Local, shared, and remote caches | Support cache layers as disposable accelerators with explicit trust and provenance boundaries. | Proposed | P1 | [RT-11](research/SEMANTIC-COMPILATION-CACHE.md), [LL-021](TODO.md#ll-021--define-semantic-action-caching-and-incremental-compilation) |
| F-STORE-001 | Git-reconstructible semantic state | Ensure a clean checkout contains sufficient authoritative inputs to reconstruct accepted program meaning; local databases/indexes/caches are derived. | Required (research contract) | P0 | [RT-19 §2.1](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [RT-27, R-STORE-001](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-001--complete-reconstruction-from-git) |
| F-STORE-002 | Aggregated multi-object SPG container layout | Store multiple SPG records/objects in a bounded number of container files or segments rather than one tracked file per object; the physical encoding remains open. | Required (research contract) | P0 | [RT-27, R-STORE-002](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-002--no-one-file-per-object) |
| F-STORE-003 | Cache-first record metadata | Read object ID and content hash before payload; check cache and skip payload read/deserialization on a cache hit. | Required (research contract) | P0 | [RT-27, R-STORE-003](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-003--cache-lookup-before-payload-deserialization) |
| F-STORE-004 | Deterministic serialization | Produce deterministic representations for equivalent semantic values under a fixed format contract. | Required (research contract) | P0 | [RT-27, R-STORE-004](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-004--deterministic-representation) |
| F-STORE-005 | Independently addressable records and blocks | Define record/block boundaries for independent access and parallel processing within one file. | Researching | P0 | [RT-27, R-STORE-006](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-006--parallel-processing-within-a-single-file-should) |
| F-STORE-006 | Seekable/independent compression | Evaluate independently decompressible blocks to support random access and parallelism. | Researching | P1 | [RT-27, R-STORE-007](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-007--independent-or-seekable-compression-blocks-should) |
| F-STORE-007 | Git-efficient append/delete history | Benchmark Git delta/repack behavior for append/delete-oriented SPG changes and stable record placement. | Researching | P0 | [RT-27, R-STORE-008](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-008--efficient-git-history-for-changing-containers-should), [Git binary efficiency](research/GIT-BINARY-SPG-STORAGE-EFFICIENCY.md) |
| F-STORE-008 | Explicit object update and deletion | Define unambiguous add/update/delete semantics and integrity checks for records. | Required (research contract) | P1 | [RT-27, R-STORE-010](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-010--explicit-object-update-and-deletion-semantics) |
| F-STORE-009 | Recoverable indexes | Treat indexes as verifiable/rebuildable derived data, not sole authoritative content. | Required (research contract) | P1 | [RT-27, R-STORE-012](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-012--recoverable-and-verifiable-indexes) |
| F-STORE-010 | Semantic identity independent of physical layout | Keep semantic object identity, content hash, lineage, occurrence/selection identity, and snapshot identity independent of file, segment, offset, and Git blob placement. | Required (research contract) | P0 | [RT-27, R-STORE-009](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-009--physical-layout-must-not-define-semantic-identity), [RT-24](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) |
| F-STORE-011 | Bounded storage and compaction complexity | Bound active containers, indexes, manifests, and tombstones; define deterministic compaction/repacking that preserves semantic content and identity. | Required (research contract) | P1 | [RT-27, R-STORE-011](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-011--bounded-operational-complexity) |
| F-STORE-012 | Semantic-merge-only SPG integration | Treat ordinary line-oriented Git text merge as unsafe for SPG containers; require complete-state semantic merge and fail-closed conflict handling. | Required (research contract) | P0 | [RT-27, R-STORE-005](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-005--no-ordinary-text-merge-of-spg-containers), [RT-24](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) |
| F-GIT-001 | Git repository integration | Use Git for repository history and collaboration while keeping Git object identity distinct from semantic identity. | Proposed | P1 | [ADR-014](docs/adr/014-git-semantic-merge.md), [RT-15](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-GIT-002 | Semantic Git merge driver | Reconcile semantic changes with typed diff/merge rather than treating binary-container text merge as valid. | Researching | P0 | [RT-24](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md), [RT-27](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md) |
| F-GIT-003 | Worktree isolation and integration | Use isolated worktrees for parallel workflows; integrate them as a separate consistency-checked operation. | Candidate | P0 | [RT-22](research/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md), [structure contracts §6](research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md#6-workflows-worktrees-and-integration) |
| F-GIT-004 | Shared immutable semantic store with per-worktree views | Allow one Toolchain to serve multiple worktrees over shared immutable semantic objects and separately versioned mutable file/interface mappings. | Proposed | P0 | [RT-23](research/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) |
| F-GIT-005 | Atomic, validation-gated publication | Publish accepted semantic changes atomically; bind validation and commit to the exact candidate tree. | Candidate | P0 | [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [structure contracts §4](research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md#4-mutation-deferred-checks-and-commit) |
| F-PKG-001 | Package and library artifacts | Define reusable package/library boundaries, identities, public contracts, and dependency metadata. | Researching | P1 | [RT-12](research/LIBRARIES-AND-TEMPLATES.md), [LL-010/011/022](TODO.md#language-packages-and-templates) |
| F-PKG-002 | Templates and instantiation | Provide reusable semantic templates and explicit specialization/instantiation rules. | Candidate | P1 | [RT-12](research/LIBRARIES-AND-TEMPLATES.md), [F-LANG-010–012](#22-core-language-values-types-structures-ownership-and-execution) |
| F-PKG-003 | Package manifest, index, and provider model | Define package manifests/indexes, sparse lookup, dependency resolution, static/dynamic package delivery, and provider interfaces. | Researching | P1 | [package system](research/PACKAGE-SYSTEM.md), [LL-022](TODO.md#ll-022--define-the-package-content-index-and-dynamic-provider-model) |
| F-PKG-004 | Package provenance and reproducibility | Record package source, integrity, licensing/trust, and reproducible build inputs. | Researching | P1 | [RT-12](research/PACKAGE-SYSTEM.md), [RT-16](research/RT-16-THREAT-MODEL-01.md) |

### 2.7 Toolchain, AI authoring, collaboration, and developer experience

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-TOOL-001 | Transport-neutral Toolchain API | Expose typed semantic operations independently of MCP/JSON-RPC or any specific client transport. | Proposed | P0 | [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [LL-024](TODO.md#ll-024--define-the-toolchain-server-and-semantic-development-api) |
| F-TOOL-002 | Toolchain Server and workspaces | Provide isolated working states, query, mutation, checkpoint, acceptance, synchronization, and recovery capabilities. | Proposed | P0 | [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) |
| F-TOOL-003 | MCP adapter and structured object exchange | Expose the domain API through MCP; the accepted JSON object-format decision is scoped to MCP-facing SPG objects only. | Accepted (scoped) | P0 | [ADR-017](docs/adr/017-mcp-agent-object-format.md), [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) |
| F-TOOL-004 | CLI, IDE, CI, and automation adapters | Allow multiple clients to use the same semantic domain API. | Proposed | P1 | [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md) |
| F-TOOL-005 | Knowledge Context | Assemble bounded, versioned, provenance-preserving information an agent may rely on, including explicit omissions and completeness. | Researching | P1 | [LL-026](TODO.md#ll-026--define-the-knowledge-context-model), [RT-14](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-TOOL-006 | Task Context | Represent task objective, scope, constraints, baseline, expected outputs, dependencies, and completion obligations separately from knowledge and authorization. | Researching | P1 | [LL-027](TODO.md#ll-027--define-the-task-context-model), [RT-14](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-TOOL-007 | LLM patch planning and execution enforcement | Require a complete approved Change Impact Plan before implementation; validate that all planned mutations were performed. | Proposed | P0 | [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [LL-023](TODO.md#ll-023--define-complete-llm-patch-planning-and-validation-gated-commit) |
| F-TOOL-008 | Multi-agent collaboration and concurrency | Coordinate isolated changes, shared immutable objects, expected-hash preconditions, and conflict handling. | Researching | P0 | [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [RT-23](research/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) |
| F-TOOL-009 | Audit trail and human approval boundaries | Record who/what changed semantic state and require human decisions where policy or ambiguity demands them. | Researching | P1 | [RT-14/16](research/RESEARCH-TAXONOMY.md#2-research-area-inventory), [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) |
| F-TOOL-010 | Diagnostics and repair suggestions | Provide structured diagnostics, source/semantic locations, explanations, and bounded repair suggestions without assuming autonomous repair authority. | Researching | P2 | [Scenario 95](research/RESEARCH-SCENARIO-95-DIAGNOSTICS-FOR-HUMANS-AND-AGENTS.md) |

| F-TOOL-011 | Semantic/syntax separation and canonical representation boundary | Keep the authoritative Semantic Model independent of Abstract Syntax Model and concrete syntax profiles; define the role and mapping of canonical Semantic IR. | Researching | P0 | [RT-31](research/RT-31-AI-ORIENTED-SYNTAX-AND-TOOLCHAIN-OPTIMIZATION.md), [RT-03](research/CORE-LANGUAGE-SEMANTICS.md), [RT-09](research/RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md) |
| F-TOOL-012 | Pluggable syntax profiles and semantic-preserving transformations | Support independently versioned parsers, generators, formatters, and textual/structured/hybrid syntax profiles over shared semantic capabilities. | Researching | P0 | [RT-31](research/RT-31-AI-ORIENTED-SYNTAX-AND-TOOLCHAIN-OPTIMIZATION.md), [RT-24](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) |
| F-TOOL-013 | Controlled AI syntax evaluation | Compare model authoring accuracy, semantic correctness, repair effort, token/cost, latency, and review effort using common tasks, pinned configurations, and independent oracles. | Researching | P0 | [RT-31](research/RT-31-AI-ORIENTED-SYNTAX-AND-TOOLCHAIN-OPTIMIZATION.md), [RT-08](research/RESEARCH-TAXONOMY.md#2-research-area-inventory) |
| F-TOOL-014 | MCP session and interaction recording | Record correlated session, request/response, tool-call, validation, and repair events with model/profile/instruction/Toolchain provenance and configurable privacy controls. | Researching | P0 | [RT-31](research/RT-31-AI-ORIENTED-SYNTAX-AND-TOOLCHAIN-OPTIMIZATION.md), [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [RT-16](research/RT-16-THREAT-MODEL-01.md) |
| F-TOOL-015 | AI error analytics and evidence-driven Toolchain optimization | Classify and attribute model, context, Toolchain, and environment failures; use reproducible statistics and held-out regression suites to improve syntax, instructions, diagnostics, and Toolchain. | Researching | P0 | [RT-31](research/RT-31-AI-ORIENTED-SYNTAX-AND-TOOLCHAIN-OPTIMIZATION.md), [RT-14 open-question program](research/RESEARCH-PROGRAM-OPEN-QUESTIONS-2026-11-19.md), [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) |
| F-TOOL-016 | Semantic Function Discovery | Discover functions from natural-language intent and structured requirements using derived semantic fingerprints and hybrid retrieval; verify hard compatibility constraints, expose ambiguity, and resolve to exact function hashes. Fingerprints and indexes are derived Toolchain data, not function identity or call semantics. | Researching | P0 | [RT-35](research/RT-35-SEMANTIC-FUNCTION-DISCOVERY-AND-RETRIEVAL.md), [RT-05](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md), [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [RT-24](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) |

### 2.8 Security, resource management, portability, and self-development

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-SEC-001 | Capability security and authorization | Require explicit authority for sensitive operations; keep task description separate from permission grants. | Researching | P1 | [RT-16](research/RT-16-THREAT-MODEL-01.md), [LL-027 security boundary](TODO.md#ll-027--define-the-task-context-model) |
| F-SEC-002 | Sandboxing and isolation | Constrain untrusted code, tools, and agent actions within explicit resource and authority boundaries. | Researching | P1 | [RT-16](research/RT-16-THREAT-MODEL-01.md) |
| F-SEC-003 | Trusted computing base and supply-chain provenance | Minimize trusted components and track artifact/dependency provenance, licensing, integrity, and attestations. | Researching | P1 | [RT-16](research/RT-16-THREAT-MODEL-01.md), [LL-009](TODO.md#ll-009--define-registry-trust-provenance-licensing-and-retention-policy) |
| F-RES-001 | Hierarchical resource accounting | Attribute CPU, memory, I/O, task/coroutine, and other resource use to nested tasks/scopes. | Researching | P1 | [RT-26](research/RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md) |
| F-RES-002 | Budgets, quotas, throttlers, and limit handlers | Set resource budgets, enforce limits/rates, and define explicit behavior when limits are exceeded. | Researching | P1 | [RT-26](research/RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md) |
| F-RES-003 | Memory allocator selection | Evaluate allocator compatibility, fragmentation, retention, latency, throughput, and FFI/runtime constraints. | Researching | P1 | [RT-25](research/RT-25-MEMORY-ALLOCATOR-COMPATIBILITY-AND-BENCHMARKING.md) |
| F-PORT-001 | Language and toolchain versioning | Version language components, toolchain, standard library, and package/module dimensions separately where needed. | Candidate | P1 | [language versioning](research/LANGUAGE-VERSIONING.md), [language-components.toml](language-components.toml) |
| F-PORT-002 | Immutable published components and same-toolchain compatibility | Published components are immutable; callable compatibility is checked within a coherent build using one toolchain version. | Accepted | P1 | [architecture decision](draft/ARCHITECTURE-DECISIONS.md), [LL-025](TODO.md#ll-025--define-cross-version-component-and-wire-compatibility) |
| F-PORT-003 | Cross-version wire compatibility | General cross-toolchain wire compatibility, schema negotiation, and persisted-message migration are not required by the current decision. | Not selected | Unranked | [architecture decision](draft/ARCHITECTURE-DECISIONS.md), [Scenario 134](research/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md) |
| F-SELF-001 | Bootstrap and self-development | Define the minimum language/compiler/runtime/tooling slice needed to develop LLMLang tools and progressively move tools to LLMLang. | Researching | P0 | [RT-21](research/RT-21-LLMLANG-SELF-DEVELOPMENT-AND-BOOTSTRAP-ROADMAP.md) |

### 2.9 External polyglot migration and repository mirroring platform

**Boundary:** This group is deliberately outside the LLMLang language core. RT-28 distinguishes (a) language semantics, (b) LLMLang compiler/Toolchain/runtime capabilities, and (c) external migration-management records and workflows. AIVibeFlow or another migration service may own the Migration Project and its lifecycle; LLMLang should expose only the language/Toolchain/interop capabilities justified by concrete requirements.

| ID | Feature | Scope and capability | Status | Priority | Sources |
|---|---|---|---|---|---|
| F-MIG-001 | Migration Project | Long-lived record binding source repositories, refs/baselines, policy, migration units, dependencies, evidence, and rollout state. | Proposed (external platform) | P0 | [RT-28 §§3, 13](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-002 | Migration Unit | Independently governed migration scope at function/type/module/package/library/service/subsystem granularity. | Proposed (external platform) | P0 | [RT-28 §3.2](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-003 | Versioned Mirror Binding | Versioned relation between source entities and LLMLang semantic entities, distinct from either side's identity. | Proposed (external platform) | P0 | [RT-28 §3.3](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-004 | Source baseline and reproducible evidence envelope | Pin source tree/commit, dependencies, compiler/toolchain, target, build flags, extractor versions, tests, and LLMLang snapshot. | Proposed | P0 | [RT-28 §3.4](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-005 | Multi-language source frontends and semantic import | Extract syntax, symbols/types, dependencies, effects, contracts, and provenance; explicitly preserve unsupported constructs as opaque/foreign boundaries. | Researching | P0 | [RT-28 §5](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-006 | Upstream change detection and reconciliation | Detect source-side changes continuously and reconcile them with the LLMLang mirror using versioned bindings and impact evidence. | Researching | P0 | [RT-28 §6](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-007 | Incremental migration | Migrate independently governed units without requiring whole-repository or whole-package rewrites. | Proposed (external platform) | P0 | [RT-28 §§2–4](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-008 | Mapping cardinality and lineage | Preserve one-to-one, one-to-many, many-to-one, split, merge, wrapper, adapter, and generated-code correspondences. | Researching | P0 | [RT-28 §3.3](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-009 | Mixed-language execution and ownership | Execute source and LLMLang implementations together through explicit interop boundaries with safe state/resource ownership. | Researching | P0 | [RT-28 §8](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md), [RT-13](research/TRANSLATION-AND-TARGET-BACKENDS.md) |
| F-MIG-010 | Differential and contract verification | Compare source and mirror behavior against explicit contracts, observations, fixtures, and bounded evidence claims. | Researching | P0 | [RT-28 §7](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-011 | Defect provenance and attribution | Distinguish upstream, mirror, adapter, oracle, environment, contract, and unresolved defect sources. | Proposed (external platform) | P1 | [RT-28 §9](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-012 | Upstream contribution workflow | Trace fixes and regression tests back to the upstream repository and its PR/review outcome. | Proposed (external platform) | P1 | [RT-28 §9.4](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-013 | Shadow execution | Compare mirror behavior without allowing it to perform authoritative production side effects. | Researching | P1 | [RT-28 §10](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-014 | Canary rollout, cutover, and rollback | Gradually route eligible work to the mirror, switch authority explicitly, and recover to the source implementation when needed. | Proposed (external platform) | P1 | [RT-28 §10](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |
| F-MIG-015 | Migration governance and recovery | Make migration transitions explicit, versioned, auditable, security-reviewed, and evidence-guarded. | Researching | P1 | [RT-28 §§4, 11–12](research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md) |

## 3. Cross-cutting architectural constraints

These constraints connect features across layers. They are not additional implementation features; they are invariants to preserve when choosing designs.

1. **Semantic identity is not Git identity.** Git blob/tree/commit IDs, semantic content hashes, operation/implementation identities, action keys, artifact hashes, and mirror-binding identities must remain distinct.
2. **Derived storage is reconstructible.** Local databases, indexes, caches, and materialized views must not become the only copy of accepted source meaning.
3. **Incomplete analysis is explicit.** Unknown or unsupported syntax, missing dependencies, incomplete source frontends, and partial evidence must not be silently interpreted as absence.
4. **Immutable accepted state.** Proposals are isolated; accepted semantic snapshots/components are not edited in place.
5. **Evidence is input-bound.** Tests, proofs, cache entries, migration decisions, and commits refer to exact baselines, tool versions, configurations, and dependency closure.
6. **Semantic merge is not byte merge.** Physical Git conflict resolution cannot substitute for typed semantic reconciliation.
7. **No universal equivalence claims from finite tests.** Test outcomes support bounded evidence claims, not universal behavioral equivalence.
8. **External migration remains external.** Migration Projects, Migration Units, Mirror Bindings, rollout states, and upstream contribution workflows do not become LLMLang language constructs merely because they use LLMLang semantic objects.
9. **Backend semantics are subordinate to LLMLang semantics.** LLVM, Rust, Go, C/C++, WASM, and other targets are implementation/interoperability choices, not sources of truth for language meaning.
10. **Task intent is not authorization.** Task Context, Knowledge Context, and execution authority remain separate concerns.

## 4. Coverage against the research taxonomy

The registry maps the current research-area taxonomy as follows:

| Research area | Registry coverage |
|---|---|
| RT-01 Product goals and design constraints | F-PROD |
| RT-02 Intent, requirements, and specification model | F-REQ |
| RT-03 Core language semantics | F-LANG |
| RT-04 Type system, effects, ownership, and capabilities | F-LANG |
| RT-05 Canonical program representation and semantic identity | F-SPG |
| RT-06 Dependency semantics and impact analysis | F-DEP |
| RT-07 Formal semantics and verification architecture | F-VER |
| RT-08 Testing, validation, and evidence model | F-TEST |
| RT-09 Compiler architecture and intermediate representations | F-COMP |
| RT-10 Runtime and execution model | F-RUN |
| RT-11 Build, incremental computation, and caching | F-BUILD |
| RT-12 Libraries, packages, templates, and artifact reuse | F-PKG |
| RT-13 Target backends and interoperability | F-BACK, F-INTEROP |
| RT-14 AI-native authoring and change protocol | F-TOOL |
| RT-15 Collaboration, version control, and semantic merge | F-GIT, F-SPG |
| RT-16 Security, isolation, trust, and governance | F-SEC |
| RT-17 Developer experience and diagnostics | F-TOOL |
| RT-18 Conformance, evolution, and ecosystem | F-PORT |
| RT-19 Toolchain Server and semantic development API | F-TOOL |
| RT-20 LLM patch planning and verified commit | F-DEP, F-TOOL, F-GIT |
| RT-21 LLMLang self-development and bootstrap | F-SELF |
| RT-22 Git repository and worktree MCP surface | F-GIT, F-TOOL |
| RT-23 Shared Toolchain and multi-worktree File Views | F-GIT |
| RT-24 Semantic representation, diff, and three-way merge | F-SPG, F-GIT |
| RT-25 Memory allocator compatibility and selection | F-RES |
| RT-26 Hierarchical resource accounting and enforcement | F-RES |
| RT-27 SPG repository storage format | F-STORE |
| RT-28 Incremental polyglot migration and semantic mirroring | F-MIG |
| RT-29 Rust capability and implementation foundation | F-LANG, F-BACK, F-INTEROP, F-RUN |
| RT-30 Bidirectional semantic translation across LLMLang and C/C++/Go/Rust | F-COMP, F-BACK, F-INTEROP, F-RUN |
| RT-31 AI-oriented syntax, semantic separation, and Toolchain optimization | F-TOOL, F-COMP |
| RT-32 Verified SPG-to-Lean pipeline | F-VER |
| RT-33 Proof backend selection and verification orchestration | F-VER, F-TEST, F-BUILD |
| RT-34 Automatic complexity inference, resource contracts and algorithm optimality verification | F-VER, F-TEST, F-COMP, F-RUN, F-BUILD |
| RT-36 Formal verification assumptions and trust boundaries | F-VER, F-INTEROP, F-SEC, F-BUILD, F-TOOL |

The mapping is an index, not proof that every research claim or scenario has been validated. RT-28's migration-management records remain explicitly outside the language core.

## 5. Known open decisions and evidence limits

The following are important open questions, not missing registry entries:

- Operation hash envelope and operation stable-ID lifecycle: LL-001 and LL-002.
- Canonical encoding, hash algorithm, hash-relevant edges, cycles, and artifact granularity: LL-004–LL-007.
- Compatibility evidence, trust, provenance, licensing, and retention: LL-008/009.
- Package identity, library publication, template instantiation, package index/provider model: LL-010–012 and LL-022.
- POSIX profile/API/runtime and LLVM backend role: LL-013–020.
- Semantic action caching and incremental compilation: LL-021.
- Toolchain Server and validation-gated patch workflow: LL-023/024.
- Knowledge Context and Task Context: LL-026/027.
- Polyglot migration source frontends, binding identity, equivalence, mixed-language ownership, and rollout: RT-28 research questions.
- SPG physical format, cache-metadata integrity, compression/index layout, compaction, and Git history efficiency: [RT-27](research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md); mandatory research constraints do not select a physical format.

The research corpus inventory and traceability reviews are not claim-level validation of all scenarios/prototypes. See [research corpus inventory](research/RESEARCH-CORPUS-INVENTORY-2026-11-20.json), [semantic traceability review](research/RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md), and [research quality/decision rules](research/RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md).

## 6. Maintenance

- Add or split a feature only when it is a durable capability or architectural constraint, not for every implementation task or scenario.
- Search existing IDs before adding entries; preserve IDs when editing.
- Link each feature to its strongest primary source, not merely to a broad index.
- Update status only when the source decision/evidence changes. A recommendation or prototype alone does not imply acceptance.
- Keep implementation tasks and milestones in [PLAN.md](PLAN.md) or an issue tracker; keep unresolved design questions in [TODO.md](TODO.md).
- When a decision is accepted, update the relevant decision/specification document first, then update this registry.
- Review this registry whenever RT taxonomy, TODO, architecture decisions, or candidate specifications change.
- Do not infer that a feature is required for the first release solely from its presence in this registry.

## 7. Primary navigation

- [Research taxonomy](research/RESEARCH-TAXONOMY.md)
- [Research and development plan](PLAN.md)
- [Open questions and decisions](TODO.md)
- [Research index](research/README.md)
- [Candidate architecture decisions](draft/ARCHITECTURE-DECISIONS.md)
- [Draft glossary](draft/GLOSSARY.md)
