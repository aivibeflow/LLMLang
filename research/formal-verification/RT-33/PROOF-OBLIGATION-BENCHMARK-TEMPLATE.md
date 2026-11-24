# Proof Obligation Benchmark Case

**Case ID:** POB-XXX  
**Revision:** 1  
**Status:** Proposed / reviewed / retired  
**Taxonomy labels:** FORM-XX; DOMAIN-XX  
**Related CF case(s):** CF-XXX or none

## 1. Intent and scope

Describe the behavior and the exact claim under evaluation. State what is in and out of scope.

## 2. Authoritative contract and assumptions

Record the contract independently of any backend syntax. List assumptions, environment constraints, numeric model, scheduler/fairness assumptions, and bounds explicitly. Mark unresolved ambiguity rather than inventing policy.

## 3. Expected proof obligations

| Obligation ID | Claim | Form/domain labels | Dependencies | Assumptions |
|---|---|---|---|---|

Explain why each obligation is required and why no stronger or weaker claim is intended.

## 4. Models and mutations

- Valid reference implementation/model:
- Incorrect mutation(s):
- Expected counterexample(s):
- Boundary inputs/traces:
- Valid alternative implementations that must remain permitted:

## 5. Semantic oracle

State the backend-independent expected outcomes and the method used to derive/check them. Identify any bounded scope and limitations.

## 6. Backend planning expectations

| Obligation ID | Candidate backend(s) | Required capability | Known limitation | Abstention/partial-result expectation |
|---|---|---|---|---|

Do not assume a candidate backend is eligible merely because it is listed.

## 7. Translation and evidence boundary

Describe the source-to-backend relation that must be justified, the trusted computing base, evidence format, and assumptions that remain trusted.

## 8. Expected result and aggregation

Specify expected per-obligation statuses (proven, disproven, unknown, unsupported, error), conditionality, boundedness, and the only valid overall aggregation.

## 9. Reproduction and evaluation record

Record exact source/contract snapshot, model/prompt/version, translator version, backend/tool version and configuration, raw outputs, oracle result, reviewer verdict, and reproduction command.
