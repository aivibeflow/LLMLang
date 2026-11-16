# Prototype 26 Results

Finite deterministic semantic core and exhaustive relational dependency checker.

Focused tests:
```
python -m unittest discover -s tests -p 'test_formal_core.py' -v
Ran 15 tests
OK
python -m unittest discover -s tests -p 'test_finite_relational_consistency.py' -v
Ran 1 test
OK
```

Tests cover cancellation, data/control flow, observable state/effects/errors, explicit call parameters, conditional influence, unsupported constructs, typed equality, non-finite input rejection, and budget exhaustion. Pairwise consistency checks analyzer statuses against exhaustive finite pair enumeration. Finite results use `FINITE_MODEL_INFLUENCE`, `FINITE_MODEL_INDEPENDENCE`, and `DECIDED_WITHIN_FINITE_MODEL`; these scoped outcomes are not LLMLang's language-level `PROVEN` status.

Full existing Dependency Graph Prototype 01 regression was not run: outbound DNS/network access prevented cloning the repository into the local container.

Limitations: finite domains only; no SMT, loops, recursion, nondeterminism, concurrency, pointers, aliasing, dynamic dispatch, foreign code, type checker, or machine-checked proof of the evaluator/analyzer. Source-to-IR and compiler/runtime correspondence are not verified.

See ../../RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md.
