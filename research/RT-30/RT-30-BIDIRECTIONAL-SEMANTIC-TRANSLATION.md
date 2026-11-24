# RT-30: Bidirectional semantic translation between LLMLang and C, C++, Go, and Rust

**Date:** 2026-11-23  
**Status:** Proposed research brief; no translation architecture, target priority, or runtime design is selected  
**Scope:** Research automated translation in both directions between LLMLang and C, C++, Go, and Rust, with preservation of the source program's defined and observable semantics.

## 1. Research objective

Determine how LLMLang can serve as both:

1. a source language translated into C, C++, Go, and Rust; and
2. a semantic interchange language into which supported programs written in those languages can be imported and from which equivalent target programs can be generated.

The intended capability is automated, bidirectional translation, not merely FFI bindings or one-way code generation. The study must distinguish semantic equivalence from textual/source-level round-tripping and must report unsupported or unverified cases rather than silently changing behavior.

LLMLang remains the semantic source of truth for LLMLang programs. A source frontend must preserve the source language's defined behavior when representing an imported program; it must not pretend that source-language semantics are LLMLang semantics when they differ.

## 2. Directions and translation contracts

### 2.1 LLMLang to target languages

Evaluate source-to-target translation for each of C, C++, Go, and Rust.

For every target, investigate:
- lowering from typed SPG and/or a normalized target-independent semantic IR;
- mapping of LLMLang values, types, object layout, inheritance, interfaces, generics, effects, errors, ownership, lifetimes, concurrency, and initialization/destruction;
- generated source structure, names, modules, build metadata, diagnostics, and reproducibility;
- target-specific runtime and library support;
- ABI, calling conventions, allocation, exception/panic boundaries, threading, atomics, and platform constraints;
- optimization and incremental regeneration while preserving semantics.

### 2.2 Target languages to LLMLang

Evaluate source frontends and semantic import for C, C++, Go, and Rust.

For each language, investigate:
- parsing and preprocessing/macro expansion boundaries;
- name/type resolution, overload and generic resolution, trait/interface satisfaction, templates, specialization, and method dispatch;
- control/data flow, aliasing, object layout, ownership/lifetime, effects, concurrency, and foreign calls;
- source constructs that are not directly expressible in the current LLMLang candidate model;
- faithful representation through LLMLang constructs, explicit low-level constructs, compatibility records, or runtime protocols;
- treatment of implementation-defined, unspecified, undefined, unsafe, or platform-specific behavior;
- source maps, provenance, diagnostics, and retention of source-level information needed for maintenance.

Do not silently replace C++ multiple inheritance, C pointer/provenance behavior, Rust ownership/borrowing, or Go interface/embedding and concurrency semantics with superficially similar LLMLang constructs.

### 2.3 Round-trip and mixed-language workflows

Investigate:
- LLMLang → target → LLMLang semantic round trips;
- target → LLMLang → same target semantic round trips;
- target A → LLMLang → target B migration;
- mixed projects in which translated and native modules coexist;
- preservation of stable identities, call bindings, ABI contracts, provenance, and incremental change boundaries;
- whether source formatting, comments, macro structure, and idiomatic source constructs can be retained as optional source-fidelity metadata without confusing them with semantic identity.

Semantic equivalence does not imply textual identity or reconstruction of the original source. State separately which round-trip properties are guaranteed.

## 3. Runtime and C backend hypothesis

A specific hypothesis to evaluate is that the C backend can realize high-level LLMLang constructs using a dedicated LLMLang runtime library.

The study must assess:
- which language capabilities can be lowered to ordinary C plus runtime calls/data structures;
- runtime components for object lifecycle, multiple inheritance/subobjects, dynamic dispatch, generics/specialization where applicable, ownership/resource management, exceptions or typed failures, concurrency, async, reflection/metadata, and contract/invariant checks;
- representation and ABI costs, allocation strategy, dispatch overhead, code size, startup cost, and portability;
- static versus dynamic runtime linkage, runtime versioning, deployment, and compatibility;
- what must be compile-time lowered versus what genuinely requires runtime support;
- whether the same runtime contracts can be implemented by C++, Go, and Rust backends or require target-specific adapters.

The runtime is an implementation mechanism, not the normative definition of LLMLang semantics. The C backend must not constrain the language to what C natively expresses.

## 4. Semantic equivalence and translation outcomes

Define explicit, testable preservation contracts. At minimum, distinguish:

1. **Exact semantic preservation under stated assumptions** — all declared observable behavior is preserved for the supported source fragment and target profile.
2. **Preservation through runtime support** — behavior is preserved using generated code plus a specified runtime/library contract.
3. **Restricted translation** — a declared subset is translated; unsupported constructs are rejected before producing a misleading artifact.
4. **Partial translation** — only a clearly identified subset is imported/exported, with machine-readable gaps and provenance.
5. **Unverified translation** — code is generated/imported but preservation has not been established; it must not be reported as equivalent.
6. **Impossible or intentionally unsupported** — preservation cannot be guaranteed under the stated assumptions or target constraints.

For every claim, define the observation model: return values, state, ordered effects, errors/failures, resource lifecycle, concurrency traces where applicable, ABI-visible behavior, and externally visible I/O. State assumptions about compiler versions, optimization, runtime, platform, and source-language standards.

Handle source-language undefined behavior carefully: do not promise preservation of behavior that the source standard does not define. Distinguish defined behavior from implementation-defined and unspecified behavior, and record the selected implementation profile.

## 5. Architecture alternatives to compare

Compare at least:
- a canonical LLMLang semantic IR with dedicated source frontends and target backends;
- direct frontend-to-backend pipelines through LLMLang semantic objects;
- a hybrid architecture with a stable semantic core and target-specific extension/compatibility representations.

For each, assess semantic completeness, implementation complexity, incremental compilation, diagnostics, source fidelity, identity stability, independent verification, plugin boundaries, and maintenance cost.

Do not assume that one universal IR can represent every detail of all four source languages without explicit extension points. Conversely, do not duplicate the entire semantic model independently in every translator if shared contracts can be established.

## 6. Required outputs

1. A source/target capability matrix for all 20 ordered language pairs, including LLMLang→each target and each source→LLMLang; identify same-language round trips and cross-target migration separately.
2. A language-by-language semantic gap register covering types, object model, memory/ownership, control/effects, errors, concurrency, ABI/FFI, macros/metaprogramming, and runtime.
3. A comparison of candidate IR and frontend/backend architectures.
4. A C runtime feasibility study with a component map, ABI contract, portability analysis, overhead measurements, and explicit limits.
5. A translation outcome and diagnostics contract, including machine-readable unsupported/unverified regions.
6. Shared executable conformance fixtures and differential tests for both directions, including negative controls and adversarial cases.
7. Reproducible prototypes, source fixtures, commands, pinned compiler/runtime versions, platform profiles, and result artifacts for executable claims.
8. A staged implementation/adoption plan identifying a small vertical slice, target ordering, dependencies, risks, and exit criteria.

## 7. Dependencies and existing evidence

Ground the study in:
- RT-03 for LLMLang source semantics and observable behavior;
- RT-04 for types, ownership, effects, capabilities, and resource protocols;
- RT-05/06 for SPG representation, identity, and dependencies;
- RT-07/08 for verification and evidence boundaries;
- RT-09/10 for compiler and runtime architecture;
- RT-13 for target backends, ABI, and interoperability;
- RT-18 for versioning and compatibility;
- RT-19/20/22/23/24 for Toolchain, change planning, repository/worktree, and semantic diff/merge;
- RT-28 for incremental polyglot migration and semantic mirroring;
- RT-29 for Rust language/compiler/runtime/ecosystem assessment.

Reuse existing scenarios and generated-code evidence where they cover the exact claim. Do not treat an existing Rust or C++ probe as evidence for general bidirectional translation.

## 8. Constraints and non-goals

- This study does not select C as the semantic foundation or require all backends to use the same runtime implementation.
- It does not assume that all source-language programs can be translated; unsupported and semantically unrepresentable cases must be explicit.
- It does not equate ABI compatibility, FFI interoperability, semantic translation, and source round-tripping.
- It does not require generated code to be idiomatic if a less idiomatic representation is necessary for faithful semantics; evaluate readability and maintainability as separate criteria.
- It does not move migration orchestration, Mirror Binding lifecycle, or repository management into the LLMLang language core.
- It does not make target compiler behavior normative for LLMLang.

## 9. Completion criteria

RT-30 is complete for its declared scope only when all ordered translation directions have an explicit capability/limitation assessment, the semantic observation model and translation outcomes are defined, the C runtime hypothesis has reproducible evidence, and at least one bounded bidirectional vertical slice is checked by differential tests against independent reference executions. Broad language support must not be inferred from a narrow passing fixture.

## RT-36 follow-up: explicit assumptions (proposed)

Translation may preserve a conditional theorem only with exact source and target correspondence, retained premises and compatible observation profiles; do not treat generated foreign bindings as implementation proof. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](../RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
