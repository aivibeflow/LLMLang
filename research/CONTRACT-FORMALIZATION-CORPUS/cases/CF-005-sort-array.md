# CF-005 — Sort an array

**Revision:** 1  
**Status:** Proposed  
**Focus:** Conjunction of ordering and permutation, under-/over-specification.

## 1. Source request

Return the input array's elements in non-decreasing order.

## 2. Clarifications

- The output contains exactly the same multiset of elements as the input.
- Equal elements may appear in any relative order; stability is not required.
- The input is not modified.
- The element domain has a total order for this case.

## 3. Interface and semantic domain

- Input: finite sequence a over a totally ordered domain.
- Output: finite sequence b over the same domain.
- The output is a new observable result; aliasing and storage identity are outside this case.

## 4. Accepted semantic oracle

Ordering:

\[
\forall i,j\,(0\le i<j<|b|\Rightarrow b_i\le b_j)
\]

Permutation/multiset preservation:

\[
Multiset(b)=Multiset(a)
\]

Input preservation:

\[
a_{after}=a_{before}
\]

## 5. Required contract properties

- The output is non-decreasing.
- The output preserves every input element with its multiplicity.
- The input remains unchanged.
- Stability is not required.
- The contract does not prescribe a sorting algorithm or complexity bound.

## 6. Negative controls

| ID | Incorrect candidate | Why it is wrong | Expected detection |
|---|---|---|---|
| NC-01 | Require only non-decreasing output | Allows [0,0,0] for any input | Reject as under-specified |
| NC-02 | Require only a permutation | Allows an unsorted output | Reject as under-specified |
| NC-03 | Require stable ordering of equal keys | Stability was explicitly not required | Reject as over-specified |
| NC-04 | Require a specific sorting algorithm | Adds an implementation constraint | Flag over-specification |

## 7. Mutation challenges

| ID | Mutated behavior | Must contract reject? | Reason |
|---|---|---|---|
| MUT-01 | Return an all-zero array | Yes, unless input multiset is all zero | Violates multiset preservation |
| MUT-02 | Return the original unsorted array | Yes, when input is not sorted | Violates ordering |
| MUT-03 | Drop one duplicate | Yes | Violates multiplicity preservation |
| MUT-04 | Return a valid sorted permutation using any algorithm | No | Meets observable contract |
| MUT-05 | Reorder equal elements | No | Stability is not required |

## 8. Boundary scenarios

| Input | Acceptable output |
|---|---|
| [] | [] |
| [4] | [4] |
| [3, 1, 2] | [1, 2, 3] |
| [2, 1, 2] | [1, 2, 2] |
| [-1, 0, -1] | [-1, -1, 0] |

## 9. Evaluation rubric

The contract must express both sortedness and exact multiset preservation. It must not impose stability or a specific algorithm. Confirm that empty and singleton inputs are valid and that the input remains unchanged.

## 10. Revision history

| Revision | Change | Reason |
|---|---|---|
| 1 | Initial case | Detect weak sorting contracts and accidental strengthening |
