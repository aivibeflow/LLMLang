# COR-13 Follow-up — Typed Ownership Across Calls

**Research area:** RT-03 / RT-04  
**Status:** Planned discriminator; not an accepted ownership or error model  
**Inputs:** [Shared semantics corpus COR-13](RT-03-04-SHARED-SEMANTICS-CORPUS.md), [return/cleanup projection](PROTOTYPES/RT-04-01/rt03_return_cleanup.py), [owned-result checker probes](PROTOTYPES/RT-04-01/test_rt04_owned_result_boundary.py)

## 1. Question

Can a typed call boundary express and check a function that transfers an owned resource while cleanup of a callee-local temporary may fail? If cleanup fails after transfer, what result must the callee return, who owns the transferred value, and can the caller safely continue or must it clean up the value before propagating the error?

The existing projection compares four exit policies: reserve then commit, transfer then cleanup, reject escape, and borrow-only. Its observations are manually constructed for one fixed nested resource scope. The RT-04 checker accepts a primitive `Result` call signature but reports `UNKNOWN_TYPE` for nested `Owned` and `ErrorWithValue` descriptors. The typed-call fragment also rejects the owned result signature. Thus the current evidence does not connect the operational ownership trace to a static caller obligation.

## 2. Competing typed-boundary hypotheses

These are experiment inputs, not a recommendation:

- **H1 — Staged transfer:** ownership remains with the callee until cleanup succeeds. A cleanup failure returns an error without the value, but only if a rule can prove that the callee still has, or successfully released, that value.
- **H2 — Transfer before cleanup:** ownership moves to the caller before local cleanup. If cleanup then fails, return an explicit error-with-value outcome; the caller must handle or dispose of the still-owned value.
- **H3 — No owned return across fallible cleanup:** reject the function or require a cleanup operation whose failure is impossible/handled before returning.
- **H4 — Borrowed return only:** the resource cannot escape the owning scope; useful as a restrictive control.

A candidate is invalid for a fixture if it loses an owned resource, duplicates its owner, permits use after move, leaks a cleanup obligation, or reports success while an observable required cleanup failed.

## 3. Minimal scenario matrix

| Scenario | Callee behavior | Required caller observation/check |
|---|---|---|
| S1 | Acquire temporary and handle; clean temporary; return handle | Caller receives exactly one owner; callee has no residual obligation |
| S2 | Transfer handle; temporary cleanup fails | Either reject statically, or return error-with-value and require one caller cleanup path |
| S3 | Staged return; temporary cleanup fails; handle cleanup succeeds | Error returned with no handle owner; both resources accounted for |
| S4 | Staged return; temporary cleanup and handle cleanup fail | Explicit residual cleanup debt or rejected state; no silent loss |
| S5 | Error branch before transfer; nested cleanup succeeds | Error returned; cleanup order is LIFO |
| S6 | Caller propagates S2 error | The owned value is cleaned or transferred exactly once before propagation |
| S7 | Caller ignores or duplicates S2 value | Static rejection |
| S8 | Branch joins success/error-with-value outcomes | Every path agrees on ownership state or receives an explicit sum type carrying the obligation |

Each case should be run under the selected candidate policies with event traces, final ownership maps, return constructors, and static diagnostics recorded separately.

## 4. Prototype contract

Extend the bounded checker and typed-call harness only enough to express:

- `Owned<T>` as a linear/affine resource-bearing value;
- `Result<T, E>` where ownership obligations are tracked in each variant;
- an explicit `ErrorWithValue<T, E, C>` (or equivalent tagged outcome) for an error plus retained owned value;
- call-site argument/result compatibility and transfer of the ownership obligation;
- branch-sensitive move/use/cleanup checks for the caller;
- cleanup failure as a distinct observable terminal result;
- fail-closed `UNKNOWN` for unsupported aliasing, dynamic dispatch, recursion, or unmodeled cleanup.

The operational harness should consume the same call tree/type descriptors as the checker and produce a trace containing acquire, move/transfer, release attempt/outcome, result tag, returned owner, and outstanding cleanup debt. Do not treat mere descriptor acceptance as proof that the execution trace preserves ownership.

## 5. Acceptance and falsification criteria

A policy passes the bounded prototype only if:

1. each accepted path has at most one owner for each live resource;
2. every resource is either transferred, released, or represented by an explicit outstanding cleanup obligation;
3. a failed cleanup cannot disappear behind a plain error or success value when the policy makes it observable;
4. callers cannot duplicate, use after move, or silently drop an owned result;
5. branch joins preserve compatible ownership states or reject;
6. independent trace oracle agrees on all finite cases in the matrix;
7. rejected and UNKNOWN cases are distinguished from proven-safe cases.

H1 is falsified if the modeled callee cannot account for the pending value after cleanup failure without loss or duplication. H2 is weakened if error-with-value makes common propagation patterns unacceptably complex or cannot be checked path-sensitively. H3/H4 are weakened if representative resource APIs require useful transfer patterns they reject. The experiment does not evaluate general borrowing, alias graphs, asynchronous cancellation, destructors with reentrancy, or concurrent ownership transfer.

## 6. Evidence quality and next step

Use finite exhaustive combinations for the two cleanup-failure flags, both return branches, both caller continuation choices, and each policy. Keep the operational model and checker projection separate, then cross-check them through shared typed fixtures. Record Python/runtime versions, exact commit, command, raw outcomes, and limitations. An independently authored review should inspect the policy table before any result is promoted to the option matrix.

If the prototype yields a stable envelope and caller obligation, update COR-13 and the option matrix. If not, preserve the counterexample and extend the semantic decision rather than generalizing from the existing cleanup projection.

This follow-up is a discriminator for Gate A in [Research State 2026-11-19](RESEARCH-STATE-2026-11-19.md); it does not select a return policy.
