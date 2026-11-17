# Example Task Template

**Task ID:** `NNNN`  
**Title:**  
**Difficulty:**  
**Status:** Proposed  
**Prerequisites:**  
**Related tasks:**  

> This file specifies the problem, not its implementation. Keep the task statement independent of any particular backend or implementation strategy. The corresponding candidate implementation belongs under `draft/examples/NNNN-<slug>/`.

## 1. Purpose

Describe what capability this task teaches or validates and why it exists in the progression.

## 2. Problem Statement

State the task as a precise request from the program user. Avoid prescribing internal implementation details unless they are part of the requirement.

## 3. Behavior and Interface

### Inputs

Describe every input source, its format, encoding, valid domain, and whether it is optional.

### Outputs

Describe exact output channels, formatting, encoding, and termination behavior.

### Errors and Edge Cases

List invalid inputs, environmental failures, boundary cases, and required behavior for each.

## 4. Requirements

Use stable requirement IDs in the form `R-NNNN-XX`. Each requirement must be externally observable, unambiguous, and testable.

- **R-NNNN-01:** ...
- **R-NNNN-02:** ...

## 5. Constraints and Non-Goals

### Constraints

List platform, runtime, dependency, resource, determinism, and compatibility constraints.

### Non-Goals

Explicitly state what this task does not require.

## 6. Acceptance Criteria

List observable conditions that must hold for the task to be accepted. Each criterion should reference one or more requirement IDs.

- [ ] ...

## 7. Test Scenarios

Provide concrete input/action and expected-output cases. Include normal, boundary, and error cases where applicable.

| Test ID | Scenario | Input / Action | Expected result | Requirements |
|---|---|---|---|---|
| T-NNNN-01 | ... | ... | ... | R-NNNN-01 |

## 8. Concepts Exercised

List language, runtime, library, compiler, or verification capabilities exercised by this task.

## 9. Completion Definition

State what artifacts must exist for a completed solution (for example source, tests, specification links, proof status, build/run instructions). Distinguish required artifacts from future enhancements.

## 10. Implementation Notes

Optional non-normative hints. Do not put requirements here; promote any mandatory behavior into Section 4.
