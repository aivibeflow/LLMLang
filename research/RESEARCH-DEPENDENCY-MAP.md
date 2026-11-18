# LLMLang Cross-Aspect Research Dependency Map

**Status:** Initial dependency hypothesis; relationships require validation  
**Updated:** 2026-11-18  
**Companion:** [Research Taxonomy](RESEARCH-TAXONOMY.md)

## 1. Purpose and interpretation

This map describes how choices in one LLMLang aspect can affect other aspects. It is a research-planning instrument, not a normative architecture and not a claim that every edge has already been proven.

The direction of an edge is **source aspect → affected aspect**. It means a change or choice in the source can impose requirements on, constrain, enable, or alter the trade-offs of the target.

Relationship types:

- **Requires:** the target depends on a capability or decision in the source.
- **Constrains:** the source narrows the viable vectors or design space of the target.
- **Influences:** the source changes target trade-offs or parameters, but does not necessarily rule out options.
- **Conflicts with:** specified vectors cannot coexist under stated assumptions. This is a symmetric incompatibility, recorded once with its conditions.
- **Enables:** the source makes a target capability or vector practical.

Confidence:

- **Established:** follows from an explicit dependency in the current model or a demonstrated result within stated scope.
- **Strong hypothesis:** architecturally compelling, but requires cross-aspect validation.
- **Open hypothesis:** plausible relationship that needs research.

A dependency is never “established” merely because two documents mention each other. Record evidence and scope.

## 2. High-level dependency structure

~~~mermaid
flowchart TD
  G[RT-01 Goals and constraints]
  I[RT-02 Intent and requirements]
  S[RT-03 Core semantics]
  T[RT-04 Types, effects, ownership, capabilities]
  P[RT-05 Program representation and identity]
  D[RT-06 Dependency semantics and impact]
  F[RT-07 Formal semantics and verification]
  E[RT-08 Tests, validation, evidence]
  C[RT-09 Compiler and IR]
  R[RT-10 Runtime and execution]
  B[RT-11 Build and cache]
  L[RT-12 Libraries and packages]
  X[RT-13 Backends and interoperability]
  A[RT-14 AI authoring and change]
  V[RT-15 Version control and merge]
  Q[RT-16 Security and trust]
  UX[RT-17 Developer experience]
  EV[RT-18 Conformance and evolution]
  TS[RT-19 Toolchain Server and semantic development API]
  CP[RT-20 LLM patch planning and verified commit]

  G --> I
  G --> S
  I --> S
  S --> T
  S --> P
  T --> P
  S --> F
  T --> F
  P --> D
  S --> D
  D --> B
  P --> B
  F --> E
  S --> E
  P --> C
  S --> C
  T --> C
  C --> R
  S --> R
  T --> R
  R --> L
  P --> L
  F --> L
  C --> X
  R --> X
  P --> V
  D --> V
  A --> E
  P --> A
  S --> A
  Q --> A
  I --> CP
  P --> CP
  D --> CP
  E --> CP
  A --> CP
  V --> CP
  Q --> CP
  TS --> CP
  CP --> TS
  Q --> R
  Q --> L
  E --> EV
  L --> EV
  X --> EV
~~~

The graph is intentionally simplified. It omits feedback edges for readability; the detailed edge register below records the principal dependencies. It is not a strict topological ordering: several topics can be researched in parallel, and later findings may send work back upstream.

## 3. Directed dependency register

| Edge | From → to | Relation | Rationale / affected choices | Confidence |
|---|---|---|---|---|
| DEP-001 | RT-01 → RT-02 | Constrains | Product goals, intended users, and acceptable human review determine what intent and requirement capture must express. | Strong hypothesis |
| DEP-002 | RT-01 → RT-03 | Constrains | Workloads, correctness expectations, portability, and non-goals shape the required semantic core. | Strong hypothesis |
| DEP-003 | RT-02 → RT-03 | Influences | Requirement and contract concepts need semantic values, predicates, states, and observable behavior to be defined. | Strong hypothesis |
| DEP-004 | RT-03 → RT-04 | Constrains | Type/effect/ownership choices must preserve the core evaluation and observable semantics. | Strong hypothesis |
| DEP-005 | RT-03 → RT-05 | Constrains | Graph node kinds and semantic identity must encode distinctions that actually affect program meaning. | Strong hypothesis |
| DEP-006 | RT-04 → RT-05 | Influences | Types, effects, capabilities, and ownership may be hash-relevant or may be referenced as separate artifacts; the identity boundary depends on their semantics. | Open hypothesis |
| DEP-007 | RT-03 → RT-07 | Requires | Formal semantics and proofs need a precisely defined source-language fragment and observation model. | Strong hypothesis |
| DEP-008 | RT-04 → RT-07 | Constrains | Proof rules and encodings must account for type/effect/resource semantics, or explicitly exclude them. | Strong hypothesis |
| DEP-009 | RT-05 → RT-06 | Requires | Dependency analysis needs stable typed entities and a defined semantic identity model. | Established within current research model |
| DEP-010 | RT-03 → RT-06 | Requires | Sound semantic dependency analysis depends on the language's formal behavior and observable boundary. | Established within Scenarios 25–34 scope |
| DEP-011 | RT-06 → RT-11 | Requires | Safe incremental planning/cache invalidation depends on dependency completeness and conservative unknown handling. | Established within Scenarios 18–25 scope |
| DEP-012 | RT-05 → RT-11 | Requires | Action cache keys and reusable results need stable semantic input identities, while remaining distinct from semantic hashes. | Strong hypothesis |
| DEP-013 | RT-03 → RT-08 | Constrains | Tests, models, and proof claims need a defined meaning for program execution and observations. | Strong hypothesis |
| DEP-014 | RT-07 → RT-08 | Enables | Formal semantics and verified proof boundaries enable stronger evidence than tests alone. | Strong hypothesis |
| DEP-015 | RT-05 → RT-09 | Requires | Compiler stages need canonical program entities/IR and reproducible references to semantic inputs. | Strong hypothesis |
| DEP-016 | RT-03 → RT-09 | Constrains | Lowering and optimization must preserve the source language's semantics. | Established as a design obligation |
| DEP-017 | RT-04 → RT-09 | Constrains | Type, effect, ownership, and capability rules determine which transformations and target representations are legal. | Strong hypothesis |
| DEP-018 | RT-03 → RT-10 | Constrains | Runtime behavior must implement the language's evaluation, state, error, concurrency, and resource semantics. | Strong hypothesis |
| DEP-019 | RT-04 → RT-10 | Constrains | Ownership, effects, capabilities, and memory model determine runtime services and ABI boundaries. | Strong hypothesis |
| DEP-020 | RT-10 → RT-12 | Influences | Library contracts and implementations depend on runtime and platform services available to packages. | Strong hypothesis |
| DEP-021 | RT-05 → RT-12 | Requires | Reusable libraries/packages need stable artifact identities and reproducible dependency references. | Strong hypothesis |
| DEP-022 | RT-07 → RT-12 | Constrains | Public contracts and compatibility claims need an explicit evidence model, especially for opaque implementations. | Strong hypothesis |
| DEP-023 | RT-09 → RT-13 | Requires | Backend alternatives consume a defined lowering interface and source semantic contract. | Strong hypothesis |
| DEP-024 | RT-10 → RT-13 | Influences | Target backends and FFI must agree with runtime, ABI, data layout, and platform behavior. | Strong hypothesis |
| DEP-025 | RT-05 → RT-15 | Requires | Semantic diff/merge requires canonical repository representation and stable identity rules. | Established in ADR-014 as an architectural prerequisite |
| DEP-026 | RT-06 → RT-15 | Influences | Merge conflict detection and impact validation benefit from semantic dependency and impact information. | Strong hypothesis |
| DEP-027 | RT-05 → RT-14 | Requires | Structured AI changes need stable graph entities, typed operations, and inspectable semantic context. | Strong hypothesis |
| DEP-028 | RT-03 → RT-14 | Constrains | The change protocol must not allow an LLM to bypass language-level semantic validation. | Strong hypothesis |
| DEP-029 | RT-08 → RT-14 | Enables | Independent validation/evidence services provide deterministic acceptance gates for model-proposed changes. | Strong hypothesis |
| DEP-030 | RT-16 → RT-10 | Constrains | Runtime isolation, capability checks, and trusted low-level primitives depend on security policy. | Strong hypothesis |
| DEP-031 | RT-16 → RT-12 | Constrains | Artifact publication, dependency resolution, provenance, and registry trust depend on supply-chain policy. | Strong hypothesis |
| DEP-032 | RT-16 → RT-14 | Constrains | Agent permissions, tool execution, approvals, and auditability depend on the security and authority model. | Strong hypothesis |
| DEP-033 | RT-08 → RT-18 | Enables | Conformance and compatibility claims require reproducible tests, proofs, or other scoped evidence. | Strong hypothesis |
| DEP-034 | RT-12 → RT-18 | Influences | Package/library evolution and compatibility policy shape ecosystem and standard-library evolution. | Strong hypothesis |
| DEP-035 | RT-13 → RT-18 | Influences | Supported targets and backend guarantees affect portability and conformance profiles. | Strong hypothesis |
| DEP-036 | RT-03 → RT-11 | Influences | Purity, state, effects, and observable environment inputs determine which computations can be cached and the sound invalidation scope. | Strong hypothesis |
| DEP-037 | RT-03 → RT-15 | Influences | Evaluation order, state, effects, errors, and concurrency determine semantic equivalence and which edits can be merged independently. | Strong hypothesis |
| DEP-038 | RT-03 → RT-16 | Influences | The language's state, effect, resource, and concurrency semantics define guarantees and threat boundaries available to security controls. | Open hypothesis |
| DEP-039 | RT-03 → RT-18 | Influences | Changes to evaluation, effects, errors, and observable behavior affect conformance profiles and semantic compatibility across versions. | Strong hypothesis |
| DEP-040 | RT-05 → RT-12 | Requires | Package indexes and dynamic dependency resolution require stable object identities and exact, verifiable Content Hash references. | Strong hypothesis |
| DEP-041 | RT-12 → RT-05 | Influences | Package content roots, manifests, and index canonicalization may require explicit separation between object identity, logical package identity, and physical archive identity. | Open hypothesis |
| DEP-042 | RT-12 → RT-11 | Influences | Compact indexes, partial retrieval, and provider-side closure resolution can share cache and incremental-computation infrastructure; cache correctness depends on exact dependency closure and snapshot identity. | Strong hypothesis |
| DEP-043 | RT-16 → RT-12 | Constrains | Dynamic providers, package provenance, signatures, and multi-provider resolution must obey explicit trust and supply-chain boundaries; content hashes alone do not establish publisher trust. | Strong hypothesis |
| DEP-044 | RT-12 → RT-17 | Influences | Compact package catalogs and selective metadata retrieval affect context efficiency, discoverability, and the usability of LLM-facing tooling. | Strong hypothesis |
| DEP-045 | RT-14 → RT-19 | Requires | The Toolchain API operationalizes structured agent changes, context retrieval, provenance, and request/change lifecycle without binding them to one transport. | Strong hypothesis |
| DEP-046 | RT-05 → RT-19 | Requires | Semantic workspaces and typed mutations need stable entity identities, immutable content hashes, and snapshot roots. | Strong hypothesis |
| DEP-047 | RT-15 → RT-19 | Constrains | Import/export, external-edit detection, branch synchronization, and semantic merge must preserve Git portability and the repository representation contract. | Strong hypothesis |
| DEP-048 | RT-16 → RT-19 | Constrains | Workspace scoping, tool permissions, acceptance, commit, sandboxing, and audit requirements constrain every server adapter and operation. | Strong hypothesis |
| DEP-049 | RT-19 → RT-17 | Influences | Structured semantic operations, stable diagnostics, and bounded context may improve agent and human workflows; this requires comparative usability evidence. | Open hypothesis |
| DEP-050 | RT-19 → RT-11 | Influences | Persistent workspace and semantic stores may reuse action-cache infrastructure, but workspace durability and cache validity are separate concerns. | Open hypothesis |
| DEP-051 | RT-02 → RT-20 | Requires | A complete patch plan needs traceable requirements to determine the initial semantic changes and the obligations propagated to callers. | Strong hypothesis |
| DEP-052 | RT-05 → RT-20 | Constrains | Immutable content-addressed function versions and hash-relevant references determine which caller versions and entry-point roots must be recomputed. | Strong hypothesis |
| DEP-053 | RT-06 → RT-20 | Requires | Complete reverse-reference discovery and dependency evidence are prerequisites for a sound caller-impact closure and plan completeness audit. | Strong hypothesis |
| DEP-054 | RT-08 → RT-20 | Requires | Plan execution and commit gates require validation evidence bound to exact candidate hashes, dependency closure, and toolchain configuration. | Strong hypothesis |
| DEP-055 | RT-14 → RT-20 | Influences | The agent change protocol must enforce plan-before-mutation, mandatory planned work, and controlled completion rather than trusting model self-report. | Strong hypothesis |
| DEP-056 | RT-15 → RT-20 | Constrains | Git commit creation, branch concurrency, exact-tree staging, and no-commit-on-failure constrain the completion transaction. | Strong hypothesis |
| DEP-057 | RT-16 → RT-20 | Constrains | Authorization must distinguish plan approval, semantic mutation, validation, commit, and remote push; agents must not bypass completion gates. | Strong hypothesis |
| DEP-058 | RT-19 → RT-20 | Enables | Workspaces, Change Sets, immutable snapshots, and repository coordination provide the operational substrate for CIP planning and verified commit. | Strong hypothesis |
| DEP-059 | RT-20 → RT-19 | Influences | Caller migration decisions, hash propagation, mandatory plan execution, and validation-gated commit add workflow and API requirements to the Toolchain Server. | Strong hypothesis |

## 4. Important feedback loops and conditional relationships

RT-03 is a foundational source for the type/effect model, semantic identity, formal verification, compiler/runtime behavior, incremental computation, semantic merge, security, and conformance. The newly recorded direct edges DEP-036–DEP-039 are research hypotheses derived from [RT-03 core semantics](CORE-LANGUAGE-SEMANTICS.md); they do not imply that any particular semantic profile has been accepted. RT-20 adds a further feedback loop: the Toolchain workflow must enforce the dependency and identity model, while practical caller-migration and hash-propagation experiments may reveal missing distinctions in RT-05/RT-06 or transaction requirements in RT-19.



These are not simple one-way dependencies. They must be tested explicitly:

1. **Semantic core ↔ type/effect/resource model (RT-03 ↔ RT-04).** The core semantics determines what types and effects must express; the selected type/effect model may require changing the semantic core.
2. **Semantic identity ↔ dependency semantics (RT-05 ↔ RT-06).** Hash boundaries determine which dependency edges propagate identity; dependency semantics determine which inputs must be committed by an artifact hash.
3. **Formal semantics ↔ canonical IR (RT-03/05 ↔ RT-07/09).** The IR must be expressive enough for the language but small enough for independently validated semantics and proof encodings.
4. **Runtime ↔ effects/ownership/concurrency (RT-04 ↔ RT-10).** Runtime primitives may reveal missing language concepts; language concepts may require a different runtime boundary.
5. **Backend ↔ language subset (RT-03/04 ↔ RT-09/13).** Backend capability must not silently define source semantics. A target may reject a valid source program, require a different implementation strategy, or impose an explicitly declared profile.
6. **Requirements ↔ verification evidence (RT-02 ↔ RT-07/08).** A proof can establish implementation conformance to a formal contract; it cannot establish that the contract correctly captures human intent.
7. **AI change model ↔ Git/semantic merge (RT-14 ↔ RT-15).** Both need stable operations, baselines, provenance, conflict semantics, and reviewable changes.
8. **Cache ↔ dependency completeness (RT-06 ↔ RT-11).** An incomplete dependency graph can make cache reuse unsound. When completeness is unknown, the cache must conservatively recompute or decline reuse.
9. **Artifact identity ↔ package/target context (RT-05 ↔ RT-12/13).** Target/environment inputs belong in an artifact identity only when they change its meaning; otherwise they may belong in binding or action context.
10. **AI change protocol ↔ Toolchain API (RT-14 ↔ RT-19).** The AI-facing change model defines the semantic intent and provenance; RT-19 defines durable workspaces, transaction boundaries, adapters, and repository synchronization.
11. **Semantic repository ↔ Toolchain synchronization (RT-15 ↔ RT-19).** Git portability and semantic merge constrain import/export and external-edit reconciliation; Toolchain experiments may expose missing repository-level atomicity or recovery requirements.

## 5. Research sequence

Use dependency depth and risk of architectural rework to order research. This is a sequence of research waves, not a waterfall. Parallel work is encouraged within a wave and across independent branches.

| Wave | Research focus | Topics | Why now / exit condition |
|---|---|---|---|
| 0 — Scope and inventory | Goals, constraints, taxonomy, existing assumptions | RT-01, RT-17 (initial UX needs) | Agree on the problem boundary; classify existing documents and unresolved questions. |
| 1 — Semantic foundations | Intent/requirements, observable semantics, state/errors, core execution model | RT-02, RT-03 | Produce candidate semantic foundations and explicit unresolved concepts. |
| 2 — Type and representation foundations | Types/effects/ownership/capabilities; SPG/IR; canonical identity | RT-04, RT-05 | Produce compatible candidate combinations for the language core and program representation. |
| 3 — Formal and dependency foundations | Formal semantics/proof boundary; dependency completeness and impact; evidence model | RT-06, RT-07, RT-08 | Establish what can be proven, what remains unknown, and what evidence supports dependency claims. |
| 4 — Execution and transformation | Compiler pipeline, runtime, target/backends, build/cache | RT-09, RT-10, RT-11, RT-13 | Evaluate end-to-end semantic preservation, execution and incremental-computation options. |
| 5 — Reuse and change | Libraries/packages, AI change protocol, Git/merge, security | RT-12, RT-14, RT-15, RT-16 | Evaluate integration boundaries and collaboration/supply-chain risks against the core. |
| 6 — Ecosystem and synthesis readiness | DX, conformance, evolution, unresolved cross-cutting concerns | RT-17, RT-18 and all unresolved P0/P1 edges | Confirm coverage, close dependency gaps, and prepare normalized option vectors for whole-specification synthesis. |

### Parallelism and provisional assumptions

- RT-02 and RT-03 can progress in parallel if requirement work records semantic assumptions explicitly.
- RT-04 and RT-05 can begin with provisional semantic models, but must be revisited after RT-03.
- RT-06 and RT-07 should proceed together: dependency analysis needs formal semantics, while proof requirements expose missing dependency distinctions.
- RT-09 and RT-10 can investigate alternatives in parallel, but must share a source semantic contract and explicit target assumptions.
- RT-12 and RT-13 can investigate representative use cases before finalizing the core, but cannot freeze package or backend formats.
- RT-14 and RT-15 can proceed in parallel after the graph/change model is sufficiently stable; their shared change identity and conflict model must be reconciled.
- RT-16 is cross-cutting and should audit each wave, not be postponed entirely to Wave 5.
- Existing implementation prototypes may continue when they test a bounded hypothesis, but they must not be treated as commitment to a language-wide architecture.

## 6. Existing research-line placement

The current Scenario 15–34 sequence is a substantial research line primarily spanning RT-02, RT-06, RT-07, and RT-08:

- Scenarios 15–18: intent-to-contract, typed Requirement IR, requirement evolution, semantic impact.
- Scenarios 19–24: impact planning, dependency discovery/classification, counterfactual analysis, coverage-guided and adaptive interaction discovery.
- Scenarios 25–28: formal semantic dependency analysis, minimal formal core, symbolic relational verification, typed IR and proof boundary.
- Scenarios 29–34: independently checked proof boundary, CPC assumption binding, strict QF_LIA profile, canonical typed relational query IR, parser-state binding, and source-to-query semantic correspondence.

This sequence is not a substitute for the other taxonomy areas. In particular, proving one narrow deterministic fragment does not define the complete LLMLang language semantics or settle the full type, ownership, effect, concurrency, runtime, or backend designs.

## 7. Maintaining the map

For each new or revised edge:

- Assign a stable DEP-NNN ID.
- Record source and target research-area IDs, relation type, rationale, affected vectors, evidence, confidence, and assumptions.
- State whether the edge is mandatory, conditional, or merely influential.
- Record the conditions under which the edge could be removed or reversed.
- Link to exact research sections or experiments where possible.
- Revisit edges whenever a foundational vector changes or a new research result contradicts an assumption.

Do not turn a strong hypothesis into a hard compatibility constraint without evidence. Do not silently discard an option because it complicates another topic; record the interaction and assess complete specifications during synthesis.
