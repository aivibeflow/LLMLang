# CF-006 — Bank-account withdrawal

**Case ID:** CF-006  
**Title:** Bank-account withdrawal  
**Revision:** 1  
**Status:** Proposed evaluation case  
**Focus:** Bidirectional success condition, conditional postconditions, state preservation, boundary values, and requirement decomposition  
**Related research:** [Contract Formalization Debug Corpus](../README.md), [Scenario 17 — Typed Requirement IR](../../../language-design/RT-02/RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md), [RT-02 — Requirement Reconstruction](../../../language-design/RT-02/RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md)

## 1. Source request

> An operation that withdraws money is successful if and only if the requested amount is positive and does not exceed the current balance. If the operation succeeds, the balance is reduced by the requested amount. If the operation fails, the balance remains unchanged.

The source wording is the complete prompt for the unclarified evaluation track.

## 2. Clarifications

No additional business-policy clarification is required to express the three stated rules.

The following representation details are intentionally not fixed by the source request and must not be silently invented by a model:
- the concrete numeric representation and currency precision;
- overflow/underflow behavior of the implementation representation;
- whether the operation has other observable outputs or side effects.

For the semantic oracle below, use mathematical values and arithmetic so that machine-integer overflow is outside this case's scope. This is an explicit benchmark abstraction, not a claim about a production account implementation.

## 3. Interface and semantic domain

- State before the operation: `old_balance`.
- Input: `amount`.
- State after the operation: `new_balance`.
- Result: Boolean `success`.

For this case's mathematical oracle, `old_balance` and `amount` are real-valued quantities and `new_balance` is the resulting balance. The source request does not independently state a global account invariant such as non-negative balance; do not add one as an extra requirement.

## 4. Accepted semantic oracle

Let:

```text
valid_withdrawal := (amount > 0) AND (amount <= old_balance)

success <-> valid_withdrawal

success  -> new_balance = old_balance - amount

NOT success -> new_balance = old_balance
```

Equivalently, the post-state is completely determined by the input and pre-state:

```text
new_balance =
    if valid_withdrawal
    then old_balance - amount
    else old_balance
```

The equivalence is important: the condition is both necessary and sufficient for success. The two implications governing the balance are separate conditional postconditions.

## 5. Required contract properties

A faithful formalization must preserve all three clauses independently:

1. **Success equivalence:** success is true exactly when `amount > 0` and `amount <= old_balance`.
2. **Successful state transition:** when success is true, subtract exactly the requested amount.
3. **Failure frame condition:** when success is false, preserve the balance exactly.

The contract must not replace the equivalence with a one-way implication. It must not omit either branch of the state transition.

### Illustrative FRETish-style decomposition

The following is a readable, FRETish-inspired sketch for the three separate requirements. It is not asserted to be validated native FRETISH syntax:

```text
BankAccount shall always satisfy
    success <-> (amount > 0 & amount <= old_balance)

BankAccount shall always satisfy
    success -> (new_balance = old_balance - amount)

BankAccount shall always satisfy
    !success -> (new_balance = old_balance)
```

## 6. Negative controls

| ID | Incorrect candidate contract or behavior | Why it is wrong | Expected detection |
|---|---|---|---|
| NC-01 | `success -> amount > 0 AND amount <= old_balance` only | Establishes necessity but not sufficiency; valid requests may fail | Detect weakened equivalence |
| NC-02 | `(amount > 0 AND amount <= old_balance) -> success` only | Establishes sufficiency but permits success for invalid requests | Detect weakened equivalence |
| NC-03 | `amount >= 0` | Allows a zero-amount withdrawal | Detect strict-positive boundary error |
| NC-04 | `amount < old_balance` | Rejects withdrawal of the entire balance | Detect exclusive upper-bound error |
| NC-05 | `success -> new_balance = amount` | Assigns the requested amount instead of subtracting it | Detect wrong state transition |
| NC-06 | No failure postcondition | Leaves failed-operation state unconstrained | Detect missing frame condition |
| NC-07 | `!success -> new_balance = old_balance - amount` | Mutates the balance on failure | Detect inverted branch |
| NC-08 | Add a requirement that every account balance is always non-negative, independent of this operation | The source request specifies this operation's behavior, not a global invariant | Detect unjustified strengthening |

## 7. Mutation challenges

| ID | Mutated implementation behavior | Must contract reject? | Reason |
|---|---|---|---|
| MUT-01 | Reports success for `amount = 0` | Yes | Amount must be strictly positive |
| MUT-02 | Reports success for `amount < 0` | Yes | Negative amount violates the success condition |
| MUT-03 | Reports success when `amount > old_balance` | Yes | Insufficient balance |
| MUT-04 | Reports failure when `amount = old_balance` and both are positive | Yes | Equality at the upper boundary is allowed |
| MUT-05 | Reports success for a valid positive amount but subtracts a different amount | Yes | Successful transition must subtract exactly the requested amount |
| MUT-06 | Reports failure but changes the balance | Yes | Failure must preserve the balance |
| MUT-07 | Uses a different internal algorithm but produces the required success value and balance | No | The contract specifies observable behavior, not implementation strategy |

## 8. Boundary scenarios

Assuming the mathematical domain stated in Section 3:

| `old_balance` | `amount` | Expected `success` | Expected `new_balance` |
|---:|---:|---|---:|
| 100 | 30 | true | 70 |
| 100 | 100 | true | 0 |
| 100 | 0 | false | 100 |
| 100 | -1 | false | 100 |
| 100 | 101 | false | 100 |
| 0 | 1 | false | 0 |
| 0 | 0 | false | 0 |
| 0 | -1 | false | 0 |

These are illustrative witnesses, not an exhaustive proof.

## 9. Evaluation rubric

A model output passes the semantic review only if it:

- expresses the success condition as a genuine biconditional, or as two logically equivalent implications;
- uses strict positivity for the requested amount;
- uses an inclusive upper bound against the pre-state balance;
- subtracts the requested amount on success;
- preserves the pre-state balance on failure;
- keeps pre-state and post-state values distinct;
- does not introduce unsupported global invariants or implementation details;
- reconstructs all three requirements in plain language without omission.

Classify the following separately:
- **Formalization defect:** any semantic mismatch, omission, or unjustified strengthening above.
- **Representation/backend limitation:** the chosen formalism cannot express a required construct.
- **Checker UNKNOWN/failure:** no semantic pass or fail should be inferred solely from an unavailable or inconclusive backend.

This case is particularly useful for testing whether a model decomposes one compound natural-language statement into multiple independently reviewable clauses while preserving their logical relationship.

## 10. Revision history

| Revision | Change | Reason |
|---|---|---|
| 1 | Initial bank-account withdrawal case | Add a compact state-transition example covering equivalence, conditional postconditions, and failure-state preservation |
