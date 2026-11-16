# Prototype 28 Results — Typed IR and Proof Boundary

**New modules**
- `src/typed_ir.py`
- `src/proof_boundary.py`

**New tests**
- `tests/test_typed_ir.py`
- `tests/test_proof_boundary.py`

The typed validator accepts only the restricted Scenario 27 fragment and creates a canonical digest that includes the observation boundary. Evidence records additionally require SHA-256 identities for both validator and encoder source builds. The typed entry point validates before invoking the symbolic backend. The evidence envelope pins the typed IR, semantic/validator/encoder/observation versions and source digests, exact SMT query, solver identity/configuration, result, and optional proof-checker receipt. A supplied receipt remains unauthenticated and cannot be promoted to a checked-proof status.

SAT witnesses can be replayed against the Scenario 26 evaluator. UNSAT without an independent proof-checker receipt is explicitly labelled `SOLVER_REPORTED_UNSAT_UNCHECKED`, not a checked proof. The receipt class is only a prototype data contract and is not authenticated or produced by an actual checker.

## Local test run

```
python -m unittest discover -s tests -v
Ran 22 tests
OK
python -m compileall -q src tests
Passed
```

The local test workspace used the Scenario 26 AST/evaluator definitions and the two new modules. It did not run the repository's complete historical test suite. No real SMT solver or independent proof checker was installed, so no actual SMT proof was generated or checked.

## Scenario 27 protocol correction

The symbolic backend no longer appends `get-value` to every query. It first runs `check-sat`, then requests a model in a second identical session only if the result is SAT. This respects SMT-LIB solver modes and avoids issuing model-inspection commands after UNSAT.

## Remaining gaps

No authenticated checker receipt, proof certificate validation, executable attestation, complete encoder proof, compiler correspondence proof, or full repository regression run. The validator covers only the small symbolic fragment, not arbitrary LLMLang source.
