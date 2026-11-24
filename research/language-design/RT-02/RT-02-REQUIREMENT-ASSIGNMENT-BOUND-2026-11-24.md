# Assignment bounds in the finite requirement analyzer

- **Date:** 2026-11-24
- **Research:** RT-02, Scenario 17, PLAN §1.0
- **Baseline:** `dec70dfe8f603661ef6777d121dbc830ea6818e4`
- **Evidence:** Twelve budget and satisfiability cases and the existing budget regression

An exceeded assignment limit must produce `UNKNOWN` before the finite analyzer can report consistency or contradiction. On the baseline, the budget function is a Python generator. Its `return None` ends iteration, so the caller receives a generator that yields zero rows and misses the `None` branch. A satisfiable requirement then appears contradictory. With no requirements, the same empty enumeration appears consistent.

The checked candidate returns the budget outcome before creating the iterator. A budget failure supplies the `ANALYSIS_BOUND_EXCEEDED` diagnostic and no scenarios. A complete enumeration retains the existing finite conclusions.

| Requirement set over 18 assignments | Baseline at limits 0 and 17 | Checked candidate at limits 0 and 17 | Both at limits 18 and 19 |
| --- | --- | --- | --- |
| One equality with six witnesses | `NEEDS_REVIEW`, `CONTRADICTION`, zero scenarios | `UNKNOWN`, `ANALYSIS_BOUND_EXCEEDED`, zero scenarios | `FINITE_MODEL_CONSISTENT`, 18 scenarios, six witnesses |
| Two mutually exclusive equalities | `NEEDS_REVIEW`, `CONTRADICTION`, zero scenarios | `UNKNOWN`, `ANALYSIS_BOUND_EXCEEDED`, zero scenarios | `NEEDS_REVIEW`, `CONTRADICTION`, 18 scenarios, no witnesses |
| No requirements | `FINITE_MODEL_CONSISTENT`, zero scenarios | `UNKNOWN`, `ANALYSIS_BOUND_EXCEEDED`, zero scenarios | `FINITE_MODEL_CONSISTENT`, zero per-scope scenarios |

The domain has three tax rates, three dates and two callers. A single rate fixes one of the three choices and leaves six satisfying combinations. The second equality selects a different rate in the same scope. These counts give a reference for the fully enumerated cases and distinguish an exhausted budget from an exhausted search.

The [regression](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_requirement_ir.py) exercises all twelve cases and checks the public scenario helper. It fails in the six over-budget cases on the baseline and passes all twelve with the fix.

```sh
cd research/PROTOTYPES/DEPENDENCY-GRAPH-01
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_requirement_ir
```

This result specifies the finite-domain candidate's bound handling. Formal backends and human acceptance still need their own evidence. An empty scenario list carries neither a budget diagnostic nor a consistency verdict by itself, so consumers that need either must use the full analysis result.
