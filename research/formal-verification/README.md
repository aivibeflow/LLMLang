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
- [CONTRACT-FORMALIZATION-CORPUS](CONTRACT-FORMALIZATION-CORPUS/)
- [PROOF-OBLIGATION-BENCHMARK](PROOF-OBLIGATION-BENCHMARK/)

## Related shared evidence

- [Lean/Logos source-bound verification prototype](../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/) (shared with semantic representation and dependency analysis).
- [Shared dependency graph prototype](../PROTOTYPES/DEPENDENCY-GRAPH-01/README.md).
- [Semantic representation and dependency analysis](../semantic-representation/README.md), [compiler preservation and translation](../compiler-and-translation/README.md), and [language semantics](../language-design/README.md).
