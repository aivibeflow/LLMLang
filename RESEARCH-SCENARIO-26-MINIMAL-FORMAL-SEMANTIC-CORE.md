# Scenario 26 — Minimal Formal Semantic Core for Dependency Proofs

Status: research result and finite-model prototype; not a language specification. Date: 2026-11-16.

## Result

A small deterministic core can express arithmetic and Boolean expressions, pure non-recursive function calls, local assignment, explicit state regions, ordered event emission, conditionals, returns, and errors. The analyzer exhaustively enumerates a declared finite input domain and compares pairs of executions that differ in exactly one factor.

A differing observable pair yields PROVEN_INFLUENCE with a witness. Complete absence of differing pairs yields PROVEN_INDEPENDENCE only within the exact finite domain, initial state, deterministic semantics, and observation boundary. The overall status is PROVEN_WITHIN_FINITE_MODEL.

Unsupported constructs or resource exhaustion yield UNKNOWN, never a partial independence proof. Fallback edges are planning hints only. UNKNOWN requires conservative revalidation.

## Semantic model

Input valuation rho, local environment eta, and state sigma are separate mappings. State consists of explicit named regions. No pointers, aliasing, implicit globals, or ambient state access are supported.

Expressions: constants, variables, state reads, unary and binary operators, and pure function calls. Commands: local assignment, state write, ordered event emission, conditional, return, and raise. Functions have expression bodies, are non-recursive, and have no ambient state access. A caller must pass a state value as an explicit argument.

The deterministic evaluator produces the observation:
Obs(P,rho,sigma0) = (outcome, result, error, visibleState, orderedEvents).
Only explicitly selected state regions are observable. A local value that changes but never affects this tuple is not a semantic dependency.

For finite domain D and input factor p:
Dep(P,p,o) iff there exist x,x' in D, equal on all factors except p, with different p values and different observable component o.
Indep(P,p,o) iff every such pair has equal observations.
Exhaustive enumeration decides these properties exactly for D. It says nothing about values outside D or other contexts.

## Findings

- x multiplied by zero is independent of x over the declared integer domain despite syntactic reading.
- A branch that changes emitted events creates a control dependency.
- A branch that changes only an unobservable local does not.
- Explicit state writes and reads are included in observations.
- Caller/callee influence is visible through explicit parameters; ignored parameters can be proven irrelevant in the finite model.
- Error outcomes and ordered effects are observable.
- Conditional influence is found even when it occurs only for a particular value of another input.
- Unsupported semantics and budget exhaustion produce UNKNOWN.

## Limitations

Finite domains only; no SMT or unbounded proof. No loops, recursion, nondeterminism, concurrency, pointers, aliasing, dynamic dispatch, foreign code, reflection, or external services. No complete type checker. Mathematical integer arithmetic only. No machine-checked proof of the Python evaluator or analyzer. Source-to-IR and compiler/runtime correspondence are not verified.

Tests validate selected cases and compare results against exhaustive pair enumeration; they are not a mathematical soundness proof for all programs.

## Architecture recommendation

Keep this finite checker as a reference oracle for small models. Scenario 27 should add a typed AST, product-program or relational-VC construction, symbolic path conditions, a narrow SMT interface, witness extraction, and timeout-to-UNKNOWN behavior. Differentially compare symbolic results with finite enumeration. Defer loops, pointers, concurrency, and foreign calls.

## References

1. Product Programs and Relational Program Logics, JLAMP 2016: https://doi.org/10.1016/j.jlamp.2016.05.004
2. Theoretical Background on Abstract Interpretation: https://cs.nyu.edu/~pcousot/publications.www/BertraneCousotEtAl-FTPL-2015.pdf
3. Andrew Myers, Proving noninterference for a while-language using small-step operational semantics: https://www.cs.cornell.edu/andru/classes/oplss19/while.pdf
4. WhyRel: an auto-active relational verifier, 2025: https://doi.org/10.1007/s10009-025-00786-1
