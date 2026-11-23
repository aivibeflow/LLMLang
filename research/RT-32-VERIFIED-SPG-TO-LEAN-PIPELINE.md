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

Distinguish at least: proven, checked-under-assumptions, tested-only, partial, unsupported, unknown, rejected, and stale. A successful Lean kernel check alone must never establish LLMLang correctness unless source-to-Lean correspondence obligations also pass.

## 4. Required comparisons and experiments

- Compare shallow, deep, and hybrid embeddings on the same bounded set of LLMLang functions.
- Start with pure deterministic functions and explicit preconditions/postconditions; add branches, loops, recursion, calls, and stateful behavior incrementally.
- Include positive and adversarial fixtures: incorrect implementations, weakened contracts, missing loop invariants, invalid termination measures, stale callee proofs, altered SPG bindings, unsupported effects, and deliberately mismatched Lean translations.
- Compare direct proof-obligation generation with generation from a control-flow/verification IR.
- Measure proof construction separately from kernel-check time; record proof size, obligation count, automation success, manual intervention, and incremental recomputation cost.
- Test invalidation after changes to bodies, contracts, dependencies, SPG identities, assumptions, Lean imports/version, and generator versions.
- Demonstrate compositional verification: callers rely on checked callee contracts, with provenance binding each contract to its implementation and exact revision.
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
4. Compositional function/callee proof model and version-bound proof artifact format.
5. Incremental verification/invalidation model tied to SPG identities and dependency closure.
6. Support matrix and explicit unsupported/unknown behavior.
7. Staged expansion proposal and measured limitations; no claim of whole-language verification.

## 7. Exit criteria

- At least one non-trivial LLMLang function is represented in Lean from SPG without a separately authored Lean implementation.
- Generated obligations cover its declared preconditions, postconditions, relevant invariants, and termination requirements.
- The Lean kernel checks the proof artifact in a pinned, reproducible environment.
- Source-to-Lean correspondence covers the complete admitted function subset and observable behavior.
- Negative fixtures reject an incorrect implementation, mismatched translation, stale proof, and unsupported construct.
- Proof provenance binds the result to exact SPG/function/contract/dependency/toolchain identities.
- Evidence distinguishes kernel-checked Lean facts from end-to-end LLMLang correctness claims.

## 8. Dependencies and non-goals

RT-03 supplies reference semantics and observable behavior; RT-05 supplies typed SPG identity and provenance; RT-07 supplies formal semantics, proof architecture, and TCB; RT-08 supplies fixtures and independent evidence; RT-09 supplies IR/lowering and source correspondence; RT-11 supplies incremental computation and invalidation; RT-24 supplies canonical semantic representation.

This study does not select Lean as the only verifier, require all LLMLang constructs to be formalized at once, define new surface syntax, make proof generation part of the language core, or claim that all program properties are decidable.
