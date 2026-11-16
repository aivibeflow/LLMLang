# Prototype 28 Results — Typed IR and Proof Boundary

**New modules**
- `src/typed_ir.py`
- `src/proof_boundary.py`

**New tests**
- `tests/test_typed_ir.py`
- `tests/test_proof_boundary.py`

The typed validator accepts only the restricted Scenario 27 fragment and creates a canonical digest that includes the observation boundary and exact initial state/local values. The typed entry point validates before invoking the symbolic backend. The evidence envelope pins the typed IR, semantic/validator/encoder/observation versions and source digests, exact SMT query, solver identity/configuration, result, and optional proof-checker receipt. A supplied receipt remains unauthenticated and cannot be promoted to a checked-proof status.

SAT witnesses are replayed against the Scenario 26 evaluator. Replay now requires exact equality of initial state and local-variable values with the environment committed in the typed IR; matching types alone are insufficient. Two regression tests were added to reject witnesses replayed against a different initial state or local environment. They have been committed but **were not executed in this environment**.

## Previously recorded baseline validation

Before the two new regression tests were added, the local prototype workspace reported:

```
python -m unittest discover -s tests -v
Ran 22 tests
OK
python -m compileall -q src tests
Passed
```

This baseline does not include the two newly added regression tests and must not be represented as validation of the latest commit. An attempt to clone the repository for a fresh run failed because this environment could not resolve github.com. Consequently, no post-fix test run or compileall run is claimed.

No real SMT solver or independent proof checker was available, so no actual SMT proof was generated or checked. The tests do not prove validator completeness, encoder soundness, checker correctness, or compiler correspondence.

## Scenario 27 protocol correction

The SMT-LIB interaction runs check-sat first and requests get-value only in a second identical solver session after SAT. UNSAT and UNKNOWN do not trigger model inspection.

## Remaining gaps

No authenticated checker receipt, proof certificate validation, executable attestation, complete encoder proof, compiler correspondence proof, or full repository regression run. The validator covers only the small symbolic fragment, not arbitrary LLMLang source.


## Post-audit focused validation

After correcting the missing `If` import in `typed_ir.py` and the missing `State` import in the proof-boundary regression test, the focused Scenario 28 test modules were run in an isolated local harness:

- typed IR tests: 10 passed;
- proof-boundary tests: 14 passed;
- total: 24 passed, 0 failures.

The harness was reconstructed from the current GitHub source/test material because the local environment could not clone the repository. This is not a byte-for-byte checkout or a full repository regression run. No real SMT solver or independent proof checker was available.
