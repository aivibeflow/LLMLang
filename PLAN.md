# LLMLang Research and Development Plan

**Status:** living plan  
**Updated:** 2026-11-18  
**Restored baseline:** detailed plan from [`aa39c8f`](https://github.com/aivibeflow/LLMLang/commit/aa39c8fc2a611ae72ff85acff3de3c16fcc4eb39), reconciled with the current project plan and repository evidence  
**Repository:** `aivibeflow/LLMLang`  
**Research corpus at plan creation:** 102 files under `research/`  
**Normative boundary:** this plan schedules research and validation. Research results are not normative language rules until explicitly reviewed and transferred to `draft/`.

## 1. Purpose

This plan consolidates the LLMLang research programme, including topics already investigated, topics with active prototypes, and topics that remain open. Its purpose is to:

- establish a dependency-aware order for research;
- preserve completed work instead of treating it as future work;
- distinguish an existing research document from a validated result or an accepted architectural decision;
- identify the evidence and exit criteria required before moving to the next stage;
- keep the research corpus in `research/` and the candidate specification in `draft/`.

The stages are ordered. Work inside a stage may proceed in parallel when its dependencies are satisfied. A later stage may be explored early, but it must not be treated as architecturally settled before its prerequisites pass their exit criteria.

## 2. Status vocabulary

Use these statuses for each item:

- **Researched** — a research document or substantial analysis exists. This does not mean the question is conclusively resolved.
- **Prototyped** — an executable prototype or focused experiment exists.
- **Partially validated** — some claims have supporting evidence, but acceptance criteria remain unmet.
- **In progress** — active work or an explicit next experiment exists.
- **Not started** — no substantial research has been recorded yet.
- **Decision pending** — alternatives have been investigated, but an explicit design decision remains open.
- **Accepted** — an explicit project decision has been recorded in a durable design document. A recommendation alone is not acceptance.

Status applies to the current evidence, not to how important the topic is. Where the repository contains related research but not a direct answer to the exact question, mark the item as partially researched rather than complete.

## 3. Stage overview

| Stage | Name | Main outcome | Gate |
|---|---|---|---|
| 0 | Research inventory and evidence hygiene | A reconciled map of existing work, claims, prototypes, gaps, and decisions | Every existing research area is mapped; evidence and decision status are explicit |
| 1 | Semantic foundation and identity | A coherent model of SPG, semantic objects, contracts, and immutable identities | Canonical semantic objects, identity boundaries, and contract relations are sufficiently defined |
| 2 | Formal semantics and verification foundation | A small formal core with independently checkable claims and explicit proof boundaries | A reference semantics and a sound, reproducible verification slice exist |
| 3 | Dependency graph, incremental computation, and cache | Sound impact analysis and cache reuse/invalidation model | Dependency completeness and cache-key soundness are demonstrated on representative changes |
| 4 | Semantic storage, versioning, and Git integration | Durable repository representation and semantic merge workflow | Clone, history, diff, merge, conflict handling, and recovery are demonstrated |
| 5 | Types, execution model, runtime, and POSIX | A small executable language/runtime slice with explicit platform boundaries | A vertical slice preserves its declared semantics on a selected target |
| 6 | Translation, backends, and optimization | Multiple target realizations and evidence-backed implementation selection | Two backends agree with reference semantics for the selected subset |
| 7 | Scale, ecosystem, collaboration, and adoption | Measured feasibility and operational model for real projects | Performance, storage, collaboration, trust, and usability criteria are measured |

---

# Stage 0 — Research inventory and evidence hygiene

**Order:** first; can run alongside maintenance of existing prototypes.  
**Purpose:** establish what the 102-file research corpus actually proves and what remains open.

### 0.1 Reconcile the research corpus

- [ ] Inventory every document, prototype, test suite, RFC, audit, and generated artifact under `research/`.
- [ ] Map each artifact to one or more research items and stages in this plan.
- [ ] Identify duplicate, superseded, orphaned, and contradictory documents.
- [ ] Verify that links in `research/README.md` resolve and that the index reflects the current corpus.
- [ ] Preserve useful historical findings; do not delete an old result merely because a newer document supersedes it.
- [ ] Separate research notes, experiment specifications, implementation artifacts, test evidence, and decisions.
- [ ] Record the exact commit/revision and tool versions needed to reproduce each important result.

**Existing evidence:** `research/README.md` indexes the corpus; scenarios 01–33 and dependency-graph prototypes 01–29 are represented in the current research index. A repository-wide audit is also present.

**Status:** partially validated — the research index and taxonomy exist, but a full artifact-by-artifact reconciliation, duplicate/orphan audit, and reproducibility audit remain open.

### 0.2 Establish research quality and decision rules

- [ ] Use a consistent research structure: problem, hypotheses, prior art, alternatives, formal model, experiments, results, limitations, decision, and draft impact.
- [ ] Distinguish observations, assumptions, conjectures, experimental results, proofs, and accepted decisions.
- [ ] Require reproducible commands, fixtures, tool versions, and expected outputs for executable experiments.
- [ ] Record negative results and rejected alternatives.
- [ ] Link every proposed specification change to its supporting research and evidence.
- [ ] Ensure that `research/` remains exploratory and `draft/` remains the candidate specification.

**Exit criteria:** every existing research artifact is discoverable from an index; every major claim has an explicit evidence level; unresolved questions are linked to `TODO.md` or a clearly identified research item.

---

# Stage 1 — Semantic foundation and identity

**Order:** after Stage 0 inventory; foundational for all later stages.  
**Purpose:** define what a LLMLang program is and what exactly its identities commit to.

### 0.3 Research taxonomy and cross-aspect dependency map

- [x] Define the research taxonomy and identify the major LLMLang research areas.
- [x] Establish an initial directed dependency map with relationship types and confidence levels.
- [x] Identify feedback loops, foundational topics, and opportunities for parallel research.
- [ ] Validate and revise dependency edges as research produces evidence; the current map is an initial hypothesis, not a settled architecture.

**Evidence:** [Research taxonomy](research/RESEARCH-TAXONOMY.md) defines 18 research areas; [cross-aspect dependency map](research/RESEARCH-DEPENDENCY-MAP.md) records 35 initial dependency edges, research waves, and feedback loops.

**Status:** initial taxonomy and dependency map completed; ongoing validation remains part of each research task.

## 1.1 Semantic Program Graph and program representation

- [ ] Define the Semantic Program Graph (SPG) as a typed semantic representation.
- [ ] Define the relationship between Specification Graph, Design Graph, and Implementation Graph.
- [ ] Define semantic nodes, edges, ownership, references, and graph boundaries.
- [ ] Separate syntax trees, source text, semantic representation, provenance, and generated artifacts.
- [ ] Determine whether multiple source syntaxes can represent the same semantic graph.
- [ ] Define canonicalization and normalization rules.
- [ ] Define semantic graph evolution, node replacement, splitting, merging, and lineage.
- [ ] Decide artifact granularity: operations, interfaces, contracts, types, implementation components, tests, models, and proofs.
- [ ] Define how recursive and mutually dependent structures are represented.

**Existing evidence:** `research/LLMLang-CONCEPT.md` describes the SPG and the three logical graph layers; dependency-graph scenarios 18–28 explore requirement evolution, dependency discovery, and formal dependency analysis.

**Status:** researched and prototyped in parts. The concept and research taxonomy establish the graph direction and layers, but canonical graph schema, full node/edge semantics, lifecycle, and identity rules remain open.

## 1.2 Semantic identity, hashes, and canonical encoding

- [ ] Define the distinct roles of logical/stable IDs, semantic hashes, operation identity, implementation identity, action keys, artifact hashes, and evidence identity.
- [ ] Specify the exact semantic payload committed by `OpHash`.
- [ ] Specify `ImpHash` and the identity of a concrete implementation.
- [ ] Define the contract identity and the identity of a class of compatible implementations.
- [ ] Define canonical typed serialization, domain separation, digest encoding, and hash algorithm agility.
- [ ] Define hash-relevant versus descriptive, provenance, and evidentiary graph edges.
- [ ] Define cycle handling in hash dependencies.
- [ ] Define which target, ABI, runtime, toolchain, and configuration properties affect implementation identity.
- [ ] Define stable-ID lifecycle, including rename, split, merge, deprecation, and replacement.
- [ ] Define collision handling and migration policy.
- [ ] Specify the invariant that a semantic change affecting an implementation changes its `ImpHash`; determine the exact dependency propagation rules that make this automatic.

**Existing evidence:** `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`, `research/LLMLang-CONCEPT.md`, and the open questions LL-001–LL-008 in `TODO.md`.

**Status:** researched; decision pending on canonical envelopes, dependency boundaries, stable-ID lifecycle, and exact `OpHash`/`ImpHash` payloads. The current project plan explicitly defers locking identity choices until cross-aspect synthesis.

## 1.3 Contracts and compatible implementations

- [ ] Define contract structure and semantics: preconditions, postconditions, invariants, effects, errors, state transitions, and assumptions.
- [ ] Define the difference between exact contract equality, refinement, substitutability, and behavioral equivalence.
- [ ] Define how one operation can have many implementations and how one implementation can satisfy multiple contracts.
- [ ] Define contract-based analogue discovery separately from call identity and dispatch.
- [ ] Define the evidence required before substituting an implementation for a specific `OpHash`.
- [ ] Define verified adapters for compatible but non-identical contracts.
- [ ] Define what may be inferred automatically and what requires proof or explicit approval.
- [ ] Define evidence binding to exact semantic inputs, assumptions, target profile, and tool versions.

**Existing evidence:** global semantic artifact store research; operation identity and analogue-discovery questions LL-001–LL-003; requirement/contract work in scenarios 15–19.

**Status:** researched; decision pending on formal compatibility, refinement/substitution criteria, and the evidence needed for implementation selection.

## 1.4 Core language semantics (RT-03)

- [x] Survey the principal semantic dimensions: value/computation model, evaluation strategy, purity and state, errors and cancellation, determinism, effects and observations, concurrency, termination/resources, and module composition.
- [x] Compare four coherent candidate profiles: pure functional (A), imperative/linear (B), concurrent/actor (C), and effectful functional (D).
- [x] Record major compatibility tensions and cross-aspect implications for types, SPG/identity, dependency analysis, proofs, compiler/IR, runtime, cache, semantic merge, security, and conformance.
- [ ] Define a shared observable-behavior model and a representative semantic test corpus.
- [ ] Implement and compare small reference semantics for at least two viable profiles.
- [ ] Validate RT-03 dependency-map edges through concrete downstream research and experiments.
- [ ] Normalize the surviving vectors for whole-specification synthesis; do not select a profile or transfer it into `draft/` by implication.

**Evidence:** [RT-03 — Core Language Semantics](research/CORE-LANGUAGE-SEMANTICS.md).

**Status:** researched at the candidate-survey level; partially validated only as a map of options and trade-offs. No semantic profile, evaluation strategy, effect model, or complete observation model has been accepted. The existing QF_LIA/Lean/Logos work covers a narrow relational fragment and is not a complete language semantics.

**Next work:** reconcile candidate profiles with RT-04 type/effect/ownership/capability research; define observations and a shared test corpus; prototype at least two candidate reference semantics; update dependency edges as evidence arrives.

## 1.5 Prior-art study for semantic representation and identity

- [ ] Compare Unison's content-addressed code identity and codebase model.
- [ ] Compare Git's object model and DAG with semantic object identity.
- [ ] Compare LLVM IR identity and canonicalization limits.
- [ ] Compare content-addressed artifact stores and package registries.
- [ ] Identify which ideas can be reused without making a target IR or source syntax the semantic authority.

**Exit criteria:** a reviewed semantic object model; explicit identity table and canonicalization proposal; contract compatibility vocabulary and evidence model; remaining foundational decisions registered in `TODO.md`.

---

# Stage 2 — Formal semantics and verification foundation

**Order:** after the semantic objects and contract boundaries from Stage 1 are stable enough to formalize.  
**Purpose:** make language meaning precise and ensure that verification claims are independently checkable.

## 2.1 Formal semantics of the language

- [ ] Compare operational, denotational, and axiomatic semantics for the initial LLMLang core.
- [ ] Define an executable reference semantics for a deliberately small subset.
- [ ] Define observable behavior: return values, errors, state changes, I/O, resource behavior, concurrency, and declared effects.
- [ ] Define semantic equivalence and refinement.
- [ ] Define evaluation order, effects, error propagation, and state transitions.
- [ ] Define semantics of contracts and their composition.
- [ ] Define semantics-preserving transformations and compiler correctness boundaries.- [ ] Define assumptions and environmental boundaries explicitly.

**Existing evidence:** `research/LLMLang-FORMAL-VERIFICATION.md`, `research/LLMLang-CONCEPT.md`, typed requirement IR and formal dependency scenarios 25–33.

**Status:** partially researched; a complete language semantics is not yet established.

## 2.2 Proof architecture and proof boundary

- [ ] Determine which claims belong in Lean, SMT, specialized checkers, testing, or trusted runtime code.
- [ ] Define the trusted computing base for each proof claim.
- [ ] Define proof object formats, proof checking, provenance, and evidence reuse.
- [ ] Separate solver answers from independently checked proofs.
- [ ] Define exact binding between source-level assumptions, typed IR, serialized queries, and proof obligations.
- [ ] Define fail-closed behavior for unsupported or ambiguous constructs.
- [ ] Define how proof status is represented: candidate, unknown, checked, rejected, or proven.
- [ ] Define the relationship between proof validity and specification adequacy; a proof cannot establish that the specification captures user intent.

**Existing evidence:** scenarios 28–33, prototype 29, Lean CPC parser-state binding prototype, Logos integration, and `research/LLMLang-FORMAL-VERIFICATION.md`.

**Status:** partially validated; pinned Lean 4.34.0 / Logos build and the complete parser-state, typed-renderer, and JSON decoder test step passed in CI run [44175854422](https://github.com/aivibeflow/LLMLang/actions/runs/44175854422) on commit `08076b9e95e5b1bfc2368fc00b049efea620b9b4`. `SourceQuerySemantics` compiled successfully, so `translateExpr_preserves_eval` was kernel-checked for the deliberately small pure Int/Bool expression fragment. This is not a proof of source-program-to-query translation, command/program semantics, paired execution, CPC assumption binding end-to-end, or whole-program correctness. Keep those boundaries explicit.

## 2.3 Lean, Logos, SMT, and solver integration

- [x] Complete explicit Lean build and test validation for the pinned Lean 4.34.0 environment and pinned Logos revision; CI run [44175854422](https://github.com/aivibeflow/LLMLang/actions/runs/44175854422) passed all build and test steps.
- [x] Implement the CPC parser-state bridge and exact symbol identity binding; obtain a successful pinned CI build and adversarial validation (CI run 44175854422 passed the existing parser-state tests).
- [x] Implement construction of expected `Eo.Term` values from the canonical typed Relational Query IR; the pinned CI renderer and AST-equivalence tests pass. Full end-to-end validation against source-derived CPC assumptions remains open.
- [x] Implement strict versioned JSON decoding and rejection of malformed or unsupported input; the full pinned CI test step, including adversarial decoder tests, passes.
- [x] Kernel-check the expression-level source-to-query preservation theorem for the typed pure Int/Bool expression fragment (`SourceQuerySemantics.lean`, CI run 44175854422); [ ] prove source-to-query correspondence for the actual canonical relational query encoder and expand to commands/paired program executions.
- [ ] Verify the exact assumption list and query binding adversarially, including malformed inputs, duplicate/extra declarations, wrong sorts, and mismatched query assumptions.
- [ ] Keep QF_LIA as a conservative profile; reject unsupported strings, nonlinear arithmetic, and constructs outside the profile.
- [ ] Test SAT/UNSAT/UNKNOWN handling and solver protocol failures.
- [ ] Record what is checked by Lean, what is trusted in Logos, and what remains outside the proof boundary.

**Existing evidence:** scenarios 29–33; `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`; QF_LIA Python prototype and focused tests; CI workflow.

**Status:** partially validated. The pinned Lean/Logos build and complete current test suite pass (run 44175854422). The expression-level theorem is kernel-checked for its stated fragment. Exact source-to-query correspondence, complete CPC assumption binding to the original query, and program-level proof obligations remain open.

## 2.4 Correctness of optimization and translation

- [ ] Define proof obligations for semantic graph rewrites.
- [ ] Define proof obligations for compiler optimizations.
- [ ] Study translation validation versus proving the optimizer correct.
- [ ] Evaluate Alive2 and related LLVM validation techniques.
- [ ] Define differential and property-based testing against reference semantics.
- [ ] Define when testing is sufficient evidence and when formal proof is required.

**Prior art:** Lean, SMT solvers, TLAPS, Dafny, K Framework, Vellvm, Alive2.

**Status:** not started as a complete LLMLang-wide verification architecture; prior-art research and selected formal prototypes exist.

**Exit criteria:** a small, executable reference semantics; at least one end-to-end, independently checked proof path with explicit assumptions; a documented trusted computing base; reproducible CI validation.

---

# Stage 3 — Dependency graph, incremental computation, and cache

**Order:** after Stage 1 identity and Stage 2 semantic/proof boundaries are sufficiently defined.  
**Purpose:** compute only what has actually been invalidated while preserving soundness.

## 3.1 Semantic dependency model

- [ ] Define semantic dependencies separately from provenance, audit observations, and traceability.
- [ ] Define hash-relevant dependency edges and dependency closure.
- [ ] Define how dependencies are discovered from static analysis, typed IR, runtime observations, tests, and formal semantics.
- [ ] Define confidence/evidence classes for dependency edges.
- [ ] Define sound conservative may-depend graphs.
- [ ] Define how missing or incomplete dependency evidence affects reuse.
- [ ] Define cycles and strongly connected components for analysis and scheduling.
- [ ] Define change-impact analysis for requirement, contract, design, implementation, and target changes.

**Existing evidence:** scenarios 18–28 and prototypes 18–28 in `research/PROTOTYPES/DEPENDENCY-GRAPH-01/`.

**Status:** extensively researched and prototyped in Scenarios 18–28 and dependency-graph prototypes 18–28; completeness, integration with the full semantic model, and end-to-end soundness remain open.

## 3.2 Incremental analysis and invalidation

- [ ] Define invalidation for type checking, contract checking, optimization, code generation, tests, and proofs.
- [ ] Define the difference between semantic impact and evidence staleness.
- [ ] Define how an `ImpHash` change propagates through dependent semantic nodes and action results.
- [ ] Define safe reuse when only non-semantic metadata changes.
- [ ] Define conservative fallback when dependency completeness cannot be established.
- [ ] Define impact planning and non-interference gates.
- [ ] Benchmark small local edits, shared component edits, and broad semantic changes.

**Existing evidence:** `research/SEMANTIC-COMPILATION-CACHE.md`, scenarios 18–28, and dependency graph prototypes.

**Status:** researched and prototyped in parts; full compiler integration and empirical validation are not implemented.

## 3.3 Semantic build and cache graph
- [ ] Define optional package-distributed cache-index files for validation, compilation, analysis, tests, and proofs; decide whether indexes and result payloads are embedded or separately fetched.
- [x] Establish the version-identity split for cache records: composite `LanguageVersion`, append-only component-registry digest, and separate `ToolchainIdentity`; record the candidate design in `research/LANGUAGE-VERSIONING.md`.
- [x] Add an experimental version-bound cache-record validator and tests covering language-version, registry-digest, and toolchain changes to Action Key inputs. This remains a prototype, not a normative cache-index format.
- [ ] Bind every cached result to exact Action Key inputs and complete dependency closure; define compatibility evidence for reuse across different language or toolchain identities.
- [ ] Define cache-index merge, conflict handling, artifact availability/eviction, and trust/evidence checks.

- [ ] Define typed build actions and their inputs/outputs.
- [ ] Keep Semantic Hash, Action Key, and Artifact Hash distinct.
- [ ] Include tool identity, tool version, configuration, target, environment, runtime, and policy inputs whenever they can affect a result.
- [ ] Define deterministic versus nondeterministic action handling.
- [ ] Define local, workspace, remote, and global cache layers.
- [ ] Define cache integrity, trust, provenance, and eviction.
- [ ] Define test and proof evidence caching with exact subject and assumption binding.
- [ ] Define behavior for incomplete dependency closure: invalidate conservatively or disable caching.
- [ ] Define reproducibility requirements and cache poisoning defenses.

**Existing evidence:** `research/SEMANTIC-COMPILATION-CACHE.md`, `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`, `research/COMPILATION-CACHE-SPEEDUP-ESTIMATE.md`, [Language Versioning](research/LANGUAGE-VERSIONING.md), and the exploratory [Package Identity Prototype 01](research/PROTOTYPES/PACKAGE-IDENTITY-01/README.md).

**Status:** researched; the version-binding design and a first experimental cache-record validator now exist. The initial component registry is `language-components.toml` and is append-only. The candidate validator keeps LanguageVersion, registry digest, and ToolchainIdentity distinct and includes them in Action Key construction. The cache-index wire format, compatibility declarations, complete dependency-closure model, merge/conflict policy, and broader implementation validation remain open.

## 3.4 Quantify compilation speedup

- [ ] Validate the analytical model in `COMPILATION-CACHE-SPEEDUP-ESTIMATE.md`.
- [ ] Implement reproducible benchmarks for cold, warm, local-edit, component-edit, and broad-change builds.
- [ ] Measure cache hit rates by action type.
- [ ] Measure hashing, dependency discovery, scheduling, storage, and verification overhead.
- [ ] Compare against clean and conventional incremental builds in representative Rust, Go, and C++ projects.
- [ ] Report speedup distributions and workload assumptions rather than a single headline number.
- [ ] Identify workloads where caching is neutral or slower.

**Status:** analytical estimate researched in `research/COMPILATION-CACHE-SPEEDUP-ESTIMATE.md`; empirical benchmark results still required.

**Exit criteria:** a dependency-completeness policy; sound action-key model; tests showing that relevant changes invalidate all affected results and irrelevant changes preserve valid results; reproducible benchmark data.

---

# Stage 4 — Semantic storage, versioning, and Git integration

**Order:** after identity and dependency boundaries are stable enough to persist.  
**Purpose:** make semantic programs durable, portable, reviewable, and mergeable in ordinary repositories.

**Current workstream status:** Git representation and semantic merge research is completed at concept level. The full report is [Git semantic repository research](research/GIT-SEMANTIC-REPOSITORY.md); [ADR-014](docs/adr/014-git-semantic-merge.md) records a **Proposed** direction, not an irreversible accepted architecture. Implementation and benchmarking are deferred until cross-aspect synthesis.

## 4.1 Semantic object storage

- [ ] Compare KV databases, content-addressed object stores, relational indexes, and filesystem layouts.
- [ ] Define canonical object encoding and immutable object lifecycle.
- [ ] Define indexes for graph traversal, reverse dependencies, contracts, and implementation discovery.
- [ ] Define transactions and atomic publication of graph revisions.
- [ ] Define garbage collection and reachability.
- [ ] Define crash recovery, corruption detection, backup, and replication.
- [ ] Define local repository storage versus shared/global artifact storage.
- [ ] Define portability without requiring a live external database.

**Existing evidence:** `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md` and the current Git representation research.

**Status:** researched at architectural level; storage prototype and recovery tests remain open.

## 4.2 Git representation and repository model

- [ ] Define the canonical Git-visible representation of a semantic program.
- [ ] Compare storing canonical serialized semantic objects directly in Git with storing KV-backed objects plus repository manifests.
- [ ] Define the mapping between Git commits/trees and semantic graph snapshots.
- [ ] Preserve ordinary Git clone, fetch, push, branch, tag, and history behavior.
- [ ] Define readable textual representation, diff strategy, and generated metadata.
- [ ] Define how large objects and binary artifacts are handled.
- [ ] Define repository portability and reproducibility from a clean clone.

**Existing evidence:** `research/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md`.

**Status:** researched; implementation and interoperability tests remain open.

## 4.3 Semantic diff, merge, and conflict resolution

- [ ] Define semantic diff independently of textual diff and AST diff.
- [ ] Define three-way merge over semantic graph snapshots.
- [ ] Define conflict classes: same-node edits, contract/implementation divergence, identity collisions, dependency conflicts, split/merge conflicts, and metadata-only conflicts.
- [ ] Define automatic merge when changes are provably independent.- [ ] Define conservative conflict behavior when independence cannot be established.
- [ ] Define interactive conflict resolution and preservation of both alternatives.
- [ ] Define post-merge validation: graph integrity, type checking, contract checking, dependency completeness, tests, and proofs.
- [ ] Define merge reproducibility and audit history.

## 4.4 Git integration workflow

- [ ] Prototype a Git merge driver that invokes the LLMLang semantic merge tool.
- [ ] Prototype a Git mergetool integration for interactive conflicts.
- [ ] Define clean fallback behavior when the tool is unavailable.
- [ ] Test merges in normal Git workflows and across operating systems.
- [ ] Verify that merge drivers do not silently discard unresolved semantic conflicts.
- [ ] Document repository setup and team workflows.

**Exit criteria:** clean clone reconstructs the program; commits map deterministically to semantic snapshots; semantic diff/merge works on independent and conflicting changes; Git fallback and interactive resolution are tested.

---

# Stage 5 — Types, execution model, runtime, and POSIX

**Order:** after the semantic core and initial proof boundary; a small vertical slice should be chosen early.  
**Purpose:** define what programs mean when executed and how LLMLang interacts with systems.

## 5.1 Type system and data model

- [ ] Define primitive and algebraic data types.
- [ ] Compare structural and nominal typing.
- [ ] Research generic and polymorphic types.
- [ ] Evaluate refinement types and dependent types.
- [ ] Define typed states, state transitions, and constrained values.
- [ ] Define ownership, borrowing, lifetimes, references, and aliasing.
- [ ] Define mutability and resource management.
- [ ] Define effects, capabilities, and error types.
- [ ] Define type inference and explicit annotations.
- [ ] Define compatibility between types exposed by different implementations.
- [ ] Determine which guarantees are enforced by types, contracts, or proofs.

**Existing evidence:** concept and formal-verification research; typed requirement and typed relational IR prototypes.

**Status:** partially researched; complete language type-system design remains open.

## 5.2 Execution semantics and runtime architecture

- [ ] Define interpreter/reference execution.
- [ ] Define VM requirements, if a VM is needed.
- [ ] Define runtime representation of values and semantic calls.
- [ ] Define explicit call binding to immutable operation identity.
- [ ] Define error propagation, cancellation, and resource cleanup.
- [ ] Define memory model and concurrency semantics.
- [ ] Define threads, synchronization, atomics, signals, blocking I/O, and scheduling boundaries.
- [ ] Define capability and security model.
- [ ] Define trusted low-level primitives and their contracts.
- [ ] Define runtime versioning and its contribution to implementation identity.

**Status:** partially researched at concept level; execution model and runtime implementation are open.

## 5.3 POSIX architecture and conformance

- [ ] Select initial POSIX edition and explicit conformance profile.
- [ ] Define LLMLang-facing API: close POSIX mapping versus safer typed facade.
- [ ] Define a shared contract for multiple POSIX implementations.
- [ ] Separate portable runtime implementation from native Linux syscall implementation.
- [ ] Define conformance evidence, optional features, and implementation-defined behavior.
- [ ] Define error, resource, process, file, and descriptor semantics.
- [ ] Define concurrency and environment-dependent behavior.
- [ ] Define initial vertical slice, such as process startup, basic file I/O, and errors.
- [ ] Select initial Linux architecture and isolate syscall ABI details.
- [ ] Define how existing C libraries and external ABI boundaries are called.
- [ ] Define the trusted low-level runtime boundary.
- [ ] Compare behavior using conformance, differential, and contract-derived tests.
- [ ] Define precisely what POSIX compatibility and formal verification claims cover.

**Existing evidence:** `research/POSIX-RUNTIME-ARCHITECTURE.md`; related open questions LL-013–LL-019 in `TODO.md`.

**Status:** researched at architectural level in `research/POSIX-RUNTIME-ARCHITECTURE.md`; POSIX edition/profile, API, vertical slice, conformance evidence, and implementation decisions remain open.

**Exit criteria:** a small typed executable subset; reference execution; one POSIX vertical slice with explicit contracts and conformance scope; tests for observable behavior and error cases.

---

# Stage 6 — Translation, backends, implementation selection, and optimization

**Order:** after a reference semantics and a stable semantic subset exist.  
**Purpose:** realize the same source semantics on multiple targets without making any target language the source of truth.

## 6.1 Translation architecture

- [ ] Decide whether backends consume typed SPG directly or a normalized target-independent semantic IR.
- [ ] Define the lowering pipeline and preservation obligations.
- [ ] Define target capability declarations and unsupported constructs.
- [ ] Define explicit translation outcomes: exact under assumptions, preserved with runtime support, restricted, unsupported, and unverified.
- [ ] Define runtime support as part of a target realization.
- [ ] Define generated artifact identity and reproducibility.
- [ ] Define verification independent of the code generator wherever practical.
- [ ] Define incremental translation and selective verification invalidation.

**Existing evidence:** `research/TRANSLATION-AND-TARGET-BACKENDS.md`, `research/LLVM-BACKEND-ARCHITECTURE.md`, and formal-verification research.

**Status:** researched at architectural level in `research/TRANSLATION-AND-TARGET-BACKENDS.md`; backend contract, source semantics, and preservation theorem remain open.

## 6.2 Backend selection and cross-backend validation

- [ ] Define the minimal common semantic subset for backend experiments.
- [ ] Evaluate Python as an experimental/reference target.
- [ ] Evaluate Go as the first serious compiled target.
- [ ] Evaluate Rust for ownership and systems-language coverage.
- [ ] Evaluate C++ for ABI and platform coverage.
- [ ] Consider Java as an alternative compiled target.
- [ ] Implement two backends for the same subset.
- [ ] Compare each backend against the same reference semantics and scenario corpus.
- [ ] Compare return values, errors, state changes, and declared observable effects.
- [ ] Reject silent semantic weakening; report restrictions explicitly.

**Existing evidence:** target selection recommendation in `research/TRANSLATION-AND-TARGET-BACKENDS.md`.

**Status:** researched as a recommendation; no first target is formally selected and no complete cross-backend validation exists.

## 6.3 LLVM backend

- [ ] Define LLVM's role as a replaceable backend, not the canonical LLMLang semantic representation.
- [ ] Define a conservative LLVM IR subset and lowering contract.
- [ ] Research poison, undef, overflow flags, pointer semantics, aliasing, floating-point flags, and memory ordering.
- [ ] Define how LLVM optimization passes are validated against LLMLang semantics.
- [ ] Evaluate Alive2 and Vellvm and their applicability/limitations.
- [ ] Define supported LLVM versions and reproducible toolchain identity.
- [ ] Test generated code against reference semantics.

**Existing evidence:** `research/LLVM-BACKEND-ARCHITECTURE.md`.

**Status:** researched in `research/LLVM-BACKEND-ARCHITECTURE.md`; implementation, lowering validation, and target-specific correctness evidence remain open.

## 6.4 Implementation discovery, selection, and optimization

- [ ] Separate discovery of contract-compatible implementations from selection of a concrete implementation.
- [ ] Define selection constraints: target, ABI, capabilities, runtime, security, performance, and deployment environment.
- [ ] Define static binding versus runtime dispatch.
- [ ] Define specialization and multi-versioning.
- [ ] Define cost models and profile-guided selection.
- [ ] Define safe fallback when no compatible implementation is available.
- [ ] Define whether and how implementation choice can change without changing operation semantics.
- [ ] Measure dispatch and adaptation overhead.
- [ ] Define optimization across semantic nodes while preserving contracts.

**Existing evidence:** global semantic artifact store and POSIX runtime architecture.

**Status:** partially researched; selection semantics and policy remain open.

**Exit criteria:** two backends preserve the same reference semantics for a defined subset; target limitations are explicit; implementation selection never bypasses operation identity or compatibility evidence.

---

# Stage 7 — Scale, ecosystem, collaboration, and adoption

**Order:** after the core vertical slice; some prior-art research can start earlier.  
**Purpose:** determine whether LLMLang remains practical for large codebases and real teams.

## 7.1 Performance and scalability

- [ ] Benchmark semantic graph size and traversal.
- [ ] Benchmark canonicalization and hashing.- [ ] Benchmark dependency discovery and impact planning.
- [ ] Benchmark compilation and cache performance.
- [ ] Benchmark proof and test execution costs.
- [ ] Benchmark storage, indexing, and garbage collection.
- [ ] Benchmark large repositories and highly connected graphs.
- [ ] Benchmark concurrent edits and merge operations.
- [ ] Compare with Rust, Go, and C++ workflows on representative projects.
- [ ] Report memory, latency, throughput, cache hit rates, and confidence intervals.
- [ ] Identify pathological workloads and fallback strategies.

## 7.2 Libraries, packages, templates, and artifact ecosystem

### Package indexes and dynamic package delivery
- [ ] Define optional derived-result cache indexes in package archives and their integration with the semantic action cache; indexes must be independently omittable and must not affect logical package identity.

- [ ] Define the logical package-content model: roots, included objects, typed dependency edges, exports, modules, evidence, and provenance.
- [ ] Define compact canonical binary index tables and their key ordering; require binary-search and deterministic streaming-merge semantics.
- [ ] Compare whole-index compression with independently compressed blocks; measure codec, block-size, lookup, scan, and memory trade-offs.
- [ ] Evaluate optional sparse and hierarchical sparse indexes; establish when their lookup benefit justifies their storage and maintenance cost.
- [ ] Define index integrity, corruption detection, sparse-index reconstruction, and logical-versus-physical index identity.
- [x] Draft a human-readable TOML manifest schema candidate and an illustrative manifest fixture; keep binary encoding for machine indexes and object payloads where their formats require it.
- [x] Draft the Package Content Root Hash projection, identity exclusions, and validation invariants independently of raw TOML bytes and physical archive encoding.
- [x] Implement an exploratory executable package-identity model and focused fixtures for PMI-001–PMI-014; record its limits and test evidence.
- [ ] Review and validate the manifest schema, canonical typed hash encoding, and digest algorithm with independent implementations and adversarial fixtures before treating them as stable.
- [ ] Define static package archive and optional generated human-readable index (for example, `INDEX.md`) derived from the machine index.
- [ ] Define Dynamic Package requests by exact root Content Hash values and explicit dependency policies.
- [ ] Define exact-hash transitive dependency closure, optional/target/feature dependency semantics, and fail-closed missing-dependency behavior.
- [ ] Define provider snapshot consistency, deterministic logical package roots, and separation of content from delivery metadata.
- [ ] Define multi-provider index merge, availability metadata, selective retrieval, and trust/provenance boundaries.
- [ ] Prototype and benchmark small, medium, and large indexes plus dynamic dependency-closure construction.

**Existing evidence:** [Package System: Static and Dynamic Packages](research/PACKAGE-SYSTEM.md), extending the earlier [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md) and [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md) proposals.

**Status:** researched and prototyped at an exploratory level. A candidate TOML manifest schema, example fixture, Package Content Root Hash projection, identity exclusions, and PMI-001–PMI-014 invariants are documented; an independent Python prototype exercises these invariants (18 focused tests pass). Provider-side closure resolution, actual static/dynamic builders, binary index encoding, compression, and sparse lookup remain unimplemented. No normative wire format, codec policy, provider protocol, cache-index schema, final manifest schema, canonical hash encoding, or digest algorithm has been accepted.


- [ ] Define Package versus Library boundaries.
- [ ] Define library identity and public machine-readable contracts.
- [ ] Define dependency resolution and versioning.
- [ ] Define template instantiation, customization, detachment, and migration.
- [ ] Define global semantic artifact store and registry interfaces.
- [ ] Define artifact publication, signing, mirroring, licensing, revocation, retention, and garbage collection.
- [ ] Separate content integrity from publisher trust and licensing rights.
- [ ] Define opaque implementation evidence and verification limitations.

**Existing evidence:** `research/LIBRARIES-AND-TEMPLATES.md` and `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`; related TODO items LL-006–LL-012.

**Status:** researched in `research/LIBRARIES-AND-TEMPLATES.md`, `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`, and `research/PACKAGE-SYSTEM.md`; package/index/provider design is proposed but not accepted, and operational policy, benchmarks, and trust implementation remain open.

## 7.3 Parallel development and collaboration

- [ ] Define concurrent graph edits and optimistic update rules.
- [ ] Define stable identity under rename, split, and merge.
- [ ] Define independent changes to contracts and implementations.
- [ ] Define conflict detection and safe automatic resolution.
- [ ] Define reviewable semantic change sets.
- [ ] Define provenance, authorship, approval, and audit trails.
- [ ] Define collaboration across branches, forks, and shared artifact registries.
- [ ] Test large multi-contributor scenarios.

**Existing evidence:** requirement evolution and semantic impact scenarios 18–19; Git semantic merge research.

**Status:** partially researched; end-to-end team workflow remains open.

## 7.4 Security, trust, and reproducibility

- [ ] Define trust boundaries among LLM authors, compiler, runtime, plugins, external tools, and artifact registries.
- [ ] Define deterministic validation independent of LLM claims.
- [ ] Define supply-chain provenance and signed evidence.
- [ ] Define sandboxing and capability restrictions for generated code.
- [ ] Define cache poisoning and malicious artifact defenses.
- [ ] Define secret handling and isolation of build/test environments.
- [ ] Define reproducible builds and attestations.
- [ ] Define recovery and revocation when a tool, proof checker, or implementation is compromised.

**Status:** not yet consolidated into a complete security architecture; this is a high-priority research gap.

## 7.5 Developer experience and adoption

- [ ] Define human-readable source and semantic review workflows.
- [ ] Define diagnostics that explain semantic impact and failed contracts.
- [ ] Define editor, language-server, and debugging requirements.
- [ ] Define migration and interoperability with existing languages and build systems.
- [ ] Evaluate learning curve and review quality for human developers.
- [ ] Evaluate LLM authoring workflows without treating generated output as trusted.
- [ ] Build representative end-to-end examples.
- [ ] Define practical adoption criteria and migration strategy.

**Status:** not started as a systematic study; initial authoring-protocol material exists in the Development Engine RFC, but DX/adoption evidence is not yet systematic.

**Exit criteria:** representative large-project benchmarks; working collaboration and recovery workflows; documented trust/security model; practical developer workflow evaluated with real tasks.

## 7.6 Toolchain Server and semantic development API (RT-19)

- [x] Identify the architectural gap between the existing Development Engine RFC and an operational agent-facing Toolchain API.
- [x] Draft a research proposal for a transport-neutral domain API with MCP, CLI, IDE, and CI adapters.
- [x] Define candidate Workspace, Change Set, immutable Snapshot, and typed mutation-envelope responsibilities.
- [x] Draft ADR-015 as a Proposed decision record with explicit non-decisions and validation gates.
- [x] Implement Prototype 01 for in-memory immutable objects/snapshots, isolated workspaces, typed changes, optimistic checks, acceptance, and single-file import/export.
- [x] Add a focused Python test suite and GitHub Actions workflow for the prototype.
- [x] Record the Git-authoritative/reconstructible-store boundary from Proposed ADR-014; do not silently change the ADR.
- [ ] Compare in-memory and persistent embedded backends behind one storage contract.
- [ ] Specify transaction, crash-recovery, and cross-boundary acceptance/export/commit state machines.
- [ ] Specify semantic import/export, external-edit detection, and atomic multi-file publication.
- [ ] Specify optimistic concurrency, multi-agent workspaces, idempotency, and conflict handling.
- [ ] Specify MCP Tools/Resources/Prompts schemas and independently test them with an MCP client.
- [ ] Prototype deterministic import/change/validate/accept/export/re-import as one vertical slice.
- [ ] Add failure-injection, security, authorization, and comparative source-editing tests.

**Existing evidence:** [RT-19 research proposal](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) builds on [Development Engine RFC](research/RFC-DEVELOPMENT-ENGINE.md), [Git semantic repository research](research/GIT-SEMANTIC-REPOSITORY.md), and [ADR-014](docs/adr/014-git-semantic-merge.md).

**Status:** proposal and Proposed ADR-015 drafted; a narrow in-memory lifecycle prototype and focused CI test workflow are present. No API contract, persistent storage backend, multi-file synchronization algorithm, MCP surface, or ADR has been accepted. The prototype is evidence for workflow mechanics only, not implementation completion.

**Exit criteria:** deterministic round-trip identity; stale/conflicting mutations rejected; accepted snapshots immutable; multiple workspaces isolated; crash/restart and export interruption recover safely; external edits are detected; MCP adapter independently tested; authorization and benchmark results documented.

---

## 7.7 LLM patch planning, caller migration, hash propagation, and verified commit (RT-20)

- [x] Capture the requirement that the complete function-change plan must be established before implementation.
- [x] Separate upward contract propagation from hash/reference propagation through callers.
- [x] Record per-call-site compatibility decisions: migrate to a new callee version, preserve the old immutable version, adapt, fork, or remain unresolved.
- [x] Require shared-caller version-split analysis when different consumers need old and new behavior.
- [x] Define a candidate Change Impact Plan (CIP), plan-completeness checks, and mandatory plan execution.
- [x] Specify the proposed completion gate: freeze candidate, verify plan coverage, validate and audit exact hashes, then create a Git commit only on success.
- [ ] Reconcile the function hashId and call-reference assumptions with the canonical identity model in RT-05.
- [ ] Specify reverse-reference completeness for direct, indirect, dynamic, external, and generated call sites.
- [ ] Prototype single-chain propagation, mixed old/new callers, shared-caller splits, multiple call sites, and branching/converging graphs.
- [ ] Prove that unplanned mutations and omitted planned changes are rejected.
- [ ] Prototype failed-validation/no-commit, exact-tree commit, concurrency rejection, and idempotent retry behavior.
- [ ] Reconcile the completion transaction with RT-19 persistence, crash recovery, atomic export, and Git coordination.

**Evidence:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) records the proposed workflow and invariants. It is a research proposal, not an accepted identity or Toolchain decision.

**Status:** workflow proposal drafted from design discussion. No caller-migration planner, hash-closure engine, plan-enforcement mechanism, or validation-gated commit implementation exists yet.

**Exit criteria:** a complete server-validated plan precedes all mutations; every relevant call site has an evidence-backed compatibility decision; contract and hash propagation are independently correct; old/new behavior and shared-caller version splits work; every planned change is enforced; commit is created only for the exact candidate that passed all mandatory checks.

---

# 4. Cross-cutting prior-art research

This is a continuous comparative track. It informs the stages above but does not replace LLMLang-specific experiments.

| System / technology | Research focus | Relevant stages |
|---|---|---|
| LLVM | IR, lowering, optimization, backend and ABI boundaries | 2, 5, 6 |
| Rust | Ownership, borrowing, lifetimes, type system, systems runtime | 5, 6, 7 |
| Lean | Formalization, proof checking, trusted kernel, executable semantics | 2 |
| TLAPS | Proof of system properties and compositional reasoning | 2 |
| SMT solvers | Constraint encoding, solver protocols, proof evidence, unknown results | 2, 3 |
| Dafny | Contracts, refinement, verification workflow | 1, 2, 5 |
| K Framework | Executable formal semantics and language definition | 2 |
| Vellvm | Formal LLVM semantics and compiler correctness | 2, 6 |
| Alive2 | Translation validation for LLVM optimizations | 2, 6 |
| Bazel / Skyframe | Dependency graphs, incremental evaluation, action caching | 3 |
| Salsa | Incremental computation and dependency tracking | 3 |
| Adapton | Demand-driven incremental computation | 3 |
| Nix | Reproducible, content-addressed builds and dependency isolation | 3, 4, 7 |
| Git | Object model, DAG history, merge drivers, mergetool integration | 4 |
| Unison | Content-addressed code identity and semantic naming | 1, 4 |
| POSIX | Standardized interfaces, conformance, implementation-defined behavior | 5 |
| C / C++ ABIs | Interoperability, memory layout, calling conventions, platform boundary | 5, 6 |
| Package and artifact registries | Distribution, trust, provenance, licensing, retention | 7 |

For each system, record: the specific problem it solves, its model, what can be reused, what cannot be reused, the assumptions it makes, and the LLMLang experiment needed to validate applicability.

---

# 5. Current known research baseline

The following is a snapshot of known work, not a claim that all corresponding questions are resolved.

| Area | Existing artifacts / evidence | Current assessment |
|---|---|---|
| Core concept and SPG | `LLMLang-CONCEPT.md` | Researched; semantic model still evolving |
| Formal verification architecture | `LLMLang-FORMAL-VERIFICATION.md` | Researched; complete formal semantics not finished |
| Typed requirements and contracts | Scenarios 15–19; prototypes 16–19 | Prototyped; broader language integration remains |
| Dependency discovery and impact | Scenarios 20–28; prototypes 20–28 | Extensively prototyped; sound end-to-end completeness remains |
| SMT/proof boundary | Scenarios 29–34; Logos/Lean binding prototype; QF_LIA profile and typed query IR | Partially validated; pinned Lean CI build and current tests pass; QF_LIA path remains restricted/candidate and source-to-query/program-level correspondence remains unproved |
| Semantic compilation cache | `SEMANTIC-COMPILATION-CACHE.md` | Researched; implementation and empirical validation remain |
| Cache speedup estimate | `COMPILATION-CACHE-SPEEDUP-ESTIMATE.md` | Analytical estimate exists; benchmarks remain |
| POSIX runtime | `POSIX-RUNTIME-ARCHITECTURE.md` | Researched; profile and vertical slice remain open |
| Translation/backends | `TRANSLATION-AND-TARGET-BACKENDS.md` | Researched; backend implementation remains |
| LLVM backend | `LLVM-BACKEND-ARCHITECTURE.md` | Researched; lowering and validation remain |
| Libraries and templates | `LIBRARIES-AND-TEMPLATES.md` | Researched; detailed decisions remain |
| Global artifact store | `GLOBAL-SEMANTIC-ARTIFACT-STORE.md` | Researched; store and trust implementation remain |
| Git representation and semantic merge | `GIT-SEMANTIC-REPOSITORY.md`; ADR-014 | Research completed at concept level; ADR-014 is Proposed; implementation and merge evaluation deferred |
| Toolchain Server and semantic development API | `RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md`; Development Engine RFC | Proposal drafted; API, storage, synchronization, MCP adapter, and failure semantics remain unvalidated |
| Security and developer experience | Distributed across concept and architecture notes | Needs systematic research |

The research index currently includes Scenarios 01–34 and the dependency-graph prototypes. The scenario numbering is a historical sequence, not a substitute for the stage ordering in this plan. The scenario numbering is a historical sequence, not a substitute for the stage ordering in this plan.

---

# 6. Research vectors and integrated specification synthesis

The project must not treat an individual research report as producing one mandatory answer. Each research may identify multiple promising development vectors (approaches, design choices, or internally coherent option families), including assumptions, trade-offs, constraints, evidence, and unresolved questions.

## 6.1 Required output of each research

Each research report should, where applicable, provide:

- A clearly scoped aspect of LLMLang and the questions investigated.
- Multiple viable development vectors rather than only one preferred recommendation. Do not manufacture alternatives when only one viable vector is known.
- For each vector: principles, assumptions, benefits, costs, risks, limitations, and evidence.
- Compatibility requirements, constraints, and known incompatibilities with other aspects.
- Upstream dependencies and downstream impact, linked to the dependency map.
- Open questions and confidence/evidence level; distinguish facts from hypotheses and recommendations.

For each new report, update the research taxonomy and affected dependency-map edges before marking the research complete.

## 6.2 Cross-aspect dependency model

Maintain explicit directed relationships:

- **Requires:** one aspect/vector depends on another.
- **Constrains:** a choice narrows viable choices elsewhere.
- **Influences:** a choice changes trade-offs without making other choices impossible.
- **Conflicts with:** two choices cannot coexist under stated assumptions.
- **Enables:** a choice makes another capability or vector practical.

Each edge must record rationale, affected vectors, direction, and confidence. Revisit edges when evidence changes assumptions. Use the map to identify foundational topics, downstream topics, feedback loops, and parallel work.

## 6.3 Research order

Research order is dependency-driven, not simply the order topics were proposed. The current provisional sequence is:

1. Goals, constraints, and semantic foundations.
2. Program representation and identity.
3. Core language semantics, types, effects, ownership, and concurrency.
4. Specification and verification model.
5. AI-native authoring and change model.
6. Build, incremental computation, and tooling.
7. Version control and collaboration.
8. Runtime, deployment, interoperability, and ecosystem.

This is a dependency hypothesis, not a rigid serial schedule. Independent subtopics may proceed in parallel using explicit provisional assumptions.

## 6.4 Synthesis: from vectors to complete specifications

After relevant research coverage is sufficient:

1. Normalize vectors into a common decision/option model, preserving links to evidence.
2. Identify mutually compatible, conditionally compatible, dependent, and conflicting vectors.
3. Construct the Cartesian product of viable vector sets as the initial candidate specification space.
4. Eliminate or mark combinations violating explicit compatibility constraints; do not silently treat every combination as valid.
5. Preserve traceability from each candidate choice to research, evidence, assumptions, and dependency edges.
6. Compare complete candidate specifications as integrated wholes using shared criteria: coherence, correctness, expressiveness, simplicity, feasibility, performance, incremental behavior, AI-agent usability, interoperability, and evolvability.
7. Use pairwise/local analysis only as diagnostic tools; the primary comparison unit is the complete candidate specification.
8. If exhaustive enumeration is impractical, use documented constraints, equivalence classes, staged enumeration, or representative sampling without losing promising vectors.

## 6.5 Synthesis status

| Activity | Status | Exit condition |
|---|---|---|
| Define research taxonomy and initial dependency map | **Completed** | 18 research areas and 35 initial dependency edges are documented; ongoing updates remain required |
| Conduct and complete aspect research | **In progress** | RT-03 now has a candidate-profile survey; semantic validation/reference semantics, types/effects/ownership, security, and other gaps remain |
| Normalize vectors and validate compatibility | **Not started** | Common option schema and conditional compatibility constraints are defined |
| Generate candidate specification space | **Not started** | Valid combinations are enumerated or represented by a documented constrained search |
| Compare complete candidate specifications | **Not started** | Integrated candidates are evaluated against shared criteria and representative scenarios |
| Select and baseline a specification direction | **Not started** | A coherent candidate is selected with rationale and unresolved risks recorded |

# 7. Cross-stage invariants

These invariants guide every research and implementation stage:

1. **Semantic source of truth:** target languages, generated code, and backend IRs do not redefine LLMLang semantics.
2. **Explicit operation identity:** a call identifies the intended immutable operation semantics; analogue discovery is a separate optimization.
3. **Explicit implementation identity:** a concrete implementation has its own identity, including all semantics-relevant inputs.
4. **Evidence is scoped:** tests and proofs apply only to the exact subjects, assumptions, targets, and tool versions they cover.
5. **Unknown is not proven:** unsupported, incomplete, ambiguous, or unchecked cases fail closed.
6. **Sound incremental reuse:** a result is reused only when all result-determining dependencies are captured and unchanged.
7. **Semantic changes propagate by identity:** hash-relevant changes alter the appropriate identity and invalidate dependent results automatically.
8. **Provenance is not semantics:** authorship, history, and audit data do not alter semantic identity unless explicitly defined as behaviorally relevant.
9. **No silent weakening:** a backend or runtime must report restrictions and unsupported semantics rather than silently dropping guarantees.
10. **Research is not specification:** only reviewed and explicitly accepted decisions enter `draft/`.

---

# 8. Immediate execution order

The next concrete work should follow this order, while respecting the dependency map:

1. **Extend the now-passing Stage 2 Lean CI slice:** run 44175854422 passed pinned Lean 4.34.0 / Logos compilation and the complete current test step. The small expression-level preservation theorem is kernel-checked; next prove the actual canonical relational-query encoder's semantic correspondence and its binding to CPC assumptions. Do not claim a proof until CI passes without sorry.
2. **Continue the formal-verification line:** the tested CPC parser-state binding and adversarial assumption-list checks now pass Lean CI. Before treating the relational query as correctly constructed, version the wire envelope to bind explicit `factor_left`/`factor_right` declarations and independently validate that `factor_difference` is exactly their inequality (Scenario 32 §11). Then prove source-expression-to-query preservation for the supported slice and expand carefully to commands and paired program executions. Keep QF_LIA narrow and fail closed.
3. **Advance RT-03 from candidate survey to validation:** use [CORE-LANGUAGE-SEMANTICS.md](research/CORE-LANGUAGE-SEMANTICS.md) as the current option inventory; reconcile A–D with RT-04, define observable behavior and a common test corpus, then prototype at least two reference semantics. Keep all profiles provisional until synthesis.
4. **In parallel, research type/effect/ownership/capability/concurrency alternatives (RT-04):** record dependencies on core semantics and identify incompatible vectors.
5. **Consolidate Stage 1 identity decisions:** settle canonical OpHash/ImpHash payloads, stable identity lifecycle, contract identity, and hash-relevant dependency boundaries only after the cross-aspect implications are understood.
6. **Connect Stages 1–3:** verify that semantic identity, dependency completeness, Action Keys, invalidation, and evidence staleness form one coherent model.
7. **Quantify cache benefits:** turn the analytical speedup estimate into reproducible benchmarks; include cold/warm builds and local/component/broad changes.
8. **Audit security and trust (RT-16):** compiler, runtime, LLM authoring interface, package/artifact store, build/test environment, and proof pipeline.
9. **Defer Stage 4 implementation and merge benchmarks** until whole-specification synthesis has narrowed representation, identity, and merge-policy choices; retain ADR-014 as Proposed.
10. **Research package distribution and index storage (RT-12):** the TOML manifest and package identity proposal now have focused tests; the first logical index-table schema and deterministic in-memory merge prototype are also in place. The lazy k-way merge, bounded-memory external cross-table reference validator, and streaming ZIP archive writer/verifier are prototyped and CI-tested. The archive path now parses the manifest, recomputes the logical index hash and Package Content Root Hash, and checks root membership. Next validate dependency-policy semantics and schema completeness, extend manifest checks to cache-index payloads, and measure archive-container memory behavior. The current ZIP-based writer/verifier is exploratory and does not settle the archive or binary index format. Only after those contracts are stable should binary encoding, block compression, sparse lookup, and benchmarks be designed. Keep all wire-format and provider decisions provisional.
11. **Only then select vertical slices and implementation commitments:** POSIX/runtime, backends, scalability, ecosystem, and adoption should be validated against a coherent candidate specification.

Do not skip a gate because a document exists. A research document is evidence that a topic was investigated, not proof that its design is correct or complete.

---

# 9. Maintenance
- Update this plan when a research item starts, produces evidence, is superseded, or reaches an accepted decision.
- Keep stable item names and links where possible so other documents can refer to them.
- Add new work to the appropriate stage rather than appending an unprioritized backlog.
- Record cross-stage dependencies explicitly.
- When a decision is accepted, update `TODO.md` and the relevant research/design document; do not mark it accepted solely because this plan recommends it.
- Keep implementation bugs and short-lived tasks in the appropriate issue/task tracker; this document is the ordered research and development programme.
- Review this plan whenever the research corpus or architecture changes materially.