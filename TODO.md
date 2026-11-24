# LLMLang — Open Questions and Decisions

This file is the project-wide register of unresolved design questions and decisions that require discussion.

**Stage 0.2 research-process tracking:** [quality review protocol](research/QUALITY-REVIEW-PROTOCOL.md) and [warning-only pilot results](research/RT-00-QUALITY-RULES-PILOT-2026-11-23.md) are proposals, not accepted governance decisions. Maintainer acceptance, corpus-wide claim audit, pilot reviewer measurements, and foundational experiment reruns remain open under [PLAN.md §0.2](PLAN.md#02-establish-research-quality-and-decision-rules) / [issue #285](https://github.com/aivibeflow/LLMLang/issues/285). No new LL design-question ID is created for this process implementation task.

**Pilot follow-up:** [Ten-report current-main audit](research/RT-00-QUALITY-RULES-REAL-REPORT-PILOT-2026-11-23.md) records known heading/metadata false alarms and a reproducible pinned structural sample. It does not select the process policy or resolve technical evidence identity LL-008; maintainer approval and corpus/experiment audits remain open.


It is not a specification. Items here may contain hypotheses and recommendations; only decisions explicitly accepted and transferred into the appropriate project documents become part of the design baseline.

The [Stage 0.2 warning adjudication](research/RT-00-QUALITY-RULES-ADJUDICATION-2026-11-23.md) resolves the *documentation triage classification* of 33 historical warnings (16 layout-only; 17 documentation gaps). It does not decide evidence validity, select any LLMLang semantics or satisfy open LL evidence-identity questions. The eight provenance gaps and nine other process gaps are tracked by [issue #285](https://github.com/aivibeflow/LLMLang/issues/285), rather than creating unrelated LL design-question IDs.

**Stage 0.2 provenance distinction:** [Pinned eight-report publication-history report](research/RT-00-QUALITY-RULES-PROVENANCE-RECHECK-2026-11-23.md) finds recoverable Git tree snapshots but does not authenticate original uncommitted run sources. The five-workload [historical recheck workflow](.github/workflows/research-historical-rechecks.yml) is a new bounded execution, not proof of historical experiment/toolchain identity. Keep the missing original-run attestations and other nine documentation crosswalk gaps tracked in [issue #285](https://github.com/aivibeflow/LLMLang/issues/285).

**Research evidence-navigation progress (2026-11-23):** [Nine supplementary report crosswalks](research/RT-00-QUALITY-RULES-NAVIGATION-REMEDIATION-2026-11-23.md) document the nine non-baseline process gaps classified in the Stage 0.2 pilot. This is a retrospective documentary correction, not a claim of originally-attested experimental runs or a normative specification. Keep eight original-run provenance/host gaps and the remaining research-quality policy adoption / corpus validation work under [issue #285](https://github.com/aivibeflow/LLMLang/issues/285).

**Stage 0.2 claim-level follow-up:** [Second 12-report/24-claim review](research/RT-00-QUALITY-RULES-CLAIM-COHORT2-2026-11-23.md) records eight local *interpretation risks* (not eight newly proven defects): Lean source/back-end correspondence, historical RT-05 unsuccessful tests, SAT sample bias, wire-runtime extrapolation, prospective SQLite provenance, stale RT-00 counts, RT-24 proposal/approval distinction, and finite FFI alias coverage. Machine-verified exact source pointers are insufficient for research correctness. Keep issue #285 open for independent technical review, representative corpus sampling, original-run attestations and maintainer policy adoption; no LL semantic decision is made here.

**Research quality technical validity follow-up:** [Orthogonal falsification controls](research/RT-00-QUALITY-RULES-ORTHOGONAL-ORACLES-2026-11-23.md) are source-pinned independent-code cross-checks for Scenario 110/112 and the RT-24 Git-tree counterexample. They do not establish an independent second **human** scientific review, a complete serializer, full-language scheduler semantics or original execution provenance. Continue [issue #285](https://github.com/aivibeflow/LLMLang/issues/285) for all remaining acceptance/maintainer authority checks.

**Stage 0.2 independent review handoff (pending):** [Eight diverse claim IDs](research/quality-audit/2026-11-23-independent-review-handoff.md) have a ready-to-use human Q1–Q5 reviewer protocol, but **no independent reviewer has completed it**. Separate [orthogonal model CI #45261537559](https://github.com/aivibeflow/LLMLang/actions/runs/45261537559) passed seven tests on 3,456 JSON and 21,840 fairness inputs plus a Git-negative control; this is experimental corroboration in restricted models, not source-to-compiler correctness or accepted language policy. Keep [issue #285](https://github.com/aivibeflow/LLMLang/issues/285) open for original-run provenance, independent claim review, generalization and maintainer quality-process adoption.

**Stage 0.2 corpus sampling task:** the [root research census and 24-document independent-review queue](research/RT-00-QUALITY-RULES-ROOT-CORPUS-CENSUS-2026-11-23.md) is a fixed Git-tree structural sweep with per-file warnings and source identity. Every queued document initially has `NOT REVIEWED`; an independent human must inspect actual claims and evidence, including zero-warning reports, before correctness/false-negative judgments or policy decisions. Continue [issue #285](https://github.com/aivibeflow/LLMLang/issues/285) without treating structural metrics as full research acceptance.

**Observed Stage 0.2 root census:** [309-file/2,035-warning summary](research/quality-audit/2026-11-23-root-census-observations.json) is a reproducible *heading/metadata* scan of one pinned Git tree, not a defect count. The [24 selected reviewer candidates](research/RT-00-QUALITY-RULES-ROOT-CORPUS-CENSUS-2026-11-23.md) include 8 Scenario, 8 RT and 8 other root research documents; all remain unreviewed. Ask independent human reviewers to identify real claim-quality gaps and false negatives before applying required quality gates. Keep issue #285 open for scientific verification and maintainer adoption.

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

- **GitHub issue:** [#344](https://github.com/aivibeflow/LLMLang/issues/344)

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

- **GitHub issue:** [#345](https://github.com/aivibeflow/LLMLang/issues/345)

- **Status:** Open
- **Priority:** P1
- **Question:** How is an Operation Stable ID created, preserved, split, merged, deprecated, or replaced as an operation evolves?
- **Context:** Stable ID identifies the logical lineage; OpHash identifies one immutable semantic version and is the call target. These roles must not collapse into one identifier.
- **Options to investigate:** Explicit author-assigned IDs; tool-generated IDs with explicit lineage operations; rules for split/merge and unrelated operations with equivalent contracts.
- **Recommendation:** Keep lineage changes explicit and auditable; never infer identity solely from names or contract similarity.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 3.6.

### LL-003 — Specify contract-based analogue discovery and substitution

- **GitHub issue:** [#346](https://github.com/aivibeflow/LLMLang/issues/346)

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

- **GitHub issue:** [#347](https://github.com/aivibeflow/LLMLang/issues/347)

- **Status:** Open
- **Priority:** P0
- **Question:** What canonical serialization, domain separation, digest format, and hash-algorithm migration policy should LLMLang use?
- **Context:** Stable content identities are foundational to SPG nodes, dependencies, reproducible builds, and OpHash.
- **Options to investigate:** Canonical typed binary encoding versus canonical structured text; algorithm-tagged digests; explicit migration/dual-hash strategy.
- **Recommendation:** Specify typed canonical encoding and domain separation before standardizing any digest spelling. Keep algorithm identity explicit in the digest representation.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), sections 4–5.

### LL-005 — Define hash-relevant dependency edges and cycles

- **GitHub issue:** [#348](https://github.com/aivibeflow/LLMLang/issues/348)

- **Status:** Open
- **Priority:** P0
- **Question:** Which SPG relationships affect an artifact's content identity, and how are semantic cycles represented without ambiguous recursive hashing?
- **Context:** The dependency graph may contain relationships that are descriptive, evidentiary, or semantic. Only a well-defined subset should propagate content hashes.
- **Options to investigate:** Acyclic hash-dependency graph with non-hash-relevant back-references; canonical group/root objects for mutually recursive components.
- **New evidence:** Two exact group encodings preserve addresses under display renames and propagate relevant changes to callers. Structural canonicalization can share a value address across symmetric members. Compare the cost of that invalidation with a design that pins Contract-level bindings separately from implementation closures. [RT-05 recursive identity](research/RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md)
- **Recommendation:** Keep the hash-dependency relation acyclic for the initial model; represent other graph relations separately until a canonical cyclic-group scheme is justified.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 5; [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), section 5.

### LL-006 — Decide artifact granularity for the initial SPG/store

- **GitHub issue:** [#349](https://github.com/aivibeflow/LLMLang/issues/349)

- **Status:** Open
- **Priority:** P1
- **Question:** Which entities must be independently addressable in the first model, and what is the smallest useful reusable unit?
- **Context:** Candidate entities include operations, interfaces, contracts, types, expressions, implementation components, tests, models, and proofs. Excessive fragmentation can make the graph difficult to manage.
- **Recommendation:** Start with stable semantic boundaries that support independent reuse, verification, or change-impact analysis; do not require every expression to become a global artifact.
- **New evidence** · The typed SPG fixture measures which selected values change after a body edit, a binding update, and a contract revision. It also compares the addressable units for interfaces, types, tests, models, and proofs. [RT-05 Typed Semantic Program Graph](research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md#6-artifact-granularity-and-trade-offs)
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), sections 4 and 6.

### LL-007 — Separate target-profile semantics from implementation identity

- **GitHub issue:** [#350](https://github.com/aivibeflow/LLMLang/issues/350)

- **Status:** Open
- **Priority:** P1
- **Question:** Which target/environment properties belong in an implementation's hash context, and which belong only in a binding or target profile?
- **Context:** Architecture, ABI, data layout, kernel/libc versions, and feature configuration may affect semantics, but including irrelevant environment details would prevent safe reuse.
- **Recommendation:** Hash only properties that can affect the artifact's interpretation or behavior; keep deployment-selection constraints in the binding when they do not alter the artifact itself.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), sections 3.5, 5, and 8.

### LL-008 — Define compatibility evidence and evidence reuse rules

- **GitHub issue:** [#351](https://github.com/aivibeflow/LLMLang/issues/351)

- **Status:** Open
- **Priority:** P1
- **Question:** What evidence is required for a binding to claim compatibility, and when may tests/proofs be reused after surrounding artifacts change?
- **Context:** Hash equality is not behavioral equivalence; tests, declarations, and formal proofs are different evidence strengths and must be tied to exact inputs and assumptions.
- **Recommendation:** Bind evidence to exact artifact hashes, target profile, assumptions, and tool versions. Reuse only when all proof/test-relevant inputs are unchanged or a sound reuse rule is established.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 9.

### LL-009 — Define registry trust, provenance, licensing, and retention policy

- **GitHub issue:** [#352](https://github.com/aivibeflow/LLMLang/issues/352)

- **Status:** Open
- **Priority:** P2
- **Question:** How are artifacts published, signed, mirrored, licensed, revoked, cached, and garbage-collected across registries?
- **Context:** Content addressing establishes integrity, not trust, ownership, or redistribution rights.
- **Recommendation:** Keep artifact identity separate from attestations and policy. Defer registry topology and advanced trust policy until the semantic artifact model is stable.
- **Related:** [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), section 10.

---

## Language, packages, and templates

### LL-010 — Decide whether Package is part of the SPG

- **GitHub issue:** [#353](https://github.com/aivibeflow/LLMLang/issues/353)

- **Status:** Open
- **Priority:** P1
- **Question:** Is Package a first-class semantic graph object or a distribution-level container referencing SPG objects?
- **Context:** This affects the boundary between program semantics, distribution, dependency resolution, and provenance.
- **Recommendation:** Initially keep Package as a distribution/identity concept unless a concrete semantic use case requires it inside the SPG.
- **Related:** [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), sections 3 and 12.

### LL-011 — Define Library identity and publication requirements

- **GitHub issue:** [#354](https://github.com/aivibeflow/LLMLang/issues/354)

- **Status:** Open
- **Priority:** P1
- **Question:** Is Library a package subtype, a reusable semantic role, or both; and what minimum public specification must a library expose?
- **Context:** Consumers need to know which claims are verifiable when implementation details are private or opaque.
- **Recommendation:** Treat Library as a reusable component role and require machine-readable public contracts for semantic integration; make verification limits explicit for opaque implementations.
- **Related:** [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), sections 3 and 12.


### LL-022 — Define the package content, index, and dynamic-provider model

- **GitHub issue:** [#355](https://github.com/aivibeflow/LLMLang/issues/355)

- **Status:** Open
- **Priority:** P1
- **Question:** What logical content model, human-readable manifest schema, binary index format, compression and sparse-lookup strategy, and provider protocol should support both static packages and dynamically assembled packages?
- **Context:** Consumers need to inspect package contents and merge indexes efficiently without downloading all objects. A provider should be able to receive exact root Content Hash values and construct an archive from its local content store, including the exact required dependency closure. Indexes may become large enough that whole-file decompression or full in-memory loading is undesirable. An initial TOML manifest schema and package-identity proposal now exist. The archive prototype parses the v1 manifest and recomputes the prototype logical index and Package Content Root Hash; the canonical typed encoding and digest algorithm remain research-only, not normative.
- **Options to investigate:**
  - A human-readable text manifest (TOML is the current candidate), separated from the compact binary indexes.
  - A compact sorted index loaded wholly into memory for small packages.
  - Independently compressed sorted blocks with a block directory for larger indexes.
  - Optional one-level or hierarchical sparse indexes for random access to large or remote indexes.
  - Static prebuilt archives versus dynamic provider-built archives sharing one logical package model.
  - Provider operations for metadata query, index retrieval, dependency resolution, package construction, and exact object retrieval.
- **Recommendation:** Use a human-readable text manifest, with TOML as the current candidate; do not encode the manifest as a binary index. Reserve compact binary encoding for canonical machine indexes (and object payloads whose own formats require it). Keep the package index compact and sorted by explicitly specified keys; support binary search and deterministic streaming merge. Investigate independently compressed blocks as the scalable representation and make sparse lookup optional/derived, not mandatory for every package. A generated `INDEX.md` may aid browsing but is not authoritative. Treat dynamic packaging as materialization of exact requested roots plus an explicit required-dependency closure against one consistent content-store snapshot. Never silently substitute a different dependency hash. Compute logical package identity from a canonical typed projection, not raw manifest text or archive bytes; separate it from provider metadata, timestamps, signatures, compression, and transport. An exploratory executable prototype now exercises the candidate PMI invariants; its algorithm, table shapes, and current test coverage are not normative. A first logical schema for Objects, Dependencies, Exports, and Modules plus a deterministic in-memory merge prototype has also been added; it is not a streaming or binary index implementation. See [Package Manifest and Content Identity](research/PACKAGE-MANIFEST-AND-IDENTITY.md) and [Package Identity Prototype 01](research/PROTOTYPES/PACKAGE-IDENTITY-01/README.md).
- **New evidence:** the first logical schema for Objects, Dependencies, Exports, and Modules is documented in [Package Index Logical Schema](research/PACKAGE-INDEX-LOGICAL-SCHEMA.md). Prototype 01 tests schema validation, cross-table references, canonical ordering, deterministic merge, conflict rejection, and merge laws. A lazy k-way merge, bounded-memory external cross-table reference validator, and deterministic streaming ZIP archive writer/verifier are implemented and CI-tested. The archive prototype parses the manifest, recomputes the logical index hash and Package Content Root Hash using the identity prototype, verifies declared roots are included, and streams object bytes while checking exact SHA-256 Content Hashes and sizes; ZIP is not a normative format.
- **New evidence:** Prototype 01 now resolves exact required/optional dependency closure under the three manifest policies against one immutable Content Store snapshot. It rejects missing or substituted hashes, requires explicit boolean selections for traversed conditional edges, handles cycles and shared dependencies, and recomputes index included flags. A disk-backed Provider-to-archive pipeline now stores traversal queue, visited object metadata, and dependency rows in SQLite; sorted index iterators feed the streaming archive writer and payloads are opened one at a time. It remains a prototype: measure actual resource bounds and connect a production Content Store adapter.\n- **Next gaps:** finalize dependency-kind and condition semantics; decide empty-module and Stable ID rules; determine whether further identity-bearing tables are required; measure disk-backed traversal and ZIP central-directory memory; implement and test a real Content Store snapshot adapter; investigate multi-provider composition; extend manifest-to-index checks to cache-index payloads and any future identity-bearing tables; evaluate archive container alternatives and measure ZIP central-directory memory overhead before selecting a scalable archive design. Binary index block representation, compression, sparse lookup, provenance, and trust remain subsequent work.
- **Related:** [Package System: Static and Dynamic Packages](research/PACKAGE-SYSTEM.md), [Package Manifest and Content Identity](research/PACKAGE-MANIFEST-AND-IDENTITY.md), [illustrative manifest.toml](research/examples/package/manifest.toml), [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md), [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), and research area RT-12.

### LL-012 — Define template instantiation and migration semantics

- **GitHub issue:** [#356](https://github.com/aivibeflow/LLMLang/issues/356)

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

- **GitHub issue:** [#357](https://github.com/aivibeflow/LLMLang/issues/357)

- **Status:** Open
- **Priority:** P1
- **Question:** Which POSIX edition and which mandatory/optional/implementation-defined feature profile should the first LLMLang POSIX library target?
- **Context:** Conformance claims are meaningless without a precisely scoped edition and profile.
- **Recommendation:** Choose a small, explicit POSIX Core profile first; record optional and implementation-defined behavior separately.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-014 — Choose the LLMLang-facing POSIX API shape

- **GitHub issue:** [#358](https://github.com/aivibeflow/LLMLang/issues/358)

- **Status:** Open
- **Priority:** P1
- **Question:** Should the public API mirror POSIX closely, or expose a safer typed façade while preserving a documented mapping to POSIX semantics?
- **Context:** A direct mapping improves familiarity and portability; a typed façade can make ownership, errors, and capabilities explicit but may change the surface API.
- **Recommendation:** Preserve POSIX behavioral compatibility while allowing LLMLang types to express ownership, errors, and capabilities more precisely. Validate with concrete API examples before deciding.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-015 — Define the first portable and native runtime vertical slices

- **GitHub issue:** [#359](https://github.com/aivibeflow/LLMLang/issues/359)

- **Status:** Open
- **Priority:** P1
- **Question:** Which minimal functions and runtime mechanisms should be implemented first to validate both the portable runtime and the native Linux syscall runtime?
- **Context:** The project needs a bounded end-to-end milestone exercising compiler semantics, errors, resources, and ABI boundaries.
- **Recommendation:** Select a small shared-contract slice (for example, process startup, basic file I/O, and error handling) before expanding the API.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-016 — Select initial native architectures and isolate syscall ABI details

- **GitHub issue:** [#360](https://github.com/aivibeflow/LLMLang/issues/360)

- **Status:** Open
- **Priority:** P2
- **Question:** Which Linux architectures should be supported first, and how should architecture-specific syscall stubs and ABI details be isolated?
- **Context:** Native runtime portability depends on keeping architecture-specific mechanics behind explicit target-specific artifacts.
- **Recommendation:** Begin with one target architecture for the first vertical slice, but define an abstraction boundary that permits additional architectures.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-017 — Define the trusted low-level runtime boundary

- **GitHub issue:** [#361](https://github.com/aivibeflow/LLMLang/issues/361)

- **Status:** Open
- **Priority:** P1
- **Question:** Which runtime components may initially be implemented as trusted assembly, compiler intrinsics, or external code, and how is that trust boundary represented?
- **Context:** Native syscall entry and a small number of machine-specific operations may be difficult to express or verify in the initial language implementation.
- **Recommendation:** Minimize the trusted computing base, enumerate every trusted primitive, and expose explicit contracts and verification limits.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-018 — Specify POSIX concurrency and environment-dependent semantics

- **GitHub issue:** [#362](https://github.com/aivibeflow/LLMLang/issues/362)

- **Status:** Open
- **Priority:** P2
- **Question:** How should LLMLang's memory/concurrency model relate to POSIX threads, signals, blocking I/O, scheduling, and Linux kernel ordering guarantees?
- **Context:** These behaviors are observable and cannot be treated as incidental implementation details.
- **Recommendation:** Define the language memory model independently, then specify explicit refinement/compatibility mappings for POSIX and kernel behavior.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), section 13.

### LL-019 — Scope POSIX conformance and formal-verification claims

- **GitHub issue:** [#363](https://github.com/aivibeflow/LLMLang/issues/363)

- **Status:** Open
- **Priority:** P1
- **Question:** How are optional and implementation-defined POSIX behaviors represented, tested, and verified, and what exactly does a conformance or proof claim cover?
- **Context:** A single “POSIX-compatible” label can hide unsupported options, assumptions, and unverified environment behavior.
- **Recommendation:** Publish feature-scoped conformance and evidence claims with explicit assumptions and exclusions.
- **Related:** [POSIX Runtime Architecture](research/POSIX-RUNTIME-ARCHITECTURE.md), sections 10 and 13.

---

### LL-020 — Define LLVM backend role and semantic boundary

- **GitHub issue:** [#364](https://github.com/aivibeflow/LLMLang/issues/364)

- **Status:** Open
- **Priority:** P1
- **Question:** Should LLVM be the initial native-code backend, an optional backend among several, or only one implementation of a replaceable backend interface; and what exact semantic guarantees must the LLMLang-to-LLVM lowering preserve?
- **Context:** LLVM can provide IR processing, optimization, target code generation, object emission, and JIT infrastructure. LLVM IR/bitcode is not the canonical semantic representation of LLMLang, and LLVM's own semantics (including poison/undefined behavior, overflow flags, pointer rules, floating-point flags, and memory ordering) may not match LLMLang semantics.
- **Options to investigate:**
  - LLVM as the initial optimized native backend, an optional backend, or one backend behind a stable LLMLang-owned interface.
  - Cranelift as a candidate for fast Debug compilation and/or JIT workloads; do not assume it is a replacement for LLVM without comparative evidence.
  - A direct native backend for a narrowly justified target/use case where measured requirements cannot be met through existing backends.
  - WebAssembly through LLVM or a dedicated toolchain, evaluated as a target/runtime profile rather than assumed to be a separate compiler architecture.
  - A mode-specific strategy (for example, different backends for Debug, Release, and JIT) only if the same semantic conformance requirements can be demonstrated.
  - A target support matrix covering architecture, operating system, ABI, object format, linker, sysroot/system libraries, runtime, and required tooling.
- **Recommendation:** Keep every backend behind a replaceable boundary and preserve SPG/LLMLang semantics as the source of truth. Treat LLVM as the leading existing native-code candidate, not as an irrevocably selected or mandatory backend. Establish a small semantic subset and conservative lowering contract before implementation claims. Select the initial backend and any Debug/Release/JIT split only after reproducible, same-workload comparisons of compile latency/throughput, runtime behavior, output size, memory use, target coverage, diagnostics/debug information, toolchain burden, and semantic-conformance evidence. Do not build a custom backend merely for architectural purity. Treat LLVM verification/compilation as distinct from proof of source-contract correctness.
- **Decision gate:** Resolve this item only when the target support matrix, benchmark protocol and workload corpus, semantic-conformance gates, candidate results, maintenance costs, and explicit rationale for the initial backend configuration are recorded. Unknown or unsupported target/semantic combinations must remain explicit; a favorable benchmark cannot compensate for missing correctness evidence.
- **Related** — [LLVM Backend Architecture](research/LLVM-BACKEND-ARCHITECTURE.md) · [Translation and Target Backends](research/TRANSLATION-AND-TARGET-BACKENDS.md) · [LLVM integer preservation evidence](research/RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md)

### LL-021 — Define semantic action caching and incremental compilation

- **GitHub issue:** [#365](https://github.com/aivibeflow/LLMLang/issues/365)

- **Status:** Open
- **Priority:** P0
- **Question:** What is the canonical model for cacheable compiler/tooling actions, their Action Keys, dependency closure, environment inputs, and reusable outputs/evidence?
- **Context:** Semantic Hash identifies immutable program meaning; it is not sufficient as a build cache key. A computation's result can also depend on action implementation, toolchain, target, configuration, runtime, and other environment inputs. Tests and proofs must be reusable only for the exact inputs and assumptions they cover.
- **Options to investigate:** Cache at file/module/function/action granularity; byte-deterministic versus semantically deterministic outputs; local/workspace/remote/global cache layers; optional cache-index files in package archives; language-version versus compiler-build version granularity; conservative handling of incomplete dependencies and nondeterministic actions.
- **Recommendation:** Model compilation and analysis as a typed dependency graph of actions. Keep Semantic Hash, Action Key, and Artifact Hash distinct. Permit reuse only when dependency closure and all result-determining inputs are captured; otherwise invalidate conservatively or mark the action non-cacheable. Every result records a composite `LanguageVersion`, the digest of the append-only ordered component registry used to interpret it, and a separate `ToolchainIdentity`; these are distinct Action Key inputs whenever result-determining. The initial registry is `language-components.toml`; its entries are append-only and new coordinates are appended only at the end. Permit optional package-distributed cache indexes for validation, compilation, tests, and proofs; key them by exact Action Key (not bare object hash), address payloads by Artifact Hash, and ensure cache metadata never affects semantic package identity. Reuse across behavior-changing toolchain versions is forbidden unless explicit compatibility evidence exists.
- **Related:** [Semantic Compilation Cache](research/SEMANTIC-COMPILATION-CACHE.md), [Package System: Static and Dynamic Packages](research/PACKAGE-SYSTEM.md), [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), [Formal Verification](research/LLMLang-FORMAL-VERIFICATION.md).

### LL-024 — Define the Toolchain Server and semantic development API

- **GitHub issue:** [#367](https://github.com/aivibeflow/LLMLang/issues/367)

- **Status:** Discussion
- **Priority:** P0
- **Question:** What transport-neutral Toolchain API, workspace/Change Set lifecycle, storage contract, transaction model, and repository synchronization protocol should LLMLang provide to agents and other clients?
- **Context:** The Development Engine RFC already makes structured semantic changes the intended machine interface and treats MCP as an optional adapter. It does not yet define durable workspace handles, mutation envelopes, storage/recovery semantics, multi-agent concurrency, or how accepted semantic snapshots are synchronized safely to canonical text files and Git.
- **Options to investigate:** An in-memory engine with explicit checkpoints; a persistent embedded semantic/workflow store; a shared remote service; MCP-native implementation versus a transport-neutral domain API with MCP/CLI/IDE adapters. Git-visible repository inputs must remain sufficient to reconstruct accepted source meaning under the Proposed ADR-014 direction.
- **Recommendation:** Start with a modular monolith, transport-neutral typed API, in-memory prototype, and a storage abstraction designed to admit a persistent embedded backend. Keep accepted SPG snapshots immutable; use expected-hash preconditions and optimistic concurrency; separate semantic acceptance, filesystem export, Git commit, and push. Do not make an external database the sole source of truth.
- **Related:** [RT-19 — Toolchain Server and Semantic Development API](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [ADR-015](docs/adr/015-toolchain-server-semantic-api.md), [Toolchain Prototype 01](research/PROTOTYPES/TOOLCHAIN-SERVER-01/README.md), [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md), [Git semantic repository](research/GIT-SEMANTIC-REPOSITORY.md), [ADR-014](docs/adr/014-git-semantic-merge.md).

### LL-023 — Define complete LLM patch planning and validation-gated commit

- **GitHub issue:** [#366](https://github.com/aivibeflow/LLMLang/issues/366)

- **Status:** Discussion
- **Priority:** P0
- **Question:** How must the Toolchain determine, before implementation, every function version and call-site reference that will change when a callee evolves, while allowing different callers to preserve or migrate to different immutable callee versions?
- **Context:** Function versions are being explored as content-addressed objects identified by hashId. A changed callee can require caller contract changes and/or caller hash changes when a hash-relevant reference is rewritten. These are distinct propagation relations. A caller that needs new behavior may migrate, while another must preserve the old callee version. Shared callers may need version splits. The agent must execute every approved plan item, and Git commit must be gated by successful validation of the exact candidate.
- **Questions to resolve:** Call-site identity and reverse-reference completeness; compatibility evidence for migrate/preserve/adapt/fork; contract propagation boundaries; hash closure and entry-point roots; version splitting for shared callers; plan revision and approval; evidence invalidation; exact-tree commit, concurrency, retries, and failure recovery.
- **Recommendation:** Introduce a versioned Change Impact Plan with separate Dependency Analysis and Change Implementation Plan views. Make compatibility decisions edge-specific. Validate completeness server-side before permitting mutations. Enforce every planned function/reference change. Expose one authorized completion operation that validates and audits the frozen candidate and creates a Git commit only if all mandatory gates pass; keep remote push separate.
- **Related:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md), [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md), [RT-05 identity research](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md), [RT-06 dependency research](research/RESEARCH-SCENARIO-25-FORMAL-SEMANTIC-DEPENDENCY-ANALYSIS.md).

### LL-025 — Define cross-version component and wire compatibility

- **Tracking:** Resolved; no open issue. The accepted decision is recorded below.

- **Status:** Resolved
- **Priority:** P2
- **Question:** Must immutable LLMLang components interoperate across toolchain versions, and is a general wire-schema evolution protocol required?
- **Decision (2026-11-20):** Published components are read-only/immutable. Compatibility is required only within a coherent build performed by one toolchain version. The toolchain statically checks caller arguments against the callee's declared callable prototype; mismatches fail the build. The current architecture does not require cross-version wire compatibility, schema negotiation, or persisted-message migration.
- **Boundary:** This does not resolve behavioral Contract refinement, cross-version ABI, dynamic loading, external RPC, or persistence formats. Callable type compatibility and behavioral contract compatibility remain distinct.
- **Reconsideration trigger:** Independently built component exchange, cross-toolchain linking, dynamic loading, external RPC, persisted serialized messages, or a separately versioned binary/plugin ABI.
- **Related:** [Architecture Decision — Immutable Components and Single-Version Toolchain Compatibility](draft/ARCHITECTURE-DECISIONS.md), [Scenario 134](research/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md).

### LL-028 — Define backend-independent proof selection and evidence orchestration

- **GitHub issue:** [#390](https://github.com/aivibeflow/LLMLang/issues/390)
- **Status:** Open
- **Priority:** P0
- **Question:** How should LLMLang classify proof obligations and select, combine, and validate backends such as Lean, SMT, and TLA+ without making backend-specific semantics authoritative or silently weakening a contract?
- **Context:** Contract meaning and authoritative LLMLang semantics must remain independent of proof engines. A single contract may generate heterogeneous obligations, and one obligation may benefit from complementary or independent backends. RT-32 investigates one Lean route; it does not settle whether all evidence should reduce to Lean.
- **Questions to resolve:** Obligation taxonomy and typed planner inputs; versioned backend capability profiles; deterministic and auditable selection/abstention; backend-specific translation correspondence; proof certificates and trusted computing base; combination of complementary/diverse results; finite model bounds and environment assumptions; proven/disproven/unknown/unsupported/error semantics; evidence provenance and dependency closure; caching and invalidation; whether Lean is useful as an optional checker for selected results without requiring universal reduction to Lean.
- **Recommendation:** Keep Contract IR backend-independent. Select one or more backends per proof obligation from explicit capability profiles, and abstain when required semantics or evidence strength is unsupported. Preserve each translation/correspondence obligation and all assumptions. Never aggregate partial, unknown, unsupported, or untrusted results into proven.
- **Related:** [RT-33](research/RT-33-PROOF-BACKEND-SELECTION-AND-ORCHESTRATION.md), [RT-32](research/RT-32-VERIFIED-SPG-TO-LEAN-PIPELINE.md), [RT-07](research/LLMLang-FORMAL-VERIFICATION.md), [contract formalization corpus](research/CONTRACT-FORMALIZATION-CORPUS/README.md).

### LL-029 — Build a representative proof-obligation benchmark

- **Status:** Open
- **Priority:** P0 (supports RT-33)
- **Question:** Can the Toolchain reliably generate a complete and sound obligation set, classify heterogeneous obligations, select eligible verification backends, validate translations, and aggregate evidence without hiding uncertainty?
- **Context:** The CF corpus (CF-001–CF-005) tests semantic fidelity of natural-language-to-contract formalization, not the downstream proof pipeline. RT-33 requires representative obligations beyond simple array algorithms and explicit tests for unsupported or incomplete evidence.
- **Scope:** Instantiate the multi-label taxonomy in [the Proof Obligation Benchmark](research/PROOF-OBLIGATION-BENCHMARK.md): six obligation forms and ten semantic domains. Cover boundary, negative, conditional, and composed cases; include multi-backend scenarios and explicit abstention tests. Evaluate contract formalization, obligation generation, and backend verification as separate layers.
- **Recommendation:** Start with a small seed set spanning structurally different domains and at least one multi-backend case. Expand toward the proposed 80-case coverage matrix only where cases add distinct semantic or planner coverage; do not treat 80 as a quota.
- **Related:** [RT-33](research/RT-33-PROOF-BACKEND-SELECTION-AND-ORCHESTRATION.md), [Proof Obligation Benchmark](research/PROOF-OBLIGATION-BENCHMARK.md), [CF corpus](research/CONTRACT-FORMALIZATION-CORPUS/README.md), [Issue #390](https://github.com/aivibeflow/LLMLang/issues/390).

## AI authoring contexts

### LL-026 — Define the Knowledge Context model

- **GitHub issue:** [#368](https://github.com/aivibeflow/LLMLang/issues/368)

- **Status:** Open
- **Priority:** P1
- **Question:** What versioned, provenance-preserving, bounded representation defines the knowledge made available to an LLM agent for a specific development task, and how can the Toolchain assemble it without silently omitting required or exposing unauthorized information?
- **Context:** A Knowledge Context is intended to describe the information an agent may rely on: selected requirements, contracts, design decisions, implementation objects, dependency information, diagnostics, verification evidence, project documents, and explicitly admitted external sources. It is not a runtime variable scope, an unstructured prompt, or automatically the same thing as the complete semantic dependency closure.
- **Questions to resolve:** Source and trust classes; exact object/snapshot/version references; required versus optional entries; deterministic selection versus relevance ranking; completeness and omission evidence; stale, conflicting, unavailable, or unknown inputs; token/size budgets; access control, redaction, and data minimization; context manifest identity and provenance; cache/reuse and invalidation; relationship to semantic dependencies, snapshot identity, and action-cache identity; agent-facing rendering and retrieval APIs.
- **Recommendation:** Research an immutable context manifest pinned to an explicit baseline, with typed entries, source provenance, inclusion rationale, required/optional status, access restrictions, and explicit completeness/unknown outcomes. Do not claim completeness from relevance ranking alone, and do not silently treat missing or stale sources as absent.
- **Related:** RT-14 AI-native authoring; RT-05 representation and identity; RT-06 dependency analysis; RT-16 security and trust; RT-19 Toolchain Server; [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md); [Open-question research program](research/RESEARCH-PROGRAM-OPEN-QUESTIONS-2026-11-19.md).

### LL-027 — Define the Task Context model

- **GitHub issue:** [#369](https://github.com/aivibeflow/LLMLang/issues/369)

- **Status:** Open
- **Priority:** P1
- **Question:** What explicit, versioned object describes an agent's development task, its scope, constraints, expected outputs, dependencies, and completion obligations throughout planning, execution, review, and handoff?
- **Context:** A Task Context should distinguish the task being performed from the Knowledge Context supplied to inform it, from runtime execution state, and from authorization grants. It may refer to a baseline snapshot, target semantic objects, requirements, a Knowledge Context, a Change Set, a Change Impact Plan, acceptance criteria, and required validation evidence.
- **Questions to resolve:** Task identity and revision lifecycle; objective and traceability to requirements; in-scope and out-of-scope objects; constraints and non-goals; prerequisites and dependency ordering; expected deliverables; acceptance and verification obligations; state transitions, cancellation, retries, delegation, decomposition, and handoff; concurrent agents and ownership; approval boundaries; binding to baseline snapshots and Change Sets; provenance and audit history; relationship to RT-20 planning and RT-19 workspace transactions.
- **Security boundary:** A Task Context describes what work is requested and what obligations apply; it MUST NOT itself grant capabilities or elevate authority. Authorization must be evaluated through the independent RT-16 capability and policy model.
- **Recommendation:** Research a typed task record with explicit objective, scope, constraints, linked Knowledge Context and baseline, expected outputs, prerequisites, and machine-checkable completion obligations. Keep lifecycle and schema alternatives open until they are tested against multi-step and delegated agent workflows.
- **Related:** RT-14 AI-native authoring; RT-02 requirements and intent; RT-16 security and trust; RT-19 Toolchain Server; RT-20 patch planning; [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md); [Open-question research program](research/RESEARCH-PROGRAM-OPEN-QUESTIONS-2026-11-19.md).

## Deferred engineering tasks

### DEFERRED-001 — Repair canonical query semantics Lean module

- **GitHub issue:** [#343](https://github.com/aivibeflow/LLMLang/issues/343) (Deferred / someday; excluded from the active execution sequence).

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
