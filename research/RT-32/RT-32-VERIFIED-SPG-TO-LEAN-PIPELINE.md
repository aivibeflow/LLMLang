# RT-32 — Verified SPG-to-Lean Pipeline

**Status:** Research brief; proposed Toolchain/formal-verification capability, not a language rule or accepted architecture  
**Priority:** P0  
**Primary area:** RT-07 — Formal semantics and verification architecture  
**Related areas:** RT-03, RT-05, RT-08, RT-09, RT-11, RT-24  
**Boundary:** This is a compiler/verification Toolchain capability. It must not make Lean the runtime or semantic authority of LLMLang, and must not require developers or agents to maintain a second, independently authored implementation.

## 1. Purpose

Research a sound, reproducible pipeline that derives a Lean representation and machine-checkable proof obligations from an LLMLang function represented in the Semantic Program Graph (SPG), together with its contracts and the authoritative LLMLang reference semantics.

The intended workflow connects implementation and formal verification as artifacts derived from one semantic source. The developer or coding agent authors the LLMLang function and contracts; the Toolchain constructs the Lean-side representation, generates verification conditions, assists with proof construction, and asks the Lean kernel to check the resulting proof. A generated Lean definition is not by itself evidence that the original LLMLang implementation satisfies its contract.

## 2. Research questions

1. What canonical, typed SPG/semantic IR subset is sufficient to represent function bodies, control flow, calls, effects, ownership-relevant behavior, contracts, and termination evidence?
2. Which embedding strategy is appropriate for each claim?
   - **Shallow embedding:** map admitted LLMLang constructs to corresponding Lean definitions/types and generate theorems over them.
   - **Deep embedding:** define LLMLang syntax/operations and operational semantics in Lean, enabling proofs about interpretation, type preservation, and translation.
   - **Hybrid:** use shallow embeddings for practical function-level proofs and a deep semantic model for language-to-Lean correspondence and the compiler-correctness boundary.
3. How can Lean definitions be generated from SPG without merely copying the contract into a tautological theorem or proving a separately written algorithm?
4. How are proof obligations derived from preconditions, postconditions, structure invariants, branches, calls, loops, recursion, effects, and termination?
5. How should loop obligations cover invariant initialization, preservation, exit/postcondition, and termination measures? How should recursive and mutually recursive functions be handled?
6. How are callees verified compositionally from contracts, and how are callee proof identities and assumptions bound to exact SPG versions?
7. What source-to-Lean correspondence theorem establishes that the generated Lean term faithfully represents the selected LLMLang function and observable behavior?
8. How can SMT solvers, Lean tactics, and LLM-generated proof candidates cooperate while all accepted proofs remain independently kernel-checked?
9. Which constructs must be rejected or marked unverified when the Lean model cannot represent their semantics precisely?
10. How are proof artifacts versioned, cached, invalidated, reproduced, and incrementally recomputed after SPG, contract, compiler, Lean, dependency, or assumption changes?
11. What is the trusted computing base (TCB), including SPG extraction, IR lowering, Lean generation, obligation generation, Lean kernel, imported axioms, external solvers, and runtime assumptions?
12. How does the approach scale from a small verified subset to concurrency, FFI, resource behavior, and target-specific runtime semantics?
13. What is the minimal typed Proof Dependency Graph (PDG) needed to represent proof artifacts, proof obligations, assumptions, contract dependencies, and dependency closure without duplicating the SPG?
14. How should conditional caller proofs be represented when a callee contract is available but no checked implementation proof exists, and how are those assumptions discharged when evidence arrives?
15. Which identities and dependency edges determine proof reuse, re-composition, and invalidation when implementations, contracts, proof artifacts, assumptions, or toolchains change?

## 3. Candidate pipeline

Evaluate, without presupposing the final architecture:

1. **Authoritative input:** LLMLang function, resolved calls, types/effects/ownership facts, contracts, invariants, and provenance in a versioned SPG snapshot.
2. **Admissibility and normalization:** validate membership in a declared verification profile; produce a typed, deterministic verification IR while retaining exact SPG identity and source correspondence.
3. **Lean representation generation:** generate the Lean definition/model and required semantic support definitions. Keep executable representation distinct from theorem statements.
4. **Proof-obligation generation:** derive verification conditions from contracts and control-flow/termination structure; record the SPG nodes and assumptions justifying every obligation.
5. **Proof construction:** use deterministic tactics, SMT-assisted discharge, reusable lemmas, and optional LLM-generated proof candidates. Proof generation is untrusted.
6. **Kernel checking:** have the pinned Lean kernel check every accepted proof artifact; record Lean version, imports, axioms, options, and exact inputs.
7. **Source correspondence:** establish within the declared trust boundary that the generated Lean definition/model corresponds to authoritative LLMLang semantics for the exact SPG snapshot.
8. **Evidence publication:** publish a proof-carrying result linked to function, contract, dependency closure, compiler/generator versions, proof artifact, assumptions, and verification status.
9. **Proof dependency tracking:** maintain a typed PDG projection over proof artifacts and their dependencies. A caller proof must record the exact callee contract theorem/identity it consumes, whether that dependency is backed by a checked callee proof or remains an explicit assumption, and the dependency-closure status. The PDG supplements the SPG; it does not replace source-level call/declaration relations or become a second semantic authority.

Distinguish at least: proven, checked-under-assumptions, conditional, pending_dependencies, tested-only, partial, unsupported, unknown, rejected, and stale. A successful Lean kernel check alone must never establish LLMLang correctness unless source-to-Lean correspondence obligations also pass. `conditional` means a proof term is valid only under explicitly listed assumptions that are not yet discharged; `pending_dependencies` means one or more required evidence artifacts have not yet been bound or checked. Neither status may be presented as `proven`.

### 3.1 Compositional proofs and the Proof Dependency Graph

Research a compositional model in which each function is verified locally against its own contract, while callers are verified using the contracts of callees rather than re-proving their implementations.

- A **local proof** establishes that one exact implementation/SPG revision satisfies one exact contract under a declared semantic profile and assumptions.
- A **compositional caller proof** establishes the caller's contract assuming the preconditions and postconditions of the exact callee contracts used at each call site. It must record those contract dependencies as formal hypotheses/theorem parameters, not merely as prose metadata.
- A caller may be analyzed before a callee implementation proof exists. The resulting theorem may be kernel-checked under the callee contract as an explicit unclosed assumption, but the result is `conditional` or `pending_dependencies`, never end-to-end `proven`.
- When a checked callee proof artifact is available and matches the exact callee contract identity, implementation/SPG provenance, semantic profile, and assumptions required by the caller, bind it to the dependency edge and discharge that assumption. The caller's proof closure can then be promoted only when every other proof and correspondence obligation is closed.
- A callee contract is an abstraction boundary, not evidence by itself that its implementation satisfies it. Nor does a proof of contract satisfaction establish that the contract adequately captures user intent.

The PDG is a specialized, typed evidence graph associated with the SPG. It should represent at least:

| Node/edge | Required meaning |
|---|---|
| Function proof node | Local proof artifact for a particular function implementation and contract. |
| Contract theorem node | Canonical semantic identity of the theorem statement, including types, context/imports, and relevant axioms/assumptions. |
| Proof artifact node | Kernel-checkable artifact plus Lean/kernel version, imports, options, and provenance. |
| Caller-to-contract edge | Exact call-site dependency on a callee contract theorem, including required precondition and consumed postcondition. |
| Contract-to-proof edge | Evidence that a particular implementation revision discharges that contract theorem. |
| Assumption edge | Explicit unresolved premise, with identity, origin, scope, and discharge condition. |
| Proof-closure edge | Dependency relation used to compute whether the complete transitive evidence closure is closed, stale, or incomplete. |

Keep distinct identities for function/SPG revision, contract semantic identity and source provenance, implementation identity, proof artifact identity, verification profile, and toolchain identity. Formatting-only edits need not change a canonical semantic contract identity, but equivalence must be established by canonicalization or proof, never guessed. A proof artifact is not interchangeable merely because its human-readable theorem name is unchanged.

Define at least these evidence states and transitions (final names and granularity remain research questions):

- `conditional`: a valid proof candidate/theorem depends on one or more explicit, unclosed assumptions.
- `pending_dependencies`: proof construction is ready or complete, but required dependency artifacts or bindings have not yet been checked/resolved.
- `proven`: all local obligations, source correspondence obligations, and transitive dependency assumptions are closed by compatible checked evidence under the declared trust boundary.
- `stale`: one or more identities on which the result depends no longer match the current source, contract, semantics, assumptions, or toolchain.

The research must decide whether `conditional` and `pending_dependencies` are orthogonal dimensions or mutually exclusive statuses; they must not collapse into a boolean `verified` flag.

### 3.2 Incremental reuse and invalidation rules

Evaluate these cases explicitly:

1. **Callee body changes, contract semantic identity unchanged:** re-check the callee's local proof. If the new checked proof discharges the same contract theorem under compatible assumptions, a caller's mathematical proof may be reused; refresh the PDG binding/closure rather than regenerating the caller theorem unnecessarily.
2. **Callee contract changes:** invalidate or re-compose every caller proof that consumed the old contract identity. A caller proof parameterized by the old theorem may remain a reusable conditional artifact, but it is not evidence for the new contract until re-composed and checked.
3. **Caller implementation or contract changes:** re-check that caller's local proof and propagate invalidation only through callers whose consumed contract/proof dependencies are affected.
4. **Dependency implementation, proof artifact, assumptions, semantics, or toolchain changes:** compute invalidation from exact typed dependency edges and identity keys. A changed proof artifact with an equivalent checked theorem may permit rebinding after compatibility checks; never infer equivalence from names or matching source text alone.
5. **Missing or incomplete dependency closure:** fail closed; do not publish `proven` even if the caller's isolated Lean theorem passes kernel checking.

The PDG must support deterministic closure computation, incremental invalidation, proof replay, provenance queries, and explanations for why an artifact is reusable, conditional, pending, or stale.

## 4. Required comparisons and experiments

- Compare shallow, deep, and hybrid embeddings on the same bounded set of LLMLang functions.
- Start with pure deterministic functions and explicit preconditions/postconditions; add branches, loops, recursion, calls, and stateful behavior incrementally.
- Include positive and adversarial fixtures: incorrect implementations, weakened contracts, missing loop invariants, invalid termination measures, stale callee proofs, altered SPG bindings, unsupported effects, and deliberately mismatched Lean translations.
- Compare direct proof-obligation generation with generation from a control-flow/verification IR.
- Measure proof construction separately from kernel-check time; record proof size, obligation count, automation success, manual intervention, and incremental recomputation cost.
- Test invalidation after changes to bodies, contracts, dependencies, SPG identities, assumptions, Lean imports/version, and generator versions.
- Demonstrate compositional verification: callers rely on checked callee contracts, with provenance binding each contract to its implementation and exact revision.
- Prototype a typed PDG projection and test conditional caller proofs, assumption discharge, transitive proof closure, and all incremental reuse/invalidation cases in §3.1–3.2.
- Evaluate independent proof replay and reproducibility in pinned CI.

## 5. Safety and soundness constraints

- LLMLang reference semantics and observable behavior remain authoritative; Lean is a proof/checking representation, not a substitute definition of language behavior.
- Never claim source correctness from a theorem about generated Lean code without justified source-to-Lean semantic correspondence.
- Do not generate a second hand-maintained implementation as the proof target. Any generated Lean model must be mechanically tied to SPG.
- Do not trust an LLM, tactic script, SMT solver, or code generator as a proof checker. The Lean kernel is the final checker for Lean proof terms; any external checker needs an explicitly reviewed trust boundary.
- Make assumptions, axioms, admitted theorems, unsupported constructs, and environmental/runtime premises explicit. No silent fallback or unsound approximation.
- Keep proof validity separate from contract adequacy: satisfying a contract does not prove that the contract captures user intent.
- Fail closed when source correspondence, dependency completeness, or supported semantics cannot be established.

## 6. Deliverables

1. Comparison report for shallow, deep, and hybrid embedding strategies.
2. Bounded SPG-to-Lean translation and proof-obligation prototype with pinned Lean toolchain and reproducible fixtures.
3. Source-to-Lean correspondence argument for the supported subset, with explicit assumptions and TCB.
4. Compositional function/callee proof model, including conditional proofs and explicit assumption discharge.
5. Typed PDG schema/prototype and version-bound proof artifact format, linked to but distinct from SPG.
6. Incremental verification/invalidation model tied to SPG and PDG identities and transitive proof closure.
7. Support matrix and explicit unsupported/unknown behavior.
8. Staged expansion proposal and measured limitations; no claim of whole-language verification.

## 7. Exit criteria

- At least one non-trivial LLMLang function is represented in Lean from SPG without a separately authored Lean implementation.
- Generated obligations cover its declared preconditions, postconditions, relevant invariants, and termination requirements.
- The Lean kernel checks the proof artifact in a pinned, reproducible environment.
- Source-to-Lean correspondence covers the complete admitted function subset and observable behavior.
- Negative fixtures reject an incorrect implementation, mismatched translation, stale proof, and unsupported construct.
- Proof provenance binds the result to exact SPG/function/contract/dependency/toolchain identities.
- A caller with an unproved callee is never reported as `proven`; a conditional proof is explicitly marked and its assumptions are machine-traceable.
- A checked callee proof can discharge the corresponding caller assumption only when contract, implementation provenance, semantics, profile, and toolchain compatibility checks pass.
- PDG closure and invalidation fixtures cover changed bodies, changed contracts, stale/missing proof artifacts, unresolved assumptions, and transitive callers.
- Evidence distinguishes kernel-checked Lean facts from end-to-end LLMLang correctness claims.

## 8. Dependencies and non-goals

RT-03 supplies reference semantics and observable behavior; RT-05 supplies typed SPG identity and provenance; RT-07 supplies formal semantics, proof architecture, and TCB; RT-08 supplies fixtures and independent evidence; RT-09 supplies IR/lowering and source correspondence; RT-11 supplies incremental computation and invalidation; RT-24 supplies canonical semantic representation.

This study does not select Lean as the only verifier, require all LLMLang constructs to be formalized at once, define new surface syntax, make proof generation part of the language core, or claim that all program properties are decidable.

## Public-interface integration (2026-11-24; proposed)

For a public operation, generate separately identified obligations for implementation body satisfies its provided contract, and provided contract refines the exact public contract. A caller proof consumes only the public contract facts actually needed; represent an unresolved provider as a traceable conditional assumption. A closed program claim needs an admitted binding and discharged assumptions, including semantic correspondence. PDG must distinguish body proof, refinement proof, binding admission, and public-contract use; recompose exact evidence after provider changes rather than rerun unaffected modular proofs or report an unresolved caller as unconditionally proven. Add negative fixtures for wrong revision, stronger provider precondition, divergence, stale proof, and incompatible observation models.

Related: [Public interfaces and verified contract refinement](../RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## Explicit assumptions and conditional verification (RT-36; proposed)

Use formal hypotheses, extract transitive actual axioms, and distinguish immutable claim identity, evidence closure and scoped trust authorization. A matching proof can discharge a premise only with compatible subject, context and semantics; retain its residual premises. Research cyclic discharge rejection and selective revocation separately. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](../RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This is a candidate follow-up, not an adopted rule or new experimental result.
