# CF-003 — First matching element

**Revision:** 1  
**Status:** Proposed  
**Focus:** Quantification, minimality, optional results, exact index/value relation.

## 1. Source request

Find the index of the first element equal to the target. Return no value if the target does not occur.

## 2. Clarifications

- Search the whole sequence.
- First means the smallest valid index.
- The result is an optional index, not the element value.
- The input sequence is not modified.

## 3. Interface and semantic domain

- Input: finite sequence a, target value t.
- Output: Some(i) or None.
- Let n = |a|.

## 4. Accepted semantic oracle

If the result is Some(i), then:

\[
0\le i<n \land a_i=t \land
\forall j\,(0\le j<i\Rightarrow a_j\ne t)
\]

If the result is None, then:

\[
\forall j\,(0\le j<n\Rightarrow a_j\ne t)
\]

Together these conditions define the smallest matching index when one exists.

## 5. Required contract properties

- A returned index is in bounds.
- The indexed element equals the target.
- No earlier element equals the target.
- None is permitted exactly when no element matches.
- The contract does not prescribe linear search, binary search, or traversal order.

## 6. Negative controls

| ID | Incorrect candidate | Why it is wrong | Expected detection |
|---|---|---|---|
| NC-01 | Return any matching index | Omits the meaning of first | Reject with repeated target values |
| NC-02 | Return index 0 for every non-empty array | Does not establish a match | Reject |
| NC-03 | Require all elements to be distinct | Unrequested input restriction | Reject as over-specification |
| NC-04 | Return the matching value rather than its index | Wrong result meaning | Reject |

## 7. Mutation challenges

| ID | Mutated behavior | Must contract reject? | Reason |
|---|---|---|---|
| MUT-01 | Return a later occurrence | Yes | Violates minimality |
| MUT-02 | Return an index whose element differs from target | Yes | Violates match condition |
| MUT-03 | Return None although a match exists | Yes | Violates completeness |
| MUT-04 | Use another algorithm but return the smallest matching index | No | Implementation is not prescribed |

## 8. Boundary scenarios

| Array | Target | Expected result |
|---|---:|---|
| [] | 5 | None |
| [5] | 5 | Some(0) |
| [1, 5, 5] | 5 | Some(1) |
| [1, 2, 3] | 5 | None |
| [5, 1, 5] | 5 | Some(0) |

## 9. Evaluation rubric

The key discriminator is minimality. A contract that only says the returned index contains the target is too weak. Ensure that the universal quantifier excludes every earlier index and that None is equivalent to absence of a match.

## 10. Revision history

| Revision | Change | Reason |
|---|---|---|
| 1 | Initial case | Distinguish a match from the first match |
