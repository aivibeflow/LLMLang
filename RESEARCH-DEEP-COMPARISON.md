# Deep Comparative Research: LLMLang-Adjacent Projects

**Research date:** 2026-11-16  
**Scope:** Source-level and architecture-document review of linkly, Edict, DSP CodeGen, and agent-spec. This is a design comparison, not a code audit or independent benchmark.

## 1. Executive findings

The initial landscape scan identified four especially relevant projects. Reading their RFCs, schemas, implementation files, and working documentation changes the comparison in several important ways:

- **linkly is the closest broad platform analogue.** It has a semantic rather than syntactic IR, a language/compiler/runtime, a knowledge base with progressive disclosure, an agent protocol, and an explicit proposal/review/merge workflow. Its IR also specifies canonical JSON (RFC 8785/JCS) for document equality, hashing, and signatures. However, the inspected design is still a single program IR, not three independently maintained Specification, Design, and Implementation graphs; canonical document hashing is not the same as fine-grained node-level content addressing with a Merkle dependency DAG.
- **Edict is the strongest concrete reference for machine-native program editing and incremental semantic checks.** It has a JSON AST, stable node IDs for patch targeting, structural SHA-256 hashes of definitions, dependency-aware invalidation, and selective contract re-verification. Its incremental path still performs structural validation, resolution, type checking, complexity checking, and effect checking across the module before narrowing contract verification.
- **DSP CodeGen is the strongest graph-first codebase model.** It stores structural entities and edges in a persistent graph, uses stable UIDs independent of paths, binds graph entities to code via markers, computes semantic changesets and impact, and regenerates only affected code. But the graph deliberately omits private implementation functions, and its graph verifier is structural lint rather than a semantic proof engine.
- **agent-spec is the strongest reference for governed human intent and evidence traceability.** It separates human-owned Requirement IR from derived Code Graph IR, lowers requirements into work units and Task Contracts, links requirements to code symbols, and records liveness/evidence. It has explicit human decision envelopes and evidence digests. Its current AI-verifier surface is intentionally provider-neutral and no real model provider is wired in.

The closest architectural precedent to LLMLang is therefore not one project but a combination:
- linkly for the integrated semantic-IR + agent-protocol platform;
- agent-spec for human-owned requirements, governance, and traceability;
- Edict for structured AST editing, diagnostics, and incremental verification;
- DSP CodeGen for graph identity, code bindings, and incremental generation.

## 2. Detailed project reviews

## 2.1 linkly

Repositories and primary documents:
- Repository: https://github.com/choiyounggi/linkly
- Current semantic IR RFC: https://github.com/choiyounggi/linkly/blob/main/rfcs/0066-semantic-ir-v2.md
- Knowledge Base RFC: https://github.com/choiyounggi/linkly/blob/main/rfcs/0005-knowledge-base.md
- Agent Protocol RFC: https://github.com/choiyounggi/linkly/blob/main/rfcs/0006-agent-protocol.md
- Proposal intent RFC: https://github.com/choiyounggi/linkly/blob/main/rfcs/0010-proposal-intent.md
- Repository README: https://github.com/choiyounggi/linkly

### What is actually designed

The Semantic IR is a **flat table of semantic nodes plus ID references**, not a nested syntax tree. Nodes represent declarations, behavior, effects, and constraints. The RFC explicitly favors flat structure for constrained decoding, low-cost node-level diffs/fragments, and stable serialization order.

Important structural rules include:
- node IDs are unique dot-path identifiers within an IR document;
- a child has at most one owning parent;
- ownership edges are acyclic;
- child order is semantically meaningful for workflows/pipelines/concurrency;
- named non-owning references are separately modeled;
- dangling references are checked against the merged full document.

The IR is a semantic hub for language lowering, runtime, compiler, and agent protocol. It distinguishes semantic effects such as repository calls, network calls, cache access, transactions, authorization, and event emission from workflow behavior and declarations.

The current RFC-0066 is marked Accepted and supersedes the original RFC-0001. Earlier references to RFC-0001 should not be treated as the current canonical specification.

### Content identity: overlap and gap

The IR serialization appendix specifies RFC 8785 JSON Canonicalization Scheme for document equivalence, hashing, and signatures. This is a real overlap with LLMLang's canonicalization concerns.

However, the inspected model does not establish:
- an independent immutable content hash for every semantic node;
- recursive node hashes incorporating hash-relevant dependencies;
- a Merkle DAG over the three semantic layers;
- cache/approval/evidence identities pinned to a complete transitive semantic dependency closure.

The node ID is a logical identifier (a dot-path), not a content hash. This aligns with LLMLang's Stable ID vs Content Hash separation, but linkly's documented granularity is different.

### Agent protocol and change governance

The protocol has a fixed set of JSON-RPC methods and explicit roles. The important pattern is that **ir.propose does not mutate the IR**. It creates a pending proposal and a review task. A Reviewer decides approved/rejected; only after approval does the server merge the fragment and validate the merged result.

The proposal can include structural intent such as attaching newly authored nodes or moving references. The receiving side validates the resulting ownership graph rather than trusting a surface-level diff.

Reliability is unusually explicit:
- idempotency keys are required for side-effecting dispatch/proposal operations;
- a repeated key returns the original response;
- key uniqueness and the side effect are committed atomically;
- reuse of a key with different parameters is an error;
- retry policy distinguishes retryable/non-retryable errors and constrains retry amplification;
- tasks have explicit states and terminal-state rules.

This is close to LLMLang's Change Set / approval boundary in spirit. But the protocol does not show an approval bound to a Merkle digest of the complete proposal plus baseline and transitive dependencies. Its KB version pins are a separate mechanism.

### Knowledge Base and context efficiency

The KB has three progressive-disclosure levels:
1. a root routing index;
2. category routing indexes;
3. the selected document body and explicitly referenced resources.

The logical interface separates route, load, and version verification. Routing is constrained to use only the routing index, not to load every document body and then search it. Agents record the exact KB document versions used; a stale pin forces routing/loading again.

This is a strong design for LLMLang's Context Planner:
- retrieval and content loading are separate operations;
- the routing surface is deliberately much smaller than the full corpus;
- provenance pins make context assumptions explicit;
- stale knowledge can be detected instead of silently reused.

It does not, by itself, solve token budgeting, context minimization across an arbitrary semantic graph, or reuse of context deltas against a precise content-addressed snapshot.

### What LLMLang should study

1. Flat semantic node tables and explicit distinction between owning and non-owning edges.
2. Progressive disclosure as a protocol invariant, not merely a prompt-writing convention.
3. Proposal-only mutation followed by independent review and server-side merge.
4. Structural intent (attach / move) to disambiguate semantic graph edits.
5. Atomic idempotency semantics for tool calls that create tasks or proposals.
6. Explicit retry/deadline/cancellation behavior in multi-agent workflows.
7. JCS as a canonical serialization option, while retaining node-level Merkle hashing as a separate layer.

### Risks / lessons

- A flat IR is agent-friendly, but the IR's node catalog can become very large and tightly coupled to one canonical semantic model.
- Stable dot-path IDs can become awkward if identity is derived from hierarchy or naming; LLMLang should define identity behavior for rename/move separately from content changes.
- A protocol can be explicit yet still leave external approval identity/authority to the host system. LLMLang should state clearly which component attests the human approver.
- A canonical hash of one whole document is not sufficient for efficient partial invalidation or cross-layer proof reuse.

## 2.2 Edict

Repository and primary files:
- Repository: https://github.com/Sowiedu/Edict
- AST schema: https://github.com/Sowiedu/Edict/blob/main/schema/edict.schema.json
- Incremental checking: https://github.com/Sowiedu/Edict/blob/main/src/incremental/check.ts
- Dependency graph: https://github.com/Sowiedu/Edict/blob/main/src/incremental/dep-graph.ts
- Structural diff: https://github.com/Sowiedu/Edict/blob/main/src/incremental/diff.ts
- AST patch engine: https://github.com/Sowiedu/Edict/blob/main/src/patch/apply.ts

### Canonical representation and identity

Edict programs are structured JSON ASTs. The schema includes more than executable syntax: functions can carry contracts, intent declarations, approval gates, blame/provenance annotations, complexity constraints, effects, and bodies.

The AST patch interface addresses nodes by nodeId and supports replace, delete, and insert operations. The implementation deep-clones the AST, indexes nodes by ID, and applies patches sequentially. A failed patch batch returns structured errors and does not return the mutated clone as a successful result.

This is a useful agent-facing mutation API, but it is not equivalent to LLMLang's proposed optimistic concurrency control:
- the patch operation is addressed by node ID;
- the inspected patch structure has no mandatory expected Content Hash / expected revision precondition;
- the patch engine itself does not establish a durable immutable Change Set or approval artifact;
- callers still need to validate the resulting AST through the compiler pipeline.

### Structural hashing and incremental checking

Edict's structural diff computes SHA-256 over canonical JSON for each top-level definition, stripping nested node ID fields so cosmetic ID changes do not mark the definition as semantically changed. Definitions are compared by name. Added, modified, and deleted definitions are marked changed. Import changes conservatively mark all functions and constants dirty.

A definition-level dependency graph records call and type-reference dependencies. Reverse edges are used to calculate the transitive dependents of changed definitions.

The incremental checker then:
1. validates the module schema;
2. resolves names;
3. type-checks;
4. checks complexity constraints;
5. checks effects;
6. computes changed definitions and their transitive dependents;
7. selectively verifies contracts only for affected functions.

This is a useful distinction: **the contract-verification stage is incremental, while several earlier compiler analyses still run module-wide**. It avoids overstating the current implementation as a fully incremental compiler.

The cache statistics surfaced by contract verification can be inspected, but the inspected diff model is not a Merkle DAG over all semantic nodes. It is a definition-level structural-hash plus dependency-graph approach.

### What LLMLang should study

1. Canonical structural hashing that ignores identity-only fields.
2. Explicit dependency extraction from calls and type references.
3. Reverse-dependency invalidation and conservative handling of uncertain dependency changes.
4. Separating the expensive verification phase from cheaper mandatory front-end checks.
5. Structured AST patches addressed by stable node identity.
6. Typed diagnostics and machine-readable proof/verification outcomes.
7. Intent/provenance/approval annotations as first-class schema fields.

### Risks / lessons

- Comparing by definition name means renames can appear as delete+add unless a separate identity mapping exists.
- Stripping all nested IDs from structural hashes is useful for cosmetic identity changes, but the exact set of hash-excluded fields must be specified carefully; some IDs may carry semantic reference meaning.
- If the dependency graph misses a dependency kind, incremental verification can become unsound. Conservative invalidation is safer than optimistic reuse.
- A patch API without expected-hash preconditions can overwrite newer state if multiple agents operate concurrently.
- A clone-and-patch operation is not by itself a complete transactional Change Set protocol; atomicity, conflict detection, review, and provenance are separate responsibilities.

## 2.3 DSP CodeGen

Repository and primary document:
- Repository: https://github.com/Loqira-Labs/dsp-codegen
- Working methodology and command contract: https://github.com/Loqira-Labs/dsp-codegen/blob/main/skills/dsp-codegen/SKILL.md
- Known issues: https://github.com/Loqira-Labs/dsp-codegen/blob/main/skills/dsp-codegen/KNOWN-ISSUES.md

### Graph model

DSP CodeGen uses one graph for two purposes:
- structural memory of an existing codebase;
- a compiler-like IR/source of truth for generating new code.

Entities include modules, types, configs, functions, and external dependencies. Edges express imports and why a dependency exists. Public/shared entities have typed contracts at language seams. Stable UIDs are independent of paths; path is an attribute. A marker such as @dsp followed by a UID binds a graph entity to a code region.

The graph is persisted under .dsp/ and is intended to be version-control friendly. A resident runtime serves the CLI and browser UI. The graph is the source of truth after initial creation; code changes are expected to begin in the graph.

### Deterministic generation boundary

The methodology deliberately separates deterministic and nondeterministic work:
- graph topology, language selection, wiring, contracts, and stubs are generated deterministically;
- implementation bodies are written by an LLM;
- the contract barrier is frozen before implementation bodies are generated in parallel;
- agents load only their module sheet, dependency contracts, and their own specs, not the entire graph or other modules' implementations;
- changesets and recipient/impact queries scope regeneration to affected modules.

This is a concrete implementation of a token-efficiency principle: consumers need dependency contracts, not dependency implementation bodies.

### Verification boundary

The project's own documentation says the graph verifier is static, language-agnostic lint. It checks things such as missing files, misplaced/duplicate markers, missing symbols, phantom imports, missing public contracts, and cross-language missing fields. Deeper confidence comes from the language compiler, tests, and cross-language coherence harnesses.

A critical scope boundary is explicit: private functions are not modeled in the graph. Their bodies are written freely inside the module; module tests and the compiler are the safety net.

The project also documents lifecycle statuses such as planned, contract, implementation, verified, and stale. Pre-code entities are intentionally exempt from code-presence checks.

### What LLMLang should study

1. Stable UIDs independent of file paths and symbol spelling.
2. Explicit graph-to-source binding markers and validation of marker placement.
3. Graph-first semantic changesets and recipient/impact analysis.
4. Deterministic generation of public interfaces/stubs before LLM-generated bodies.
5. Contract-only dependency context for implementation agents.
6. Per-module/per-batch worktrees and barriers for parallel generation.
7. A graph lifecycle that distinguishes planned/contract/implemented/verified/stale.

### Risks / lessons

- A graph that models only public boundaries cannot provide complete semantic coverage of private implementation behavior.
- A graph verifier must not be presented as a formal verifier. Structural consistency, compiler acceptance, behavioral tests, and proofs are different evidence classes.
- Binding markers create a consistency obligation between graph identity and code. Rename/move operations must update or preserve bindings deterministically.
- A graph-first workflow needs explicit reconciliation for legitimate code edits that bypass the graph, generated files, and partial failures during regeneration.
- Stable graph UIDs do not automatically provide content-addressed version identity.

## 2.4 agent-spec

Repository and primary documents:
- Repository: https://github.com/ZhangHanDong/agent-spec
- Intent Compiler architecture: https://github.com/ZhangHanDong/agent-spec/blob/main/docs/intent-compiler/architecture.md
- README: https://github.com/ZhangHanDong/agent-spec/blob/main/README.md
- Changelog: https://github.com/ZhangHanDong/agent-spec/blob/main/CHANGELOG.md
- Validation matrix: https://github.com/ZhangHanDong/agent-spec/blob/main/docs/intent-compiler/reference-validation-matrix.md

### Two different IRs and the trust boundary

agent-spec explicitly distinguishes:
- **Requirement IR**: durable, human-reviewed normative truth describing what the system must do;
- **Code Graph IR**: derived, rebuildable, freshness-aware facts about what the program currently contains.

The Intent-Code Linker connects the two without allowing derived code facts to rewrite accepted requirements. Requirement-derived test obligations are intended to remain code-independent.

This is conceptually close to LLMLang's separation between normative specification and implementation facts. It does not provide a full independent Design Graph layer in the same sense as LLMLang.

### Governance, lowering, and contracts

The toolchain includes requirement intake/import, governance, requirement graph validation, work-unit lowering, Task Contracts, plan DAGs, test obligations, lifecycle checks, traceability, and archive workflows.

Human decision points use structured envelopes. The calling agent may draft bounded candidate options, but the CLI validates them and does not invent candidates. A human judgment can be recorded with its verdict, reasoning, scenario ID, and evidence digest. The record deliberately omits identity/authority fields because the CLI cannot attest who the human is; an external system must bind the approver to the digest.

The project distinguishes three state axes:
- governance (whether a requirement is accepted);
- execution progress (whether work is planned, active, verified, archived);
- liveness (whether current evidence says the requirement is honored, violated, unproven, or not applicable).

That is an important lesson for LLMLang: governance state, execution state, and current conformance should not be collapsed into one status field.

### Evidence and stale data

The project documents trace ledger v2, affected-scope evidence, normalized provider outcomes, source spans, worktree/VCS references, replay, and failure explanation. Replay reads stored evidence; it does not rerun tools, models, or source analysis. Stale or unavailable code intelligence must not produce definitive bindings or passing evidence.

The provider model distinguishes code intelligence, diagnostics, verification, transformation, and agent guidance. Skills guide generation but are not themselves acceptance evidence. A provider that is required but unavailable, errors, or skips cannot be treated as pass.

### Important implementation-status qualification

There is some documentation drift:
- the architecture document still labels several parts of its target architecture as planned extensions;
- the README describes the dual-IR pipeline, code grounding, execution bundles, Atlas, and liveness surfaces as current capabilities;
- the changelog describes shipped delivery boundaries and subsequent enforcement work.

Therefore, the architecture document should be read together with the current README/changelog and actual implementation, not as a complete status ledger on its own.

One explicit limitation is unambiguous: the AI verifier has a provider abstraction and off, stub, and caller modes, but **no real model provider is wired in**. The stub mode emits uncertainty rather than pretending to prove a scenario. In caller mode, the host agent supplies judgments through a two-step request/resolve flow.

### What LLMLang should study

1. Human-owned normative requirements versus derived code facts.
2. Requirement governance states separate from delivery progress and conformance liveness.
3. Work-unit lowering and Task Contracts as an intermediate execution surface.
4. Test obligations derived from requirements rather than implementation structure.
5. Typed provider roles and normalized pass/fail/unavailable/error/skip outcomes.
6. Freshness-gated code bindings and explicit stale/capability gaps.
7. Trace records bound to evidence digests, source spans, worktrees, and VCS state.
8. Replay as inspection of immutable recorded evidence, not a silent rerun.
9. Explicit human-judgment envelopes while leaving identity attestation to an authorized external authority.

### Risks / lessons

- A code graph should be derived and rebuildable; it should not silently become the source of normative intent.
- An AI-generated acceptance judgment is not a deterministic proof. Preserve its provenance and evidence class.
- An uncertain or unavailable result must remain distinct from pass.
- Architecture documents can lag implementation. LLMLang should maintain an explicit feature-status ledger and keep RFC status, shipped implementation, and tested behavior separate.

## 3. Cross-project comparison

| Capability | linkly | Edict | DSP CodeGen | agent-spec |
|---|---|---|---|---|
| Agent-native structured program representation | Semantic flat IR | JSON AST | Graph IR | Requirement IR + Code Graph IR |
| Normative requirements separate from code facts | Partial / semantic intent embedded in IR | Function intent/contracts | Graph is source of truth for modeled structure | Explicitly separated |
| Independent Design representation | No clear equivalent | No | No distinct design layer | No distinct design layer |
| Stable logical node/entity IDs | Dot-path IDs | AST node IDs | Stable UID independent of path | Requirement IDs + code symbol IDs |
| Canonical content hashing | JCS for IR document equality/hash/signature | SHA-256 structural hash per definition | Graph snapshots/diff; not equivalent to node Merkle DAG | Fingerprints/digests and graph freshness; not full semantic Merkle DAG |
| Fine-grained Merkle DAG | Not established in inspected RFCs | No | No | No |
| Structured patch/change API | ir.propose with fragment and structural intent | replace/delete/insert by nodeId | graph operations and apply | requirement/work-unit/contract workflow |
| Expected-hash optimistic concurrency on each edit | Not established in inspected protocol | Not in inspected AST patch shape | Not established by UID alone | Fingerprint/freshness checks in selected flows |
| Human approval gate | Explicit proposal → Reviewer decision → merge | Approval annotations/gates, but not full project Change Set governance | Human intent freeze and review stages | Human requirement governance and contract acceptance |
| Incremental impact/reverification | Not shown as full semantic invalidation | Definition dependency graph; contract verification incremental | Semantic diff + recipients/impact + incremental regeneration | Affected scope, Atlas impact, targeted checks |
| Independent verification | Compiler/runtime/differential checks | Type/effect/contracts/Z3/WASM | Structural lint + compiler/tests/coherence | Deterministic lifecycle providers + human/agent judgments |
| Explicit uncertainty/unavailability | Structured errors; KB pin conflicts | Verification coverage/structured errors | Verify gates fail on missing structural conditions | Explicit uncertain/unavailable/skip states |
| Context/token efficiency | Progressive disclosure KB | Compact AST and structured diagnostics | Contract-only dependency context and per-module sheets | Bounded graph/context retrieval and omission manifests |

## 4. What appears genuinely differentiated in LLMLang

The individual ingredients are not unique. The potential architectural value is in their **composition and consistency model**.

### 4.1 Three independent semantic layers

The inspected projects use one semantic IR, a program AST, one code graph, or a two-track requirement/code model. None of the four reviewed projects clearly establishes three separately maintained but linked layers:

- Specification Graph: normative obligations and externally observable behavior;
- Design Graph: architecture, decomposition, choices, interfaces, and rationale;
- Implementation Graph: concrete code-level structure and implementation facts.

This may be LLMLang's clearest structural differentiator. The Design Graph must have its own semantics and lifecycle; it should not become a duplicate of requirements or a decorative architecture diagram.

### 4.2 One identity model across edits, snapshots, and evidence

Stable IDs and structural hashes already appear in other projects, but the reviewed designs do not combine them into a single model with:
- Stable ID for logical continuity;
- Content Hash for an immutable semantic state;
- hash-relevant dependency edges;
- a Merkle DAG spanning nodes and layer roots;
- explicit hash boundaries excluding presentation-only metadata;
- exact hash identities on changes, approvals, builds, caches, and verification evidence.

This combination could provide a stronger basis for concurrency, incremental verification, replay, and reproducibility.

### 4.3 A single governed change lifecycle across all layers

linkly has proposal/review/merge for its IR. agent-spec has requirement governance and Task Contract acceptance. Edict has surgical patches. DSP CodeGen has graph-first diff and regeneration.

LLMLang can connect these into one consistent lifecycle:
1. capture human intent and clarifications;
2. propose a Change Set against an exact baseline;
3. show semantic diff and affected graph closure;
4. validate permissions and structural invariants;
5. obtain approval bound to the exact proposal and baseline;
6. apply atomically;
7. run required verification;
8. record evidence against exact resulting hashes.

The key is not merely having an approval step. It is ensuring the approved proposal cannot silently change between review and commit.

### 4.4 Verification evidence as first-class graph data

The strongest projects distinguish different kinds of evidence, but LLMLang can make evidence a graph-linked artifact:
- verifier/tool identity and version;
- exact input hashes and dependency closure;
- scope and assumptions;
- outcome class (PROVEN, DISPROVEN, UNKNOWN, NOT_CHECKED, plus test/analysis evidence classes where applicable);
- diagnostics/counterexamples;
- provenance and timestamp;
- validity/invalidation dependencies.

A verification result should become stale when any hash-relevant input changes. A cached result should be reused only when the exact required input identities and verifier configuration match.

## 5. Concrete design lessons for LLMLang

The following are recommendations for further design discussion, not adopted decisions.

### 5.1 Keep three identities separate

Do not conflate:
- logical identity (Stable ID);
- semantic version identity (Content Hash);
- source location identity (path, file, line, generated region).

DSP CodeGen demonstrates why path must not be identity. Edict demonstrates why identity fields may need exclusion from structural hashes. linkly demonstrates canonical serialization. LLMLang should formalize all three together.

### 5.2 Define canonicalization before the Merkle scheme

Specify:
- canonical serialization per node kind;
- normalization of maps, sets, ordered lists, numbers, Unicode, and references;
- which metadata is excluded;
- domain separation by object kind and schema version;
- hash algorithm/version agility;
- treatment of unresolved references and invalid nodes;
- how dependencies contribute to parent hashes.

Do not assume RFC 8785 alone solves semantic canonicalization. It canonicalizes JSON representation; it does not decide which fields are semantically relevant or whether array order is meaningful.

### 5.3 Make every edit conditional on a baseline

Edict's nodeId patching is a useful API, but LLMLang should require preconditions for mutation:
- expected node Content Hash;
- expected parent/edge hash when changing relationships;
- expected layer root or Change Set baseline where required.

Conflicts should be reported as semantic conflicts, not silently resolved by last-writer-wins.

### 5.4 Separate fast validation from expensive proof work

Edict's pipeline suggests a practical distinction:
- always run cheap structural and name/type/effect checks required for safe interpretation;
- selectively rerun expensive contract/proof checks for the affected dependency closure;
- cache only when the full verifier input identity matches.

Do not skip mandatory front-end checks merely because a downstream proof is cached.

### 5.5 Keep code intelligence and correctness verification separate

DSP CodeGen and agent-spec both make this distinction. A graph provider answers what code structure exists and what may be affected. A compiler, test runner, analyzer, or prover answers what is valid or correct under a given contract. A fresh graph is not proof of behavior.

### 5.6 Treat context as a planned artifact

Combine linkly's progressive disclosure with DSP CodeGen's contract-only dependency context and agent-spec's bounded retrieval:
- identify task-relevant graph seeds;
- retrieve typed relations and minimal supporting facts;
- project only relevant content into model context;
- record omissions and truncation explicitly;
- bind continuation/reuse to a context fingerprint;
- never treat an ID or hash as a substitute for content the model has not received.

### 5.7 Keep human authority outside the model trust boundary

agent-spec's explicit separation between human judgment evidence and identity attestation is valuable. LLMLang should record the exact approval subject and digest, but only a trusted host/identity system should attest who approved it and under what authority.

## 6. Open questions for LLMLang

1. What is the exact semantic boundary between Specification and Design? Which facts may appear in both, and which layer owns each?
2. Can a Design node be independently versioned and approved without changing the Specification root?
3. Does an Implementation node represent a source symbol, a code region, a build artifact, or all three through linked node kinds?
4. How should Stable IDs survive rename, move, split, merge, and delete/recreate?
5. Which edges are hash-relevant, and which are traceability/navigation-only?
6. Are layer roots independent, with a separate project root linking them, or is there a single project Merkle root?
7. How are external dependencies, compiler versions, toolchain configuration, and environment facts included in verification identities?
8. What is the authority boundary for approving requirements, design decisions, and implementation changes?
9. Which changes require approval, and which can be auto-accepted under an explicit policy?
10. How are generated code regions reconciled with manual edits?
11. How is partial failure handled if a Change Set updates graph state but code generation or verification fails?
12. What evidence is sufficient to mark an item verified, and what exact changes invalidate that evidence?

## 7. Recommended next work

Before adopting implementation details from any project, build a small LLMLang design spike around four cross-cutting scenarios:

1. **Rename a semantic entity** while preserving logical identity, updating references, and invalidating only the correct content hashes.
2. **Two agents edit the same node** from the same baseline; one commits first and the second receives a semantic conflict instead of overwriting.
3. **Change a specification requirement** and compute the affected design nodes, implementation symbols, tests, and proof obligations.
4. **Reuse a verification result** after an unrelated graph edit, proving that only results whose exact hash inputs remain unchanged can be reused.

For source-level follow-up, the highest-value files to inspect next are:
- linkly: RFC-0066, RFC-0005, RFC-0006, RFC-0010, compiler invariants and IR validation tests;
- Edict: AST schema, patch tests, incremental checker tests, contract cache implementation and structured error catalog;
- DSP CodeGen: graph persistence format, UID allocation, snapshot/diff implementation, marker reconciliation, verify tests;
- agent-spec: governance transitions, Task Contract parser/validator, Atlas freshness model, trace ledger v2 serialization and replay tests.

## 8. Sources and scope notes

The primary source links are listed in each project section. The comparison used repository documentation and selected source files available on the repositories' default branches on 2026-11-16.

Project maturity, test counts, and production-readiness labels are maintainer claims unless independently demonstrated. This review did not execute the projects' test suites, audit their security, benchmark performance, or verify all claimed features end-to-end. The findings should guide targeted experiments, not be treated as certification of project quality.
