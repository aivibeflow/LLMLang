# LLMLang: Translation and Target-Language Backends

**Status:** Research proposal; not a normative LLMLang decision  
**Date:** 2026-11-16  
**Scope:** Translating LLMLang programs into other programming languages

> This document records a proposed direction for cross-language translation. It extends the existing Semantic Program Graph (SPG) concept but does not settle the final IR, compiler architecture, or supported target languages.

## 1. Goal

LLMLang should be able to serve as a semantic source language from which implementations for multiple conventional programming languages can be generated.

A single LLMLang program should potentially produce implementations in Rust, Go, C++, Python, and other targets without manually re-expressing its business rules for each language.

The goal is not merely to translate LLMLang syntax into superficially similar syntax in another language. The generated target program must preserve the declared semantics of the source program to the extent that the target platform can represent them.

Translation is therefore a compiler and verification problem, not a text-to-text rewriting task.

## 2. Separate semantic intent from target implementation

The architecture should distinguish at least these concepts:

| Concept | Meaning |
|---|---|
| Semantic value | The exact immutable semantic definition of a program entity: what it means and what behavior it requires |
| Semantic Program Graph (SPG) | The typed graph connecting semantic values, requirements, contracts, types, effects, and dependencies |
| Target implementation | A realization of a semantic value for a particular target language, runtime, and platform |
| Code artifact | The generated source files and associated build inputs |
| Build artifact | The compiled or packaged output produced from code artifacts |
| Verification evidence | Results establishing which properties of a target implementation have been checked, under which assumptions and toolchain |

One semantic value may have multiple target implementations:

```text
SemanticValue H_sem
    ├── Rust implementation H_rust
    ├── Go implementation H_go
    ├── C++ implementation H_cpp
    └── Python implementation H_python
```

The target implementations may have different implementation hashes and different source artifacts while referring to the same semantic value.

A change to business rules creates a new semantic value. It does not silently rewrite the old target implementations: each target implementation must be regenerated, adapted, or explicitly retained as an implementation of the previous semantic value.

## 3. Translation pipeline

A proposed translation pipeline:

```text
LLMLang source / structured mutations
              |
              v
      Semantic Program Graph
              |
              v
   Semantic analysis and normalization
              |
              v
     Target capability analysis
              |
              v
       Target-specific lowering
              |
              v
       Target code generation
              |
              v
      Build / compile / package
              |
              v
       Independent verification
              |
              v
   Target implementation + evidence
```

### 3.1 Parse and construct the semantic graph

The source representation is parsed or updated as structured graph mutations. The resulting SPG, rather than the original text, is the input to translation.

The translator must not infer missing business rules from naming, comments, or incidental source formatting. Any ambiguity that affects behavior must be represented as an unresolved issue and handled before claiming a semantics-preserving translation.

### 3.2 Normalize semantic constructs

Before lowering, the compiler may normalize equivalent surface forms into canonical semantic constructs. Normalization must preserve semantics and be deterministic for a given language and semantic-version definition.

Normalization should make implicit behavior explicit where needed, including:
- evaluation order;
- integer overflow and numeric conversion behavior;
- nullability and option values;
- error propagation;
- resource lifetime and ownership;
- concurrency and memory-ordering constraints;
- observable effects;
- exception and cancellation behavior.

The exact normalization rules remain to be specified.

### 3.3 Analyze target capabilities

For a requested target, the compiler determines whether each required semantic construct is:
- directly supported;
- implementable through a runtime or compatibility layer;
- implementable with a documented restriction;
- not representable while preserving the required semantics.

This analysis must happen before code generation is treated as successful. A backend must not silently weaken a contract to make code compile.

### 3.4 Lower and generate

Target-specific lowering converts normalized semantic constructs into constructs available in the target language and its runtime.

The backend generates code and any required support files. Generated code should be deterministic for fixed inputs and a fixed generator/toolchain identity, unless an explicitly documented nondeterministic step is required.

### 3.5 Build and verify

Compilation success is necessary but not sufficient. The generated implementation must be checked against the source semantic value and its applicable requirements.

The translator must report verification status precisely; it must not equate successful code generation or compilation with semantic equivalence.

## 4. Intermediate representation and backend architecture

A possible direction is to use the SPG as the semantic source of truth and define one normalized, target-independent semantic IR for the constructs that require lowering.

This is a proposal, not a settled design. It should be evaluated against the alternative of translating directly from typed SPG nodes into target-specific forms.

If a normalized IR is introduced, it should:
- preserve links to originating SPG semantic values and requirements;
- make evaluation order and observable effects explicit;
- represent control flow, data flow, types, errors, ownership, and concurrency constraints;
- avoid embedding target-language syntax in the semantic layer;
- allow target-specific extensions without making the common semantic core ambiguous;
- have a canonical, versioned representation suitable for hashing and caching.

A backend should be a replaceable target-specific component. It consumes the relevant semantic graph/IR and emits a target implementation plus machine-readable diagnostics and metadata.

Potential backend layers:

1. **Common semantic analysis:** checks language-level validity and computes normalized semantics.
2. **Target capability model:** declares supported constructs, limitations, and runtime requirements.
3. **Target lowering:** maps semantic constructs to target-level operations.
4. **Code generator:** emits target-language source.
5. **Runtime/support package:** implements semantics that the target language does not provide directly.
6. **Target verifier adapters:** invoke compilers, analyzers, test runners, and other verification tools.

The compiler architecture should not require separate, unrelated semantic definitions for each target language.

## 5. Runtime and compatibility support

Some LLMLang semantics may not map directly to a target language. A runtime support library may provide the missing behavior.

Examples include:
- checked arithmetic where the target's default arithmetic differs;
- explicit result/error types where the target idiom differs;
- deterministic resource cleanup;
- capability checks;
- runtime contract checks;
- structured cancellation;
- concurrency primitives with defined memory semantics;
- compatibility wrappers for platform-specific behavior.

A runtime library is part of the target implementation's semantic realization. Its exact version and relevant configuration must therefore be included in implementation identity and verification inputs.

The backend must distinguish between:
- semantics implemented natively by the target;
- semantics supplied by the LLMLang runtime;
- semantics approximated under an explicit restriction;
- semantics that cannot be preserved on that target.

## 6. Semantic portability and translation outcomes

A useful proposed concept is **Semantic Portability**: the degree to which a semantic value can be realized on a target while preserving its declared behavior and guarantees.

The compiler should produce an explicit translation outcome, rather than a binary success/failure that hides important qualifications.

Suggested outcome categories:

| Outcome | Meaning |
|---|---|
| Exact under stated assumptions | All declared relevant semantics are represented; the assumptions and verification scope are explicit |
| Preserved with runtime support | Semantics are preserved using a specified LLMLang runtime or compatibility layer |
| Restricted | Translation is possible only after an explicit, accepted restriction of the source requirements |
| Unsupported | At least one required semantic construct cannot be represented on this target |
| Unverified | Code was generated, but the required verification has not established preservation |

These categories are proposed terminology. Their formal definitions and whether they should be represented as an ordered portability scale remain open.

A restriction must never be introduced silently. If a target cannot preserve a requirement, the compiler should identify the affected requirement and explain the limitation. A human or an authorized policy must explicitly approve any change to the required semantics.

## 7. Verification strategy

Verification should be independent of the code generator wherever practical.

Possible checks include:

- target compiler and linker diagnostics;
- static analysis and type checking;
- contract and invariant checks;
- generated unit and scenario tests derived from source requirements;
- property-based testing;
- differential testing against a trusted LLMLang interpreter or reference implementation;
- fuzzing and boundary-value testing;
- memory-safety and concurrency analysis;
- formal proofs for properties with tractable formal models.

Differential testing can execute the same input scenarios against a source-level reference semantics and the generated target implementation, then compare observable results. It is valuable evidence but does not prove equivalence for all possible inputs unless combined with stronger methods and assumptions.

Verification evidence must state:
- the semantic value and dependency closure it applies to;
- the target implementation hash;
- target language and language version;
- compiler, runtime, verifier, and relevant configuration identities;
- the properties and requirements checked;
- assumptions, exclusions, and limitations;
- result and timestamp.

Evidence becomes stale when any input on which it depends changes. Reuse is safe only when the cache key commits to all relevant semantic, target, runtime, toolchain, policy, and verifier inputs.

## 8. Hashes, identity, and reproducibility

The proposed identity separation is:

| Object | Hash should identify |
|---|---|
| Semantic value | Canonical source semantics and hash-relevant semantic dependencies |
| Normalized IR value | Canonical normalized representation, if a distinct IR is adopted |
| Target implementation | Target-specific realization, including relevant lowering choices and runtime dependencies |
| Code artifact | Exact generated source/build-input content |
| Build artifact | Exact build output and relevant build provenance/inputs, according to a defined artifact model |
| Verification evidence | A result bound to the exact subject and verification inputs |

The exact hash boundaries need further design. In particular, the project must decide whether generator identity belongs directly in the target implementation hash, in a separate generation record, or in both. Regardless of that choice, reproducibility and cache validation require recording the generator version and configuration.

A semantic change must change the semantic value hash. A generator change need not change the semantic value hash, but it may produce a different target implementation or code artifact and must invalidate any verification evidence whose inputs include the generator.

Generated artifacts should be reproducible for fixed semantic input, target configuration, backend version, runtime version, and toolchain, to the extent that the target toolchain permits reproducible output.

## 9. Incremental translation

Content-addressed semantic nodes and explicit dependencies can support incremental generation.

If one semantic node changes:
1. identify the target implementation nodes that depend on it through hash-relevant translation dependencies;
2. invalidate only affected lowering and generation results;
3. reuse unchanged generated components where their dependency keys remain valid;
4. rebuild affected artifacts;
5. rerun only verification whose inputs changed, while retaining valid evidence for unaffected nodes.

The invalidation graph must distinguish semantic dependencies from non-semantic relations such as provenance, authorship, and traceability. Such metadata should not cause semantic values to be rehashed unless it is explicitly part of program behavior.

The dependency-driven prototype demonstrates selective version selection for caller values, but it does not yet implement translation dependency graphs or incremental multi-target generation.

## 10. Source-language and target-language boundaries

The translator should not assume every LLMLang construct has a direct equivalent in every target language.

Examples of difficult mappings include:
- ownership and borrowing in languages with different memory models;
- algebraic data types in languages without native sum types;
- refinement types and dependent constraints;
- effect systems;
- deterministic concurrency semantics;
- capability-based security;
- transactional state changes;
- explicit error and cancellation semantics;
- cyclic or recursive type definitions.

Each backend must define its mapping strategy and limitations. A construct may be represented by generated wrappers, runtime checks, a restricted encoding, or may be rejected for a particular target.

The source semantics remain authoritative. Target-language idioms are implementation choices and must not redefine source behavior.

## 11. Suggested development sequence

The following sequence is a research plan, not a commitment to implement every item immediately.

1. **Choose a small semantic subset.** Include pure functions, primitive and algebraic types, explicit errors, and simple contracts.
2. **Define reference semantics.** Provide an executable interpreter or another trusted way to evaluate the selected subset.
3. **Specify one target backend.** Start with one target (for example, Python or Go) and document every mapping and limitation.
4. **Build differential tests.** Generate source-level scenarios and compare target behavior with the reference semantics.
5. **Add a second backend.** Use it to test whether the semantic layer is genuinely target-independent rather than shaped around the first target.
6. **Introduce runtime support selectively.** Add only when a semantic construct cannot be represented directly and the compatibility behavior can be specified and tested.
7. **Add incremental generation.** Reuse hashes and dependency analysis to avoid regenerating unaffected target components.
8. **Expand the semantic subset.** Add ownership, effects, state machines, and concurrency only with explicit mapping and verification strategies.

## 12. Open questions

1. Should the backend consume SPG directly, or should LLMLang define a separate normalized semantic IR?
2. Which semantic constructs belong in the common core, and which should be language extensions?
3. What is the formal definition of a semantics-preserving translation for LLMLang?
4. Which observable behaviors must be compared: return values, errors, state changes, I/O, timing constraints, resource behavior, or all declared effects?
5. How should target-specific restrictions be represented, reviewed, and approved?
6. Should runtime support be a single standard library, versioned per target, or composed from independently hashed semantic modules?
7. How should generator identity, compiler identity, and build configuration contribute to implementation and artifact hashes?
8. What verification evidence is sufficient to label a translation exact under stated assumptions?
9. How should platform-dependent behavior and nondeterministic operations be modeled?
10. Which target language should be implemented first, and what representative subset gives the strongest test of the architecture?

## 13. Relationship to existing LLMLang concepts

This proposal builds on, but does not replace, the existing concepts:

- **SPG:** remains the proposed structured semantic model of the program.
- **Specification, Design, and Implementation Graphs:** remain distinct logical layers; target implementations belong to the implementation side and must trace back to the semantics they realize.
- **Content addressing:** can identify immutable semantic values and target-specific realizations independently.
- **Dependency-aware change analysis:** can support selective regeneration and verification invalidation.
- **Provenance separation:** generation history and verification records should remain distinct from semantic identity unless deliberately made semantic.

No claim is made here that the current prototype implements a compiler, a normalized IR, a target backend, or semantic equivalence checking.

## 14. Guiding principle

**One semantic definition; multiple target-specific realizations; independently checked preservation of behavior.**

LLMLang should make it possible to generate implementations in conventional languages without making those languages the source of truth for business semantics. When preservation cannot be established, the toolchain must expose the exact limitation rather than silently generating code with weaker behavior.

## 15. Initial target-language selection

This section records a preliminary engineering recommendation for choosing the first target backend. It does **not** establish a binding decision about the first officially supported LLMLang target.

### 15.1 Recommendation

Use a staged approach rather than trying to select one language for every purpose:

1. **Python — first experimental backend and executable reference target.**
   Python is a practical first target for validating the translation pipeline because code generation is comparatively simple, the language has a small syntactic surface, and generated programs are easy to execute in differential tests. It can help validate the semantic subset, diagnostics, test generation, and the end-to-end backend interface with relatively little target-specific machinery.
2. **Go — first serious compiled backend.**
   Go is the recommended second target, and the first target for testing a statically typed compiled implementation. It offers a comparatively straightforward compiler and build workflow, static typing, and a practical deployment model, without requiring the backend to solve the full complexity of Rust's ownership and lifetime system or C++'s broader language and ABI surface.
3. **Rust — subsequent backend for stronger systems-language coverage.**
   Rust should be added after the common semantics and backend contract have been exercised by Python and Go. Its ownership, borrowing, and lifetime rules make it a valuable but more demanding target.
4. **C++ — later backend.**
   C++ should follow once the type, memory, runtime, and target-compatibility models are more mature. Its language complexity, templates, object model, memory model, and ABI concerns make it a costly first backend.

Java is a plausible alternative compiled target: records and sealed classes can represent some algebraic data type patterns, but its generated code and runtime model would need separate evaluation. It is not currently preferred over Go for the initial compiled backend.

### 15.2 Why Python should not define LLMLang semantics

Python is recommended as an early implementation target for experimentation, not as the language whose limitations shape LLMLang.

LLMLang's semantic core must remain independent of Python's dynamic typing and runtime behavior. Static type guarantees, ownership constraints, effects, overflow rules, concurrency guarantees, and other source-level properties must remain explicit in LLMLang even when Python cannot enforce them statically.

Where Python cannot preserve a required property directly, the backend must use an explicitly specified runtime mechanism, report a restriction, or reject the translation. It must not silently weaken the source contract merely to produce executable Python.

### 15.3 Comparative first-backend assessment

The following is a qualitative engineering assessment for the initial LLMLang subset, not a universal ranking of language difficulty.

| Target | Relative initial backend effort | Main advantage | Main challenge | Proposed role |
|---|---|---|---|---|
| Python | Low | Simple code generation and fast execution of generated scenarios | Dynamic typing and runtime-only enforcement for some guarantees | First experimental backend |
| Go | Low–medium | Static typing and relatively simple compiled toolchain | Mapping algebraic data types, effects, and richer type constraints | First serious compiled backend |
| Java | Low–medium | Mature compiler ecosystem; records and sealed classes | More verbose encodings and JVM-specific runtime assumptions | Alternative compiled backend |
| Rust | Medium–high | Strong type system and memory-safety model | Ownership, borrowing, lifetimes, and trait resolution | Later systems backend |
| C++ | High | Broad systems and platform coverage | Language complexity, templates, object/memory model, and ABI | Later backend |

The ranking may change depending on the semantic subset. For example, a subset requiring strict ownership guarantees may make Rust a more informative early target, while a subset centered on rapid executable differential testing favors Python.

### 15.4 Cross-backend validation milestone

After the first Python backend works, implement the same small semantic subset in Go. Both generated implementations should be checked against the same LLMLang reference semantics and the same generated scenario corpus.

At minimum, compare all declared observable outcomes for each scenario, including:
- returned values;
- declared errors and error categories;
- state changes;
- declared external effects, where the test environment can observe them.

The purpose is not merely to show that both backends compile. It is to test whether the semantic model is genuinely target-independent and whether both backends preserve the same source-level behavior.

A mismatch between Python, Go, and the reference semantics should be treated as a semantic or backend defect to investigate, not resolved by choosing one target's behavior as authoritative.

### 15.5 Decision status and remaining questions

**Current status: recommendation only; no target language has been formally selected or declared mandatory.**

Before treating this sequence as an implementation commitment, the project should:
- define the minimal semantic subset used for the first backend;
- define the reference semantics and the observable behavior compared by differential tests;
- establish the backend capability-reporting contract;
- decide whether Python's role is limited to an experimental backend or whether it should also serve as a maintained reference implementation;
- confirm that Go is the preferred first compiled target after evaluating the chosen subset.

This recommendation refines open question 10 in Section 12; it does not close that question.

## RT-36 follow-up: explicit assumptions (proposed)

Foreign and target translation correspondence assumptions must be explicit and scoped to exact target/ABI/artifact; a successful build or proof of a model alone does not discharge them. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
