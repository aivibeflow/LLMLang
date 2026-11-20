# Research Preparation — RT-03/04 Source Semantics, Calls, Effects and Ownership

**Status:** Prepared; not executed.  
**Priority:** P0 — first execution batch.  
**Primary gate:** Research State Gate A.  
**Related open questions:** LL-001, LL-003, LL-005, LL-008; RT-03 and RT-04 taxonomy gates.

## 1. Decision space to investigate

Establish a source-level, snapshot-bound account of one operation call that can mutate state, produce ordered effects, return or retain owned resources, fail during work or cleanup, and be followed by further calls through aliases.

The work must compare the existing RT-03 profiles and RT-04 alternatives without selecting one. It must establish what the source means before using a fixture-level AST, an action-list model, a generated program, or a type checker as evidence of source completeness.

## 2. Existing evidence to read first

Read these together:

- [RT-03 core semantics](../CORE-LANGUAGE-SEMANTICS.md)
- [RT-04 alternatives](../RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md)
- [Shared RT-03/04 corpus](../RT-03-04-SHARED-SEMANTICS-CORPUS.md), especially COR-13
- [COR-13 typed ownership follow-up](../RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md)
- [Scenarios 97–108](../RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md) — cleanup, paths, solver policy, mutation and aliases
- [Scenarios 119–133](../RESEARCH-SCENARIO-119-OWNED-RESULT-MATCHING.md) through [Scenario 133](../RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md) — call result ownership, SQLite observations, guard/resource roles, durable invocation evidence, common workload and generated Rust
- [Research State](../RESEARCH-STATE-2026-11-19.md), Gate A and suggested next sequence
- [Plan](../../PLAN.md), Sections 1.4 and 1.4.1

The latest merged evidence includes a common COR-13 workload checked by two execution models, typed caller recovery, and a generated Rust result. Treat those as bounded evidence for their stated fixtures, not proof of general source-to-runtime correspondence.

## 3. Questions the study must answer

### 3.1 Source and call-boundary completeness

1. What source constructs are admitted in the first study fragment?
2. How are declarations, call targets, overload/dispatch choices, argument evaluation, call sites and control-flow edges represented?
3. What ties an extracted call and its resource/effect summary to an exact source revision and semantic snapshot?
4. How are unresolved, dynamic, external, indirect and fallback call targets represented?
5. What evidence demonstrates that all relevant calls and mutation sites were observed?
6. Which conditions force UNKNOWN rather than an empty call set or a successful completeness assertion?

### 3.2 Ordered effects and observations

1. Which effects are visible: return values, errors, state writes, I/O, resource transitions, callbacks, cancellation and scheduler observations?
2. How are effect payloads and order represented across call, branch and cleanup boundaries?
3. Which effects commute, and what evidence is needed before reordering or eliminating them?
4. How do effect summaries propagate through callees, handlers, aliases and foreign boundaries?
5. What is the distinction between a declared effect permission, an observed effect, and runtime authority?

### 3.3 Ownership, transfer and cleanup

1. At what point does ownership transfer: before cleanup, after cleanup, or through a staged/conditional disposition?
2. What resource states can be returned on each success, error, cancellation and cleanup-failure outcome?
3. How are retained, consumed, pending-destruction and unknown dispositions represented?
4. How do caller match arms establish, forward, recover or discharge obligations?
5. How do alias identity, multi-resource roles, conditional release and shared callers change later admissible calls?
6. Which cleanup order, primary-error selection and secondary-error carrier preserve all obligations?

### 3.4 Recursion and execution budgets

Compare total recursion, typed divergence/partiality, source-level fuel, VM/operator gas and external deadlines. Determine how budget exhaustion interacts with:
- already completed effects;
- owned resources and cleanup;
- cancellation and task termination;
- nested calls and recursive SCCs;
- deterministic replay and evidence reuse.

Do not assume fuel exhaustion is identical to an ordinary error or cancellation.

## 4. Preparation of the common fixture set

Prepare a language-neutral corpus before implementing another checker. Each fixture must contain source, an explicit typed/snapshot representation, an expected observable contract, and an independent hand-reviewed trace description.

| Fixture family | Required discriminators |
|---|---|
| Call shape | direct, indirect, unresolved, dynamic/fallback, changed callee version |
| State/effects | ordered writes, same values with different traces, payload changes, handler rejection |
| Ownership | transfer before/after cleanup, retained/consumed result, aliased resource |
| Cleanup | success, primary failure, cleanup failure, multiple cleanup failures, LIFO nesting |
| Caller behavior | forward, recover, release, retain, incompatible shared-caller consumers |
| Foreign roles | one/two resources, shared/exclusive aliases, conditional release, incomplete footprint |
| Cancellation | request, acknowledgement, terminal completion, cleanup still running |
| Recursion/budget | bounded recursion, mutual recursion, exhaustion before/after effect, cleanup on exhaustion |

For every fixture include at least one positive case, one negative case, one ambiguous/UNKNOWN case, and a nearby mutation that should invalidate stale evidence.

## 5. Proposed method

1. Freeze a small syntax/AST and source inventory for the fixture corpus.
2. Define the observation record before implementing an evaluator. Include ordered events, payloads, terminal outcome, resource disposition and final state.
3. Build a source/snapshot adapter with explicit coverage evidence. Do not accept a caller-supplied boolean as proof that extraction is complete.
4. Derive call, effect, alias and ownership summaries from the pinned source representation.
5. Compare the derived summaries with an independent transition oracle and the existing RT-03 evaluators.
6. Extend the existing COR-13 workload rather than inventing a disconnected resource microbenchmark.
7. Add a second execution implementation only after the source contract is fixed. Keep implementation agreement separate from independent review of the contract.
8. Exercise both supported and unsupported constructs. Unsupported source, missing provenance, incomplete points-to information or uncertain foreign disposition must remain UNKNOWN or be rejected conservatively.

## 6. Validation matrix

- Transfer before cleanup versus after cleanup.
- Cleanup success/failure on normal, Result-error, cancellation and budget-exhaustion paths.
- Same scalar result with different ordered effects.
- Same diagnostic with different resource dispositions.
- Alias changes between the first and later call.
- Two consumers requiring old and new callee behavior.
- A foreign callback that re-enters or creates a dependent resource.
- An unresolved provider result and a delayed/stale terminal result.
- Recursive call cycles where an effect occurs before exhaustion.
- An unsupported source construct that must block a completeness claim.

Use exhaustive enumeration only where the finite domain is explicit. For larger domains, define seeded property/stateful tests and preserve the minimized counterexample.

## 7. Deliverables

- Versioned source fixture corpus and observation schema.
- Source-to-call/effect/resource extraction contract, including coverage and UNKNOWN rules.
- Transition oracle independent from the implementation under test.
- Comparative report for the RT-03/04 candidate combinations actually exercised.
- Counterexample catalogue and exact reproduction commands.
- Updated COR-13 mapping, research state, dependency map and option-matrix rows.

## 8. Exit criteria

The study may report a bounded result only when:
- every accepted source fixture maps to an exact pinned snapshot;
- call, effect, alias and resource summaries are derived from that snapshot;
- unknown or missing edges cannot be silently treated as absent;
- event order/payload, terminal outcome and resource dispositions are compared;
- later calls through aliases are checked against the live resource state;
- unsupported constructs and all tested failure paths are explicit;
- independent review challenges the source contract and fixture completeness;
- all claims state their fragment and assumptions.

No exit criterion authorizes selection of RT-03 profile A–D or an RT-04 type/resource architecture.
