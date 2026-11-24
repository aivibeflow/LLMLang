# RT-33 — Proof Backend Selection and Verification Orchestration

**Status:** Research brief; proposed Toolchain/formal-verification capability, not an accepted backend choice or language rule  
**Priority:** P0  
**Primary area:** RT-07 — Formal semantics and verification architecture  
**Related areas:** RT-02, RT-03, RT-05, RT-08, RT-09, RT-11, RT-19, RT-32  
**Tracking:** [Issue #390](https://github.com/aivibeflow/LLMLang/issues/390)  
**Boundary:** Contract meaning and authoritative LLMLang semantics remain backend-independent. Lean, SMT solvers, TLA+, and future engines are verification mechanisms, not sources of LLMLang semantics. This brief does not select a universal backend.

## 1. Purpose

Research how the Toolchain determines which verification backend or combination of backends should check each proof obligation derived from a backend-independent Contract IR and the authoritative LLMLang semantic model.

The system must choose based on the semantic shape of an obligation, the capabilities and limitations of available backends, the required evidence strength, and the declared trust boundary. It must not choose a backend merely because the contract was authored in a particular notation, nor silently weaken an obligation to fit a backend.

## 2. Proposed architecture

1. **Source intent and clarifications:** retain original requirements, provenance, and explicit ambiguity resolutions.
2. **Backend-independent Contract IR:** represent preconditions, postconditions, invariants, frame/effect constraints, state-transition properties, termination/resource properties, assumptions, and provenance with typed semantics.
3. **Proof-obligation decomposition:** derive independently identifiable obligations from the contract and relevant implementation/semantic model. Preserve dependencies and the exact source/contract snapshot.
4. **Backend capability analysis:** compare each obligation's semantic features with versioned backend capability profiles, including supported theories, finite/infinite-state limits, arithmetic domains, concurrency/temporal constructs, evidence formats, and soundness boundaries.
5. **Backend planning:** select one or more eligible backends per obligation, or explicitly report that no available backend can handle it. A plan may use complementary analyses rather than forcing a single engine.
6. **Translation and checking:** generate backend-specific artifacts and establish the required correspondence between each artifact and the authoritative obligation. A solver's answer is not automatically a proof of the original LLMLang claim.
7. **Evidence aggregation:** combine results only under explicit composition rules, retain per-obligation provenance and assumptions, and compute an overall result without masking unknown or unsupported parts.
8. **Incremental reuse:** bind results to exact semantic identities, obligation identities, translation versions, backend versions/configurations, assumptions, and dependency closure.

This is a Toolchain verification-planning capability. It does not belong in LLMLang surface syntax as a mandatory backend annotation.

## 3. Candidate backend roles (hypotheses, not a fixed mapping)

| Backend | Potential strengths | Limitations to investigate |
|---|---|---|
| Lean | General theorem proving, inductive definitions, compositional proofs, kernel-checkable proof terms, semantic correspondence theorems | Proof construction cost, library/modeling effort, automation boundaries, TCB and imported axioms |
| SMT | Arithmetic, bit-vectors, arrays, uninterpreted functions, decidable fragments, fast verification-condition discharge | Theory/fragment limits, quantifier behavior, solver trust, proof certificate availability/checking, unknown and timeout semantics |
| TLA+ / model checking | State-transition systems, temporal properties, concurrency/protocol behavior, counterexample traces | State-space explosion, finite model bounds, fairness assumptions, refinement/correspondence to implementation |
| Other engines | Specialized domains such as separation logic, termination, or model finding | Must meet the same capability, soundness, provenance, and reproducibility criteria |

These are candidate roles, not exclusive assignments. Arithmetic obligations may be discharged by SMT while a Lean theorem checks a larger compositional argument; a state-transition model may be explored in TLA+ while a separate correspondence obligation relates the model to LLMLang semantics. Such combinations must be researched rather than assumed.

## 4. Obligation model and selection inputs

For each obligation, investigate a typed descriptor containing:
- stable obligation identity and exact Contract IR/source semantic snapshot;
- claim kind and logical structure (arithmetic, algebraic, memory/ownership, state transition, temporal, termination, resource, refinement, or source correspondence);
- types, domains, theories, quantifiers, effects, and relevant semantic features;
- assumptions, invariants, environment constraints, and dependency obligations;
- required evidence strength and whether a meaningful counterexample is expected;
- available backend capability-profile versions and known unsupported constructs;
- translation path, correspondence obligation, and trusted computing base;
- resource limits, reproducibility inputs, and expected evidence artifact format.

The classifier and planner must be conservative. If an obligation cannot be classified confidently, uncertainty remains explicit; the system must not guess a narrower obligation.

## 5. Selection and orchestration questions

1. Which obligation taxonomy guides backend selection without encoding backend-specific syntax into Contract IR?
2. Should selection be rule-based, capability-query based, cost/quality optimized, learned from measured outcomes, or hybrid? Which parts must remain deterministic and auditable?
3. How are backend capability profiles versioned, tested, and independently reviewed?
4. When should one obligation be sent to multiple backends (diverse checking, complementary decomposition, or fallback), and how is agreement/disagreement interpreted?
5. How can a backend-specific translation be shown to preserve the original obligation's meaning?
6. Which proof formats/certificates can be independently checked, and where is a solver/backend itself inside the trusted computing base?
7. How should finite model bounds, fairness assumptions, arithmetic overflow models, abstraction, and environment assumptions be surfaced?
8. How are SAT, UNSAT, UNKNOWN, timeout, crash, unsupported, and malformed-result outcomes distinguished?
9. How are obligations decomposed and recomposed without losing quantifier scope, assumptions, dependency links, or proof strength?
10. Can Lean serve as an optional independent checking/integration layer for selected results without requiring every backend to reduce to Lean? What evidence is needed for each route?
11. How are evidence identities, cache keys, invalidation, and reproducibility handled when backend, translation, solver version, configuration, or semantic snapshot changes?
12. How should the planner expose cost, latency, proof robustness, and counterexample quality without allowing optimization to lower the required evidence standard?

## 6. Result semantics and safety rules

The orchestration layer must preserve at least these outcomes:

- **proven** — every required obligation is supported by evidence meeting its declared checking and correspondence requirements, with all required assumptions discharged.
- **disproven** — a valid counterexample or checked refutation demonstrates violation of the exact obligation under its declared model and assumptions.
- **unknown** — no conclusive result was obtained, including timeout, resource exhaustion, solver unknown, incomplete dependencies, or unresolved evidence.
- **unsupported** — no available backend/translation supports the required semantics with the required evidence strength.
- **error** — backend or orchestration execution failed or returned malformed/inconsistent output.

A project/function result is proven only if all mandatory obligations and source/implementation correspondence obligations are closed. A successful check of a translated artifact alone is insufficient. Unsupported, unknown, error, conditional assumptions, or missing obligations must never be collapsed into success.

A counterexample is scoped to its model, bounds, assumptions, and translation correspondence. Finite model checking does not imply an unbounded theorem. UNSAT from a solver does not imply a source-level proof unless the solver result and translation are covered by an accepted trust/checking basis.

## 7. Evidence composition and trust

Research a typed evidence graph binding source requirements and clarifications; Contract IR and obligation identities; implementation/SPG revision and semantic profile; backend-specific input/output artifacts; backend, translator, checker, libraries, options, and resource limits; assumptions, model bounds, environment constraints, and dependency closure; correspondence evidence from source semantics to backend model and back; and final aggregation rule/result.

Do not assume that two backends agreeing makes either translation sound. Diversity can improve confidence only when independence assumptions and shared failure modes are understood. Preserve disagreement and partial evidence for diagnosis.

RT-32's SPG-to-Lean work remains relevant and should be generalized carefully: Lean is one candidate proof backend and a possible checker for selected evidence, not the required universal destination for all proofs.

## 8. Evaluation plan

Use the backend-independent [contract formalization debug corpus](CONTRACT-FORMALIZATION-CORPUS/README.md) as a starting point, extending it with arithmetic, arrays, algebraic properties, state machines, concurrency, temporal/fairness claims, termination, and resource bounds.

For each case, preserve one semantic oracle and compare correct backend selection/abstention; translation fidelity and unsupported-feature detection; proof/counterexample correctness against independent oracles; evidence strength, trust assumptions, and reproducibility; false success/failure rates; proof construction/checking time, memory, cost, and counterexample usefulness; and robustness across backend/tool versions.

Do not score a backend as successful merely because it proves an incorrectly weakened or incomplete translation. Contract semantic fidelity and non-overconstraint remain separate from backend proof success.

## 9. Dependencies and exit criteria

**Dependencies:** RT-03 reference semantics; RT-05 SPG and semantic identity; RT-07 verification architecture; RT-08 testing/evidence model; RT-09 typed IR and lowering; RT-11 incremental computation/cache; RT-32 SPG-to-Lean correspondence; contract formalization corpus.

**Exit criteria:**
1. A backend-independent obligation taxonomy and typed planner input are specified.
2. Lean, SMT, and TLA+ are compared on representative shared obligations, with other engines considered where justified.
3. Capability profiles and selection/abstention rules are reproducible and versioned.
4. Translation soundness and trust requirements are explicit for every supported backend route.
5. Evidence composition preserves partial, conditional, unknown, unsupported, and conflicting outcomes.
6. Adversarial corpus cases demonstrate that unsupported semantics and weakened translations cannot yield false proven results.
7. The research documents whether a Lean checking route is useful for selected artifacts and why universal Lean reduction is or is not justified.

## 10. Explicit non-decisions

This brief does not select Lean, SMT, TLA+, or any other engine as universal verifier; require all proofs to be translated into Lean; make backend choice part of Contract IR semantics or LLMLang source syntax; assert that all backends provide independently checkable proof certificates; treat backend agreement as proof of translation correctness; or make a recommendation normative before comparative research and explicit review.
