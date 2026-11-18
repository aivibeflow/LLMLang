# SCW-05 — Declaration contexts: implementation breakdown

**Status:** In progress  
**Parent:** Research Scenario 34, task SCW-05  
**Scope:** Define the finite declaration context used by the initial deterministic QF_LIA source fragment. This task defines the data model only; validation rules and typing judgments belong to SCW-06 and SCW-07.

## Design decisions

- A variable has a stable `VariableId`; its identity is not derived from its display/source name.
- Every declaration records its source name, role (`input`, `local`, or `state`), and sort (`Int` or `Bool`).
- A declaration context is a finite ordered collection of declarations. Order is retained for deterministic traversal and canonical symbol assignment; it does not imply execution order.
- Context lookup is by `VariableId`. Name uniqueness, duplicate-ID rejection, scope, initialization, legal reads/writes, and observation eligibility are validation obligations for SCW-06.
- The declaration model must not depend on Logos, CPC, cvc5, Python, or the solver integration layer.
- This task does not change the existing expression AST or claim that its string-based variable references are context-validated. That connection is SCW-07.

## Fine-grained tasks

- [ ] **SCW-05.1 — Define variable identity.** Add a small identity type with decidable equality and representation suitable for finite contexts.
- [ ] **SCW-05.2 — Define declaration roles.** Distinguish input, local, and state declarations without conflating role with sort.
- [ ] **SCW-05.3 — Define typed declarations.** Store identity, source name, role, and `ExprSort` in one declaration record.
- [ ] **SCW-05.4 — Define finite declaration contexts.** Represent an ordered finite collection and provide identity-based lookup.
- [ ] **SCW-05.5 — Add focused examples/tests.** Exercise lookup, role distinction, and both sorts; do not test SCW-06 validation rules here.
- [ ] **SCW-05.6 — Integrate the module into the pinned Lean build.** Add the module to the library roots and ensure CI kernel-compiles it.
- [ ] **SCW-05.7 — Record evidence.** Update Scenario 34 only after the module and tests pass in CI; record exact commit and run.

## Acceptance criteria

- All three roles and both sorts are representable.
- Variable identity is independent of source-name text.
- Contexts are finite and preserve declaration order.
- Lookup is by stable identity and returns the declared role/name/sort together.
- The module has no imports from external checker/solver integration.
- Lean compilation and focused tests pass in the pinned toolchain.
- No `sorry`, `admit`, or new project-local axioms are introduced.

## Explicit non-goals

- Rejecting duplicate IDs or duplicate names.
- Enforcing declaration scope, initialization, read/write legality, or observation eligibility.
- Proving source expression typing or connecting existing string references to declarations.
- Defining commands, execution, symbolic execution, or relational semantics.
