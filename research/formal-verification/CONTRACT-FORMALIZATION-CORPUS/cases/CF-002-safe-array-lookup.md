# CF-002 — Safe array lookup

**Revision:** 1  
**Status:** Proposed  
**Focus:** Index validity, option-valued results, boundary conditions.

## 1. Source request

Implement a function that looks up an element by index and returns no value when the index is outside the array.

## 2. Clarifications

- The input index is a mathematical integer and may be negative.
- An in-range index returns the element at exactly that index.
- An out-of-range index returns an explicit absence value; it does not throw, clamp, or wrap.
- The array is not modified.

## 3. Interface and semantic domain

- Input: finite sequence a, integer i.
- Output: optional value Some(value) or None.
- Let n = |a|.

## 4. Accepted semantic oracle

\[
lookup(a,i) =
\begin{cases}
Some(a_i) & \text{if } 0\le i<n \\
None & \text{otherwise}
\end{cases}
\]

The sequence remains unchanged.

## 5. Required contract properties

- The valid index interval is half-open: 0 ≤ i < n.
- Both negative indices and i = n are invalid.
- A valid lookup returns the element at the requested index, not merely any element with an equal value.
- Invalid lookup returns None.

## 6. Negative controls

| ID | Incorrect candidate | Why it is wrong | Expected detection |
|---|---|---|---|
| NC-01 | Treat i = n as valid | One-past-the-end is not an element index | Reject |
| NC-02 | Require i ≥ 0 but omit i < n | Upper bound is missing | Reject |
| NC-03 | Clamp invalid indices to nearest endpoint | Changes specified absence behavior | Reject |
| NC-04 | Return None for all indices | Under-specifies valid lookup behavior | Reject |

## 7. Mutation challenges

| ID | Mutated behavior | Must contract reject? | Reason |
|---|---|---|---|
| MUT-01 | Read at index n | Yes | Invalid access |
| MUT-02 | Return the last element for index n | Yes | Clamping is not allowed |
| MUT-03 | Return None for a valid index | Yes | Violates exact lookup |
| MUT-04 | Return Some(a_i) for valid i, otherwise None | No | Required behavior |

## 8. Boundary scenarios

For a = [11, 22, 33]:

| Index | Expected result |
|---:|---|
| -1 | None |
| 0 | Some(11) |
| 2 | Some(33) |
| 3 | None |

For an empty array, every integer index returns None.

## 9. Evaluation rubric

Check that the model formalizes both directions of the conditional: valid indices return the exact indexed value, and all invalid indices return absence. The upper bound must be strict. The contract must not hide an out-of-bounds read behind a postcondition that only describes successful calls.

## 10. Revision history

| Revision | Change | Reason |
|---|---|---|
| 1 | Initial case | Exercise strict bounds and explicit invalid-input behavior |
