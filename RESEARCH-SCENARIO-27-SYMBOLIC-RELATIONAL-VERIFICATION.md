# Scenario 27 — Symbolic Relational Verification for the Core

**Status:** Research result with SMT-LIB backend prototype; actual Z3 integration not executed in this environment  
**Date:** 2026-11-16  
**Related:** Scenarios 25–26

## 1. Objective

Replace exhaustive finite input enumeration with a symbolic relational query. For each factor p, construct two executions of the same program. All inputs other than p are shared; the two copies of p are independent. Ask whether the two observations can differ:

\[
\exists x_L,x_R.\quad x_L\equiv_{\neg p}x_R
\land x_L[p]\ne x_R[p]
\land Obs(P,x_L)\ne Obs(P,x_R)
\]

- SAT gives a concrete witness pair and establishes influence.
- UNSAT establishes independence over the complete domain represented by the selected SMT theories and encoding.
- UNKNOWN, timeout, missing solver, unsupported syntax, or invalid encoding gives UNKNOWN.

This is a relational property / 2-safety reduction using a product of two executions.

## 2. Implemented fragment

The prototype consumes the Scenario 26 AST and supports:
- SMT sorts Int, Bool, and String;
- integer +, -, *, unary negation, <, <=;
- Boolean and, or, not;
- equality for supported sorts;
- pure non-recursive function calls, inlined with explicit parameters;
- conditionals encoded as SMT ite expressions;
- assignments to explicitly initialized local variables and input variables;
- writes to explicitly initialized state regions;
- a single final top-level Return;
- selected observable state regions.

Integer values have mathematical unbounded-integer semantics, not machine overflow semantics. Strings currently support literals and equality only. All non-selected inputs are shared between the two runs. Initial state and initial local values are identical and fixed in both runs.

## 3. Query construction

For factor p, create two fresh SMT symbols p_L and p_R. Every other input q is represented by one shared symbol q. Source identifiers are mapped to generated SMT symbols, so arbitrary source names cannot alter SMT-LIB syntax.

Encode the program twice and compare observation dimensions:
\[
(assert\ (not\ (=\ p_L\ p_R)))
\]
\[
(assert\ (or\ (not\ (=\ Obs_{L,1}\ Obs_{R,1}))\ldots))
\]
Then issue check-sat. For SAT, request values for all input symbols to reconstruct a counterexample. To identify which observation dimensions are influenced, issue one additional query per dimension. A dimension-specific UNKNOWN is preserved as UNKNOWN:dimension rather than treated as unchanged.

The observation boundary consists of the return value and explicitly selected state regions. The outcome is fixed to normal return in this fragment. Errors and event traces are not encoded.

## 4. Solver boundary

The implementation emits SMT-LIB 2 and invokes an external solver process (default command z3 -in -smt2). This avoids binding LLMLang's semantic API to a particular Python package. The solver is a trusted component in this prototype; no independently checked proof certificate is produced.

The implementation handles sat, unsat, and unknown, process absence/failure, and wall-clock timeout. Unknown and timeouts never become proofs.

## 5. Test strategy and current evidence

The test suite uses a fake SMT-LIB process to exercise protocol handling deterministically:
- SAT response and witness decoding;
- UNSAT → PROVEN_INDEPENDENCE;
- UNKNOWN → UNKNOWN;
- missing executable and timeout → UNKNOWN;
- shared symbols for unchanged inputs;
- ite encoding of branches;
- observable state in the relational formula;
- pure function inlining;
- rejection of unsupported effects and sorts.

Two integration tests run only when a real z3 executable is present. They compare unbounded symbolic results with Scenario 26's finite oracle for simple arithmetic examples.

**Environment limitation:** this environment has neither the Z3 executable nor the z3-solver Python package. Network/DNS access prevented installation. Therefore deterministic protocol tests ran, but no real SMT solver accepted or solved the emitted formulas in this run. The Z3 integration tests were skipped. This is an explicit validation gap, not a successful solver integration claim.

## 6. Limitations

No loops, recursion, nondeterminism, concurrency, pointers, aliasing, dynamic dispatch, foreign code, reflection, external services, event traces, raised errors, or return statements nested inside branches. Assignments target input variables or explicitly initialized local variables; there is no local-variable declaration/type-inference pass. There is no source parser, full type checker, machine-checked proof of the encoding, proof-certificate checker, or source-to-IR/compiler/runtime correspondence proof.

The encoding's soundness is conditional on the AST and modeled semantics matching the intended program semantics, and on trusting the SMT solver's result. UNSAT does not establish correctness of the human requirement or correctness of an upstream compiler translation.

## 7. Architecture implications

Scenario 26 remains the finite reference oracle for small instances. Scenario 27 adds a symbolic backend for the restricted fragment. The two should be run differentially on generated small programs once a real solver is available.

Keep evidence distinct:
- PROVEN_INFLUENCE — symbolic SAT witness;
- PROVEN_INDEPENDENCE — symbolic UNSAT result;
- UNKNOWN — unsupported, timeout, solver unknown, or encoding failure;
- OBSERVED_DEPENDENCY — experimental evidence from Scenarios 20–24, not a proof.

Only proof results whose input root, AST/semantics version, observation boundary, solver identity/version, and solver configuration are pinned should be reusable. This prototype records SMT queries but does not yet implement persistent proof records or cache identity.

## 8. Next step

**Scenario 28 — Type-Safe Semantic IR and Proof Boundary:** add a typed AST validation pass, explicit return/effect/error semantics, a versioned observation contract, and a reproducible solver identity/configuration record. Then run the real Z3 integration suite and differential tests. Expand the supported language only after the proof boundary is explicit.

## 9. References

1. Product Programs and Relational Program Logics, Journal of Logical and Algebraic Methods in Programming, 2016. https://doi.org/10.1016/j.jlamp.2016.05.004
2. Microsoft Research, Programming Z3. https://z3prover.github.io/papers/programmingz3.html
3. Microsoft Z3 Guide, Introduction to Z3 Python API. https://microsoft.github.io/z3guide/programming/Z3%20Python/Introduction/
4. Z3 Python API reference, Solver and model(). https://z3prover.github.io/api/html/z3.z3.html
5. KestRel: Relational Verification Using E-Graphs for Program Alignment, 2024. https://arxiv.org/abs/2404.08106
