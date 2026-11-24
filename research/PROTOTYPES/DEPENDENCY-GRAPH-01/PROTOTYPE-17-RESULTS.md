# Prototype 17: Typed Requirement IR — Results

**Status:** Research prototype; implementation and focused tests committed.  
**Related research:** [Research Scenario 17](../../RT-02/RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md)

## Objective

Replace opaque formal-predicate strings with a small typed representation that can be checked independently, while retaining provenance, explicit uncertainty, and caller/callee business-policy ownership.

## Implemented

`src/requirement_ir.py` provides:
- typed variables with finite domains (`bool`, `int`, `text`);
- predicate, conjunction/disjunction, and negation nodes;
- event trigger, action, and temporal-bound records;
- requirement owner, scope, constraint, source/decision references, assumptions, unresolved items, and explicitly required dimensions;
- structural and type checks;
- dangling-provenance checks;
- finite-domain contradiction detection per scope;
- underdetermination checks for dimensions explicitly marked as required;
- exhaustive satisfying/violating scenario enumeration;
- caller-policy ownership and explicit callee policy-input checks;
- an UNKNOWN result when the assignment bound is exceeded.

The IR does not parse natural language. The test constructs are supplied explicitly.

## Focused tests added

Ten tests cover:
1. typed IR with trigger, action, temporal metadata, and provenance;
2. contradictory constraints;
3. explicitly required but underdetermined dimensions;
4. missing provenance;
5. unresolved questions and assumptions;
6. type mismatch;
7. satisfying scenarios and counterexamples;
8. bounded analysis returning UNKNOWN;
9. caller-owned policy passed as an explicit callee input;
10. wrong policy owner and missing callee input detection.

Run:

```bash
cd PROTOTYPES/DEPENDENCY-GRAPH-01
python -m unittest discover -s tests -p 'test_requirement_ir.py' -v
```

## Interpretation

The experiment shows that a small typed AST can support useful independent checks without requiring a general theorem prover. It also shows that "underdetermined" must be scoped: the checker can only know which dimensions matter if the requirement model explicitly marks them as required.

Finite-domain consistency is not proof of completeness or correctness. The generated scenarios are model assignments, not yet executable tests against an implementation.

## Execution status

The test source was reviewed and committed. The execution environment used for this repository operation could not reach GitHub from the local container, so the new test suite was **not executed locally in this run**. No claim is made that the tests pass. The full repository suite was not run.

## Limitations

- no natural-language parser or intent inference;
- finite domains only;
- no arithmetic expression tree or general SMT backend;
- no temporal semantics despite typed temporal metadata;
- no state-transition execution;
- no implementation conformance proof;
- no authorization or authority verification;
- no automatic discovery of missing requirements;
- no automatic derivation of required dimensions.

## Result

The prototype establishes a concrete next design point: Requirement IR should be a typed, provenance-carrying semantic layer, while formal solvers and test frameworks remain pluggable backends. It should not be treated as a universal formal language or as an automatic truth detector.
