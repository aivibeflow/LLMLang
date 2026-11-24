# RT-29: Rust as a foundation and reference for LLMLang capabilities

**Date:** 2026-11-23  
**Status:** Proposed research brief; no language, compiler, runtime, or tooling architecture is selected  
**Scope:** Determine which Rust language capabilities, semantic mechanisms, implementation techniques, and ecosystem components are useful foundations or reference points for LLMLang, and which should not be transferred.

## 1. Research objective

Evaluate Rust systematically as a potential foundation for LLMLang capabilities. Distinguish three meanings of “foundation”:

1. **Semantic and language-design reference:** Rust as prior art for language features and observable guarantees.
2. **Implementation foundation:** Rust as an implementation language and source of reusable compiler/runtime/toolchain techniques or libraries.
3. **Ecosystem and interoperability foundation:** Cargo, crates, build tooling, diagnostics, FFI, target support, and integration patterns as possible infrastructure.

Do not assume LLMLang should reproduce Rust, inherit Rust semantics, or expose Rust implementation details. LLMLang's semantic source of truth remains its own specification. Rust is a candidate reference and implementation substrate whose suitability must be demonstrated per capability.

## 2. Research questions

### 2.1 Language and semantic capabilities

Compare Rust's model and practical guarantees with LLMLang's intended requirements for:
- ownership, moves, borrowing, lifetimes, aliasing, and interior mutability;
- RAII, deterministic destruction, partial initialization, field/base destruction order, and cleanup during failure;
- type systems, nominal and structural types, traits, generics, explicit specialization/coherence, and compile-time constraints;
- enums, pattern matching, exhaustiveness, and evolution of public variants;
- errors (Result and ?), panics, unwinding/abort, cleanup failure, and error composition;
- concurrency, Send/Sync, atomics, memory ordering, data-race prevention, and structured task lifetimes;
- async/await, cancellation, task scheduling, and resource cleanup;
- modules, visibility, packages, macros, compile-time evaluation, and diagnostics;
- FFI, ABI boundaries, unsafe code, and interoperability with C/C++ and other target languages.

For every area, identify Rust's actual guarantee, the mechanism enforcing it, its limitations and escape hatches, and the observable behavior LLMLang would need to specify independently.

### 2.2 Compiler, runtime, and toolchain implementation

Evaluate Rust as an implementation language and inspect relevant Rust ecosystem components for:
- compiler frontends, parsing, typed IR, optimization and code generation;
- LLVM integration and source-to-backend semantic preservation;
- memory allocation, resource management, concurrency, async runtime, and platform abstraction;
- serialization, content-addressed storage, hashing, graph processing, incremental computation, and caching;
- diagnostics, source maps, language-server/editor integration, and test infrastructure;
- package/build systems, reproducibility, cross-compilation, plugin/extension boundaries, and supply-chain security.

Separate language guarantees from library/runtime conventions and implementation details. Assess API maturity, maintenance, portability, licensing, security posture, performance, and integration cost before recommending reuse.

### 2.3 Capability mapping and architecture fit

Produce a capability matrix mapping each LLMLang capability to:
- Rust analogue or relevant Rust ecosystem component;
- layer: language semantics, compiler, Toolchain, runtime/library, or external service;
- degree of fit: direct reuse, adaptation, independent implementation, or unsuitable;
- semantic mismatches and required compatibility adapters;
- evidence level, dependencies, risks, and open questions.

Explicitly classify which capabilities belong in LLMLang's language core and which belong in compiler/Toolchain, runtime/library, or external services. Do not move repository management, SPG storage, semantic mirroring, or migration orchestration into the language merely because Rust crates can implement them.

### 2.4 Comparative and executable validation

Use focused, reproducible probes where documentation comparison is insufficient. Prefer shared workloads and semantic fixtures already used by LLMLang (including ownership/cleanup, generated Rust, async cancellation, atomics, allocator and backend-preservation cases). Compare the LLMLang reference model with Rust behavior only for the exact supported fragment and pinned compiler/toolchain versions.

Include negative controls for invalid transfers, such as assuming Rust Drop can report ordinary cleanup errors, assuming borrow checking solves all runtime resource protocols, assuming Send/Sync imply application-level correctness, or assuming Rust's package/build model is an appropriate semantic model for LLMLang.

## 3. Required outputs

1. A capability-to-Rust mapping matrix covering language, compiler, Toolchain, runtime, and ecosystem layers.
2. A comparison of at least two coherent adoption vectors where evidence supports alternatives (for example, Rust-like ownership/borrowing versus LLMLang-specific ownership contracts; reuse of Rust components versus independent components).
3. A compatibility and non-transferability register identifying where Rust behavior conflicts with existing LLMLang candidate semantics or requirements.
4. A dependency update linking the study to affected research areas.
5. A staged adoption recommendation distinguishing proven reusable components, candidates requiring prototypes, and capabilities that must remain LLMLang-defined.
6. Reproducible source fixtures, commands, pinned versions, and results for any executable claims.

## 4. Constraints and non-goals

- This study does not select Rust as the LLMLang implementation language, nor authorize wholesale reuse of Rust semantics.
- It does not make Rust's borrow checker, trait system, macro system, Cargo, or LLVM lowering normative for LLMLang.
- It does not treat Rust compiler behavior as a substitute for an independently defined LLMLang semantic model.
- It does not revise accepted LLMLang decisions or existing candidate contracts; conflicts must be recorded for explicit resolution.
- It does not assume Rust is the only relevant comparator. Use other languages or systems when they expose a meaningful alternative or limitation.

## 5. Initial dependencies

Ground the study in RT-03 (semantics), RT-04 (types/ownership/effects/capabilities), RT-09 (compiler), RT-10 (runtime), RT-13 (backends/interoperability), RT-18 (evolution/compatibility), and RT-25 (allocator compatibility). Consume existing Rust-focused scenarios and generated-Rust evidence rather than duplicating them. The new work is the integrated capability map and explicit decision about where Rust is a sound foundation, only a reference, or unsuitable.

## 6. Completion criteria

RT-29 is complete only when the capability matrix covers all major LLMLang capability areas, every recommendation is traceable to evidence and assumptions, incompatible transfers are explicit, and the proposed adoption sequence is checked against the cross-aspect dependency map. A survey or a successful generated-Rust fixture alone is not sufficient.

## RT-36 follow-up: explicit assumptions (proposed)

Rust libraries and unsafe/FFI components require exact provider identity, explicit contract assumptions and scoped proof/authorization status; Rust type checking alone is not behavioral conformance evidence. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
