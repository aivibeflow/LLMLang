# Contract Formalization Case Template

**Case ID:** CF-NNN  
**Title:**  
**Revision:** 1  
**Status:** Proposed  
**Focus:**  
**Related research:**  

## 1. Source request

Exact wording presented to the model. Do not include hidden oracle details here.

## 2. Clarifications

List clarification questions and authoritative answers. If meaning is not specified, mark it unresolved; do not invent an answer.

## 3. Interface and semantic domain

Define input/output types, relevant state, valid input domain, and assumptions needed to interpret the request.

## 4. Accepted semantic oracle

Give a language-neutral mathematical definition of required observable behavior. Define notation, quantifier ranges, empty-domain behavior, and state/frame conditions.

## 5. Required contract properties

List semantic facts a faithful contract must express. Distinguish required properties from optional strengthening.

## 6. Negative controls

| ID | Incorrect candidate contract or behavior | Why it is wrong | Expected detection |
|---|---|---|---|
| NC-01 | ... | ... | ... |

Include under-specification and over-specification controls where meaningful.

## 7. Mutation challenges

| ID | Mutated implementation behavior | Must contract reject? | Reason |
|---|---|---|---|
| MUT-01 | ... | Yes/No | ... |

Also list valid implementation alternatives that the contract must permit.

## 8. Boundary scenarios

Include empty, singleton, minimum/maximum, and invalid cases as applicable.

## 9. Evaluation rubric

Specify semantic-fidelity checks and common model failure modes. Keep proof-engine failures separate from contract-quality failures.

## 10. Revision history

| Revision | Change | Reason |
|---|---|---|
| 1 | Initial case | ... |
