# LLMLang — Open Questions and Decisions

This file is the project-wide register of unresolved design questions and decisions that require discussion.

It is not a specification. Items here may contain hypotheses and recommendations; only decisions explicitly accepted and transferred into the appropriate project documents become part of the design baseline.

## How to use this register

Each item has a stable ID. Keep the ID when the wording or status changes.

Statuses:

- **Open** — not yet discussed enough to make a decision.
- **Discussion** — actively being explored; alternatives or evidence are being developed.
- **Decision needed** — the alternatives and consequences are sufficiently understood, but an explicit project decision is required.
- **Resolved** — the decision was made and recorded in a durable project document.

For each item, record the question, why it matters, possible directions where known, a recommendation where useful, and links to relevant research. Do not mark an item Resolved merely because a recommendation exists. When resolving an item, record the decision and link to the document/commit that captures it. Remove obsolete duplicates only after preserving any useful history in the relevant document.

Priority is a planning aid, not a measure of correctness:

- **P0** — blocks foundational identity, semantics, or architecture decisions.
- **P1** — important for the first coherent design/prototype.
- **P2** — can be deferred without invalidating the initial design.

---

## Operation identity and calls

### LL-001 — Define the canonical OpHash envelope

- **Status:** Open
- **Priority:** P0
- **Question:** What exact canonical semantic data is committed by an Operation Hash (OpHash)?
- **Context:** We have agreed on the principle that a call explicitly names an immutable semantic operation version. OpHash must identify the exact operation semantics, not merely a logical function name or a replaceable implementation.
- **Options to investigate:**
  - Hash the canonical interface and contract together.
  - Include selected semantic context (for example, effects, capability requirements, ABI/calling convention, or target constraints) only when it changes the operation's meaning.
  - Define a dedicated Operation Definition artifact that references these components by typed hashes.
- **Recommendation:** Prefer a dedicated, typed operation-definition envelope with explicit references to interface and contract artifacts, plus only those additional fields that affect call semantics. Avoid duplicating their full content in multiple places.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 3.6.

### LL-002 — Define Operation Stable ID lifecycle

- **Status:** Open
- **Priority:** P1
- **Question:** How is an Operation Stable ID created, preserved, split, merged, deprecated, or replaced as an operation evolves?
- **Context:** Stable ID identifies the logical lineage; OpHash identifies one immutable semantic version and is the call target. These roles must not collapse into one identifier.
- **Options to investigate:** Explicit author-assigned IDs; tool-generated IDs with explicit lineage operations; rules for split/merge and unrelated operations with equivalent contracts.
- **Recommendation:** Keep lineage changes explicit and auditable; never infer identity solely from names or contract similarity.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 3.6.

### LL-003 — Specify contract-based analogue discovery and substitution

- **Status:** Open
- **Priority:** P1
- **Question:** How does tooling discover operations with equivalent or compatible contracts, and what evidence is required before an implementation can serve a call addressed by a particular OpHash?
- **Context:** Analogue discovery is an optimization/reuse mechanism, not call identity resolution. A candidate must not silently change the meaning of a call.
- **Options to investigate:** Exact contract-hash match; structural contract comparison; proof of refinement/equivalence; explicit verified adapters for non-identical contracts.
- **Recommendation:** Separate candidate discovery from acceptance. Require evidence against the exact OpHash and target constraints; otherwise do not substitute transparently.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), sections 3.6 and 9.

---

## Semantic identity and artifact store

### LL-004 — Choose canonical encoding and hash algorithm policy

- **Status:** Open
- **Priority:** P0
- **Question:** What canonical serialization, domain separation, digest format, and hash-algorithm migration policy should LLMLang use?
- **Context:** Stable content identities are foundational to SPG nodes, dependencies, reproducible builds, and OpHash.
- **Options to investigate:** Canonical typed binary encoding versus canonical structured text; algorithm-tagged digests; explicit migration/dual-hash strategy.
- **Recommendation:** Specify typed canonical encoding and domain separation before standardizing any digest spelling. Keep algorithm identity explicit in the digest representation.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), sections 4–5.

### LL-005 — Define hash-relevant dependency edges and cycles

- **Status:** Open
- **Priority:** P0
- **Question:** Which SPG relationships affect an artifact's content identity, and how are semantic cycles represented without ambiguous recursive hashing?
- **Context:** The dependency graph may contain relationships that are descriptive, evidentiary, or semantic. Only a well-defined subset should propagate content hashes.
- **Options to investigate:** Acyclic hash-dependency graph with non-hash-relevant back-references; canonical group/root objects for mutually recursive components.
- **Recommendation:** Keep the hash-dependency relation acyclic for the initial model; represent other graph relations separately until a canonical cyclic-group scheme is justified.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 5; [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), section 5.

### LL-006 — Decide artifact granularity for the initial SPG/store

- **Status:** Open
- **Priority:** P1
- **Question:** Which entities must be independently addressable in the first model, and what is the smallest useful reusable unit?
- **Context:** Candidate entities include operations, interfaces, contracts, types, expressions, implementation components, tests, models, and proofs. Excessive fragmentation can make the graph difficult to manage.
- **Recommendation:** Start with stable semantic boundaries that support independent reuse, verification, or change-impact analysis; do not require every expression to become a global artifact.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), sections 4 and 6.

### LL-007 — Separate target-profile semantics from implementation identity

- **Status:** Open
- **Priority:** P1
- **Question:** Which target/environment properties belong in an implementation's hash context, and which belong only in a binding or target profile?
- **Context:** Architecture, ABI, data layout, kernel/libc versions, and feature configuration may affect semantics, but including irrelevant environment details would prevent safe reuse.
- **Recommendation:** Hash only properties that can affect the artifact's interpretation or behavior; keep deployment-selection constraints in the binding when they do not alter the artifact itself.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), sections 3.5, 5, and 8.

### LL-008 — Define compatibility evidence and evidence reuse rules

- **Status:** Open
- **Priority:** P1
- **Question:** What evidence is required for a binding to claim compatibility, and when may tests/proofs be reused after surrounding artifacts change?
- **Context:** Hash equality is not behavioral equivalence; tests, declarations, and formal proofs are different evidence strengths and must be tied to exact inputs and assumptions.
- **Recommendation:** Bind evidence to exact artifact hashes, target profile, assumptions, and tool versions. Reuse only when all proof/test-relevant inputs are unchanged or a sound reuse rule is established.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 9.

### LL-009 — Define registry trust, provenance, licensing, and retention policy

- **Status:** Open
- **Priority:** P2
- **Question:** How are artifacts published, signed, mirrored, licensed, revoked, cached, and garbage-collected across registries?
- **Context:** Content addressing establishes integrity, not trust, ownership, or redistribution rights.
- **Recommendation:** Keep artifact identity separate from attestations and policy. Defer registry topology and advanced trust policy until the semantic artifact model is stable.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 10.

---

## Language, packages, and templates

### LL-010 — Decide whether Package is part of the SPG

- **Status:** Open
- **Priority:** P1
- **Question:** Is Package a first-class semantic graph object or a distribution-level container referencing SPG objects?
- **Context:** This affects the boundary between program semantics, distribution, dependency resolution, and provenance.
- **Recommendation:** Initially keep Package as a distribution/identity concept unless a concrete semantic use case requires it inside the SPG.
- **Related:** [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), sections 3 and 12.

### LL-011 — Define Library identity and publication requirements

- **Status:** Open
- **Priority:** P1
- **Question:** Is Library a package subtype, a reusable semantic role, or both; and what minimum public specification must a library expose?
- **Context:** Consumers need to know which claims are verifiable when implementation details are private or opaque.
- **Recommendation:** Treat Library as a reusable component role and require machine-readable public contracts for semantic integration; make verification limits explicit for opaque implementations.
- **Related:** [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), sections 3 and 12.


### LL-022 — Define the package content, index, and dynamic-provider model

- **Status:** Open
- **Priority:** P1
- **Question:** What logical content model, human-readable manifest schema, binary index format, compression and sparse-lookup strategy, and provider protocol should support both static packages and dynamically assembled packages?
- **Context:** Consumers need to inspect package contents and merge indexes efficiently without downloading all objects. A provider should be able to receive exact root Content Hash values and construct an archive from its local content store, including the exact required dependency closure. Indexes may become large enough that whole-file decompression or full in-memory loading is undesirable. An initial TOML manifest schema and package-identity proposal now exist, but the canonical typed encoding, digest algorithm, and executable conformance fixtures remain open.
- **Options to investigate:**
  - A human-readable text manifest (TOML is the current candidate), separated from the compact binary indexes.
  - A compact sorted index loaded wholly into memory for small packages.
  - Independently compressed sorted blocks with a block directory for larger indexes.
  - Optional one-level or hierarchical sparse indexes for random access to large or remote indexes.
  - Static prebuilt archives versus dynamic provider-built archives sharing one logical package model.
  - Provider operations for metadata query, index retrieval, dependency resolution, package construction, and exact object retrieval.
- **Recommendation:** Use a human-readable text manifest, with TOML as the current candidate; do not encode the manifest as a binary index. Reserve compact binary encoding for canonical machine indexes (and object payloads whose own formats require it). Keep the package index compact and sorted by explicitly specified keys; support binary search and deterministic streaming merge. Investigate independently compressed blocks as the scalable representation and make sparse lookup optional/derived, not mandatory for every package. A generated `INDEX.md` may aid browsing but is not authoritative. Treat dynamic packaging as materialization of exact requested roots plus an explicit required-dependency closure against one consistent content-store snapshot. Never silently substitute a different dependency hash. Compute logical package identity from a canonical typed projection, not raw manifest text or archive bytes; separate it from provider metadata, timestamps, signatures, compression, and transport. An exploratory executable prototype now exercises the candidate PMI invariants; its algorithm, table shapes, and current test coverage are not normative. A first logical schema for Objects, Dependencies, Exports, and Modules plus a deterministic in-memory merge prototype has also been added; it is not a streaming or binary index implementation. See [Package Manifest and Content Identity](research/PACKAGE-MANIFEST-AND-IDENTITY.md) and [Package Identity Prototype 01](research/PROTOTYPES/PACKAGE-IDENTITY-01/README.md).
- **New evidence:** the first logical schema for Objects, Dependencies, Exports, and Modules is documented in [Package Index Logical Schema](research/PACKAGE-INDEX-LOGICAL-SCHEMA.md). Prototype 01 tests schema validation, cross-table references, canonical ordering, deterministic merge, conflict rejection, and merge laws. A lazy k-way merge, bounded-memory external cross-table reference validator, and deterministic streaming ZIP archive writer/verifier are implemented and CI-tested. The archive prototype streams object bytes and verifies exact SHA-256 Content Hashes and sizes; ZIP is not a normative format.
- **Next gaps:** finalize dependency-kind and condition semantics; decide empty-module and Stable ID rules; determine whether further identity-bearing tables are required; define manifest-to-index consistency checks and recompute/verify the logical Package Content Root Hash during archive validation. Evaluate archive container alternatives and measure ZIP central-directory memory overhead before selecting a scalable archive design. Binary index block representation, compression, sparse lookup, provider-side dependency closure, provenance, and trust remain subsequent work.
- **Related:** [Package System: Static and Dynamic Packages](research/PACKAGE-SYSTEM.md), [Package Manifest and Content Identity](research/PACKAGE-MANIFEST-AND-IDENTITY.md), [illustrative manifest.toml](research/examples/package/manifest.toml), [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), and research area RT-12.

### LL-012 — Define template instantiation and migration semantics

- **Status:** Open
- **Priority:** P2
- **Question:** How are template instances represented, customized, detached, and migrated when a template changes?
- **Context:** Template updates must not silently overwrite local modifications or rewrite existing programs.
- **Options to investigate:** Copied semantic objects with provenance; parameterized references; hybrid model with explicit generated/customized/detached states.
- **Recommendation:** Instantiation should produce ordinary traceable SPG objects; updates should be explicit migrations represented as reviewable change sets.
- **Related:** [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), sections 6–8 and 12.

---

## Runtime and system interfaces

### LL-013 — Select the initial POSIX edition and conformance profile

- **Status:** Open
- **Priority:** P1
- **Question:** Which POSIX edition and which mandatory/optional/implementation-defined feature profile should the first LLMLang POSIX library target?
- **Context:** Conformance claims are meaningless without a precisely scoped edition and profile.
- **Recommendation:** Choose a small, explicit POSIX Core profile first; record optional and implementation-defined behavior separately.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-014 — Choose the LLMLang-facing POSIX API shape

- **Status:** Open
- **Priority:** P1
- **Question:** Should the public API mirror POSIX closely, or expose a safer typed façade while preserving a documented mapping to POSIX semantics?
- **Context:** A direct mapping improves familiarity and portability; a typed façade can make ownership, errors, and capabilities explicit but may change the surface API.
- **Recommendation:** Preserve POSIX behavioral compatibility while allowing LLMLang types to express ownership, errors, and capabilities more precisely. Validate with concrete API examples before deciding.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-015 — Define the first portable and native runtime vertical slices

- **Status:** Open
- **Priority:** P1
- **Question:** Which minimal functions and runtime mechanisms should be implemented first to validate both the portable runtime and the native Linux syscall runtime?
- **Context:** The project needs a bounded end-to-end milestone exercising compiler semantics, errors, resources, and ABI boundaries.
- **Recommendation:** Select a small shared-contract slice (for example, process startup, basic file I/O, and error handling) before expanding the API.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-016 — Select initial native architectures and isolate syscall ABI details

- **Status:** Open
- **Priority:** P2
- **Question:** Which Linux architectures should be supported first, and how should architecture-specific syscall stubs and ABI details be isolated?
- **Context:** Native runtime portability depends on keeping architecture-specific mechanics behind explicit target-specific artifacts.
- **Recommendation:** Begin with one target architecture for the first vertical slice, but define an abstraction boundary that permits additional architectures.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-017 — Define the trusted low-level runtime boundary

- **Status:** Open
- **Priority:** P1
- **Question:** Which runtime components may initially be implemented as trusted assembly, compiler intrinsics, or external code, and how is that trust boundary represented?
- **Context:** Native syscall entry and a small number of machine-specific operations may be difficult to express or verify in the initial language implementation.
- **Recommendation:** Minimize the trusted computing base, enumerate every trusted primitive, and expose explicit contracts and verification limits.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-018 — Specify POSIX concurrency and environment-dependent semantics

- **Status:** Open
- **Priority:** P2
- **Question:** How should LLMLang's memory/concurrency model relate to POSIX threads, signals, blocking I/O, scheduling, and Linux kernel ordering guarantees?
- **Context:** These behaviors are observable and cannot be treated as incidental implementation details.
- **Recommendation:** Define the language memory model independently, then specify explicit refinement/compatibility mappings for POSIX and kernel behavior.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-019 — Scope POSIX conformance and formal-verification claims

- **Status:** Open
- **Priority:** P1
- **Question:** How are optional and implementation-defined POSIX behaviors represented, tested, and verified, and what exactly does a conformance or proof claim cover?
- **Context:** A single “POSIX-compatible” label can hide unsupported options, assumptions, and unverified environment behavior.
- **Recommendation:** Publish feature-scoped conformance and evidence claims with explicit assumptions and exclusions.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), sections 10 and 13.

---

### LL-020 — Define LLVM backend role and semantic boundary

- **Status:** Open
- **Priority:** P1
- **Question:** Should LLVM be the initial native-code backend, an optional backend among several, or only one implementation of a replaceable backend interface; and what exact semantic guarantees must the LLMLang-to-LLVM lowering preserve?
- **Context:** LLVM can provide IR processing, optimization, target code generation, object emission, and JIT infrastructure. LLVM IR/bitcode is not the canonical semantic representation of LLMLang, and LLVM's own semantics (including poison/undefined behavior, overflow flags, pointer rules, floating-point flags, and memory ordering) may not match LLMLang semantics.
- **Options to investigate:** LLVM as the primary native backend; LLVM as one optional backend; multiple backends sharing a canonical LLMLang IR. Also investigate a conservative initial LLVM IR profile and explicit evidence requirements for lowering and optimization.
- **Recommendation:** Keep LLVM behind a replaceable backend boundary. Preserve SPG and LLMLang semantics as the source of truth; introduce LLVM only after defining a small semantic subset and a conservative lowering contract. Treat LLVM verification/compilation as distinct from proof of source-contract correctness.
- **Related:** [LLVM Backend Architecture](research/LLVM-BACKEND-ARCHITECTURE.md); [Translation and Target Backends](research/TRANSLATION-AND-TARGET-BACKENDS.md).

### LL-021 — Define semantic action caching and incremental compilation

- **Status:** Open
- **Priority:** P0
- **Question:** What is the canonical model for cacheable compiler/tooling actions, their Action Keys, dependency closure, environment inputs, and reusable outputs/evidence?
- **Context:** Semantic Hash identifies immutable program meaning; it is not sufficient as a build cache key. A computation's result can also depend on action implementation, toolchain, target, configuration, runtime, and other environment inputs. Tests and proofs must be reusable only for the exact inputs and assumptions they cover.
- **Options to investigate:** Cache at file/module/function/action granularity; byte-deterministic versus semantically deterministic outputs; local/workspace/remote/global cache layers; optional cache-index files in package archives; language-version versus compiler-build version granularity; conservative handling of incomplete dependencies and nondeterministic actions.
- **Recommendation:** Model compilation and analysis as a typed dependency graph of actions. Keep Semantic Hash, Action Key, and Artifact Hash distinct. Permit reuse only when dependency closure and all result-determining inputs are captured; otherwise invalidate conservatively or mark the action non-cacheable. Every result records a composite `LanguageVersion`, the digest of the append-only ordered component registry used to interpret it, and a separate `ToolchainIdentity`; these are distinct Action Key inputs whenever result-determining. The initial registry is `language-components.toml`; its entries are append-only and new coordinates are appended only at the end. Permit optional package-distributed cache indexes for validation, compilation, tests, and proofs; key them by exact Action Key (not bare object hash), address payloads by Artifact Hash, and ensure cache metadata never affects semantic package identity. Reuse across behavior-changing toolchain versions is forbidden unless explicit compatibility evidence exists.
- **Related:** [Semantic Compilation Cache](research/SEMANTIC-COMPILATION-CACHE.md), [Package System: Static and Dynamic Packages](research/PACKAGE-SYSTEM.md), [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), [Formal Verification](research/LLMLang-FORMAL-VERIFICATION.md).

### LL-022 — Define the Toolchain Server and semantic development API

- **Status:** Discussion
- **Priority:** P0
- **Question:** What transport-neutral Toolchain API, workspace/Change Set lifecycle, storage contract, transaction model, and repository synchronization protocol should LLMLang provide to agents and other clients?
- **Context:** The Development Engine RFC already makes structured semantic changes the intended machine interface and treats MCP as an optional adapter. It does not yet define durable workspace handles, mutation envelopes, storage/recovery semantics, multi-agent concurrency, or how accepted semantic snapshots are synchronized safely to canonical text files and Git.
- **Options to investigate:** An in-memory engine with explicit checkpoints; a persistent embedded semantic/workflow store; a shared remote service; MCP-native implementation versus a transport-neutral domain API with MCP/CLI/IDE adapters. Git-visible repository inputs must remain sufficient to reconstruct accepted source meaning under the Proposed ADR-014 direction.
- **Recommendation:** Start with a modular monolith, transport-neutral typed API, in-memory prototype, and a storage abstraction designed to admit a persistent embedded backend. Keep accepted SPG snapshots immutable; use expected-hash preconditions and optimistic concurrency; separate semantic acceptance, filesystem export, Git commit, and push. Do not make an external database the sole source of truth.
- **Related:** [RT-19 — Toolchain Server and Semantic Development API](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md), [Git semantic repository](research/GIT-SEMANTIC-REPOSITORY.md), [ADR-014](docs/adr/014-git-semantic-merge.md).

## Deferred engineering tasks

### DEFERRED-001 — Repair canonical query semantics Lean module

- **Status:** Deferred / someday
- **Priority:** P3
- **Task:** Reintroduce and complete the canonical query semantics proof prototype, then add it to the Lean build only after it compiles and its theorem is kernel-checked.
- **Context:** The experimental module `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CanonicalQuerySemantics.lean` attempted to define an evaluator for the actual dependent `QueryTerm` in `LLMLangLogosBinding.lean`, translate it into the independent semantic query representation from `SourceQuerySemantics.lean`, and prove evaluation preservation. The attempt was removed from the active build and deleted after it broke Lean CI; it is intentionally not part of the current validated baseline.
- **Observed failure modes (Lean 4.34.0, pinned Logos revision):**
  - Lean's termination checker could not establish structural/decreasing recursion for the evaluator over the sort-indexed dependent `QueryTerm`; one nested recursive call remained unproven.
  - The source semantic IR's `and`/`or` constructors did not match the canonical IR's list-valued operands. A correct translation must explicitly account for the representation difference and its identity/empty-list semantics, or initially exclude these operators.
  - A trailing documentation comment introduced additional parser errors during the attempted repair.
  - The attempted `partial` workaround was not an acceptable basis for a kernel-checked semantic-preservation theorem; the theorem was removed rather than weakening the proof obligation.
- **Recovery:** The failing module was removed from `lakefile.lean` roots and deleted. The previously validated roots remain `LLMLangLogosBinding` and `SourceQuerySemantics`. Do not restore the failed implementation verbatim.
- **Suggested approach when resumed:** Start with a small supported constructor subset (for example literals, symbols, negation, addition, and subtraction); design a structurally recursive evaluator or a non-dependent helper with an explicit size measure; prove the subset's translation/evaluation theorem first; then extend operators incrementally. Handle list-valued Boolean operators only after defining and testing their exact fold/identity semantics. Keep every increment behind the pinned Lean CI gate and do not add unproved `sorry`/unsafe/partial shortcuts.
- **Acceptance criteria:** The module builds under the pinned Lean 4.34.0 and Logos revision; the semantic-preservation theorem is accepted by Lean's kernel without `sorry` or untrusted shortcuts; positive and adversarial tests pass; the active Lean CI workflow remains green. The result must still be described as query-level correspondence only, not source-program-to-query or whole-program correctness.
- **Related:** `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/LLMLangLogosBinding.lean`, `SourceQuerySemantics.lean`, and Scenarios 29–33.

## Maintenance rules

- Add a new item when a discussion exposes a durable unresolved design question, not for every implementation task or transient note.
- Search this register before adding an item; extend an existing ID when the question is the same.
- Keep implementation tasks, bugs, and milestones in an issue tracker or plan if one is introduced. This file is for design questions and decisions.
- When discussion produces a decision, update the item's status and decision summary, then link the normative or research document that records it.
- If a decision is later reopened, preserve its history and explain why the prior decision is being reconsidered.
- Review this file when changing foundational documents so that resolved or newly discovered questions do not drift out of sync.
