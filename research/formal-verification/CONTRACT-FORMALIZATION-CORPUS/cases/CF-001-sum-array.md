# CF-001 — Sum every array element

**Revision:** 1  
**Status:** Proposed  
**Focus:** Whole-array quantification, half-open index ranges, empty arrays, implementation independence.

## 1. Source request

Write a function that returns the sum of all integers in the input array.

## 2. Clarifications

- Every element is included exactly once.
- The empty array has sum zero.
- The mathematical result uses unbounded mathematical integers. Machine-integer overflow behavior is outside this case and must not be guessed.

## 3. Interface and semantic domain

- Input: finite sequence a of mathematical integers.
- Output: mathematical integer r.
- No mutation or other observable effects are required.

Let n = |a|, with valid sequence indices 0 through n-1.

## 4. Accepted semantic oracle

\[
r = \sum_{i=0}^{n-1} a_i
\]

The sum over an empty index set is 0. Equivalently, the result is the fold of addition over the complete sequence, with identity 0.

## 5. Required contract properties

- The result includes every element, including index n-1 when n is positive.
- No element outside the sequence is part of the result.
- Empty input returns zero.
- The contract describes the result, not a loop, traversal direction, accumulator, or particular algorithm.

## 6. Negative controls

| ID | Incorrect candidate | Why it is wrong | Expected detection |
|---|---|---|---|
| NC-01 | Sum indices 0 ≤ i < n-1 | Omits the final element | Reject using a non-empty array with a non-zero last element |
| NC-02 | Sum indices 0 ≤ i ≤ n | Includes an invalid index | Reject as an invalid range / undefined access |
| NC-03 | Require n > 0 | Excludes a valid empty input | Reject as an unjustified precondition |
| NC-04 | Require a particular iteration order | Adds an implementation constraint | Flag over-specification |

## 7. Mutation challenges

| ID | Mutated behavior | Must contract reject? | Reason |
|---|---|---|---|
| MUT-01 | Skip the last element | Yes | Violates the complete-sequence sum |
| MUT-02 | Return zero for every input | Yes | Violates the result equation for suitable inputs |
| MUT-03 | Read one element past the end | Yes | Invalid sequence access; memory safety is also a separate obligation |
| MUT-04 | Traverse right-to-left but sum all elements | No | Same observable mathematical result |

## 8. Boundary scenarios

| Input | Expected result |
|---|---:|
| [] | 0 |
| [7] | 7 |
| [4, -4] | 0 |
| [10, 20, 30] | 60 |
| [5, 0, -2, 9] | 12 |

The [10, 20, 30] case is a useful discriminator: the omitted-last-element mutant returns 30 rather than 60.

## 9. Evaluation rubric

A faithful formalization must quantify over the entire half-open range and define the empty case. It must not encode the loop bound from a candidate implementation as the specification. Check that the model does not silently switch to machine arithmetic or add a non-empty-array precondition.

## 10. Revision history

| Revision | Change | Reason |
|---|---|---|
| 1 | Initial case | Establish the basic off-by-one contract oracle |
