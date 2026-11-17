# LLMLang

**LLMLang** is an experimental concept for an AI-native programming language and development environment designed around large language models as primary program authors, with independent machine validation of their output.

> **Core principle:** Don't make the LLM remember the rules. Make the language and its tooling enforce them.

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

## Documents

- [LLMLang-CONCEPT.md](LLMLang-CONCEPT.md) — full concept, architecture, design principles, proposed toolchain, development stages, and open questions.
- [REPOSITORY-AUDIT-2026-11-17.md](REPOSITORY-AUDIT-2026-11-17.md) — repository-wide documentation consistency audit, fixes, and validation scope.
- [LLMLang-FORMAL-VERIFICATION.md](LLMLang-FORMAL-VERIFICATION.md) — architectural requirement for one canonical semantics and generated formal/executable representations.
- [POSIX-RUNTIME-ARCHITECTURE.md](POSIX-RUNTIME-ARCHITECTURE.md) — proposed standard POSIX library with portable and native Linux runtimes, one shared contract, conformance/differential testing, and progressive formal verification.
- [TRANSLATION-AND-TARGET-BACKENDS.md](TRANSLATION-AND-TARGET-BACKENDS.md) — translation pipeline, backend architecture, semantic portability, and target-language research.
- [LIBRARIES-AND-TEMPLATES.md](LIBRARIES-AND-TEMPLATES.md) — package/library dependencies, public contracts, templates, and reproducible reuse.
- [RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md](RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md) — research on transforming contextual business intent into traceable, reviewable formal contracts.
- [RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md](RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md) — research on a typed, provenance-carrying Requirement IR, finite-domain consistency checks, and scenario generation.
- [Prototype 16 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-16-RESULTS.md) — end-to-end experiment for caller-scoped business-rule evolution and contract acceptance.
- [Prototype 17 Results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-17-RESULTS.md) — typed Requirement IR experiment with provenance, contradiction/underdetermination checks, and finite scenarios.

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

- [Scenario 29 — Verified SMT Proof Checking and Encoder Validation](RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md) — Logos/Lean proof checking, exact assumption binding, QF_LIA semantic profile, and encoder proof obligations.
- [Prototype 29 results](PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-29-RESULTS.md) — current tool availability and implementation acceptance gate.


- [Scenario 30 — CPC Assumption Binding](RESEARCH-SCENARIO-30-CPC-ASSUMPTION-BINDING.md) — source-level audit of Logos's parser and soundness API; exact structural binding of the parsed CPC assumption list to the canonical LLMLang relational query; adversarial mismatch tests and the conservative MVP boundary.

- [Scenario 31 — Strict QF_LIA Relational Query Profile](RESEARCH-SCENARIO-31-STRICT-QF-LIA-PROFILE.md) — a separate conservative proof-eligible subset; rejects strings and nonlinear arithmetic, emits QF_LIA only, and removes the constant outcome string from the observation query.


- [Scenario 32 — Canonical Typed Relational Query IR](RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md) — immutable typed relational query representation, separate QF_LIA rendering, and pinned Logos-Term API audit.
- [Scenario 33 — CPC Parser State and Exact Symbol Binding](RESEARCH-SCENARIO-33-CPC-PARSER-STATE-BINDING.md) — preserving Logos parser state to recover exact UConst identities without writing a second CPC parser.
- [Prototype QF_LIA profile](PROTOTYPES/DEPENDENCY-GRAPH-01/src/qf_lia_profile.py) and [typed query IR](PROTOTYPES/DEPENDENCY-GRAPH-01/src/qf_lia_ir.py) — strict relational query builder and typed SMT-LIB renderer.
- [QF_LIA focused tests](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_qf_lia_profile.py) — accepted/rejected constructs, canonical IR, and renderer checks.


- [Lean CPC parser-state binding prototype](PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/) — pinned Lean/Lake package retaining the Logos CPC parser's final declaration state and binding expected Bool/Int declarations to exact UConst nodes; not yet compiled.
