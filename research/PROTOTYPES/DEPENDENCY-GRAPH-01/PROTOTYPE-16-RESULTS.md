# Prototype 16: Business Intent to Formal Contract — Results

**Status:** Research prototype; successful local unit-test run  
**Related research:** [Research Scenario 15](../../RT-02/RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md)

## Objective

Exercise a small end-to-end path from stakeholder language to a caller-scoped business rule, a provenance-carrying formal candidate, explicit human acceptance, and a new project snapshot. The key test is whether a business-rule change for one caller leaves another caller and a generic callee unchanged.

## Scenario

Two callers use the same generic calculation capability:

- \`preferred_order\`: 15% since 2026-01-01;
- \`standard_order\`: 20% since 2026-01-01.

A new statement says: "Reduce the preferred-customer tax rate to 12% starting next month."

The system does not infer what "next month" means. A clarification decision explicitly selects:

- applicability is based on \`order_date\`, not \`invoice_date\`;
- effective date is 2026-12-01;
- decision authority is the Tax policy owner.

The preferred caller's rule changes to 12%. The standard caller remains at 20%. The prototype also generates a boundary example and counterexamples showing why \`order_date\` and \`invoice_date\` are not interchangeable: an order placed before the effective date but invoiced afterward produces different rates under the two interpretations.

## Implemented path

1. \`IntentSource\` retains the exact stakeholder statement and gets a content digest.
2. \`ClarificationDecision\` records the question, alternatives, selected interpretation, and named authority.
3. \`BusinessRule\` records caller scope, rate, effective date, date basis, and source/decision hashes.
4. \`FormalCandidate\` contains readable illustrative predicates for applicability and selected rate.
5. Each \`FormalClause\` carries source and decision references plus a provenance status.
6. \`accept_candidate\` rejects unresolved, ungrounded, assumed, or inferred clauses and requires an explicit authorized approver.
7. \`ValidatedContract\` binds the accepted candidate and scope; a separate approval digest records the approver.
8. The content store retains source, decision, rule, clause, candidate, and accepted-contract values. Contextual provenance links are stored separately in \`RelationStore\`.
9. A new snapshot is built with caller-policy selections and a fixed generic \`calculate_tax\` contract.

## Result

The local experiment produced:

| Check | Result |
|---|---|
| Changed snapshot root | Yes |
| Changed selection keys | \`caller:preferred_order\` only |
| Preferred caller changed | Yes, 1500 → 1200 basis points |
| Standard caller changed | No, remains 2000 basis points |
| Generic callee contract changed | No |
| Generic calculation implementation changed | No |
| Stored semantic values in scenario | 18 |
| Provenance links | accepted contract → source intent; accepted contract → clarification decision |

For a taxable basis of 10,000 cents, the generic operation returns 1,200 cents at 12% and 2,000 cents at 20%. The rate is an explicit input; the calculation function does not select customer or jurisdiction policy.

## Tests

Nine new unit tests passed locally:

- clarification requires a selected alternative and explicit authority;
- caller scope and date basis are explicit;
- formal clauses retain source and decision provenance;
- acceptance requires authorized human approval;
- unresolved and ungrounded clauses cannot be accepted;
- effective-date boundary examples distinguish order date from invoice date;
- generic calculation accepts explicit policy input and uses integer half-up rounding;
- changing the preferred rule changes only the preferred caller selection;
- project snapshot changes while the callee contract hash remains identical.

Run from \`PROTOTYPES/DEPENDENCY-GRAPH-01\`:

\`\`\`bash
python -m unittest discover -s tests -p 'test_business_intent.py' -v
\`\`\`

## What this prototype demonstrates

- A policy change can be scoped to the caller that owns the policy.
- A reusable callee can remain generic by accepting explicit policy data.
- Clarification decisions and human acceptance can be represented separately from LLM-generated candidates.
- Clause-level provenance can be preserved in a small data model.
- Content-addressed snapshots make the changed selection visible without rewriting unchanged selections.

## What it does not demonstrate

- It does not parse natural language or autonomously detect ambiguity. The clarification is supplied explicitly by the test scenario.
- It does not determine whether the named approver is truly authorized. The \`authorized\` boolean is a test seam, not an access-control implementation.
- It does not prove that the formal candidate captures the stakeholder's full intent.
- Formal predicates are illustrative strings, not parsed or checked by a formal logic engine.
- The tax function is ordinary Python; no source-to-contract proof is performed.
- The prototype does not model jurisdiction selection, tax exemptions, multiple tax components, currency conversion, or legal compliance.
- The snapshot experiment is single-process and in-memory; it is not a distributed transaction or persistent project build.
- The tests cover the new module; they are not a run of the entire repository test suite.

## Conclusion

The most important result is the selective evolution: the preferred caller's policy selection changes, while the standard caller and shared calculation contract remain unchanged. The prototype also makes the trust boundary explicit: candidate generation and contract acceptance are different operations.

The next useful increment is not a larger LLM prompt. It is a typed, machine-checkable Requirement IR and a small validator that can detect unsupported clauses, unresolved assumptions, contradictions, and vacuous contracts before acceptance.
