# Formal verification and evidence

[Research index](../README.md) · [Research taxonomy](../research-management/RESEARCH-TAXONOMY.md) · [Dependency map](../research-management/RESEARCH-DEPENDENCY-MAP.md)

This direction groups related research studies without changing their RT identifiers, research status, or accepted decisions.

## Studies

| ID | Scope |
|---|---|
| [RT-07](RT-07/) | Formal semantics and verification architecture |
| [RT-08](RT-08/) | Testing, validation, and evidence model |
| [RT-32](RT-32/) | Verified SPG-to-Lean pipeline and compositional proof dependency graph |
| [RT-33](RT-33/) | Proof backend selection and verification orchestration |
| [RT-34](RT-34/) | Automatic complexity inference, resource contracts, and algorithm optimality verification |
| [RT-36](RT-36/) | Formal verification assumptions, trust boundaries and conditional proof management |

## Dedicated research artifacts

- [RT-32 recursive proof discharge](RT-32/RT-32-RECURSIVE-PROOF-DISCHARGE-2026-11-25.md) — distinguishes checked recursive induction from unsupported conditional cycles.
- [RT-07 Lean and Logos proof boundary](RT-07/RT-07-LEAN-LOGOS-PROOF-BOUNDARY-RECHECK-2026-11-25.md) — distinguishes parser verdict conditions, source hypotheses and exact native axiom closure.
- [RT-07 observation equivalence proof](RT-07/RT-07-STATE-RESULT-OBSERVATIONAL-EQUIVALENCE-2026-11-25.md) — kernel-checked equivalence of full observations and preservation of all postconditions.
- [RT-07 operational, denotational and axiomatic comparison](RT-07/RT-07-THREE-SEMANTICS-STATE-RESULT-2026-11-25.md) — finite state/Result and ordered-history semantics.
- [RT-07 Boolean effect order](RT-07/RT-07-BOOLEAN-EFFECT-ORDER-2026-11-25.md) — compares eager and short-circuit evaluation with ordered effects.
- [RT-07 nondeterministic refinement](RT-07/RT-07-NONDETERMINISTIC-REFINEMENT-2026-11-25.md) — compares may, must and explicit nontermination observations.
- [RT-07 sequential contract composition](RT-07/RT-07-SEQUENTIAL-CONTRACT-COMPOSITION-2026-11-25.md) — checks exact handoff and error-trace composition.
- [RT-07 explicit environment boundary](RT-07/RT-07-EXPLICIT-ENVIRONMENT-BOUNDARY-2026-11-25.md) — checks conditional assumptions, observable absence and native correspondence.
- [RT-07 state/Result reference entry](RT-07/RT-07-STATE-RESULT-REFERENCE-ENTRY-2026-11-25.md) — exposes the executable restricted reference semantics and typed admission.
- [RT-07 dead-store alias boundary](RT-07/RT-07-DEAD-STORE-ALIAS-BOUNDARY-2026-11-25.md) — checks when declared write visibility and intervening reads permit removal.
- [RT-07 partial-output observations](RT-07/RT-07-PARTIAL-OUTPUT-OBSERVATIONS-2026-11-25.md) — verifies accepted bytes, terminal failure and adapter traces under coalescing.
- [RT-07 proof validity and adequacy](RT-07/RT-07-PROOF-VALIDITY-AND-ADEQUACY-2026-11-25.md) — proves the transfer condition for recorded intent and checks feasibility and coverage controls.
- [RT-07 per-claim Lean trust](RT-07/RT-07-PER-CLAIM-LEAN-TRUST-2026-11-25.md) — checks exact theorem types, transitive assumptions and native evaluation trust.
- [RT-07 incremental solver evidence](RT-07/RT-07-INCREMENTAL-SOLVER-EVIDENCE-2026-11-25.md) — binds validated models and independent Lean refutations to active assertion and assumption scopes.
- [CONTRACT-FORMALIZATION-CORPUS](CONTRACT-FORMALIZATION-CORPUS/)
- [PROOF-OBLIGATION-BENCHMARK](PROOF-OBLIGATION-BENCHMARK/)

## Related shared evidence

- [Lean/Logos source-bound verification prototype](../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/) (shared with semantic representation and dependency analysis).
- [Shared dependency graph prototype](../PROTOTYPES/DEPENDENCY-GRAPH-01/README.md).
- [Semantic representation and dependency analysis](../semantic-representation/README.md), [compiler preservation and translation](../compiler-and-translation/README.md), and [language semantics](../language-design/README.md).
