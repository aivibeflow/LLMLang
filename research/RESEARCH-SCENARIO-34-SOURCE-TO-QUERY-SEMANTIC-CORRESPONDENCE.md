# Research Scenario 34 — Source-to-Query Semantic Correspondence

**Status:** Formalization target and proof plan; no source-to-query correspondence theorem has yet been implemented or proved.  
**Date:** 2026-11-17  
**Depends on:** Scenarios 26–33.  
**Question:** What must be defined and proved before a QF_LIA relational query generated from an LLMLang program can be treated as a faithful encoding of that program's semantics?

## 1. Objective and trust boundary

The outstanding gap is not another serialization check. It is a semantic theorem connecting:

1. a well-formed source program in a precisely delimited deterministic fragment;
2. its execution under an explicit input and initial state;
3. the paired executions used for a counterfactual dependency query;
4. the Boolean formula represented by the canonical relational query IR.

The theorem must be independent of Python tests and independent of the SMT solver. Python may remain the current query producer, but Lean must define the source-fragment semantics and validate or reconstruct the query in a way that does not trust Python's claim that the query is correct.

The proof is staged. A theorem about expressions is not a theorem about commands; a theorem about one execution is not a theorem about paired execution; a theorem about a Lean query evaluator is not yet a theorem about SMT-LIB or CPC.

## 2. Initial source fragment

The first formal fragment is intentionally smaller than the Python prototype's accepted syntax.

### 2.1 Values and types

- Values are mathematical integers and Booleans.
- Types are exactly `Int` and `Bool`.
- Integer arithmetic is unbounded mathematical arithmetic, not machine-word arithmetic.
- Boolean operators have ordinary two-valued semantics.
- Equality is type-preserving; ordering is defined only for integers.

This is the same arithmetic model required by QF_LIA. Machine overflow, floating point, strings, pointers, and memory aliasing are outside this fragment.

### 2.2 Expressions

The initial expression grammar contains:

- integer and Boolean literals;
- typed input/local/state variable references;
- unary integer negation and Boolean negation;
- integer addition, subtraction, and multiplication by a literal integer constant;
- integer and Boolean equality;
- integer less-than and less-than-or-equal;
- Boolean conjunction and disjunction;
- typed conditional expressions (`ite`).

The source typing relation must be explicit. The query IR's result-sort index is not a substitute for proving that the source expression is well typed.

Multiplication is accepted only when at least one operand is syntactically an integer literal after the source fragment's specified normalization. No algebraic simplification or constant folding may be silently assumed by the proof.

### 2.3 Commands and program shape

The initial command grammar contains:

- assignment to a local;
- assignment to an explicitly declared observable or internal state region;
- conditional with two command sequences;
- one top-level final return.

The initial program has:
- an explicit finite declaration context for inputs, locals, and state regions;
- a fully specified initial state;
- no uninitialized reads;
- no loops, recursion, exceptions, events, I/O, external calls, concurrency, nondeterminism, or pointer/alias operations;
- no early return from a nested branch; control flow is normalized so every path reaches the single final return.

The prototype may accept a wider set than the first theorem. The theorem's accepted grammar is authoritative for the proof milestone; unsupported constructs must be rejected rather than approximated.

## 3. Source operational semantics

Define a typed environment as a total mapping from declared names to values of their declared types. Define a machine configuration as:

`Configuration = (programCounter, locals, state)`

For the initial no-loop fragment, a big-step semantics is also acceptable:

`⟨commands, locals, state⟩ ⇓ ⟨locals', state'⟩`

The rules must specify:

- expression evaluation against the current locals and state;
- assignment evaluation before updating the target;
- branch selection using the evaluated Boolean condition;
- sequential command execution;
- final return evaluation after all preceding commands.

State writes are sequential and visible to later commands. Observable state is selected by an explicit observation contract; internal state must not become observable merely because it exists in the implementation.

The semantics must be deterministic. Prove determinism before using a single-valued execution function in the relational theorem.

## 4. Relational semantics

For a selected input factor (p), construct two initial input environments (ho_L) and (ho_R) with these constraints:

- the selected factor may differ;
- every other declared input is equal on both sides;
- initial state is identical;
- no other environmental source exists in this fragment.

Run the same source program on both sides from the same initial state. Define the observation as a typed tuple containing:

- returned value;
- values of exactly the state regions named by the observation contract.

The initial fragment has only normal termination. The outcome discriminator can therefore be omitted, but this omission is justified only by the source grammar and a proof that every accepted program returns normally. It must not be generalized to a language with exceptions or divergent execution.

Define:

`FactorDiff := inputL[p] ≠ inputR[p]`

`ObservationDiff := observe(run(P, ρL, σ0)) ≠ observe(run(P, ρR, σ0))`

The query's intended proposition is:

`FactorDiff ∧ ObservationDiff`

A satisfying assignment is a concrete counterexample witness that changing only factor (p) can change an observed result. Unsatisfiability establishes independence only under the stated fragment, input model, and observation contract.

## 5. Required correspondence theorems

The proof must be split into independently reviewable lemmas.

### SC-1 — Expression typing preservation

If a source expression is well typed with result sort (s), its translation is a well-typed QueryTerm of sort (s).

### SC-2 — Expression evaluation preservation

For every well-typed source expression (e) and well-formed environment (ho):

`evalSource(e, ρ) = evalQuery(translateExpr(e), ρ)`

This theorem covers all accepted expression constructors, including Boolean operations, comparisons, conditional expressions, and literal multiplication.

### SC-3 — Command-sequence preservation

For every accepted command sequence and initial local/state environment, source execution and translated symbolic execution produce equivalent final locals and state.

The symbolic execution result must retain path conditions. Conditional branches may be represented by guarded updates or by `ite`; the proof must show that the chosen representation is equivalent to operational branch selection.

### SC-4 — Program observation preservation

For every accepted program and input/state environment, the observation extracted from source execution equals the observation extracted from the translated execution.

### SC-5 — Paired-execution preservation

For every pair of input environments satisfying the shared-input and shared-initial-state constraints, the two translated executions preserve both source observations. This must be proved for arbitrary left/right values, not only finite test domains.

### SC-6 — Relational-query correctness

The canonical query formula evaluates to true exactly when:
- the selected factor differs between the two inputs; and
- the source observations differ.

This is the core source-to-query correspondence theorem.

### SC-7 — QF_LIA admissibility

Every query generated from a program accepted by the strict fragment is in QF_LIA. In particular, the proof must show:
- all symbols have declared Bool/Int sorts;
- all arithmetic operators are linear;
- no unsupported term is emitted;
- every query symbol is bound to the intended left/right input, local, or state value.

A Python validator test is useful regression coverage, but it cannot replace this theorem or an independently checked Lean validator.

## 6. Lean implementation architecture

Do not put all semantics into the existing Logos binding module. Split the proof core from the external checker integration.

Proposed modules:

- `SourceSyntax.lean` — typed source expression and command ASTs, declaration contexts, and well-formedness predicates.
- `SourceSemantics.lean` — expression evaluation and deterministic command/program execution.
- `SymbolicTranslation.lean` — source-to-symbolic translation and path-condition construction.
- `Correspondence.lean` — SC-1 through SC-7 theorems.
- `LogosBinding.lean` — existing CPC parser bridge, JSON decoder, and Eo.Term renderer.

The Lean proof core must not import cvc5, invoke a solver, or trust Python-generated proof claims. The external Logos binding can consume a query only after Lean has validated its source/query correspondence certificate or independently reconstructed the expected query.

Avoid introducing a generic compiler framework prematurely. The first formalization should use a small inductive syntax and explicit functions.

## 7. Proof strategy and order

1. Define typed expressions and a typed environment.
2. Prove expression evaluation is total for well-typed terms.
3. Define QueryTerm evaluation independently of Logos syntax.
4. Define `translateExpr` and prove SC-1 and SC-2 by structural induction.
5. Define command execution and prove determinism.
6. Define symbolic execution for assignments and conditionals.
7. Prove SC-3 and SC-4.
8. Define paired inputs and observations; prove SC-5.
9. Define the relational formula and prove SC-6.
10. Prove linearity and declaration completeness (SC-7).
11. Only then connect the Lean relational formula to the existing canonical JSON decoder and exact Logos assumptions.

At each stage, add executable examples and negative tests, but do not label tests as proofs. Each theorem should be a kernel-checked Lean theorem with no `sorry`, admitted axiom, or unreviewed custom axiom.

## 8. Important semantic hazards

- **Integer model:** QF_LIA uses mathematical integers. If LLMLang later uses bounded machine integers, overflow semantics require a different encoding or explicit range proof.
- **Evaluation order:** source expressions and symbolic rewrites must preserve evaluation order. This fragment has pure expressions, so reordering is safe only after purity is part of the grammar.
- **Short-circuit Boolean operators:** decide whether `and`/`or` are short-circuiting or total pure operators. With pure, total expressions their values agree, but this must not be generalized to effectful expressions.
- **State:** reads after writes must observe the updated state. A translation that reads only the initial state is invalid.
- **Branching:** both branches must be translated under the correct path condition; merging branch results with `ite` must preserve the operational semantics.
- **Observations:** only contract-selected state and the return value are compared. Trace, events, errors, and termination are absent by construction, not silently ignored.
- **Declarations:** a name-to-symbol map must be injective and sort-correct. Query variable identity must distinguish left and right copies and shared inputs.
- **Source/query binding:** matching a query's declarations to parser-assigned Logos UConst identifiers is necessary but does not prove that the query describes the source program.

## 9. Acceptance criteria for the first proof milestone

The milestone is complete only when:

- the Lean source grammar exactly documents the accepted fragment;
- a Lean validator rejects malformed or unsupported source programs;
- SC-1 and SC-2 are proved for every accepted expression constructor;
- SC-3 and SC-4 are proved for assignment, conditional, and return;
- SC-5 and SC-6 are proved for paired execution and the relational query;
- SC-7 is proved for the generated formula;
- all theorem modules compile in CI;
- the theorem modules contain no `sorry`, `admit`, or project-local axioms;
- adversarial tests demonstrate rejection of loops, recursion, effects, unsupported sorts, uninitialized state, and nonlinear multiplication;
- the existing Logos binding tests continue to pass.

A proof of only SC-2 is a valuable intermediate result, but must be reported as expression-level correspondence only.

## 10. Non-goals

This scenario does not prove:
- correctness of the Python parser or validator;
- that the formal fragment captures all intended LLMLang semantics;
- correctness of LLVM/native code generation;
- correctness of the cvc5 solver;
- correctness of the Logos parser (its checker soundness theorem is a separate boundary);
- absence of bugs in the Lean kernel or trusted compiler;
- that a formal requirement matches human intent.

The formal result is always conditional on the declared source semantics, input assumptions, and observation contract.
