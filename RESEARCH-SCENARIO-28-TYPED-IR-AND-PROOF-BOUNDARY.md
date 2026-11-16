# Scenario 28 — Type-Safe Semantic IR and Proof Boundary

**Status:** Research prototype; independent SMT proof checking is not implemented  
**Date:** 2026-11-16  
**Related:** Scenarios 26–27

## 1. Objective

Prevent a solver result from being promoted into a semantic proof unless the IR is well-formed, the observation boundary is explicit, and the evidence is bound to the exact query and toolchain.

The boundary has three logically distinct obligations:

1. **IR validity:** the AST belongs to a precisely defined, typed fragment.
2. **Encoding validity:** the SMT encoding preserves that fragment's semantics.
3. **Proof validity:** the solver's answer (and, for UNSAT, proof artifact) is bound to the exact encoded query and independently checked.

A successful type check addresses only the first obligation. It does not prove the encoder correct. A solver's UNSAT answer alone is an oracle result, not an independently checked proof.

## 2. Typed AST validator

Added `src/typed_ir.py`:
- supported sorts are Int, Bool, String;
- Python bool is distinguished from int (because bool subclasses int);
- arithmetic/comparison operators have explicit operand/result types;
- equality requires equal operand sorts;
- conditions must be Bool;
- variable reads, assignment targets, state reads/writes, and observable state regions must be declared;
- function arity and parameter uniqueness are checked;
- recursive calls and state access from pure functions are rejected;
- only the Scenario 27 command fragment is accepted: assignments, state writes, conditionals, and one final top-level return;
- branch environments must join with equal types;
- initial state, initial locals, input declarations, and observation selection participate in a canonical SHA-256 IR digest.

`analyze_typed_symbolically` is the safe front door: it validates before invoking the existing SMT encoder. Direct calls to the lower-level encoder remain possible in Python; a production API must make bypassing the validator impossible by construction.

## 3. Observation contract

For this restricted fragment the observable boundary is explicit:
- normal-return outcome;
- return value;
- each selected state region.

Events and raised errors are intentionally excluded because the symbolic encoder does not currently model them. The validator rejects those commands instead of silently omitting them. This is a key safety property: an unsupported observable effect must cause rejection/UNKNOWN, not an independence result.

The observation boundary is included in the IR digest and the evidence record. It is not a universal LLMLang observation model; it is a versioned contract for this one fragment.

## 4. Evidence envelope

Added `src/proof_boundary.py`. An immutable evidence record binds:
- canonical typed-IR digest;
- semantic and validator versions;
- encoder version;
- observation-contract version and dimensions;
- exact SMT query SHA-256;
- solver name/version, executable SHA-256, command and options;
- solver result;
- optional proof artifact digest and checker identity;
- digest of the complete record.

The prototype deliberately distinguishes:
- `SOLVER_REPORTED_UNSAT_UNCHECKED`;
- `PROOF_CHECKED_INDEPENDENCE`;
- `SOLVER_REPORTED_SAT_COUNTEREXAMPLE_UNCHECKED`;
- `COUNTEREXAMPLE_CONFIRMED_BY_REFERENCE_EVALUATOR`;
- `UNKNOWN`.

The receipt object is only a data contract in this experiment. It is not authenticated, does not launch a checker, and can be forged by arbitrary Python code. Therefore even a supplied receipt is labelled `UNAUTHENTICATED_CHECKER_RECEIPT_PRESENT`; the prototype cannot issue a `PROOF_CHECKED_INDEPENDENCE` claim. A real implementation must obtain a receipt from an isolated proof checker, bind it to the exact query and proof bytes, and authenticate the checker/tool identity. The solver executable digest is supplied by the caller; this prototype does not inspect or attest the binary itself.

For SAT, the prototype replays the candidate pair through the Scenario 26 reference evaluator and confirms that only the selected factor differs and the modeled observation changes. This is useful counterexample validation, but it is not an independent proof of the SMT encoder's correctness.

## 5. Protocol correction in Scenario 27

The SMT-LIB standard restricts `get-value` to the solver's SAT mode. The earlier Scenario 27 script appended `get-value` unconditionally after `check-sat`, including when the answer was UNSAT. The standard specifies that model inspection commands are available after SAT, while proof/core commands are available after UNSAT.

The low-level factor statuses are also deliberately named `SOLVER_REPORTED_SAT` and `SOLVER_REPORTED_UNSAT` (with `SOLVER_COMPLETED_WITHIN_SYMBOLIC_FRAGMENT` as the aggregate) rather than `PROVEN_*`. This prevents a solver's unverified response from being mistaken for a checked proof. A SAT witness is separately replayable; an UNSAT result needs an independently checked proof artifact before it can be promoted.

The backend is corrected to:
1. send the satisfiability query containing `check-sat`;
2. return immediately for UNSAT or UNKNOWN;
3. only after SAT, start an identical solver session and append `get-value` to retrieve the model.

This removes the invalid post-UNSAT model request. It also makes the solver interaction two-phase; both sessions must use the same solver binary, options, and deterministic query. The exact query remains the evidence identity.

## 6. External proof-checking landscape

The SMT-LIB 2.6 reference defines the distinct solver modes and the permitted model/proof inspection commands. cvc5 documents Alethe proof output and integration with independent checkers such as Carcara; current documented Alethe theory coverage is limited, so proof support must be selected per logic rather than assumed for every SMT formula. Z3 exposes proof objects, but its documentation describes best-effort granularity, including opaque steps for some procedures. Therefore a future LLMLang proof backend should abstract over solver + proof format + checker, and only promote results for combinations with a validated proof path.

Useful sources:
1. SMT-LIB 2.6 reference, command modes and get-value/get-proof: https://smt-lib.org/papers/smt-lib-reference-v2.6-r2024-09-20.pdf
2. cvc5 Alethe proof output and checker ecosystem: https://cvc5.github.io/docs/cvc5-1.4.2/proofs/output_alethe.html
3. cvc5 tutorial, proof certificates and checking: https://cvc5.github.io/tutorials/beginners/outputs.html
4. Z3 Programming Guide, proof objects and granularity: https://z3prover.github.io/papers/programmingz3.html
5. veriT, proof-producing SMT solver: https://www.verit-solver.org/

## 7. Tests and validation scope

New focused tests cover:
- accepted well-typed AST;
- bool/int confusion;
- undeclared variables and assignment targets;
- wrong branch conditions and branch joins;
- recursive calls and state access in pure functions;
- observation-boundary changes in the semantic digest;
- exact query binding for proof receipts;
- refusal to equate solver UNSAT with checked proof;
- SAT counterexample replay and rejection of invalid pairs;
- validation before solver invocation.

The tests are executed against the Scenario 26 AST/evaluator interface. They do not prove validator completeness, encoder soundness, checker correctness, or the correctness of an actual SMT solver. No real Z3/cvc5 executable is available in this environment.

## 8. Design consequences

- Type checking must precede SMT generation.
- The typed IR and its semantic version are part of every proof identity.
- The observation boundary is a first-class input, never an implicit default.
- SAT is a candidate counterexample until replayed against the reference semantics.
- UNSAT is a solver-reported result until a proof artifact is independently checked.
- A proof cache key must include typed IR, observation contract, encoder, exact query, solver binary/version/options, and checker identity/version.
- Unsupported syntax, unknown effects, failed validation, missing evidence, and timeout all fail closed to UNKNOWN or rejection.

## 9. Next step

**Scenario 29 — Independent Proof-Checker Integration and Encoder Validation.**

Choose one restricted SMT theory with available proof production and an independent checker. Build a small proof pipeline end-to-end, pin solver/checker artifacts, and test deliberately corrupted proof files. In parallel, differentially compare the symbolic encoder with the Scenario 26 evaluator over generated finite inputs. Only after both tracks pass should the system promote symbolic UNSAT to a checked proof status.
