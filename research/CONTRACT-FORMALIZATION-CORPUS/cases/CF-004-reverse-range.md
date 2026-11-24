# CF-004 — Reverse a selected range

**Revision:** 1  
**Status:** Proposed  
**Focus:** State transformation, index mapping, frame conditions, unchanged prefix/suffix.

## 1. Source request

Reverse the elements of the array between the given start and end positions.

## 2. Clarifications

For this case, positions define a half-open range [start,end).

- The range must satisfy 0 ≤ start ≤ end ≤ n.
- Only elements inside the range may change.
- The selected range is reversed in place.
- Elements outside the range remain unchanged.
- An empty or singleton range is valid and leaves the array unchanged.

## 3. Interface and semantic domain

- Input state: finite sequence a, integers start and end.
- Output state: finite sequence b.
- The operation is in-place at the API level; the oracle models observable before/after sequence values.
- Let n = |a|.

## 4. Accepted semantic oracle

Precondition:

\[
0\le start\le end\le n
\]

Postcondition:

\[
|b|=n
\]

\[
\forall i\,(0\le i<start\Rightarrow b_i=a_i)
\land
\forall i\,(end\le i<n\Rightarrow b_i=a_i)
\]

\[
\forall k\,(0\le k<end-start\Rightarrow
b_{start+k}=a_{end-1-k})
\]

This specifies the exact permutation within the selected range and a frame condition outside it.

## 5. Required contract properties

- The interval is half-open.
- The range length and array length are preserved.
- Every selected position receives its mirrored source position.
- Prefix and suffix outside the range are unchanged.
- Empty and singleton ranges are valid.
- No particular swap or temporary-storage strategy is required.

## 6. Negative controls

| ID | Incorrect candidate | Why it is wrong | Expected detection |
|---|---|---|---|
| NC-01 | Reverse [start,end] inclusively | Includes end, outside the selected range | Reject |
| NC-02 | Reverse the entire array | Changes elements outside the requested range | Reject |
| NC-03 | Require start < end | Excludes valid empty ranges | Reject |
| NC-04 | Require pairwise swaps | Prescribes an algorithm, not behavior | Flag over-specification |

## 7. Mutation challenges

| ID | Mutated behavior | Must contract reject? | Reason |
|---|---|---|---|
| MUT-01 | Change element at index end | Yes, when end < n | Violates frame condition |
| MUT-02 | Reverse one extra element | Yes | Violates range mapping |
| MUT-03 | Leave a selected element in its original position when values distinguish positions | Yes | Violates reversal mapping |
| MUT-04 | Produce the exact reversed sequence using a temporary buffer | No | Same observable result |

## 8. Boundary scenarios

For a = [10, 20, 30, 40, 50]:

| Range | Expected result |
|---|---|
| [0, 5) | [50, 40, 30, 20, 10] |
| [1, 4) | [10, 40, 30, 20, 50] |
| [2, 2) | [10, 20, 30, 40, 50] |
| [3, 4) | [10, 20, 30, 40, 50] |

## 9. Evaluation rubric

Check both the modified region and the frame condition. A model that specifies only the final contents of the selected range may permit corruption elsewhere. Check that end is exclusive and empty ranges are admitted.

## 10. Revision history

| Revision | Change | Reason |
|---|---|---|
| 1 | Initial case | Exercise state-transforming contracts and frame conditions |
