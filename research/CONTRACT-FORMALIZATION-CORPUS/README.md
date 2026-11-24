# Contract Formalization Debug Corpus

**Status:** Initial evaluation corpus; non-normative  
**Purpose:** Debug and compare AI models that turn function descriptions and clarified requirements into formal contracts.  
**Related research:** [Scenario 15](../RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md), [Scenario 17 — Typed Requirement IR](../RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md), [RT-02](../RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md), [RT-32](../RT-32-VERIFIED-SPG-TO-LEAN-PIPELINE.md).

## 1. Purpose and scope

This corpus isolates the **contract-formalization step** from implementation generation and proof construction. Given a natural-language function request, a model should produce a contract that captures the accepted meaning without silently weakening, strengthening, or changing it.

It is designed to reveal whether a model:
- identifies inputs, outputs, state changes, preconditions, and postconditions;
- handles empty inputs and boundary values;
- quantifies over the correct range and uses inclusive/exclusive bounds correctly;
- distinguishes mathematical specification from implementation algorithm;
- preserves observable behavior without accidental implementation constraints;
- asks for clarification instead of inventing missing policy;
- produces contracts strong enough to reject plausible incorrect implementations;
- avoids contracts so strong that they reject valid implementations.

A successful proof of a candidate contract is **not** a successful corpus result by itself. A model can formalize the wrong meaning and then prove that wrong contract.

## 2. Corpus structure

- [TEMPLATE.md](TEMPLATE.md) — required structure for new cases.
- [CF-001 — Sum every array element](cases/CF-001-sum-array.md)
- [CF-002 — Safe array lookup](cases/CF-002-safe-array-lookup.md)
- [CF-003 — First matching element](cases/CF-003-first-match.md)
- [CF-004 — Reverse a selected range](cases/CF-004-reverse-range.md)
- [CF-005 — Sort an array](cases/CF-005-sort-array.md)
- [CF-006 — Bank-account withdrawal](cases/CF-006-bank-withdrawal.md) — biconditional success condition, success/failure postconditions, and failure-state preservation.

Each case separates:
1. **Source request** — exact wording presented to the model.
2. **Clarifications** — authoritative answers that remove ambiguity; absent clarifications must remain unresolved.
3. **Accepted semantic oracle** — language-neutral mathematical meaning.
4. **Negative controls** — plausible incorrect contracts and the defect each demonstrates.
5. **Mutation challenges** — incorrect behaviors that the contract must reject, plus valid alternatives it must permit.
6. **Evaluation notes** — common formalization errors and required model behavior.

The semantic oracle is an evaluation reference, not a selected LLMLang contract syntax or normative language rule.

## 3. Evaluation dimensions

Score these dimensions separately:
1. **Semantic fidelity** — matches the accepted oracle.
2. **Completeness** — constrains every required observable outcome.
3. **Non-overconstraint** — does not impose behavior absent from the request.
4. **Type/logic correctness** — expressions are well-typed and well-formed.
5. **Boundary handling** — covers empty, singleton, and endpoint cases.
6. **Ambiguity handling** — asks for clarification or marks unresolved meaning.
7. **Counterexample discrimination** — rejects the negative controls.
8. **Implementation independence** — does not prescribe an algorithm unless required.

Do not collapse these dimensions into one pass/fail score. Record unsupported constructs and checker UNKNOWN separately from semantic failure.

## 4. Suggested evaluation procedure

1. Present only the **Source request** to the model.
2. Provide listed clarifications only after the model asks, or run a separate clarified-input track.
3. Ask for a contract and a plain-language reconstruction of what it permits and forbids.
4. Compare the result with the semantic oracle; review omissions and unsupported extra constraints.
5. Test negative controls. Where practical, generate witnesses showing that a bad behavior satisfies a weak candidate contract.
6. Translate the candidate into each evaluated formalism only after preserving the model's original output.
7. Record proof/checker outcomes separately from semantic-fidelity review.

For each run, preserve the exact prompt, model/version, settings, raw output, normalized typed representation (if available), reviewer verdict, and reproducible checker/proof results. Never overwrite earlier runs when prompts, models, or corpus versions change.

## 5. Relationship to proof-obligation evaluation

This corpus evaluates contract formalization only. Its six initial cases are not intended to cover the full space of proof obligations or backend behavior. The separate [Proof Obligation Benchmark](../PROOF-OBLIGATION-BENCHMARK.md) evaluates downstream obligation generation, backend planning, translation correspondence, verification, and evidence aggregation. Keep the two evaluation layers separate: a downstream proof cannot compensate for a semantically incorrect contract.

## 6. Versioning and limitations

Case IDs are stable and must never be reused. Changes to accepted meaning require an explicit case revision and a note explaining the semantic change. Wording-only corrections should also be recorded.

The initial cases do not cover overflow, concurrency, floating-point behavior, aliasing, ownership, exceptions, termination, or temporal properties. Add those as separate cases with explicit semantics.

No surface contract language, Contract DSL, Contract IR schema, proof backend, or LLMLang semantic rule is selected by this corpus.

## 7. Planned RT-34 resource-contract extension

[RT-34](../RT-34-AUTOMATIC-COMPLEXITY-INFERENCE.md) and its [complexity benchmark plan](../RT-34-COMPLEXITY-BENCHMARK.md) propose new formalization cases with explicit size measures, cost models, worst/expected/amortized scopes and resource guarantees. CF-005 remains unchanged: functional sorting does not imply a complexity requirement. Include underspecified requests where clarification or abstention is correct, and mutations that preserve function behavior while violating a stated bound. Allocate new stable CF IDs when fixtures are independently adjudicated; no new executable coverage is claimed by this plan.
