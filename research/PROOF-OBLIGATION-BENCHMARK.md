# Proof Obligation Benchmark

**Status:** Proposed research/evaluation corpus; non-normative  
**Purpose:** Evaluate proof-obligation generation, backend planning, verification, and evidence aggregation independently and end-to-end.  
**Related research:** [RT-33 — Proof Backend Selection and Verification Orchestration](RT-33-PROOF-BACKEND-SELECTION-AND-ORCHESTRATION.md), [RT-32 — Verified SPG-to-Lean Pipeline](RT-32-VERIFIED-SPG-TO-LEAN-PIPELINE.md), [RT-07](RESEARCH-TAXONOMY.md#2-research-area-inventory).  
**Related corpus:** [Contract Formalization Debug Corpus](CONTRACT-FORMALIZATION-CORPUS/README.md).

## 1. Why a separate benchmark

The existing Contract Formalization Debug Corpus (CF-001–CF-005) evaluates whether a model reconstructs the intended contract from a function request. It does not, by itself, evaluate whether the Toolchain decomposes that contract into proof obligations, selects suitable verification engines, or correctly interprets their evidence.

This benchmark extends the evaluation downstream without conflating those tasks. The two corpora are complementary and retain separate case IDs and acceptance criteria:

- **CF corpus:** Is the formalized contract semantically faithful to the source request?
- **Proof Obligation Benchmark:** Given an authoritative contract and a defined semantic/implementation model, are the obligations, verification plan, and evidence sound and complete for the stated scope?

A proof of an incorrectly formalized contract is not a successful result. Likewise, a backend success is not evidence for the original LLMLang claim unless the translation and correspondence boundary are justified.

## 2. Evaluation layers

Evaluate the following layers separately and as a complete pipeline:

1. **Contract formalization (A):** source intent and clarifications are reconstructed faithfully. Reuse CF cases and their semantic oracles; do not score this layer as a backend result.
2. **Proof-obligation generation (B):** derive the obligations entailed by the accepted contract and relevant implementation semantics. Check completeness, soundness, dependency links, assumptions, and source binding. The generator must not invent obligations that strengthen the contract or omit obligations that weaken it.
3. **Backend planning and verification (C):** classify each obligation, select one or more eligible backends, translate it, establish correspondence, run the checker, and aggregate evidence without promoting partial or unsupported evidence to proven.

Record per-layer outcomes. A failure in one layer must not be hidden by success in another.

## 3. Taxonomy

The taxonomy is **multi-label, not mutually exclusive**. One case can exercise several obligation forms and semantic domains. This is intentional: real contracts commonly generate a dependency graph of heterogeneous obligations.

### 3.1 Obligation forms

These describe the logical role an obligation plays in a contract or proof.

| ID | Class | What must be established | Representative examples |
|---|---|---|---|
| FORM-01 | Preconditions | Calls or operations are admitted only when required assumptions hold; invalid inputs are rejected or represented as specified. | Array index is in range; divisor is non-zero; a handle is live before use; caller has required authority. |
| FORM-02 | Postconditions | The result and observable state after an operation satisfy the promised outcome. | Returned value is the sum; result is sorted; lookup returns the first match; successful transfer changes ownership. |
| FORM-03 | Invariants | A predicate remains true at every required observation point or across every permitted state. | BST ordering; heap property; resource accounting never becomes negative; state-machine invariant is preserved. |
| FORM-04 | Frame and effect conditions | State outside the declared modification/effect footprint is preserved, and forbidden effects do not occur. | Prefix/suffix outside a reversed range remain unchanged; a read-only operation does not mutate input; one tenant cannot modify another tenant's data. |
| FORM-05 | Termination and progress | An operation terminates or meets a specifically stated progress guarantee under explicit assumptions. | Loop variant decreases; recursion reaches a base case; a continuously enabled task eventually runs under stated fairness assumptions. |
| FORM-06 | Refinement and equivalence | An implementation, optimization, translation, or abstraction preserves the required source observations or refines the specification. | Optimized sort refines the abstract sort contract; generated Rust preserves source behavior; two implementations are observationally equivalent. |

### 3.2 Semantic domains

These describe the subject matter or semantic theory needed to reason about an obligation.

| ID | Domain | What must be reasoned about | Representative examples |
|---|---|---|---|
| DOMAIN-01 | Arithmetic and numeric semantics | Mathematical versus machine integers, overflow, division, rounding, floating point, and numeric bounds. | Checked addition; no overflow in an index calculation; exact quotient/remainder relation; floating-point error bound. |
| DOMAIN-02 | Algebraic properties | Algebraic structures and laws used by an algorithm or transformation. | Associativity/commutativity under stated assumptions; monoid fold; validity of reassociation; matrix or polynomial identity. |
| DOMAIN-03 | Data-structure properties | Shape, ordering, reachability, uniqueness, and structural consistency. | BST ordering; heap order; linked-list acyclicity; balanced-tree rotation preserves invariants. |
| DOMAIN-04 | Ownership and memory safety | Lifetime, aliasing, borrowing, allocation, deallocation, and valid access. | No use-after-free; no double-free; conflicting mutable aliases are excluded; weak reference upgrade is checked. |
| DOMAIN-05 | Resource properties | Quantified resource use and resource-state constraints under an explicit cost/resource model. | Memory stays below a bound; file descriptors are released; recursion depth is bounded; operation count is O(n log n) under a stated model. |
| DOMAIN-06 | State transitions | Legal transitions, transition guards, state preservation, and operation sequencing. | Payment cannot be captured before authorization; closed connection cannot be reused; transaction commit is atomic with respect to its contract. |
| DOMAIN-07 | Temporal and liveness properties | Properties over traces or executions, including always/eventually, starvation, and fairness. | No request remains pending forever under stated assumptions; eventually every queued item is served; forbidden state is never reached. |
| DOMAIN-08 | Concurrency and memory-model properties | Interleavings, synchronization, atomicity, happens-before, data races, linearizability, and deadlock. | Race freedom; concurrent queue linearizability; lock discipline; no lost update; publication is visible under a specified memory model. |
| DOMAIN-09 | Error, exception, and failure atomicity | Error outcomes, propagation, cleanup, rollback, and state after partial failure. | Error is propagated; primary exception is preserved; failed transaction leaves state unchanged; cleanup failures are composed as specified. |
| DOMAIN-10 | Security and capability properties | Authority, isolation, confidentiality, integrity, and permitted information flow. | Unauthorized caller is rejected; tenant isolation; secret is not exposed in output; operation requires a specific capability. |

### 3.3 Cross-cutting dimensions

These are **not additional obligation classes**. Apply them across both axes:

- **Boundary coverage:** empty, singleton, minimum/maximum values, endpoint indices, zero, overflow boundary, and state-space boundary.
- **Assumptions:** explicit preconditions, environment constraints, fairness assumptions, scheduler/runtime profile, arithmetic model, and finite-model bounds.
- **Negative controls:** counterexamples and mutations that must be rejected.
- **Conditional evidence:** claims that hold only when named assumptions are discharged.
- **Composition:** dependencies between obligations, including caller/callee contracts and invariants shared across operations.
- **Uncertainty:** ambiguity, unsupported semantics, incomplete models, bounded-only results, and missing correspondence evidence.

## 4. Required case design

Each case should use the [benchmark case template](PROOF-OBLIGATION-BENCHMARK-TEMPLATE.md) and include, where applicable:

1. Stable case ID, revision, provenance, and taxonomy labels.
2. Source-level description, authoritative contract, and explicit assumptions.
3. Expected obligation set and dependency graph, with a rationale for each obligation.
4. At least one valid implementation/model and one plausible incorrect mutation.
5. Boundary and adversarial inputs or execution traces.
6. Expected semantic outcome/oracle independent of the backend under test.
7. Candidate backend capabilities and known limitations, without presupposing that a backend must succeed.
8. Required translation/correspondence evidence and trusted assumptions.
9. Expected result classification and aggregation rules.
10. Reproducible execution instructions and recorded tool/backend versions.

For a mature case family, aim to cover these variants:

- a normal positive case;
- a boundary case;
- a negative/counterexample case;
- a conditional case whose proof depends on explicit assumptions;
- a composed case with multiple dependent obligations.

Not every individual case needs all five variants, but each class/domain should have meaningful positive and negative coverage. The initial planning target is **up to 5 cases for each of the 16 taxonomy entries (up to 80 cases)**. This is a coverage target, not a quota: multi-label cases should be preferred over artificial duplication, and coverage gaps should be reported rather than filled with weak examples.

## 5. Representative obligation examples

The following are seed examples for future cases, not completed benchmark cases:

- **Preconditions:** safe array access (0 <= i < length); division with a non-zero divisor; closing a resource only when the caller owns the required capability.
- **Postconditions:** sum includes every element exactly once; sort is nondecreasing and preserves the input multiset; first-match search returns the least matching index.
- **Invariants:** every child of a BST node obeys the ordering relation; a heap's parent priority is no lower than its children; outstanding resource count equals acquired minus released resources.
- **Frame/effects:** reversing [start, end) preserves all positions outside the range; a query leaves the database unchanged; a failed update does not mutate unrelated records.
- **Termination/progress:** a search loop decreases a non-negative measure; recursive traversal consumes a finite structure; a scheduler satisfies a stated fairness guarantee.
- **Refinement/equivalence:** optimized and reference implementations produce the same observable result and effects; a source-to-target translation preserves specified error and memory behavior.
- **Arithmetic/numeric:** checked multiplication rejects overflow; a bounded index expression cannot wrap; a floating-point routine stays within an explicit error tolerance.
- **Algebraic:** reassociation is valid only for an operation with the required associativity; parallel reduction agrees with the sequential fold under stated algebraic assumptions.
- **Data structures:** tree rotations preserve ordering and node identity; list insertion preserves acyclicity and reachability.
- **Ownership/memory:** no reference outlives its owner; a mutable borrow excludes conflicting access; deallocation occurs exactly once.
- **Resources:** a parser uses memory linear in input size under a specified allocator model; all acquired descriptors are eventually released.
- **State transitions:** a payment state machine excludes captured -> authorized; a transaction either commits all declared writes or none.
- **Temporal/liveness:** every accepted request eventually completes if the worker remains enabled and the scheduler satisfies the stated fairness condition.
- **Concurrency:** a concurrent queue is linearizable to a sequential queue specification; a publication protocol forbids reading an uninitialized payload.
- **Errors/failure:** an operation returning failure leaves its abstract state unchanged; cleanup preserves the primary failure and records secondary failures.
- **Security/capabilities:** a caller lacking ReadSecret cannot observe a secret; cross-tenant operations cannot affect another tenant's state.

## 6. Multi-backend and composition scenarios

Include cases that require more than one kind of reasoning. Backend roles below are hypotheses to evaluate, not fixed assignments:

- **Sorting with machine arithmetic:** ordering/permutation obligations plus index and overflow obligations; compare SMT arithmetic with an independently checked structural proof where appropriate.
- **Concurrent queue:** sequential data-structure invariant and linearizability plus temporal progress; compare state-space exploration (for example TLA+) with implementation-level proof/checking.
- **State machine with numeric guards:** transition legality plus arithmetic boundary conditions; exercise complementary model checking and SMT reasoning.
- **Cross-language translation:** source/target observational equivalence, error behavior, and memory/ownership conditions; require evidence for the translation relation, not just target verification.
- **Ownership-aware structure:** alias/lifetime obligations composed with a mutable data-structure invariant.

A backend may discharge only part of a case. The benchmark must record which exact obligations it covers and what remains open.

## 7. Result model and failure controls

At minimum, retain the RT-33 result distinctions:

- **proven** — the exact obligation is established within the declared assumptions and trust boundary;
- **disproven** — a valid counterexample refutes the obligation;
- **unknown** — the backend cannot decide or did not complete;
- **unsupported** — required semantics or evidence are outside the backend's declared capabilities;
- **error** — translation, execution, or infrastructure failed in a way that prevents a sound verdict.

Also record conditionality, boundedness, assumptions, translation correspondence, backend/tool versions, and provenance. A bounded model check must not be reported as an unbounded proof. Missing or unverified translation correspondence must prevent a backend result from being promoted to proof of the source obligation.

Include explicit **abstention tests**: the correct planner response is sometimes unsupported, unknown, or a partial plan—not a forced backend selection or a weakened obligation. Evidence aggregation must never turn a missing, failed, conditional, or unsupported obligation into an overall proven result.

## 8. Scoring and reporting

Report separate scores for:

- obligation-generation soundness and completeness;
- taxonomy classification accuracy (including multi-label assignments);
- backend eligibility and selection quality;
- translation/correspondence validity;
- checker verdict correctness against the independent oracle;
- evidence aggregation and assumption handling;
- correct abstention and uncertainty reporting;
- reproducibility and provenance completeness.

Do not collapse these into a single accuracy number. Report per-class/domain coverage, positive/negative balance, boundary coverage, unsupported coverage, and the number of obligations left unresolved. Preserve raw outputs and versioned benchmark runs; never overwrite prior runs when a model, prompt, contract, translator, or backend changes.

## 9. Scope and non-decisions

This document establishes an evaluation plan, not an accepted LLMLang architecture or language rule. It does not:

- select Lean, SMT, TLA+, or any other universal backend;
- require every obligation to be reducible to Lean;
- define the normative Contract IR schema or surface contract syntax;
- claim that the proposed taxonomy is complete;
- prescribe one backend per taxonomy label;
- treat testing, bounded model checking, solver output, or target compilation as proof beyond its stated scope.

The [executable seed corpus and infrastructure](PROOF-OBLIGATION-BENCHMARK/README.md) provides twelve proposed finite reference/mutation cases, an offline runner, and experiment protocol. The next steps are independent adjudication, backend integration and controlled evaluation; see the linked issues. Finite smoke results do not establish unbounded proofs.

## 10. Planned RT-34 resource-complexity expansion

[RT-34](RT-34-AUTOMATIC-COMPLEXITY-INFERENCE.md) and its [32-case proposed benchmark matrix](RT-34-COMPLEXITY-BENCHMARK.md) extend DOMAIN-05 to model-scoped asymptotic upper/lower/tight bounds, task optimality, symbolic size/cost summaries, recursion, memory, amortized/probabilistic costs, target correspondence and stale evidence. Keep FORM/DOMAIN tags multi-label; do not reuse case IDs. Preserve finite-vs-unbounded scope: a finite oracle does not establish asymptotic growth. Score correct abstention and bound precision separately from soundness. The matrix is a planning artifact, not a claim that the executable POB corpus already covers these cases.
