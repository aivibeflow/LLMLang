# Global Content-Addressed Semantic Artifact Store

**Status:** Proposed research direction  
**Scope:** Reusable implementations, contracts, interfaces, and bindings across LLMLang libraries, including POSIX and operating-system ABI wrappers. This document extends the library/package model but does not silently make the proposal normative.

## 1. Motivation

A LLMLang library that wraps an external API must describe the externally visible interface and its contract. The behavior of a wrapper can depend on the target environment and on the version of the wrapped system:

- libc version and implementation;
- operating-system and kernel version;
- architecture and syscall ABI;
- calling convention and data layout;
- feature flags, configuration, and relevant runtime capabilities.

Consequently, different library variants may need distinct contracts or implementations even when most of their functions remain unchanged.

Copying every function into every library version would create unnecessary duplication. The proposed solution is to separate library manifests and interface bindings from globally reusable, immutable semantic artifacts.

## 2. Core Proposal

A library is primarily a versioned collection of externally visible interfaces and bindings. Each binding associates an interface and contract with a selected implementation.

Implementations and other reusable semantic artifacts live in a shared content-addressed store. Any library may reference an artifact by its content identity. If two libraries use exactly the same artifact, they reference the same stored object rather than storing duplicate copies.

The logical model is:

`Library = Manifest(Interfaces, Bindings, TargetProfile, Dependencies)`

`Binding = (InterfaceRef, ContractRef, ImplementationRef, CompatibilityEvidence)`

The library's own identity commits to its manifest and the exact referenced artifact identities. The implementation objects are not owned by the library.

This model allows two library versions to differ in one wrapper while reusing all unchanged wrappers and lower-level components.

## 3. Separate Semantic Entities

At minimum, distinguish the following entities.

### 3.1 Interface

Describes the externally visible callable surface:

- operation name and stable identity;
- parameter and result types;
- calling convention and ABI-level representation where relevant;
- error/result representation;
- visibility and capability requirements.

An interface is not merely a function name or source-level signature. ABI-relevant details must be explicit when they affect callers.

### 3.2 Contract

Describes externally observable semantics:

- preconditions and postconditions;
- errors and failure behavior;
- state transitions and invariants;
- memory, ownership, and lifetime guarantees;
- concurrency and synchronization guarantees;
- observable effects;
- environmental assumptions and version constraints.

A contract must be specific enough to distinguish behavior that matters to consumers. For example, interruption behavior, partial reads/writes, error translation, and restart behavior may be contractually significant for a POSIX wrapper.

### 3.3 Implementation

Describes the implementation of an operation, including its typed body and references to semantic dependencies. An implementation is immutable once published. A semantic change creates a new content identity.

### 3.4 Binding

Connects an interface and contract to an implementation for a particular library variant and target profile. It may also reference compatibility evidence, tests, proofs, and explicit assumptions.

A binding is not proof by itself. It is a declaration whose compatibility status must be established by appropriate evidence or remain explicitly unknown.

### 3.5 Target Profile

Captures the environment dimensions that can affect semantics or ABI compatibility, such as:

- operating system and supported version range;
- libc family and version range;
- kernel family/version constraints;
- architecture and syscall ABI;
- data model, calling convention, and feature configuration.

Only dimensions that are relevant to a particular artifact need to be included in its semantic dependency context. Descriptive metadata that cannot affect behavior should not perturb semantic identity.

### 3.6 Operation Identity and Call Address

A call must explicitly identify the exact semantic version of the operation it intends to invoke. It must not identify only a logical operation and leave the semantic version to be selected implicitly by the runtime or implementation resolver.

Distinguish three identities:

- **Operation Stable ID** — the durable identity of a logical operation across its evolution. It supports history, navigation, and discovery of related versions. It is not, by itself, a call target.
- **Operation Hash (OpHash)** — the immutable content address of one exact semantic operation definition. It commits to the operation's externally relevant interface and contract, plus any semantic context that changes the meaning of the operation. A change to that meaning produces a different OpHash.
- **Implementation Hash** — the immutable content address of one concrete implementation artifact. Multiple implementations may be candidates for the same OpHash only when their compatibility with that exact operation contract is established.

The call site records the OpHash explicitly. Therefore, the meaning of a call does not drift when a library, registry, runtime, or implementation preference changes. A runtime may select among implementations bound to that OpHash, but it may not silently redirect the call to a different semantic operation version.

Searching for analogues by contract remains valuable and can be used to discover reuse and optimization opportunities. It is a separate process from call resolution:

1. Discover candidate operations or implementations with matching or potentially equivalent contracts.
2. Establish compatibility/equivalence using explicit evidence against the call site's exact OpHash and target constraints.
3. If a candidate implementation is accepted, bind it as an implementation of the requested OpHash, or create an explicit verified adapter where semantics differ.
4. Preserve the original OpHash at the call site; never rewrite its meaning as a side effect of optimization.

A similar-looking signature, equal implementation hash, or matching subset of contract clauses is not sufficient evidence. If semantic equivalence cannot be established, the candidate must not be substituted transparently.

Illustrative notation only:

`call OpHash("…")`

The canonical OpHash envelope and its relationship to Interface, Contract, and Target Profile remain to be specified. The key invariant is already clear: **call identity is explicit and semantically pinned; implementation discovery and optimization are separate.**

## 4. Global Content-Addressed Store

The shared store should be a content-addressed artifact store rather than a mutable database of named functions.

It may contain any reusable semantic artifact, including:

- function implementations and smaller implementation components;
- interfaces and contracts;
- types, layouts, and invariants;
- dependency-graph nodes;
- tests and test fixtures;
- formal models and proof artifacts;
- compiler/runtime support artifacts.

Functions are an important initial use case, not necessarily the only permissible unit of reuse.

Each immutable artifact is addressed by a cryptographic digest of a canonical representation. The representation must be deterministic and typed/domain-separated so that different artifact kinds cannot accidentally share an identity merely because their byte payloads happen to match.

Names, descriptions, source locations, authorship, timestamps, provenance, licensing, and signatures should generally be metadata associated with an artifact or its attestations, not silently mixed into semantic identity. If a metadata field affects execution or semantics, it is not merely descriptive metadata and must be represented in the semantic content or target context.

A digest establishes content identity under the chosen canonicalization and hash algorithm. It does **not** establish behavioral equivalence, correctness, safety, compatibility, or licensing rights.

## 5. Hashing and Dependency Closure

Hashing only the visible source text of a function is insufficient.

For example, the same-looking wrapper body can behave differently depending on:

- the value and meaning of a syscall number;
- architecture-specific argument placement;
- ABI register and stack conventions;
- type sizes, alignment, and structure layout;
- helper functions and error conversion;
- memory model and runtime semantics;
- compiler or LLMLang semantic version, where it changes interpretation.

The implementation identity must therefore commit to its canonical body and all semantically relevant inputs and dependencies.

A conceptual form is:

`ImplementationHash = H(domain, canonical_body, semantic_context, typed_dependency_refs)`

Dependency references should identify exact immutable artifacts. The implementation need not inline or copy all transitive dependency content: it can refer to child artifacts by their hashes. The resulting dependency graph makes reuse and impact analysis possible.

The project must define which edges are hash-relevant. A change to a relevant dependency creates a new identity for the dependent artifact; a change to non-semantic provenance metadata need not.

Avoid treating source-text equality as proof of implementation identity. Conversely, avoid claiming that two different hashes imply different behavior: they may be behaviorally equivalent, but that requires a separate equivalence argument.

## 6. Composition and Fine-Grained Reuse

Implementations should be composable from smaller artifacts when doing so creates useful, semantically meaningful reuse.

For example, a POSIX wrapper might depend on:

- a raw syscall boundary;
- architecture-specific syscall argument setup;
- return-value decoding;
- errno translation;
- buffer or pointer validation;
- shared helper operations.

Two libc wrapper variants may share most of these components and differ only in a particular helper or policy.

The store should not require every helper to become a separately addressable artifact. Excessive fragmentation creates indirection and management overhead. The granularity should be chosen where a component has a stable semantic boundary, meaningful reuse, independent testing, or independent verification value.

A composed implementation's identity must commit to the exact dependency identities and composition semantics. Replacing a child with another artifact must not leave the parent's identity unchanged when the replacement can affect behavior.

## 7. Library Manifests and Version Variants

A library manifest lists public interfaces and binds each one to the appropriate contract and implementation for a target profile.

Illustrative notation only; this is not a proposed canonical LLMLang syntax:

```yaml
library: POSIX-Linux-glibc
release: "2.39-wrapper-profile"

target:
  os: linux
  architecture: x86_64
  syscall_abi: linux-x86_64
  libc: glibc
  libc_version: "2.39"

interfaces:
  - name: read
    interface: H_INTERFACE_READ
    contract: H_CONTRACT_READ_239
    implementation: H_IMPL_READ_SHARED
    compatibility_evidence: H_EVIDENCE_READ_239

  - name: write
    interface: H_INTERFACE_WRITE
    contract: H_CONTRACT_WRITE
    implementation: H_IMPL_WRITE
```

A second manifest for another libc or kernel profile may reference the same implementation hashes for unchanged wrappers and different hashes only where required.

The manifest is the versioned composition and selection unit. Its human-readable release label is useful metadata, but exact reproducibility and dependency resolution must use immutable content identities and explicit target constraints rather than mutable labels.

The library should not duplicate unchanged function bodies merely because the library's overall release changes.

## 8. Versioning Is Per Artifact and Per Binding

A release of libc or a kernel does not imply that every wrapper's semantics changed. The model should therefore avoid forcing all functions to receive a new implementation identity whenever the enclosing library version changes.

Instead:

- a changed interface receives a new interface artifact identity;
- a changed contract receives a new contract artifact identity;
- a changed implementation or semantic dependency receives a new implementation identity;
- a changed target profile or binding receives a new binding/manifest identity as appropriate;
- unaffected artifacts retain their identities and can be reused.

This does not mean that version differences can be ignored. The target profile and contract must state the supported environment, and evidence must establish that a reused implementation is valid for that environment.

A kernel version change may leave a wrapper's implementation bytes unchanged while changing its assumptions or supported behavior. In that case the binding or contract may change even if the implementation artifact does not.

## 9. Compatibility and Verification Evidence

The fact that an implementation is referenced by multiple libraries does not prove that it satisfies all their contracts.

Each binding should carry or reference evidence appropriate to its claims, such as:

- contract-conformance proof;
- targeted tests and test results;
- differential tests against a reference libc/kernel;
- ABI conformance checks;
- formal model or refinement proof;
- assumptions and environmental constraints.

Evidence must be tied to exact input identities: interface, contract, implementation, dependencies, target profile, and relevant toolchain/prover versions.

A proof that implementation `I` satisfies contract `C1` does not automatically prove that `I` satisfies a different contract `C2`. Nor does a test result for one target profile automatically establish compatibility with another.

Use explicit evidence states such as PROVEN, TESTED, DECLARED, UNKNOWN, and NOT_CHECKED where appropriate. Do not collapse tests, declarations, and formal proofs into one generic “verified” status.

When a wrapper is reused across several library variants, each required binding must be justified against its own contract and target constraints. The evidence may itself be reusable if its exact assumptions and inputs match.

## 10. Provenance, Licensing, and Trust

Content addressing is an integrity and deduplication mechanism, not a trust policy.

The store should preserve discoverable metadata for:

- source origin and authorship;
- license and redistribution conditions;
- derivation or modification history;
- publisher identity and signatures;
- review and verification attestations.

The same content may be referenced by many libraries without implying that every library publisher owns it or that all consumers have the same rights to redistribute it.

The store should verify an artifact's bytes against its digest on retrieval. Signatures and attestations should endorse exact immutable artifact identities. Trust policy and license compatibility must be evaluated separately from hash equality.

## 11. Impact Analysis and Evolution

Because manifests and implementations form a typed dependency graph, tooling can answer:

- Which library variants use implementation hash `H`?
- Which bindings depend on a changed syscall helper?
- Which contracts have evidence for a given implementation?
- Which target profiles are affected by a changed ABI definition?
- Which proofs or tests must be repeated after a dependency changes?
- Can an implementation change be adopted without changing the public contract?

A new implementation should not silently replace an old one. It creates a new immutable artifact and a proposed binding/manifest update. Consumers can review the semantic diff, compatibility evidence, affected dependencies, and required re-verification.

This fits LLMLang's broader change-impact model: identify affected semantic dependencies, plan updates conservatively, and do not claim completeness when dependency discovery or evidence is incomplete.

## 12. Relationship to Existing Library and Package Model

This proposal specializes the library/package concepts:

- A package remains a distribution and dependency-resolution unit.
- A library manifest describes a named set of interfaces and bindings.
- Implementations and other semantic artifacts are independently addressable objects in a shared store.
- Packages and libraries reference artifacts; they do not own or duplicate them.
- Dependency locks resolve all required references to exact immutable hashes.
- Provenance, licensing, and signatures remain associated metadata/attestations.

The global store may be physically implemented by one service, multiple registries, local caches, or replicated stores. “Global” describes the logical shared identity namespace and deduplication model, not a requirement for one centralized server.

## 13. Suggested Initial Architecture

A practical initial design should:

1. Define canonical, typed artifact envelopes and domain-separated hashes.
2. Support immutable storage and retrieval by digest.
3. Represent function implementations with explicit typed semantic dependencies.
4. Define interface, contract, target-profile, and binding artifact schemas.
5. Define library manifests that bind interfaces to contracts and implementations.
6. Add reverse dependency queries for impact analysis.
7. Record tests, proofs, assumptions, provenance, and licenses against exact hashes.
8. Start with POSIX wrappers and Linux syscall ABI as motivating examples.
9. Validate deduplication and identity stability with fixtures covering unchanged and changed wrappers across two synthetic library versions.
10. Keep physical registry topology and advanced trust policy out of the first semantic model.

## 14. Open Design Questions

These questions require further research before the proposal becomes normative:

1. What exact canonical representation and hash algorithm should be used, and how will algorithm migration work?
2. Which artifact kinds are first-class in the initial SPG/store model?
3. What is the minimal semantic unit for reuse: function, expression, type, contract, or another typed node?
4. How are cyclic semantic dependencies represented without making recursive hashing ambiguous?
5. Which target-profile dimensions belong in an implementation identity, and which belong only in a binding?
6. How should version ranges and environment predicates be represented without undermining reproducibility?
7. Should one logical interface support multiple contracts for intentionally different environment semantics, or should such cases have distinct interface identities?
8. What evidence is required before a binding can be published as compatible?
9. How should evidence be reused when only non-semantic metadata or irrelevant dependencies change?
10. How should registry replication, garbage collection, signatures, provenance, and license policy work?

## 15. Conclusion

The proposed model replaces library-local implementation ownership with a graph of immutable, reusable semantic artifacts.

Libraries become versioned manifests of external interfaces and bindings. Contracts remain independently identifiable. Implementations are stored once by content identity and can be shared across libraries and versions. Fine-grained composition allows unchanged components to be reused, while explicit dependencies, target profiles, and compatibility evidence prevent hash reuse from being mistaken for semantic compatibility.

This can make POSIX and OS ABI support evolve per wrapper rather than by copying entire library versions, while preserving traceability, reproducibility, and LLMLang's independent-verification boundary.

The proposal is a research direction pending resolution of the open questions above.

## Public-interface integration (2026-11-24; proposed)

An exported public name resolves in an immutable scoped namespace/catalog revision to an exact OpHash (or an explicitly modeled interface group revision); provider selection is a second relation from that exact operation to an exact ImplHash. The provider owns its declared implementation Contract reference; the public Contract is resolved through the operation, not duplicated independently in the binding. The binding may commit to both exact identities as proof inputs. Separate external symbol/ABI mapping from both relations. Admit providers only after body-to-provider-contract and provider-to-public-contract checks, plus target and authority constraints. A stable name is not a mutable semantic object, and a public operation need not have a provider at design time. Distinguish behavioral refinement (sufficient for contract-based clients) from observational equivalence (needed for transparent behavior-preserving rewrites).

Related: [Public interfaces and verified contract refinement](../RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
