# Research Preparation — RT-03/06/07 Path Feasibility and Source Correspondence

**Status:** Prepared; not executed.  
**Priority:** P0 — continues the current formal/source-analysis line.  
**Related open questions:** LL-005, LL-008; RT-03, RT-06 and RT-07 gates.

## 1. Objective

Prepare the next evidence step from finite path experiments to source-bound, fail-closed path analysis. A negative solver result may remove a path or dependency only when the source-to-query mapping, solver result and checking boundary support that claim. Timeouts, worker failures, unsupported constructs and unverifiable UNSAT must retain UNKNOWN/possible paths.

## 2. Existing baseline

Read:
- [Scenarios 98–108](../RT-06/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) for finite AST path coverage, repeated predicates, finite feasibility, DPLL2 comparison, UNKNOWN/timeout, mutation identity, call summaries and aliases.
- [Scenario 34 — source-to-query correspondence](../RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md), including its SCW task ledger.
- [Research State](../RESEARCH-STATE-2026-11-19.md), especially the RT-06/07 unresolved areas and Gate A.
- [Research Dependency Map](../RESEARCH-DEPENDENCY-MAP.md), especially solver-negative evidence and dependency completeness.

Scenario 34 records the checked Int/Bool expression core, command and observation preservation, and the Lean relational compiler. SCW-26–28 prove that the formula is satisfiable exactly when an admitted pair differs at the selected input and in the final return or selected state. SCW-29 and SCW-30 prove that the lowered formula belongs to the strict QF_LIA profile and that every symbol has a unique declaration of its sort and source role. JSON and proof checker correspondence remain open in SCW-31–34. [Scenario 34](../RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#76-qf_lia-admissibility-and-external-wirechecker-boundary)

## 3. Questions

### Source correspondence
- What grammar, type, scope, declaration and control-flow fragment is accepted?
- How is every AST/CFG node bound to exact source spans, source revision and declaration identity?
- How are loops, calls, early exits, exceptions, effects, aliases and recursive control flow represented?
- How is complete branch/edge coverage proved or conservatively reported?
- What happens when parser recovery, macros, generated code or dynamic dispatch obscure correspondence?

### Predicate identity and mutation
- Are predicates bound to immutable value versions rather than variable names?
- How do writes, call summaries, aliasing and field-sensitive updates change path constraints?
- Can a may-write or incomplete call summary only broaden the possible routes?
- How are path conditions correlated across calls, branches, loops and alias identities?
- What analysis is exact only for finite enumeration, and what is a sound conservative approximation?

### Solver and negative-result trust
- Which SAT/UNSAT/UNKNOWN outcomes are accepted?
- What evidence links the exact query and solver invocation to the source path?
- Which proof certificate or independent checker is required before UNSAT prunes a route?
- How are timeout, resource exhaustion, crash, malformed output, cancellation and worker orphaning represented?
- Which hard formula families, not only easy conjunctions, are required to expose performance and failure behavior?

## 4. Proposed fixture families

| Family | Required cases |
|---|---|
| Predicate identity | repeated predicate; same name after write; immutable version before/after call |
| Source/CFG | nested branches; loops; early exits; unreachable syntax; parser recovery; generated/macro origin |
| Calls | pure; known write; may-write; unknown target; callback/reentry; alias mutation |
| Heap/fields | exact, disjoint, may-alias, unknown points-to; nested fields; path-correlated aliases |
| Solver | easy SAT/UNSAT, hard SAT/UNSAT, timeout, memory limit, worker crash, malformed response |
| Evidence | checked UNSAT certificate, unchecked UNSAT, UNKNOWN, stale query, changed source or tool version |

For each case record the concrete source executions (or a bounded exhaustive oracle), source/CFG route set, solver query, witness replay and final may-dependency set.

## 5. Proposed sequence

1. Revalidate the Scenario 34 task ledger and the checked Lean modules.
2. Use the SCW-06–09 scope, typing and environment invariants as the base for command semantics.
3. Use the checked command AST and big-step rules from SCW-16–18 as the concrete reference.
4. Use the checked observation contract and single-run proof from SCW-22–23 when comparing paired outputs.
5. Use the checked relational formula, canonical binding table and concrete-witness equivalence from SCW-26–28 as the input to solver-facing lowering.
6. Use the admissibility and declaration closure theorems from SCW-29–30 to prove wire and Logos correspondence and establish the solver trust boundary (SCW-31–34).
7. Add adversarial fixtures, axiom/kernel audit and pinned proof CI (SCW-35–41).
8. In parallel, extend RT-03 path analysis only where the same source identity and mutation semantics are used; do not substitute finite route enumeration for general symbolic completeness.

## 6. Resource and worker test plan

Measure, separately:
- wall-clock deadline and actual worker termination;
- CPU and memory limits;
- process-tree cleanup, descendants and orphan prevention;
- solver startup and serialization overhead;
- SAT, UNSAT and UNKNOWN distribution by formula family and size;
- result reproducibility across pinned tool versions;
- checker time and certificate size;
- path/dependency precision lost by conservative UNKNOWN handling.

Keep timeouts as UNKNOWN. A worker killed at a deadline is not evidence of UNSAT. Record all seeds and preserve minimized failing cases.

## 7. Exit criteria

- The source fragment and excluded syntax are explicit.
- Every accepted query is bound to the exact source, typed AST/CFG and declaration context.
- Mutation and alias transitions preserve all concrete paths in the accepted fragment.
- Unsupported or untrusted negative results cannot prune paths.
- SCW theorem claims are kernel-checked at their exact stated scope; tests remain regression evidence.
- Resource/worker failures have deterministic, fail-closed outcomes.
- An independent review checks the source-to-query contract, not only implementation agreement.

No result from this study defines all LLMLang semantics or justifies broad dependency deletion outside the proven fragment.
