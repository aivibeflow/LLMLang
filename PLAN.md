# LLMLang Research and Development Plan

**Status:** living plan  
**Updated:** 2026-11-20
**Restored baseline:** detailed plan from [`aa39c8f`](https://github.com/aivibeflow/LLMLang/commit/aa39c8fc2a611ae72ff85acff3de3c16fcc4eb39), reconciled with the current project plan and repository evidence  
**PR #47 consolidation:** its cumulative research snapshot (`73d37723e6a759159b354c2cd74327517c4036c4`) was reconciled into §§1.4, 1.4.1, and 5 by the valid text update in [PR #51](https://github.com/aivibeflow/LLMLang/pull/51), commit [`7fd8eac`](https://github.com/aivibeflow/LLMLang/commit/7fd8eace9210dffdbdcd98302e19bf6bc18be756); later path-analysis evidence through Scenario 107 distinguishes replayable witnesses, trusted/checked UNSAT, conservative UNKNOWN handling, externally enforced worker deadlines, mutation-aware call-state transitions, and field-sensitive alias effects. The PR #47 consolidation remains exploratory: it records candidate vectors and validation limits without selecting language rules.<br>
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

**Terminology prerequisite:** Review [`draft/GLOSSARY.md`](draft/GLOSSARY.md) before changing this section or related RT-20/RT-24/package identity work. Preserve the distinct proposed identities `OpHash`, `ImplHash`, `CCHash`, optional `CandidateSetHash`, and conformance-evidence identity; reconcile the plan's existing `ImpHash` spelling with the glossary's `ImplHash` before treating either as normative. The glossary is a proposal, not an accepted schema or hash-envelope decision.

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
- [x] Define an initial shared observable-behavior vocabulary and finite representative corpus for pure results, explicit errors, ordered effects, handler outcomes, and final fixture state; broader language coverage remains open.
- [x] Implement a bounded executable reference-semantics slice for RT-03 candidates A and D over the shared fragment; it is an exploratory interpreter, not a complete semantics or profile selection.
- [x] Implement a second RT-03 evaluator using an independent small-step control/value-stack algorithm and differentially compare complete traces/results/final fixture state against the recursive evaluator, including nine generated two-write cases. This is algorithmic independence, not independent specification review.
- [x] Add an explicit `result_sequence` construct to both RT-03 evaluators: propagate the first Result error unchanged, skip later expressions, return the final success when all items succeed, and reject non-Result items. Differential tests also prove ordinary `sequence` remains strict and unchanged. This is an explicit prototype construct, not implicit call propagation, exceptions, cancellation, or cleanup semantics.
- [x] Add a distinct terminal `cancel` outcome to both RT-03 evaluators. Cancellation discards pending continuations, preserves already completed effects, and is observably distinct from a Result error even with the same reason payload. Differential tests cover cancellation inside nested Result/ordinary sequences. This is a synchronous control-flow slice only; async/concurrent cancellation, call boundaries, resource unwinding, and cleanup remain open.
- [x] Add a structured `with_resource` scope to both RT-03 evaluators. It records acquisition/use/release, releases after success and Result error, unwinds nested scopes LIFO on cancellation, preserves primary plus cleanup failures, and exposes unreleased resources when release fails. Differential tests cover acquisition failure, cleanup after errors/cancellation, nested unwind order, and cleanup failure aggregation. This is a fixture-level structured resource protocol, not an ownership/borrow checker; branching, transfer/return, async behavior, and source-to-scope completeness remain open.
- [x] Add a bounded boolean `if` expression to both RT-03 evaluators. Only the selected branch executes; malformed non-boolean conditions fail closed. Differential scenarios verify that enclosing resource scopes release after branch Result errors and cancellation. This covers concrete execution paths only; symbolic/path-sensitive completeness and independent path-model review remain open.
- [x] Add a third RT-03 structural path model that imports neither evaluator and independently enumerates bounded branch/resource paths. It forks non-literal conditions, respects literal booleans, models cancellation during condition evaluation, LIFO cleanup, cleanup failures, active-resource leftovers, and explicit Result-sequence short-circuiting. Tests compare predicted resource event sequences and final active-resource sets against both evaluators over a finite corpus. This is not a source-level CFG extractor or proof of branch completeness; symbolic path feasibility, source-to-expression completeness, and independent human/formal review remain open. Extend the cross-check with an exhaustive 72-case matrix over branch choice, two nested release success/failure flags, and selected/unselected normal, Result-error, and cancellation expressions. Tighten the analysis vocabulary so unknown conditions require an explicit `unknown_bool` marker, reject literal non-boolean conditions, and traverse nested addition/Result wrappers without missing cancellation paths. Add a fourth, independently derived resource outcome-algebra model that computes exact acquire/release traces, cleanup-error precedence, cancellation cleanup aggregation, and retained resources. Compare its exact outputs against both evaluators and projections against the path model over 144 generated cases (scope depths 1–3, all release flags, normal/Result-error/cancellation outcomes, and each acquisition-failure position). This validates only the bounded fixture protocol; it does not settle ownership/borrowing/transfer semantics.
- [x] Extend the bounded reference corpus with Result propagation, resource acquire/use/release, cleanup, cancellation, branching, an independent structural path model, and an independent resource outcome-algebra model. The latter compares exact traces/results/final resources against both evaluators over a 144-case generated matrix. These are finite executable cross-checks, not a formal proof or external review; broader observations and independent review remain open.
- [ ] Validate RT-03 dependency-map edges through concrete downstream research and experiments.
- [x] Extend the bounded experiment set with typed calls, owned-resource return and cleanup alternatives, recursion/fuel, and actor blocking/progress; record the limits in Scenarios 35–41 and the RT-03/04 shared corpus. These are comparative probes, not selected language rules.
- [x] Execute Scenario 97's six cleanup-error composition candidates over its 12 discriminators and a 13,230-case valid outcome/ownership product; cross-check resource obligations with a separate audit projection. This distinguishes cause carriers while leaving policy choice and source-level completeness open.
- [x] Exhaust all 128 concrete assignments of a seven-condition RT-03 AST fixture and compare them with eight structural paths and both evaluators; record the parser/source-extraction limits in Scenario 98. This is finite AST-path evidence, not source-language completeness.
- [x] Constrain repeated occurrences of the same `unknown_bool` marker to reuse their earlier path choice; compare both concrete assignments against the two feasible paths in Scenario 99. This is marker-identity correlation only, not general symbolic feasibility or source value-identity evidence.
- [x] Exhaust all four assignments in a two-variable Boolean predicate IR for sequential `x` and `x or y` branches; compare the three feasible path vectors and concrete witnesses with both evaluators and resource traces in Scenario 100. This is an exponential finite truth-table model, not a solver or source-CFG completeness result.
- [x] Cross-check Scenario 100 route sets and replayable witnesses with pinned SymPy 1.14.0 DPLL2; compare truth-table and solver medians on a conjunction family through 18 Boolean inputs in Scenario 101. The performance result covers one easy family only; solver trust, hard formulas, a real timeout boundary, and source correspondence remain open.
- [x] Compare exact finite, tri-state, bounded-hybrid, and proof-carrying path-pruning policies in Scenario 102. Eight result-policy fixtures verify that replayable witnesses establish feasibility and that timeout/UNKNOWN/errors or untrusted UNSAT do not prune a possible path; 128 fixed-seed formulas cross-check route sets and witnesses against exhaustive enumeration. This does not exercise a real solver timeout or establish source correspondence.
- [x] Exercise one real solver wall-clock limit through a per-query worker; a hard pigeonhole query is killed/reaped and remains UNKNOWN in Scenario 103. This is one pinned-backend case, not a performance distribution or general worker architecture validation.
- [x] Exhaust a two-state mutable Boolean fixture across name-conflated, unlinked versions, and transition-constrained versions in Scenario 104; name reuse across a write loses both reachable routes, while correct transition constraints recover the concrete route set. Aliasing and source/IR extraction remain open.
- [x] Compare pure, known-toggle, and unknown/may-write call summaries over the exhaustive Boolean state-pair domain in Scenario 105; incomplete summaries must havoc caller-visible state in the bounded model or they can drop reachable routes. Source-derived effect and alias summaries remain open.
- [x] Exhaust the two-field call-site alias domain for exact, disjoint, may-alias, and unknown points-to cases in Scenario 106; field-sensitive precise aliases preserve routes while incomplete alias sets broaden them conservatively. General source-derived points-to analysis remains open; Scenario 107 covers only a tiny AST subset.
- [x] Derive a toggle summary and branch-joined call alias sets from a bounded Python-shaped AST subset in Scenario 107; eight cases preserve all concrete routes, while non-relational joins can add infeasible routes. General parsing, source/CFG completeness, and path-sensitive alias analysis remain open.
- [ ] Exercise broader resource limits and difficult formula families; authenticate or check negative-result evidence before solver-based path pruning; bind immutable predicate versions and source CFG extraction to route constraints.
- [ ] Normalize the surviving vectors for whole-specification synthesis; do not select a profile or transfer it into `draft/` by implication.

**Evidence:** [RT-03 — Core Language Semantics](research/CORE-LANGUAGE-SEMANTICS.md).

**Status:** researched at the candidate-survey level; partially validated only as a map of options and trade-offs. No semantic profile, evaluation strategy, effect model, or complete observation model has been accepted. The existing QF_LIA/Lean/Logos work covers a narrow relational fragment and is not a complete language semantics.

**Next work:** integrate the typed-call, owned-result return, cleanup-disposition/composition, bounded-recursion/fuel, actor-progress, and AST-path probes into a grammar-bound source-to-model account. Compare varied satisfiable/unsatisfiable formula families and timeout/unknown behavior; model mutation/version boundaries; bind a parser/IR extractor to branch-node coverage; make effect order/payload observable in cross-profile summaries; and obtain independent human/formal review. Cover call-boundary unwinding, ownership transfer/return, asynchronous cancellation, cleanup divergence, and termination-budget exhaustion before expanding the expression fragment. Keep profile A–D alternatives open.

### 1.4.1 Type, effect, ownership, and capability alternatives (RT-04)

- [x] Survey type identity/compatibility, refinement and typestate, inference, effect representations/handlers, ownership/borrowing/lifetimes, capabilities, concurrency/memory models, and error/resource outcomes.
- [x] Cross-map candidate RT-04 mechanisms against RT-03 profiles A–D without selecting a profile.
- [x] Record candidate hash-boundary questions for operation contracts, implementations, conformance classes, and verification evidence.
- [x] Implement the first executable RT-04 declaration-level comparison for refinement, transitive effect summaries, capabilities, and affine resource consumption; add 12 focused unit tests and record the limits. This is one exploratory checker model, not two complete reference semantics.
- [x] Extend Profile B with a finite CFG resource-flow experiment and tests for branch-consistent joins, inconsistent joins, repeated consumption, loops, and malformed CFG references. This validates only the supplied CFG model, not source-to-CFG completeness.
- [x] Add direct/transitive effect-bound validation and fixtures requiring UNKNOWN for missing call-graph completeness or unresolved callees; retain definite rejection when a known effect already exceeds the bound. The completeness list is fixture-level asserted metadata, not authenticated source-analysis evidence.
- [x] Extend the executable corpus with typed call-site arity, argument-type, and expected-result checks plus a structural `Result<Ok, Err>` type-constructor experiment. Typed call-site targets must also occur in the coarse call graph; missing callee signatures yield UNKNOWN. This remains a declaration-level experiment, not source type inference or a selected ADT semantics.
- [x] Add a Profile B scoped-capability grant experiment: hierarchical POSIX path scopes, parent-child attenuation, explicit call-site grant delegation, recipient acceptance, and ancestor revocation propagation. Missing delegation yields UNKNOWN; malformed or over-broad grants fail closed. This is fixture-level static checking, not runtime token authentication or revocation.
- [ ] Replace fixture-level call-graph completeness assertions with source/snapshot-bound evidence; extend resource analysis with symbolic path conditions, transfer/return, and cleanup; define runtime capability issuer/trust and concurrent revocation semantics.
- [x] Add a first shared observable-trace fixture oracle for RT-03 profiles A and D and cross-check it against RT-04 checker vectors A and B; cover pure return, declared filesystem read, ordered writes, and undeclared effects. This is a finite compatibility oracle, not a second complete reference semantics. See [cross-profile trace report](research/RT-04-RT-03-CROSS-PROFILE-TRACES.md).
- [x] Implement a second independently derived resource outcome-algebra model and compare its exact resource traces/results/final maps against both RT-03 evaluators, plus the structural path model's resource projections, over 144 generated cases. This is independent corroboration only for the bounded resource-scope outcome rules; it is not a second complete cross-aspect semantics model.
- [ ] Independently review the comparative report and validate RT-03↔RT-04 dependency assumptions.
- [ ] Reconcile RT-04 semantic distinctions with RT-05 identity and RT-07 proof boundaries before selecting hash-bearing fields.

**Evidence:** [RT-04 alternatives report](research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md); [Prototype 01 implementation and tests](research/PROTOTYPES/RT-04-01/README.md); [Prototype 01 results](research/RT-04-PROTOTYPE-01-RESULTS.md); [scenario matrix](research/RT-04-PROTOTYPE-01-SCENARIOS.md).

**Status:** comparative survey and bounded prototypes are in place, but no type/effect/ownership/capability architecture is selected. The corpus now includes typed calls, owned-resource returns, cleanup dispositions/composition, effect-bound and capability checks, shared RT-03/RT-04 trace fixtures, and independent resource outcome/obligation projections. New studies include [COR-13](research/RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md), [Scenario 35](research/RESEARCH-SCENARIO-35-RESOURCE-RETURN-AND-CLEANUP.md), and [Scenario 97](research/RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md). The call-graph completeness metadata remains fixture asserted rather than source/snapshot-bound; source-to-CFG and path-condition completeness, ordered effect summaries, row unification/handler coverage, trusted capability evidence, and concurrent revocation remain open. Independent review and reconciliation with RT-05 identity and RT-07 proof boundaries are required before hash-boundary or architecture decisions.

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
- [x] Verify the CPC parser-state bridge and exact assumption-list binding adversarially for the version-2 relational-query envelope; pinned Lean CI run [44185102839](https://github.com/aivibeflow/LLMLang/actions/runs/44185102839) passed parser-state binding and factor-pair fixtures. This binds the CPC assumptions to the decoded query; it does not prove the decoded query is semantically derived from source.
- [ ] Prove that the canonical relational query is semantically derived from the source program; follow the fine-grained SCW-04–SCW-41 decomposition in [Scenario 34](research/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md); SCW-04 module-boundary audit is complete, and SCW-15 is the next implementation task.
- [ ] Keep QF_LIA as a conservative profile; reject unsupported strings, nonlinear arithmetic, and constructs outside the profile.
- [ ] Test SAT/UNSAT/UNKNOWN handling and solver protocol failures.
- [ ] Record what is checked by Lean, what is trusted in Logos, and what remains outside the proof boundary.

**Existing evidence:** scenarios 29–33; `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`; QF_LIA Python prototype and focused tests; CI workflow.

**Status:** partially validated. The pinned Lean/Logos build and version-2 CPC parser-state/factor-pair adversarial suite pass (run 44185102839). `SourceQuerySemantics.lean` proves expression-level preservation; `RelationalSourceQuerySemantics.lean` adds kernel-checked expression-level per-side translation, canonical input naming, shared-input/factor-split, and factor/observation-difference lemmas. The SCW-04 audit is recorded in `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SCW-04-MODULE-BOUNDARY-AUDIT.md`. SCW-15 implementation now separates `RelationalSourceQuerySemantics.lean` (imports only the independent source/query semantics) from `LogosQueryAdapter.lean` (the only module importing both semantic IR and Logos). The adapter includes a kernel theorem for semantic preservation; pinned Lean CI verification is still pending. Command execution, mutable state, complete program observations, paired program runs, and source-derived canonical query binding remain open. See Scenario 34 for decomposed tasks and gates.

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

- [x] Synthesize Scenarios 19, 20, 25 and RT-19/20/23 into a candidate Semantic Dependency Index contract; keep it explicitly non-canonical pending SPG schema decisions.
- [x] Define and implement an executable candidate SPG subset and typed dependency extractor; this is a research prototype, not the canonical language schema.
- [x] Specify candidate stable call-site identity, conditional target representation, and source/target relation constraints; validate them with focused tests.
- [x] Add a snapshot-scoped dependency-index projection so RT-20 reverse lookup excludes historical caller versions and remains pinned to one exact Semantic Snapshot.
- [x] Bind snapshot-scoped reverse lookup to explicit completeness evidence, exact snapshot/target/scope, extractor/schema identity, and the digest of the returned edge set; fail closed to UNKNOWN or NOT_CHECKED when evidence is absent or mismatched.
- [x] Connect the reverse-query result to impact-planning completeness audits; require Snapshot-bound evidence by default, preserve every evidence binding in the plan identity, and force full revalidation on missing or mismatched bindings. The research prototype does not authenticate the producer or prove its observation model complete.
- [x] Add a differential Snapshot payload-scan audit for reverse-index edge coverage and bind its evidence to the exact query.
- [x] Represent caller compatibility per exact call-site/target edge; require explicit evidence-backed migrate/preserve/adapt/fork decisions and resulting caller hashes; block plans with missing or unresolved decisions. Prototype coverage includes mixed old/new behavior and shared-caller version selection.
- [x] Bind each call-site/target alternative to its exact caller-required Contract hash; keep the provided Contract reference solely on the callee and resolve it through the existing caller-to-callee edge in RT-20 planning, validation, and semantic diff. Do not duplicate provided-contract hashes in call edges, reverse-index edges, or CIP decisions (declaration schema v2; dependency-index schema v3; not yet normatively equated with glossary CCHash).
- [ ] Reconcile the candidate subset with the canonical SPG schema and formal semantics before normative adoption.
- [ ] Define semantic dependencies separately from provenance, audit observations, and traceability.
- [ ] Define hash-relevant dependency edges and dependency closure.
- [ ] Define how dependencies are discovered from static analysis, typed IR, runtime observations, tests, and formal semantics.
- [ ] Define confidence/evidence classes for dependency edges.
- [ ] Define sound conservative may-depend graphs.
- [ ] Define how missing or incomplete dependency evidence affects reuse.
- [ ] Define cycles and strongly connected components for analysis and scheduling.
- [ ] Define change-impact analysis for requirement, contract, design, implementation, and target changes.

**Existing evidence:** scenarios 18–28 and prototypes 18–28 in `research/PROTOTYPES/DEPENDENCY-GRAPH-01/`.

**Status:** extensively researched and prototyped in Scenarios 18–28 and dependency-graph prototypes 18–28. A candidate index contract and executable typed extractor now exist in `research/SEMANTIC-DEPENDENCY-INDEX.md` and `research/PROTOTYPES/DEPENDENCY-GRAPH-01/`. The candidate schema is not canonical; reconciliation with the accepted SPG model, formal soundness, and Toolchain integration remain open.

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
- [ ] Define automatic merge when changes are provably independent.
- [ ] Define conservative conflict behavior when independence cannot be established.
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

### 4.5 End-to-end semantic merge and synchronized commit lifecycle

**Study these documents as one set before changing this workstream:**
- [Git Representation and Semantic Merge](research/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) — primary research source for repository representation and semantic merge rules.
- [ADR-014](docs/adr/014-git-semantic-merge.md) — proposed architecture direction; not Accepted.
- [RT-20](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) — caller impact, per-call-site migration/preservation, hash propagation, and verified completion.
- [RT-22](research/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md) — repository/worktree operations, merge reconciliation boundary, commit preparation, and recovery.
- [RT-23](research/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) — shared semantic state, versioned interface mappings, incremental worktree views, and synchronized semantic/filesystem commit.
- [RT-19](research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) — semantic Change Set/Snapshot lifecycle and transport-neutral API.

The documents have explicit ownership boundaries and reciprocal links. Re-read the complete set together whenever merge, rebase, cherry-pick, semantic export/import, or commit behavior changes.

**Detailed candidate contract:** [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md). RT-24 is a research proposal, not an accepted format or merge decision. Its identity/SPG reconciliation is recorded in [RT-24 Identity and SPG Reconciliation](research/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md), with the scenario comparison in [RT-24 Identity Architecture Decision Matrix](research/RT-24-IDENTITY-DECISION-MATRIX.md). There is no standalone RT-05 specification in the current repository; the relevant evidence is distributed across Studies 05–08, RT-03, Semantic Dependency Index research, and the executable prototypes.

**Refined execution order:**
- [x] Reconcile RT-24 against the current identity/SPG research and executable subset; record the competing Stable Entity ID versus content-addressed-value models, occurrence/selection and lineage boundary, current prototype fields/limitations, hash-layer distinctions, and dependency-completeness gap in RT-24 Identity and SPG Reconciliation. No identity architecture or canonical SPG schema was selected.
- [x] Compare Studies 05–08 against rename, identical-value/different-occurrence, split/merge, move, call-site, and branch-merge scenarios in RT-24 Identity Architecture Decision Matrix. This completes the comparison, not the architecture decision.
- [ ] Decide Stable Entity ID + Content Hash versus content-addressed values with explicit lineage/selection after completing RT-03/RT-04 semantic reconciliation and the decision gates recorded in the matrix.
- [ ] Reconcile the selected identity model with RT-03 language semantics and RT-04 type/effect research before freezing hash-relevant fields and canonical SPG object/edge schemas.
- [ ] Integrate the existing ReverseLookupEvidence/query_snapshot_incoming completeness gate with RT-20 CIP and the semantic merge coordinator; define the independent audit producer, observation coverage, evidence trust policy, and end-to-end fail-closed tests. The prototype already binds evidence to snapshot, target, scope, extractor/schema, and exact edge-set digest, but does not authenticate the producer or prove its observation model complete.
- [ ] Select the smallest supported SPG subset and specify its textual source inventory/manifest fixture. Keep the repository source textual; treat local stores, caches, and indexes as reconstructible derived state.
- [ ] Implement deterministic importer/exporter for that subset and test semantic round-trip, byte-identical canonical export, physical independence (format/order/file moves), explicit schema versioning, and fail-closed errors.
- [ ] Implement typed SemanticDiff with exact snapshot binding, per-call-site reference changes, root/dependency changes, lineage records, and deterministic output.
- [ ] Implement a pure three-way merge core over pinned base/ours/theirs snapshots. Apply only unambiguous rules; emit structured conflicts for update/update, delete/update, identity/lineage, retarget, dependency, root, and unsupported-context cases.
- [ ] Validate the entire merged graph, not just merged files/entities; prove that incomplete source inventory or reverse-reference context cannot yield a clean result.
- [ ] Integrate RT-20 CIP as a mandatory gate: preserve/migrate/adapt/fork per call site, support mixed old/new callers and shared-caller splits, and rebuild the candidate whenever planned changes alter it.
- [ ] Integrate Interface Mapping Revision merge separately under RT-23 parent-revision/CAS/scope rules; test disjoint keys, same-key conflicts, delete/update, and stale baselines.
- [ ] Only after the pure core passes, build a Git repository coordinator with explicit base/ours/theirs trees; then test merge, rebase, and cherry-pick against real temporary repositories. Keep per-file merge driver as an adapter, not a whole-graph correctness boundary.
- [ ] Finally integrate RT-23 exact-tree synchronized commit and idempotent crash/timeout recovery; test clone reconstruction without the original local semantic database.

**Required sequence:**
- [ ] Reconcile the canonical textual repository representation, manifests/roots, external dependency pins, and deterministic import/export; prove clean-clone reconstruction and round-trip equivalence.
- [ ] Define semantic diff over stable semantic identities, separating Git object identity, semantic identity, and action/evidence identity.
- [ ] Specify deterministic three-way SPG merge over exact base/ours/theirs snapshots, including independent add/add, same-entity update/update, delete/update, rename/move, split/merge, replacement, and dependency/lock changes.
- [ ] Define a structured conflict/result model with provenance, exact input roots, merge policy/tool versions, resolution decisions, and explicit clean/conflict/invalid/insufficient-context outcomes.
- [ ] Specify merge rules for versioned Interface Mapping Revisions separately from immutable semantic objects; use revision/CAS baselines and fail on same-key or otherwise ambiguous conflicts.
- [ ] Design a repository-level merge coordinator with complete tree context. Do not treat independent per-file merge-driver success as proof of whole-SPG consistency.
- [ ] Integrate the semantic engine with ordinary Git merge/rebase/cherry-pick. Prototype the custom merge driver and interactive mergetool, explicit local setup/doctor behavior, and fail-closed behavior when the coordinator or required context is unavailable.
- [ ] After Git creates a candidate merged tree, import/reconcile the complete LLMLang representation into the shared semantic state; run repository-wide graph/reference/contract checks and RT-20 caller-impact, per-call-site migration, hash-propagation, and evidence checks.
- [ ] Finalize only through RT-23's synchronized commit protocol: pin the exact semantic snapshot, mapping revision, worktree generation, selected regular-file changes, expected Git ref, and validation evidence; materialize canonical LLMLang representation and selected files into the actual worktree; commit them together.
- [ ] Specify idempotent recovery for interruption before/after Git ref update, timeout with unknown outcome, stale HEAD/tree, partial export, and repeated completion requests. Never report semantic state as committed merely because it exists in the Toolchain store.
- [ ] Add real temporary-repository end-to-end tests for clone/reconstruction, parallel branches, merge/rebase/cherry-pick, cross-file conflicts, mapping conflicts, RT-20 caller splits, clean and failed validation, crash recovery, and no-duplicate commit retry.
- [ ] Benchmark repository-level merge, semantic import/export, incremental worktree synchronization, and cache/store reconstruction; record platform and repository-size assumptions.

**Status:** architecture research exists and is cross-linked; RT-24 now records a candidate technical contract. Canonical representation, identity/schema reconciliation, semantic diff/merge implementation, Git integration, and tests remain open. ADR-014 remains Proposed. ADR-014 remains Proposed.

**Dependency:** canonical SPG/identity and import/export decisions from Stages 1 and 3; RT-20 impact-plan correctness; RT-19 semantic API; RT-22 repository/worktree contract; RT-23 shared-state and synchronized-commit runtime.

**Exit criteria:** clean clone reconstructs the exact declared semantic state; commits map deterministically to semantic snapshots and mapping revisions; repository-level semantic merge works for independent and conflicting changes; merged graphs pass RT-20 impact/hash/caller checks; the exact validated semantic state and selected regular files are synchronized into one recoverable Git commit; merge/rebase/cherry-pick, fallback, interactive resolution, and crash recovery are tested.

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
- [x] Add a reproducible Provider benchmark harness for chain, diamond, high-fan-out, and many-dependency graphs; report time, throughput, Python allocation peak, process RSS, temporary-directory disk high-water, and archive size.
- [x] Add CI stress coverage for 1,200-object chain and high-fan-out dependency closures.
- [ ] Run and retain representative small/medium/large benchmark baselines on controlled hardware; CI measurements are exploratory and are not acceptance thresholds.
- [ ] Define a public immutable snapshot read API that can expose exact object metadata, dependency edges, and streaming payloads without private storage access; then implement a Provider adapter for a persistent backend.

**Existing evidence:** [Package System: Static and Dynamic Packages](research/PACKAGE-SYSTEM.md), extending the earlier [Libraries and Templates](research/LIBRARIES-AND-TEMPLATES.md) and [Global Semantic Artifact Store](research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md) proposals.

**Status:** researched and prototyped at an exploratory level. A candidate TOML manifest schema, example fixture, Package Content Root Hash projection, identity exclusions, and PMI invariants are documented. The logical index, external-memory validation, streaming archive writer/verifier, exact dependency-policy resolver, and disk-backed Provider-to-archive pipeline have executable prototypes and CI coverage. The Provider uses SQLite for graph traversal state and streams sorted index rows plus one object payload at a time. A reproducible benchmark harness and 1,200-object chain/high-fan-out stress tests are implemented; CI records exploratory measurements, but controlled-hardware baselines and large-scale acceptance criteria remain open. The Toolchain Server Prototype 01 currently has only an in-memory lifecycle model and does not expose the public snapshot enumeration, dependency-edge, or streaming-payload API needed by Provider; no adapter is added against its private state. A persistent immutable-object backend and public snapshot read contract remain open. No normative wire format, codec policy, provider protocol, cache-index schema, final manifest schema, canonical hash encoding, or digest algorithm has been accepted.


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

**Status:** an initial threat model and tested authorization-policy experiment now exist in [RT-16 Threat Model 01](research/RT-16-THREAT-MODEL-01.md). They cover scope binding, human approval, replay, evidence identity, and fail-closed checks at fixture level. A complete security architecture remains open; persistent multi-client authorization, concurrency/crash injection, sandbox testing, signed/authenticated evidence, and operational approval policy are high-priority gaps.

## 7.5 Developer experience and adoption

- [ ] Define human-readable source and semantic review workflows.
- [ ] Define diagnostics that explain semantic impact and failed contracts.
- [ ] Define editor, language-server, and debugging requirements.
- [ ] Define migration and interoperability with existing languages and build systems.
- [ ] Evaluate learning curve and review quality for human developers.
- [ ] Evaluate LLM authoring workflows without treating generated output as trusted.
- [ ] Build representative end-to-end examples.
- [ ] Define practical adoption criteria and migration strategy.

**Status:** initial workload acceptance criteria and an executable CLI corpus with C and Python host references are recorded in [RT-01 Reference Workloads](research/RT-01-REFERENCE-WORKLOADS.md). These do not yet measure LLMLang implementations or human/agent usability; diagnostics, review quality, context/token use, repair effort, scope violations, and adoption criteria still need controlled study.

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
- [x] Preserve the caller-required contract hash and exact callee identity in each call-site decision; resolve the callee-provided contract through the callee declaration rather than storing a duplicate reference. Require PROVEN compatibility status plus evidence identity for resolved decisions and verify the bindings against materialized baseline/candidate objects.
- [x] Require shared-caller version-split analysis when different consumers need old and new behavior.
- [x] Define a candidate Change Impact Plan (CIP), plan-completeness checks, and mandatory plan execution.
- [x] Specify the proposed completion gate: freeze candidate, verify plan coverage, validate and audit exact hashes, then create a Git commit only on success.
- [x] Prototype a candidate Snapshot materialization check for planned call-site decisions: bind exact baseline/candidate roots, verify selected caller/callee membership and stored hashes, and inspect the actual candidate call-site target.
- [x] Audit the complete candidate dependency closure: recompute Snapshot root, traverse transitive typed references, verify object hashes and target kinds, and compare payload-derived edges with stored dependency metadata.
- [ ] Reconcile the function hashId and call-reference assumptions with identity Studies 05–08 and the RT-24 Identity and SPG Reconciliation report; no standalone RT-05 specification currently exists.
- [ ] Specify reverse-reference completeness for direct, indirect, dynamic, external, and generated call sites.
- [ ] Prototype single-chain propagation, mixed old/new callers, shared-caller splits, multiple call sites, and branching/converging graphs.
- [ ] Extend the call-site plan identity to represent one shared caller forked into multiple consumer/path-specific caller versions; the current prototype assumes one resulting version per base caller hash.
- [x] Extend CIP-to-diff enforcement with versioned output slots, exact typed-reference/call-target edge deltas (including call-site Contract bindings), post-materialization output-hash bindings, and consumer-path-specific shared-caller forks. The current implementation tests declaration add/remove/replace, typed-reference additions/rewrites, call-target add/remove/rewrite/condition changes, required-Contract migration, caller deletion, and a branching/converging caller split. Action-kind/prerequisite/evidence sufficiency, dynamic dependency completeness, behavioral compatibility, and commit authorization remain open.
- [ ] Prototype failed-validation/no-commit, exact-tree commit, concurrency rejection, and idempotent retry behavior.
- [ ] Reconcile the completion transaction with RT-19 persistence, crash recovery, atomic export, and Git coordination.

**Evidence:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](research/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) records the proposed workflow and invariants. It is a research proposal, not an accepted identity or Toolchain decision.

**Status:** RT-20 remains a research proposal. The dependency-graph prototype includes Snapshot-scoped reverse lookup, differential payload-scan auditing, per-call-site compatibility planning, candidate call-site materialization checks, and a complete explicit-declaration dependency-closure audit. The candidate declaration schema is v2: each call-site alternative pins its required Contract hash, each callable callee owns one provided-Contract reference, and RT-20 decisions preserve the caller requirement plus exact callee identity without duplicating the provided-Contract reference. The dependency-index edge projection is v3. The graph audit checks exact object hashes, transitive target resolution/kinds, and consistency between payload-derived edges and stored dependency metadata. CIP schema v2 adds exact output slots, typed-reference/call-target edge deltas, materialized output-hash bindings, and consumer-path-specific shared-caller forks. PR #24 is merged. Post-merge workflows on `cf51c15a34cee14a8b0390322be0a15d9ee85559` passed: semantic dependency 101 tests + compilation, repository structure 6 + 78 tests, and strict QF_LIA 30 tests + compileall. Action-kind/prerequisite/evidence sufficiency, dynamic dependency completeness, behavioral compatibility, and a validation-gated commit remain open.

**Evidence:** [RT-20 Candidate Call-Site Validation](research/RT-20-CANDIDATE-CALL-SITE-VALIDATION.md), [RT-20 Candidate Graph Audit](research/RT-20-CANDIDATE-GRAPH-AUDIT.md), and tests under `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/`.

**Exit criteria:** a complete server-validated plan precedes all mutations; every relevant call site has an evidence-backed compatibility decision; contract and hash propagation are independently correct; old/new behavior and shared-caller version splits work; every planned change is enforced and unplanned changes are rejected; commit is created only for the exact candidate that passed all mandatory checks.

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
| Comparative language design space | Scenarios 35–107; `RESEARCH-OPTION-MATRIX-01.md` | Broad evidence-linked alternatives added across semantics, types/resources, syntax, runtime, identity, verification, cache trust, diagnostics, scheduling, backend preservation, cleanup composition, and AST-path analysis; initial matrix only, no candidate selected and many discriminating corpora remain unrun |
| RT-03/RT-04 semantics and resource boundaries | `CORE-LANGUAGE-SEMANTICS.md`, RT-04 report, shared corpus, COR-13, Scenarios 35–41, 97–107 | Multiple bounded evaluators and focused cross-checks exist, including Scenario 97's 72 policy observations/13,230-case valid owner-debt audit, Scenario 98's 128 assignments/eight paths, Scenario 99's repeated-marker correlation, Scenario 100's finite predicate witnesses, Scenario 101's pinned solver agreement/one-family timing, Scenario 102's 128 fixed-seed formula comparisons and conservative unknown-result fixtures, Scenario 103's real worker timeout/reaping, Scenario 104's exhaustive mutation-identity counterexample, Scenario 105's pure/toggle/may-write call summary comparison, and Scenario 106's exact/may-alias transition comparison and Scenario 107's bounded source-derived alias-summary comparison; broader timeout distributions, hard-formula performance, solver trust/proof checking, parser/source completeness, general source-derived alias summaries, call/return/cleanup integration, async/concurrent cases, independent review, and cross-aspect compatibility remain open |
| Identity and call binding | RT-05 lifecycle/recursive/call-site experiments; RT-24 decision matrix | Candidate lifecycle/address models compared on finite fixtures; exact OpHash/ImpHash and contract boundaries, source correspondence, branch conflicts, and canonical SPG integration remain undecided |
| Reference workloads and agent tasks | `RT-01-REFERENCE-WORKLOADS.md`; `PROTOTYPES/CLI-WORKLOADS-01/` | Shared acceptance criteria and C/Python CLI host references exist; LLMLang candidate execution, controlled human/agent evaluation, and workload-weight calibration remain open |
| Formal verification architecture | `LLMLang-FORMAL-VERIFICATION.md` | Researched; complete formal semantics not finished |
| Typed requirements and contracts | Scenarios 15–19; prototypes 16–19 | Prototyped; broader language integration remains |
| Dependency discovery and impact | Scenarios 20–28; prototypes 20–28 | Extensively prototyped; sound end-to-end completeness remains |
| SMT/proof boundary | Scenarios 29–34; Logos/Lean binding prototype; QF_LIA profile and typed query IR | Partially validated; pinned Lean CI build and current tests pass; QF_LIA path remains restricted/candidate and source-to-query/program-level correspondence remains unproved |
| Semantic compilation cache | `SEMANTIC-COMPILATION-CACHE.md` | Researched; implementation and empirical validation remain |
| Cache speedup estimate | `COMPILATION-CACHE-SPEEDUP-ESTIMATE.md` | Analytical estimate exists; controlled runtime benchmarks remain |
| Binding and invalidation measurements | `RT-11-BINDING-INVALIDATION-BENCHMARK.md`; `PROTOTYPES/DEPENDENCY-GRAPH-01/src/binding_build_benchmark.py` | Synthetic C experiment records compile/link/verification action counts for exact versus separate linkage; production dependency discovery, remote trust, and controlled-hardware timing remain open |
| POSIX runtime | `POSIX-RUNTIME-ARCHITECTURE.md` | Researched; profile and vertical slice remain open |
| Translation/backends | `TRANSLATION-AND-TARGET-BACKENDS.md` | Researched; backend implementation remains |
| LLVM backend | `LLVM-BACKEND-ARCHITECTURE.md` | Researched; lowering and validation remain |
| Source-to-LLVM semantic preservation | Scenario 96; LL-020; `LLVM-BACKEND-ARCHITECTURE.md` | LLVM UB/poison and source-level wrapping, checked-failure, and memory-bound semantics are compared; the version-pinned source-to-IR corpus and target validation remain unrun |
| Libraries and templates | `LIBRARIES-AND-TEMPLATES.md` | Researched; detailed decisions remain |
| Global artifact store | `GLOBAL-SEMANTIC-ARTIFACT-STORE.md` | Researched; store and trust implementation remain |
| Git representation and semantic merge | `GIT-SEMANTIC-REPOSITORY.md`; ADR-014 | Research completed at concept level; ADR-014 is Proposed; implementation and merge evaluation deferred |
| Toolchain Server and semantic development API | `RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md`; Development Engine RFC | Proposal drafted; API, storage, synchronization, MCP adapter, and failure semantics remain unvalidated |
| Security and trust | `RT-16-THREAT-MODEL-01.md`; RT-16 authorization prototype | Initial threat model and 24-fixture policy experiment exist; persistent concurrent authorization, crash recovery, sandbox attacks, authenticated evidence, and operational policy remain open |
| Developer experience and adoption | `RT-01-REFERENCE-WORKLOADS.md`; Development Engine RFC | Initial workload criteria and authoring protocol exist; controlled human/agent usability, diagnostics, review quality, and adoption research remain open |

### PR #47 cumulative research scope

PR #47's cumulative snapshot (`73d37723e6a759159b354c2cd74327517c4036c4`) added research across the following plan areas. This inventory is a map of evidence to work stages, not a list of selected LLMLang rules.

| Snapshot scope | Research in the cumulative snapshot | Plan follow-through |
|---|---|---|
| Core outcomes and resource boundaries | Scenarios 35–41; COR-13; RT-03/04 shared corpus and prototypes for typed calls, owned-resource returns, cleanup dispositions, recursion/fuel, and actor progress | Continue Stage 1.4/1.4.1 with source-to-model/path completeness, ordered effects, call/return/cleanup integration, and independent review. Keep each result bounded to its fixture. |
| Language feature space | Scenarios 42–76, covering generics and dispatch, modules and initialization, compile-time and macro boundaries, numeric/string behavior, API evolution, concurrency, errors, ownership, mutability, initialization, subtyping, interfaces, layouts, disposal, and regex resource bounds | Keep alternatives in the option matrix; add discriminating executable corpora and cross-aspect checks before proposing a coherent profile. No feature policy is selected by a prior-art survey. |
| Syntax, evaluation, and API surface | Scenarios 77–89, covering call argument order, floating-point behavior, literal/comment/import/file/numeric/signature/binding/async syntax, defaults, and automatic semicolon insertion | Treat syntax/parser acceptance separately from runtime semantics and API compatibility. Pin source modes and toolchain versions when turning proposed cases into runnable comparisons. |
| Identity and digest lifecycle | Scenarios 90–91; RT-05 lifecycle, recursive identity, and call-site refactor experiments; RT-24 decision matrix | Continue Stage 1.2/1.3 and Stage 4 identity work with rename/move, recursion, call-site changes, migration, and branch-conflict cases. Do not finalize hash payloads or canonical SPG fields by implication. |
| Workloads, measurement, and trust | RT-01 CLI reference workloads, RT-11 binding/invalidation benchmark, RT-16 threat model and authorization prototype, and `RESEARCH-OPTION-MATRIX-01.md` | Continue Stage 3/7 measurements on controlled workloads and hardware, and extend security lifecycle tests. Preserve the current limits: host references are not LLMLang evaluations, synthetic action counts are not production timings, and policy fixtures are not a complete security architecture. |

The current research index spans Scenarios 01–107, the dated Research State register, and executable prototypes across RT-03/04, RT-05/11/16, and dependency analysis. Scenarios 92–107 extend coverage to operation/implementation identity, cache-result trust, scheduler fairness, human/agent diagnostics, LLVM semantic preservation, cleanup-error composition across outcomes and ownership, and bounded AST-path analysis through repeated-marker correlation, finite Boolean feasibility, solver cross-checking, real timeout isolation, mutation-aware predicate versions, call mutation summaries, field-sensitive alias sets, and a bounded AST-derived may-alias summary with join-correlation limits. Scenario numbering is a historical sequence, not a substitute for the stage ordering in this plan. The [Research State 2026-11-19](research/RESEARCH-STATE-2026-11-19.md) summarizes evidence, unresolved gates, and the next research sequence; it supplements rather than replaces the detailed stage entries here.

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

The [Research State 2026-11-19](research/RESEARCH-STATE-2026-11-19.md) consolidates the new corpus, evidence levels, open questions, and synthesis gates recorded in the research continuation work. The priorities below incorporate the cumulative research content of PR #47. Experiments and prior-art comparisons inform candidate vectors; they do not select semantics or authorize transfer into `draft/`.

1. **Close the shared source-semantics and type/resource gap.** Compare typed calls, owned-resource results, transfer/return, cleanup failure composition and ordering, ordered effects, cancellation, and recursion/fuel across RT-03 profiles and RT-04 type/resource alternatives. Scenarios 97–107 provide bounded outcome composition, ownership auditing, finite predicate paths, solver cross-checking, conservative UNKNOWN handling, one real worker deadline, mutation-identity counterexamples, call-summary transitions, alias-sensitive path cases, and one bounded source-derived alias adapter; broader hard-formula distributions, negative-result trust/checking, full parser/source correspondence, general alias/call/loop analysis, and independent review remain required before claiming source-level completeness.
2. **Advance identity and dependency completeness in parallel where independent.** Reconcile stable IDs, content-derived values, explicit lineage, and scoped selectors against import, rename/move, duplication, split/merge, recursive groups, call-site edits, and branch conflicts. Bind calls to explicit contract/implementation choices; test negative and fallback dependency reads; retain `UNKNOWN` when completeness or provenance is absent. Do not settle OpHash/ImpHash or canonical SPG fields by implication.
3. **Complete the evidence and backend-preservation gate.** Continue Scenario 34's source-to-query proof from explicit wire-envelope assumptions through the supported encoder and program fragment. For LL-020 / Scenario 96, run a version-pinned source-to-LLVM corpus and validate that overflow, partial operations, pointer bounds/provenance, and optimization flags preserve the chosen source semantics. Run a narrow shared workload against reference semantics and a second implementation/backend, comparing results, ordered effects, errors, resources, diagnostics, and rejected constructs. Keep the QF_LIA profile restricted and fail closed.
4. **Run representative workloads and human/agent evaluations.** Use RT-01's shared acceptance criteria and CLI corpus with C/Python host references when LLMLang candidates can execute it. Define workload weights before aggregate scoring; measure task success, repair attempts, diagnostics, context/token use, review quality, and scope violations separately from correctness.
5. **Extend security and operational-lifecycle evidence.** Build on RT-16's threat model and policy fixtures with persistent multi-client authorization, concurrent reservation, crash recovery around apply/accept/commit/push/publication, hostile build-worker sandbox cases, and authenticated evidence/provenance. Specify which lifecycle actions require human or policy approval.
6. **Continue package/cache validation without fixing speculative wire formats.** For RT-11/12/19/23, measure controlled cold/warm and scoped-change cases, implement a public immutable snapshot adapter and canonical dependency extraction against the SPG, and extend manifest/cache-index validation. Keep ZIP, binary index, codec, and provider choices provisional until the contracts and resource bounds are validated.
7. **Refresh the option matrix and synthesis gates from results.** Record evidence class, assumptions, confidence, unknowns, compatibility constraints, and falsifiers for each surviving vector. Compare complete candidate specifications only after major criteria have evidence; publish workload-weight sensitivity and preserve failed or unknown cases.
8. **Draft the RFC after candidate comparison.** Select and baseline only a coherent candidate with explicit rationale, compatibility evidence, and unresolved risks. A narrower RFC may proceed earlier only if it clearly scopes and labels unresolved design choices. Keep ADR-014 Proposed and defer end-to-end semantic-merge implementation/benchmarks until synthesis narrows the representation and merge policy.

The package work has separate implementation details in Stage 7.2 and the semantic storage work in Stage 4. Do not skip a gate because a document or prototype exists: each artifact is evidence for only the claims and inputs it actually covers, not proof that its design is correct or complete.

---

# 9. Maintenance
- Update this plan when a research item starts, produces evidence, is superseded, or reaches an accepted decision.
- Keep stable item names and links where possible so other documents can refer to them.
- Add new work to the appropriate stage rather than appending an unprioritized backlog.
- Record cross-stage dependencies explicitly.
- When a decision is accepted, update `TODO.md` and the relevant research/design document; do not mark it accepted solely because this plan recommends it.
- Keep implementation bugs and short-lived tasks in the appropriate issue/task tracker; this document is the ordered research and development programme.
- Review this plan whenever the research corpus or architecture changes materially.
