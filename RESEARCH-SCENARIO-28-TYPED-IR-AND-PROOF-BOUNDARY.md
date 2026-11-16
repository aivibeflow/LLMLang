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
- Python bool is distinguished from int;
- arithmetic/comparison operators have explicit operand/result types;
- equality requires equal operand sorts;
- conditions must be Bool;
- variable reads, assignment targets, state reads/writes, and observable state regions must be declared;
- function arity and parameter uniqueness are checked;
- recursive calls and state access from pure functions are rejected;
- only assignments, state writes, conditionals, and one final top-level return are accepted;
- branch environments must join with equal types;
- initial state, initial locals, input declarations, and observation selection participate in a canonical SHA-256 IR digest.

The typed entry point validates before invoking the SMT encoder. Direct calls to the lower-level encoder remain possible in Python; a production API must make bypassing the validator impossible by construction.

## 3. Observation contract

For this restricted fragment the observable boundary is explicit:
- normal-return outcome;
- return value;
- each selected state region.

Events and raised errors are intentionally excluded because the symbolic encoder does not currently model them. The validator rejects those commands instead of silently omitting them. This is not a universal LLMLang observation model; it is a versioned contract for this fragment.

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

The prototype distinguishes solver-reported SAT/UNSAT from independently checked proof. The receipt object is only a data contract: it is unauthenticated, does not launch a checker, and can be forged by arbitrary Python code. Therefore it cannot issue a checked-proof claim.

SAT models are replayed against the Scenario 26 reference evaluator. Replay binds not only the types but the exact initial state and initial-local values committed into the typed IR. A candidate witness for a different starting configuration is rejected, even if all values have the same types.

## 5. Scenario 27 protocol correction

The SMT-LIB interaction runs check-sat first and requests get-value only in a second identical solver session after SAT. UNSAT and UNKNOWN do not trigger model inspection.

## 6. Tests and validation scope

Tests cover accepted and rejected typed ASTs, digest sensitivity to the observation boundary, evidence binding, solver status distinctions, counterexample replay, and exact initial-environment matching. The two additional regression tests ensure same-type but different initial state/local values are rejected.

Recorded focused prototype run:
- `python -m unittest discover -s tests -v`: 24 tests passed;
- `python -m compileall -q src tests`: passed.

This is the local prototype workspace, not the full repository historical suite. No real SMT solver or independent proof checker was available, so no actual SMT proof was generated or checked. The tests do not prove validator completeness, encoder soundness, checker correctness, or compiler correspondence.

## 7. Design consequences

- Type checking must precede SMT generation.
- The typed IR and its semantic version are part of every proof identity.
- The observation boundary is a first-class input, never an implicit default.
- SAT is a candidate counterexample until replayed against the exact reference semantics and initial environment.
- UNSAT is a solver-reported result until a proof artifact is independently checked.
- A proof cache key must include typed IR, observation contract, encoder, exact query, solver binary/version/options, and checker identity/version.
- Unsupported syntax, unknown effects, failed validation, missing evidence, and timeout all fail closed to UNKNOWN or rejection.

## 8. Next step

**Scenario 29 — Independent Proof-Checker Integration and Encoder Validation.**

Choose one restricted SMT theory with available proof production and an independent checker. Build a small proof pipeline end-to-end, pin solver/checker artifacts, and test deliberately corrupted proof files. In parallel, differentially compare the symbolic encoder with the Scenario 26 evaluator over generated finite inputs. Only after both tracks pass should the system promote symbolic UNSAT to a checked proof status.

## 9. References

1. SMT-LIB 2.6 reference: https://smt-lib.org/papers/smt-lib-reference-v2.6-r2024-09-20.pdf
2. cvc5 Alethe proof output: https://cvc5.github.io/docs/cvc5-1.4.2/proofs/output_alethe.html
3. cvc5 tutorial, proof certificates and checking: https://cvc5.github.io/tutorials/beginners/outputs.html
4. Z3 Programming Guide: https://z3prover.github.io/papers/programmingz3.html
5. veriT, proof-producing SMT solver: https://www.verit-solver.org/
