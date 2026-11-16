# Prototype 27 Results — Symbolic Relational Verification

**Implementation:** src/symbolic_relational.py  
**Tests:** tests/test_symbolic_relational.py, tests/test_symbolic_finite_differential.py

The backend emits SMT-LIB 2 for a pair of executions. The selected input factor is duplicated; all other inputs are shared. It checks whether any modeled observable differs. SAT results may carry candidate input witnesses that require replay against the exact reference semantics. UNSAT is only a solver-reported result within the supported encoding; it is not an independently checked proof. Unsupported constructs, missing solver, timeout, and solver UNKNOWN fail closed.

## Local test run

```
python -m unittest discover -s tests -v
Ran 13 tests
OK (skipped=2)
```

The 11 executed tests use deterministic fake solver processes to validate SMT process protocol, witness parsing, SAT/UNSAT/UNKNOWN mapping, missing-solver and timeout handling, shared inputs, branch ite encoding, state observations, pure function inlining, and unsupported-feature rejection.

Two tests requiring a real Z3 executable were skipped because Z3 is not installed in the execution environment. Installing z3-solver via pip was attempted but failed because outbound DNS/network access was unavailable. Therefore no real SMT solving, emitted-formula acceptance, or finite-vs-symbolic differential run is claimed.

Python bytecode compilation (py_compile) passed for the implementation and tests.

## Limitations

Restricted deterministic AST fragment only: Int/Bool/String, arithmetic/Boolean operations, pure non-recursive functions, conditional assignments, explicit state writes, and one final top-level return. No loops, errors, events, concurrency, aliasing, dynamic dispatch, source parsing, full type checking, proof certificates, or compiler/runtime correspondence proof. Solver results are trusted; this prototype does not independently check proofs.

See [Research Scenario 27](../../RESEARCH-SCENARIO-27-SYMBOLIC-RELATIONAL-VERIFICATION.md).


## Post-audit protocol-test correction

The model-retrieval protocol test previously assumed exactly two solver-process invocations. The implementation also issues one follow-up query per observable dimension after SAT, so the test now checks the actual invariant instead: the initial query has no `get-value`, model retrieval occurs only after SAT, and observation-specific follow-up queries do not request models.

In the post-audit isolated local harness, all 12 fake-solver protocol tests passed. The one real-Z3 differential test was skipped because no Z3 executable was available. This harness was reconstructed from current GitHub source/test material; it is not a full checkout regression run and does not constitute real SMT integration.
