# Research Scenario 35 — Returning Owned Resources Across Cleanup

**Status:** candidate semantics and discriminator; no rule selected
**Aspect:** RT-03 control flow/resource outcomes × RT-04 ownership/borrowing
**Updated:** 2026-11-19

## Question

When a function returns an owned resource while local scopes still require cleanup, when does ownership move to the caller, which local cleanups run, and what does the caller observe if one of those cleanups fails?

The existing COR-07 resource model treats release failure as an observable `Result`-shaped failure and retains a resource whose release failed. It does not model ownership transfer across function boundaries. Adding `return` without resolving this interaction could silently lose a returned value, leak it on error, or run cleanup twice.

## Candidate fixture

The callee owns `temporary` and `handle`. It prepares to return `handle`, while `temporary` must be released during frame exit. The caller needs either the `handle` or an explicit failure outcome.

```text
function make_handle() -> Result<Owned<Handle>, Error>:
    with_resource temporary = acquire_temp():
        with_resource handle = acquire_handle():
            return transfer(handle)
```

Assumptions for this discriminator:

- `handle` is affine: at most one owner exists at a time.
- `transfer(handle)` consumes the callee's binding; later use or release through that binding is invalid.
- `temporary` is not returned and requires cleanup at function exit.
- `release(temporary)` may succeed or return a cleanup error. This is a model input, not a claim that all destructors are fallible.
- Acquisition and ordinary function evaluation are otherwise successful. Cancellation, panic, aliasing, and async suspension are out of scope here.

## Candidate rules

| Rule | Return and cleanup order | If `temporary` cleanup succeeds | If it fails | Main obligation |
|---|---|---|---|---|
| **R — Reserve, clean, then commit** | Evaluate return expression into a pending owned value; clean remaining locals; transfer the pending value only if cleanup succeeds | Caller receives `Ok(handle)` | Callee must dispose of the pending `handle`; report cleanup failure, aggregating any failure disposing of `handle` | Define cleanup for a value that was evaluated but not committed |
| **T — Transfer, then clean** | Move `handle` to the caller's result slot; then clean remaining locals | Caller receives `Ok(handle)` | Either caller receives the handle alongside a failure, or the protocol needs a second cleanup/rollback channel | Define partial-success result and who owns `handle` when the call reports failure |
| **X — Reject escaping scoped ownership** | Type checker rejects returning a value owned by a local cleanup scope unless it is explicitly detached | An explicit transfer/detach path can return `handle` | Local cleanup failure produces an error with no pending returned resource | Define detach and ensure the returned resource is no longer registered for local cleanup |
| **B — Borrow-only return** | A function may return a borrow only when its owner outlives the caller; a locally acquired `handle` cannot be returned by reference | Return requires an externally owned input or a different owned-result form | No local handle escapes, so only local cleanup failure is observed | Define lifetime/region constraints and keep owned transfer distinct from borrowing |

These alternatives are not exhaustive and are not ranked. Rule R requires cleanup of a pending result; T makes error outcomes potentially carry ownership. A language may instead make destructor failure an unrecoverable runtime fault, but that would change the current COR-07 error model and must be compared explicitly.

## Hand-worked observations

Use the observation tuple `(returned value, terminal outcome, cleanup trace, final owners)`.

| Rule and cleanup result | Returned value | Terminal outcome | Cleanup trace | Final owner of `handle` |
|---|---|---|---|---|
| R, cleanup succeeds | `handle` | `Ok` | `release(temporary): ok` | caller |
| R, cleanup fails; pending-handle cleanup succeeds | none | `Error(CleanupFailed(temporary))` | `release(temporary): error`, then `release(handle): ok` | no owner for `handle`; `temporary` remains a callee cleanup debt |
| R, both cleanups fail | none | error with retained cleanup debts | both failures in specified order | `handle` remains in a pending-return cleanup debt; `temporary` remains a callee cleanup debt |
| T, cleanup succeeds | `handle` | `Ok` | `release(temporary): ok` | caller |
| T, cleanup fails | `handle` plus cleanup failure | partial result (`error_with_value`) | `release(temporary): error` | caller; the result type must encode value and error together |
| X, implicit escape | none | static rejection | no execution | no runtime owner transition; the program is rejected |

The table exposes two independently observable dimensions: the function's result and resource ownership after the call. Checking only `Ok`/`Error`, or only resource events, cannot establish lifecycle correctness.

## Prior-art observations

Rust's Reference specifies that evaluating `return` moves its argument into the call's output location, destroys the activation frame, then transfers control to the caller. Drop scopes specify cleanup as control leaves scopes and define reverse declaration order for locals. This gives a concrete ownership-transfer and cleanup ordering for Rust's rules, but it does not directly settle LLMLang's fallible-cleanup case: Rust destructors are not ordinary `Result`-returning cleanup operations. [Rust Reference: return expressions](https://doc.rust-lang.org/reference/expressions/return-expr.html) · [Rust Reference: destructors and drop scopes](https://doc.rust-lang.org/reference/destructors.html)

Go's specification executes deferred functions before the function returns to its caller, in reverse registration order. Explicit return values are assigned to result parameters before deferred functions run; a deferred closure may modify named result parameters. This shows that result formation and cleanup ordering can interact observably, but Go's rule does not supply affine ownership or this scenario's cleanup-error contract. [Go specification: return and defer](https://go.dev/ref/spec#Return_statements)

These language references illustrate existing design points; their rules are not evidence that LLMLang should adopt either model.

## Proposed discriminator and evidence needed

Implement the candidate rules over the same tiny control/resource fragment and enumerate:

1. cleanup succeeds; transfer succeeds;
2. local cleanup fails; pending-result cleanup succeeds;
3. both local cleanup and pending-result cleanup fail;
4. a branch returns an owned handle while the other returns an error;
5. caller receives the handle and itself exits with an error, to verify exactly one eventual cleanup;
6. a borrow of the local handle is returned instead of ownership.

For every terminal trace, record the return value/error, ordered cleanup events, and owner set. Require no duplicated owner, no silently lost owner, no double release, and no unreported retained resource. Compare the operational model to a separate ownership-obligation projection; then add source/SPG correspondence before treating this as language evidence. Include traces in the RT-03 shared observation model and resource escape/branch rules in the RT-04 checker.

The focused [ownership-obligation projection](../PROTOTYPES/RT-04-01/rt03_return_cleanup.py) executes the reserve/commit and transfer-before-cleanup alternatives for this fixture. Ten focused tests pass. A failed staged cleanup is followed by cleanup of the pending handle; when both fail, the model retains explicit cleanup-debt owners. Transfer-before-cleanup preserves the handle in the caller and therefore yields `error_with_value` if local cleanup fails. The projection also rejects the local-borrow and implicit-escape candidates before execution, checks caller-side release after successful transfer, and handles the alternative error-return branch without transferring the handle.

The unknown-condition structural path fixture forks into two paths: one returns the handle and one returns a domain error. Its cleanup event sets are checked against concrete true/false runs of the RT-03 evaluator and the ownership projection. The shared RT-03 tree uses a literal `handle` sentinel on the first path; the ownership projection separately interprets that path as a transfer. Therefore, this compares cleanup behavior across models but does not prove source-level owned-value correspondence. On the error branch, both resources remain local and unwind in LIFO order. On the handle branch with successful local cleanup, both candidate policies agree on the value and cleanup event. If local cleanup fails, the current evaluator yields `CleanupFailed` without the value, while transfer-before-cleanup yields `error_with_value`; this is a real candidate-semantics discriminator, not a failed equivalence check. The staged policy's follow-up cleanup of the pending returned handle is still outside the evaluator.

In its caller-side cleanup phase, the projection can dispose of the `error_with_value` handle exactly once before propagating the cleanup failure. This exposes an API requirement: a conventional `Result<Owned<Handle>, Error>` cannot encode both an owned value and an error in one branch. The language would need a distinct outcome variant carrying both, or a staged-return contract that prevents the value from reaching the caller and fully defines cleanup of the pending value, including the case where that cleanup fails. The current typed-call experiment supports only `Int`, `Bool`, and `Unit` values and does not test owned values across an actual call.

The RT-04 declaration-checker probe confirms a specific type-envelope gap: Profile B accepts `Result<String, String>`, but reports `UNKNOWN_TYPE` for nested `Result<Owned<Handle>, String>` and for an `ErrorWithValue<Owned<Handle>, String, CleanupError>` descriptor. Three checker probes pass under the current Python 3.9 interpreter; the fourth probe, which imports the Python-3.10+ typed-call evaluator, is skipped because this checkout only exposes Python 3.9. The source signature table confirms that evaluator currently admits only `Int`, `Bool`, and `Unit`. These results establish current prototype boundaries, not that either result constructor is the right LLMLang API.

This is not yet a return-semantics evaluator extension or static checker: transfer rules are encoded by one model and the observations are hand-specified. Only the compatible cleanup portions are cross-checked against the evaluator and path model. The two rejection cases are fixture outcomes rather than borrow-checker proofs. It narrows the next decision: either specify a result type that can carry both a value and cleanup failure, stage the transfer and define rollback cleanup for the pending result, or require explicit detachment/ownership forms.

The strongest decision-changing witnesses are cases 2–4: they distinguish staged commit from transfer-before-cleanup and expose whether an error may carry an owned value. Case 5 checks whether ownership remains exactly-once across the call boundary. If the language instead makes all cleanup infallible by contract, demonstrate that runtime and FFI failures cannot violate that assumption before removing these cases.

## Dependency implications

- **RT-03 → RT-04:** return, errors, and cleanup ordering determine the ownership obligations that the checker must enforce.
- **RT-04 → RT-03:** affine/move rules determine whether the return path leaves a resource to clean and whether a result can carry ownership together with an error.
- **RT-03 → RT-10/13:** runtime and ABI must implement the selected transfer, cleanup, and partial-failure contract.
- **RT-05/06/11:** if cleanup and ownership transfer are observable or affect results, semantic identity and dependency summaries cannot erase those distinctions.

These are concrete dependency hypotheses for this fixture, not a general validation of all corresponding edges.

## Limits and decision gate

This includes an executable fixture projection, but not a complete executable semantics or checker. It does not establish branch-sensitive ownership soundness, borrowing/lifetime inference, async cancellation, destructor panics, actor transfer, FFI behavior, or source/SPG extraction. Do not select a rule or change normative draft semantics based on this scenario alone. Further executable comparison needs to connect the sentinel branch and owner map to a source/SPG call and result type.
