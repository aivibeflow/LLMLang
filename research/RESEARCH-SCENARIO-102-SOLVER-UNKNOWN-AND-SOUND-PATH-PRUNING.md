# Research Scenario 102 — Solver Unknowns and Sound Path Pruning

**Status:** bounded result-policy experiment plus standards/API comparison; no solver or language policy selected

**Research areas:** RT-03 path feasibility, RT-06 dependency completeness, RT-07 evidence and solver trust

**Updated:** 2026-11-19

## 1. Question

How should a path analyzer treat `SAT`, `UNSAT`, `UNKNOWN`, timeout, unsupported input, invalid models, and backend errors without confusing “not proven feasible” with “proven unreachable”? What evidence is needed before a path may be pruned?

## 2. Prior art and API behavior

- SMT-LIB 2.6 gives `sat`, `unsat`, and `unknown` distinct meanings. `unknown` means the search was inconclusive, including because of resource limits or solver incompleteness. This is a result state, not an unsatisfiability result. [SMT-LIB 2.6 reference, §4.2.5](https://smt-lib.org/papers/smt-lib-reference-v2.6-r2024-09-20.pdf)
- Z3 exposes a millisecond `timeout` parameter and `reason_unknown()` for the preceding check. Timeout and a reason string make the cause observable, but do not turn an inconclusive answer into a proof of infeasibility. [Z3 parameters](https://microsoft.github.io/z3guide/programming/Parameters/) · [Z3 Solver API](https://z3prover.github.io/api/html/classz3py_1_1_solver.html)
- The pinned SymPy 1.14 `satisfiable()` API accepts an expression, algorithm, and model options; it documents Boolean satisfiable/unsatisfiable returns and DPLL backends, but no per-query timeout parameter. A bounded caller would need a separately controlled process/service or another API/backend. [SymPy 1.14 logic API](https://docs.sympy.org/1.14/modules/logic.html) · [SymPy optional SAT backends](https://docs.sympy.org/1.14/contributing/dependencies.html)

These are API and protocol facts, not an LLMLang solver selection.

## 3. Candidate result policies

| Vector | Path classification | Benefit | Cost / failure mode |
|---|---|---|---|
| **P-A Exact finite oracle** | Exhaustively enumerate a declared finite input domain; prune only when no assignment satisfies the route. | Exact within the enumerated domain and independent of a SAT solver. | Exponential growth; does not scale to unbounded values or prove source-to-IR completeness. |
| **P-B Tri-state solver** | `SAT` with a locally replayed witness proves the route possible. `UNSAT` prunes only under an explicit trusted/checked basis. Timeout, `UNKNOWN`, invalid output, unsupported input, or backend failure retain the route as unknown. | Handles larger formulas while preserving a conservative may-path set. | An unverified backend `UNSAT` can unsoundly erase behavior; unknown routes create false positives and reduce precision. |
| **P-C Bounded hybrid** | Use exact enumeration below a declared variable/operation limit; otherwise use P-B or retain unknown. | Small cases get independent exact decisions; larger cases retain progress without claiming completeness. | The cutoff and exact-oracle implementation become part of evidence; large unknown regions remain. |
| **P-D Proof-carrying solver** | Accept a path-pruning `UNSAT` only with a proof/certificate checked by a smaller independent checker. | Reduces reliance on the solver for negative claims. | Certificate support, checker correctness, encoding correspondence, and proof-resource limits must be established. |

Agreement between two solvers is useful diagnostic evidence, but is not itself an independently checked proof: implementations may share assumptions, translations, or defects.

## 4. Conservative result contract

For a pure, immutable predicate and an exact route encoding, keep separate classifications:

- **Feasible:** a complete assignment is independently replayed and satisfies every route constraint. This is a concrete witness.
- **Infeasible:** no path is reported only when the negative result has an explicitly accepted basis: trusted backend, checked certificate, or exact finite oracle within its declared domain.
- **Unknown:** all other cases, including timeout, unsupported formula, malformed response, missing/incomplete model, failed witness replay, cancellation, or backend error.

For a may-analysis, the soundness target is `ConcreteReachable ⊆ ReportedPossible`. Feasible and unknown routes are retained; only established-infeasible routes are pruned. This permits false positives while preventing an inconclusive search from being reported as unreachable. Unknown must not be relabeled feasible, and its cause should remain available for diagnostics and evidence records.

A SAT model attached to an `UNKNOWN` response may be treated as a candidate: if a small local evaluator checks a complete assignment against the exact encoded route, it independently establishes that route's feasibility. A partial, malformed, stale, or non-replaying model does not.

This contract is conditional on the route constraints accurately representing the source path. It does not repair missing branches, stale predicate identity, mutation, effects, or parser/extractor gaps.

## 5. Bounded experiment

The result mapper is implemented in [the feasibility outcome adapter](PROTOTYPES/RT-04-01/rt03_feasibility_outcomes.py), with focused cases in [its test file](PROTOTYPES/RT-04-01/test_rt03_feasibility_outcomes.py). Eight cases exercise replayed SAT, a replayable candidate model on UNKNOWN, incomplete/invalid/non-replaying models, timeout, unsupported/error statuses, stale/contradictory models, untrusted UNSAT, and three explicit UNSAT evidence bases. Only the three explicit bases permit pruning; every inconclusive or invalid case remains in the possible-path set.

The existing SymPy adapter was also compared against Scenario 100's exhaustive analyzer on 300 deterministically seeded, depth-at-most-four Boolean formula trees over six immutable variables. All feasible-route sets agreed, and every returned DPLL model replayed to the selected branch. The reproducible CI fixture uses seed 102 for 128 such formulas in `test_rt03_sympy_predicate_paths.py`. The focused result-policy test run passed seven tests; the 300-case experiment ran on Python 3.12 with SymPy 1.14.0.

The timeout case is injected at the result-contract boundary; this experiment did **not** force a real solver timeout or measure a timeout wrapper. The generated formulas are shallow random trees, not adversarial SAT benchmarks. No claim is made about solver soundness, hard-instance scaling, a proof checker, or source-level paths.

## 6. Findings and implications

1. `UNKNOWN` is a required semantic/evidence state for bounded analysis, not a synonym for `UNSAT` and not a successful proof.
2. A replayed SAT witness is cheaply checkable for this finite pure Boolean fragment; it establishes one possible route but not route completeness.
3. Negative path pruning is the higher-trust operation. Without a checked proof or a declared trusted backend, a solver's `UNSAT` must not silently shrink a may-dependency set.
4. A timeout can reduce precision but must not change source semantics. Conservative retention may increase reported dependencies, invalidation work, or diagnostics.
5. The current SymPy DPLL experiment lacks a query-level timeout option in its documented API. A production resource bound needs an explicit process boundary or a backend with a documented limit and result-reason protocol; process termination, stale workers, and result attribution need their own recovery tests.
6. A fixed-seed generated cross-check raises confidence in the adapter for one small Boolean fragment, but does not establish broad solver correctness or independence from shared translation defects.

No candidate path-analysis or solver architecture is selected. The smallest demonstrated invariant is: **never discard an unresolved path**.

## 7. Remaining discriminators

- Compare structured families including parity/XOR encodings, pigeonhole-style constraints, repeated and contradictory predicates, and formulas with many irrelevant variables; report SAT/UNSAT separately and retain seeds/formulas.
- Exercise a real resource timeout and cancellation at an isolated worker boundary; verify that killed, crashed, malformed, and late responses map to UNKNOWN and cannot be attributed to another query.
- Check whether returned models are complete under the solver API or require explicit model completion; always replay them against a versioned immutable route formula.
- Compare exact enumeration, DPLL, and a timeout-capable solver on small domains; add a checked UNSAT certificate path before treating solver-only pruning as sound evidence.
- Add mutation/version identity and source parser/CFG extraction, then verify that unmodeled writes and missing nodes preserve UNKNOWN rather than reusing stale feasibility.
- Specify separately how an unknown path affects diagnostics, proof status, dependency completeness, incremental invalidation, and candidate scoring.

## 8. References

- [SMT-LIB 2.6 reference, satisfiability checking](https://smt-lib.org/papers/smt-lib-reference-v2.6-r2024-09-20.pdf)
- [Z3 Guide parameters](https://microsoft.github.io/z3guide/programming/Parameters/)
- [Z3 Solver API](https://z3prover.github.io/api/html/classz3py_1_1_solver.html)
- [SymPy 1.14 logic API](https://docs.sympy.org/1.14/modules/logic.html)
- [SymPy 1.14 SAT backend dependencies](https://docs.sympy.org/1.14/contributing/dependencies.html)
