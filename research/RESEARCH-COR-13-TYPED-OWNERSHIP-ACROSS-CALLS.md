# COR-13 Follow-up — Typed Ownership Across Calls

**Research area:** RT-03 / RT-04  
**Status:** Executable-policy and checker-boundary comparison; integrated typed call checking remains planned. No ownership or error model is accepted.
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

## 7. Current bounded results

The existing operational policy fixture and checker capability probes were rerun on branch `codex/save-research-state-2026-11-19` at commit `90eb104fee856f20e2fc2c91be7dd570795ae28c` with Python 3.12.14:

```sh
cd research/PROTOTYPES/RT-04-01
python -m unittest discover -s . -p 'test_rt03_return_cleanup.py' -v
python -m unittest discover -s . -p 'test_rt04_owned_result_boundary.py' -v
```

Both commands passed: 10 operational projection tests and 4 checker-boundary tests. In this finite fixture, transfer-before-cleanup returns `error_with_value` when temporary cleanup fails; the caller can release the returned handle exactly once before propagating the error. The reserve/commit alternative instead attempts cleanup of the pending handle and records an explicit cleanup debt if that release also fails. The cleanup event order agrees with the existing recursive evaluator and path model for the covered nested-scope cases.

The integrated static boundary remains open: the existing RT-04 checker accepts primitive `Result<String, String>`, while `Result<Owned<Handle>, String>`, `ErrorWithValue<Owned<Handle>, String, CleanupError>`, and the corresponding typed-call signature are rejected as unknown/unsupported. A separate preliminary caller model now exists in [`rt04_owned_call.py`](PROTOTYPES/RT-04-01/rt04_owned_call.py); it first supported explicit per-outcome action lists and now includes finite caller-supplied CFGs with join-state checks. The initial six action-list fixtures accepted release/transfer and ownership-preserving propagation, rejected ignored/duplicated/multiply-consumed/use-after-move values, and returned `UNKNOWN` for unsupported types or incomplete outcome coverage. This does **not** establish that the main checker or source-level caller obligation is sound: the model does not derive branches from syntax or prove that the supplied output descriptor matches a real caller function. The next executable increment should bind CFG dataflow to the typed call tree and cross-check caller obligations against generated operational traces.

## 8. CFG caller-flow extension

The isolated model now also includes `check_owned_call_cfg`, which propagates one owned-handle state through a caller-supplied finite control-flow graph for each tagged call outcome. It accepts only if every terminal path releases, transfers, or propagates the obligation through an output marked as carrying ownership. At joins, incoming ownership states must agree; use after a terminal action and inconsistent states are rejected. Cycles, unsupported type constructors, malformed CFG envelopes, and incomplete outcome sets fail closed as `UNKNOWN` or invalid input.

The CFG tests cover (1) success carrying a handle and `Result` error carrying none, (2) joins with incompatible ownership, and (3) leaked ownership, use after move, and cycles. A paired fixture also checks transfer-first cleanup against the operational return projection. When caller release succeeds, the returned `error_with_value` handle is released exactly once and the caller CFG accepts. When caller release fails, the operational model retains both the handle and temporary as cleanup debts; the original atomic `release` action still accepts, preserving this counterexample as a regression guard. The CFG also supports `release_attempt` with explicit success and failure successors. Success consumes ownership; failure retains the handle as caller cleanup debt. The failure edge is accepted when the owned value and debt are propagated through the output, and rejected when the debt is dropped.

The next step removes hand-authored block IDs: `check_owned_call_tree` lowers a restricted structured tree of sequences, conditionals, release attempts, and ownership actions into the CFG. A separate bounded `execute_owned_call_tree` runs one path through that same structured input with explicit cleanup and branch results. The paired test sees `released` after successful cleanup and `caller_output_cleanup_debt` after failed cleanup propagated with the owned value, while static analysis accepts both. Additional outcome-tag cases distinguish ordinary `Result` errors, which carry no handle, from `ErrorWithValue` cleanup-error branches, which must account for the still-owned handle. Missing or unrecognized outcome tags fail closed as `UNKNOWN`; these checks establish only the envelope of the isolated model. A separate table-driven trace oracle was added in `rt04_owned_call_oracle.py`; it imports neither checker nor interpreter. Exhaustive enumeration of its bounded tree space covered 154 trees of depth at most two and 9,856 combinations of tree, release and branch inputs, output-carriage flag, and initial ownership. Every path matched the interpreter's status, events, final owner, and findings; a missing release input was separately rejected. This is bounded implementation cross-checking, not independent human review or proof of general semantics. The complete RT-04-01 suite reports 174 passing tests under Python 3.12.14. This shared tree grammar is deliberately **not** the existing RT-03 typed-call AST. That AST currently admits scalar values, calls, `if`, `sequence`, locals and handled integer state; it has no owned-resource type, result-pattern match, release operation, or value-carrying cleanup error. The existing type projection rejects `Owned` and `ErrorWithValue` signatures, so direct source-to-CFG extraction from that AST would require changing its language fragment rather than merely adding a converter. The new tree removes manual CFG construction only within its own research grammar; it does not parse LLMLang source. The oracle and model each handle one abstract handle, not aliases or resource identities, and retrying release is represented as a new explicit transition. Next, obtain an independent review of the outcome contract, then specify minimal source AST nodes and outcome types before claiming source-level coverage.

## 9. Source-level boundary and outcome-shape alternatives

The prototype inspection narrows the source correspondence gap. [`rt03_reference.py`](PROTOTYPES/RT-04-01/rt03_reference.py) already constructs `ok`/`error` results and short-circuits `result_sequence`; its `with_resource` expression records release failure and returns `CleanupFailed`. However, the current resource expression carries a literal resource ID/value rather than binding an owned value usable by the body or return. Separately, [`rt03_typed_calls.py`](PROTOTYPES/RT-04-01/rt03_typed_calls.py) validates and executes only `Int`, `Bool`, and `Unit`; it has calls and scalar conditionals/locals but no result constructors, result matching, owned bindings, or release operation. Thus neither existing AST alone expresses COR-13 end to end.

Candidate minimum control nodes (syntax names below are placeholders):

| Node | Required question it makes explicit | Limitation if omitted |
|---|---|---|
| `with_owned(name, acquire, body, cleanup)` or equivalent owned binder | Which lexical binding owns the acquired resource, and when cleanup runs | A resource ID in a trace is not a value that can be moved or returned |
| `move(name)` or an equally explicit consuming use | At which expression the caller obligation changes owners | A type annotation alone cannot distinguish a borrow/use from transfer |
| exhaustive `match_result` (or general exhaustive `match`) | Which paths carry an owned payload and which error tags are covered | `result_sequence` propagates errors but does not expose caller cleanup choices |
| tagged outcome constructors | Whether a returned value, domain error, cleanup error, or combination is observable | A plain `Result<T,E>` cannot encode an owned `T` on its `Err` path |

These nodes are experiment candidates, not a proposed LLMLang grammar. A general sum-type match may subsume `match_result`; the comparison should measure exhaustiveness and ownership diagnostics rather than assume a special form.

| Outcome shape | Expressive boundary | Open cost or ambiguity |
|---|---|---|
| `Result<Owned<T>, E>` | Success transfers `T`; ordinary error carries no `T` | Cannot represent cleanup failing after `T` has already transferred without losing `T` or adding another channel |
| `ErrorWithValue<Owned<T>, E, C>` | One error tag can carry both a domain error and owned value plus cleanup error | Does not by itself cover cleanup failure after an otherwise successful body; combining two error causes needs an explicit field/precedence rule |
| `CallOutcome<T,E,C>` with `Ok(T)`, `Err(E)`, `CleanupFailed{value:T, cleanup:C}`, and `DomainAndCleanupFailed{value:T, error:E, cleanup:C}` variants | Separately tags success, ordinary error, cleanup-only failure with retained `T`, and combined domain/cleanup failure with retained `T` | More variants and a larger exhaustive-match burden; exact owner in each tag still needs static rules |
| Staged transfer plus ordinary `Result` | Keeps the familiar error-without-value shape if transfer commits after cleanup | Must specify cleanup of the pending return value and the terminal owner when that cleanup also fails |

The minimum distinguishing source cases are: (a) transfer then successful local cleanup; (b) transfer then cleanup failure when the body otherwise succeeds; (c) ordinary domain error before transfer with successful cleanup; (d) a domain error plus cleanup failure after transfer; and (e) caller cleanup success/failure followed by propagation. Each trace must expose returned tag and payload, ordered cleanup events, final owner/debt, and type-check result. Case (d) decides whether one cleanup-specific tag can preserve both error causes or the type needs a more general product payload; case (b) prevents `ErrorWithValue<T,E,C>` from being treated as a complete answer by itself.

No source-level rule is selected here. The following owner/debt table is a draft contract derived from the scenario matrix; it has not had independent human review. After review, extend a separate typed-call projection to derive branch obligations from the AST, run the five cases, and compare it with the operational and table-driven oracles. Until that source-to-obligation link exists, current checker acceptance, the 9,856 path cross-check, and RT-03's cleanup traces remain separate evidence classes.

## 10. Draft owner and cleanup-debt table

This table assumes transfer-before-cleanup for rows that return a value and distinguishes a cleanup failure after an otherwise successful body from one combined with a domain error. It also inherits the prototype's abstract rule that a failed `release_attempt` leaves the resource live. It records the logical owner labels visible in that fixture; it does **not** establish that real resource APIs retain the resource after reporting an error, or who services a debt after a stack frame exits.

| Outcome tag / condition | Owner of returned `T` at call boundary | Other outstanding resource obligation | Caller obligation | Status / unresolved point |
|---|---|---|---|---|
| `Ok(T)`; local cleanup succeeded | Caller owns exactly one `T` | None in the bounded success fixture | Release, transfer, or propagate `T` exactly once | Model-supported candidate; source typing absent |
| `Err(E)`; domain error before transfer and cleanup succeeded | No returned `T` | None | Handle domain error; no owned-value action is valid | Model-supported candidate; aligns ordinary `Result` error branch |
| `CleanupFailedWithValue(T,C)`; body otherwise succeeded, transfer preceded local cleanup, local cleanup failed | Caller owns exactly one `T` | Failed local resource has cleanup debt, labeled `callee_cleanup_debt` in the model | Dispose of or propagate `T`; preserve cleanup failure | Observed in policy projection, but the post-return carrier/responsible agent for the callee debt is unspecified |
| `DomainAndCleanupFailed(T,E,C)`; domain error and post-transfer cleanup failure both occurred | Caller owns exactly one `T` | Failed local resource has cleanup debt | Preserve both errors and handle `T` exactly once | Hypothetical only: current policy fixture has `return_handle` or `return_error`, not an error after transfer; no source constructor or debt carrier exists |
| `CleanupFailed(C)` under staged transfer; pending return handle cleanup succeeded | No returned `T` | Failed temporary remains cleanup debt | Handle cleanup error; caller has no `T` obligation | Policy projection emits plain error/no value; surviving debt carrier unresolved |
| `CleanupFailed(C)` under staged transfer; pending return handle cleanup also failed | No returned `T` | Pending handle and temporary each have cleanup debt | Handle cleanup error and any explicit debt payload | Policy projection retains two debt labels, but the ordinary error tag cannot identify or transfer those obligations |
| `ErrorWithValue(T,E,C)` with caller cleanup succeeds | Caller owns `T` on entry to the branch; none after successful release | Callee-local cleanup debt may still remain | After release, propagate `E` and `C` without `T` | Caller-flow model accepts owned-value consumption; operational fixture supplies cleanup error, not a simultaneous primary domain `E`; callee debt carrier unresolved |
| `ErrorWithValue(T,E,C)` with caller cleanup fails | Caller retains `T` as cleanup debt | Caller-side cleanup debt plus any callee-local debt | Propagate `T` and cleanup debt together or enter another explicit recovery path | CFG model accepts propagation only when the output is marked as carrying ownership; output type/debt encoding remains unspecified |

The table exposes two independent ownership domains: the returned handle and resources whose release failed while leaving the callee. A tagged return that carries only `T` and an error accounts for the former but does not automatically make the latter actionable. Candidate debt carriers include a typed debt payload in the outcome, a runtime cleanup registry, or a rule that rejects/terminates when a debt cannot be transferred; all remain open and need separate runtime/FFI failure experiments. Candidate `C` also needs a cardinality and ordering contract: a nested unwind may produce multiple cleanup errors, while the current type sketch uses a single `C`. A source AST may type-check branches only after these carrier/aggregation rules and the owner set for each tag are fixed.

## 11. Adversarial audit of the draft table

This is a self-audit against the current models, not the independent human review required by the evidence gate.

| Audit question | Evidence in the checkout | Result |
|---|---|---|
| Does ordinary `Err(E)` carry an owned value? | `check_owned_call_tree` seeds the `Result` error path without the handle; the dedicated test allows an empty branch and rejects an ownership action there | No. Treating an error tag as value-carrying would violate the present candidate contract |
| Can `ErrorWithValue(T,E,C)` already represent the combined domain-and-cleanup case? | `rt03_return_cleanup.py` has only `return_handle` and `return_error`; its `error_with_value` is produced for return-handle plus temporary-cleanup failure | Not established. The name covers more than the executable fixture; the combined `E+C+T` case remains hypothetical |
| Is callee cleanup debt discharged by returning `T`? | On transfer-first temporary cleanup failure, the model leaves `temporary: callee_cleanup_debt` while returning `handle` | No. The branch exposes two obligation domains; the model does not assign a post-frame debt carrier or recovery actor |
| Can one `C` carry all failures from nested cleanup? | The return/cleanup projection has one temporary and one handle release flag; the shared RT-03 resource model records nested cleanup errors in order | Unspecified. A scalar error, ordered list, aggregate, or bounded fixed product would differ observably and needs a separate comparison |
| Does the checker derive ownership from source branch patterns? | The caller tree is research-specific; RT-03 typed calls do not admit resource bindings, result matching, or release | No. Static acceptance of the supplied tree is not source-level proof |

This audit narrows the next experiment: the initial cleanup-stack disposition enumerator is recorded in Section 14. It varies cleanup depth and per-resource disposition while recording ordered errors; transfer timing, body outcomes, API-specific close semantics, and debt carriers remain for a later comparison. Keep `DomainAndCleanupFailed` and any generalized `C` encoding explicitly marked as unvalidated until those fixtures and independent review exist.

## 12. Cleanup and fallible-finalization prior art

Official language/runtime documentation presents several different cleanup contracts. These are comparison points, not evidence that LLMLang should copy any one model.

| System | Documented contract | What it contributes to COR-13 | What it does not establish |
|---|---|---|---|
| Rust `Drop` | `Drop::drop(&mut self)` has no result value; the standard library advises destructors to clean up and return normally. `std::fs::File` documents that dropping ignores close errors; `sync_all` is an explicit fallible operation for errors that might otherwise only be caught when the file closes. | Separates implicit destruction from explicit fallible finalization, keeping cleanup reporting in an ordinary call result. | Does not give a generic typed carrier for an error after a resource has already been transferred, or for an outstanding cleanup obligation. [Rust `Drop`](https://doc.rust-lang.org/stable/core/ops/trait.Drop.html), [Rust `File`](https://doc.rust-lang.org/std/fs/struct.File.html) |
| Go `defer` | Deferred calls run LIFO after result parameters are set but before return to the caller. A deferred function's return values are discarded; a closure may mutate named result parameters. | Shows cleanup can alter a pending result, while also making outcome composition depend on mutable named returns and explicit code in the deferred function. | Does not statically track owned payloads or automatically preserve a cleanup error; a returned cleanup error is discarded unless assigned into the named result. [Go specification: defer](https://go.dev/ref/spec#Defer_statements) |
| Zig `defer` / `errdefer` | `defer` runs on block exit; `errdefer` runs only when the block exits with an error. The reference example frees a would-be returned allocation only on error, but leaves it alive on success; a return statement inside a defer expression is forbidden. | Provides a direct error-path rollback pattern and makes the cleanup scope explicit. | The cleanup expression cannot directly replace the enclosing function's result with its own returned error; it must handle or record cleanup failure locally. [Zig language reference: `defer`](https://ziglang.org/documentation/master/#defer), [`errdefer`](https://ziglang.org/documentation/master/#errdefer) |

These mechanisms suggest two design axes that the current type sketches conflate: whether cleanup is automatic or explicitly invoked, and whether its failure changes the function outcome. A language could make implicit cleanup best-effort/infallible while offering an explicit `finish`/`close` operation with a fallible result; alternatively, it could let a scoped handler rewrite the outcome. Each choice still needs a resource-state rule for errors.

## 13. Resource disposition on cleanup error

The Boolean `release_results` input in the isolated ownership tree treats `False` as “release failed and the caller still owns a live resource.” That is valid only for a resource API whose contract promises retention on failure. It is not a portable default. Linux documents that it frees the descriptor early, so non-`EBADF` errors (including `EINTR`) must not be handled by retrying `close`; the error can still report failed/pending I/O, and recovery concerns that side effect rather than a live descriptor. Linux man-pages further report a POSIX.1-2024 `close()` rule that permits `EINTR` with the descriptor remaining open, `EINPROGRESS` with it closed, or success, while Linux keeps its existing behavior. The Open Group page was unavailable to direct retrieval during this pass (403), so this POSIX summary is attributed to Linux man-pages rather than presented as a direct standards quotation. Go's `os.File.Close` contract is at a different abstraction layer: it makes the `File` object unusable for I/O, and its `Fd` documentation warns that a closed descriptor is invalid; it does not provide a generic “retry the raw close” rule. [Linux `close(2)`](https://man7.org/linux/man-pages/man2/close.2.html), [Go `os.File.Close`](https://pkg.go.dev/os#File.Close)

This is a counterexample to a generic “release error preserves owner” rule. A failed cleanup operation may mean a still-live resource, a consumed/closed resource with a failed side effect such as pending I/O, or a platform-dependent/unknown disposition. Those states imply different safe caller actions: retrying, compensating/recovering, and propagating “unknown” cannot share one owned-value edge. This conclusion is an inference from the documented API behavior, not a LLMLang rule.

| Disposition contract a resource API would need to declare | Owner after the operation reports failure | Safe next action shape | Treatment in the current prototype |
|---|---|---|---|
| `retained` | Caller/callee still owns a live resource | Retry or transfer only if the API permits it | Modeled by `release_attempt:error` |
| `consumed` | No live resource handle remains, although the requested finalization/side effect failed | Report or compensate; do not retry close on the old handle | Modeled as an explicit input in the isolated disposition experiments; prior checker still assumes retention |
| `indeterminate` | No ownership claim is proven | Query/reconcile through an API-specific token, or return `UNKNOWN`/terminal failure | Modeled as an explicit input, but no API adapter derives it |

`consumed` may itself need a cleanup-error payload and an obligation to repair data or notify the caller, but that obligation is not resource ownership. The name `cleanup_debt` should therefore not imply that the original handle remains valid. The current model should either be scoped to retained-on-error resource contracts or extended with an API disposition field before being used as generic resource evidence.

For the API-profile comparison, keep the layers explicit: (a) an abstract API may promise retained-on-error; (b) Linux `close(fd)` reports non-`EBADF` errors after descriptor consumption, with an error payload potentially requiring diagnostics or data recovery; (c) POSIX.1-2024's `EINTR` alternatives, as summarized by Linux man-pages, include both a still-open descriptor and a closed descriptor, so a standard-only adapter cannot pick one owner state from `EINTR` alone; and (d) Go `os.File.Close` consumes the Go-level `File` capability by making it unusable, even when returning an error, without promising the raw descriptor state as a portable contract. For Linux `EBADF`, the input descriptor was already invalid rather than newly consumed by this call, so the model must not claim that this call released a live owned resource. These distinctions refine the next discriminator: combine each profile with body outcome, transfer timing, cleanup depth/failure position, and caller recovery policy. Do not permit raw-close retries for consumed or indeterminate states without a profile-specific rule. The experiment still does not derive profiles from a real platform or API call.

## 14. Bounded cleanup-disposition stack experiment

[`rt04_cleanup_disposition.py`](PROTOTYPES/RT-04-01/rt04_cleanup_disposition.py) adds an API-parameterized cleanup-stack model, separate from the owned-call checker. Each resource result is one of `ok`, `retained_error`, `consumed_error`, or `indeterminate`; local resources are attempted in LIFO order. The model also compares `continue` (attempt every outer cleanup after an inner failure) and `stop` (leave the remaining outer resources unattempted).

The focused tests exhaust all disposition vectors at stack depths 1, 2, and 3: `4 + 16 + 64 = 84` vectors for each unwind policy, **168 total paths**. They assert event order, error order, released resources, live retained resources, consumed-with-error resources, indeterminate resources, and resources skipped by stop-on-error. A mixed trace with inner retained, middle consumed, and outer success demonstrates that two cleanup errors can have different ownership effects while remaining in LIFO error order. Under stop-on-error, an inner success followed by a middle consumed-error leaves the outer resource unattempted rather than falsely marking it released.

The cleanup-stack focused suite passes five tests. At that checkpoint the full RT-04-01 suite reported 179 passing tests on Python 3.12.14 (`python -m unittest discover -s . -p 'test_*.py' -v`). The stack experiment takes API dispositions as inputs and does not choose a debt carrier. The prior owned-call tree still assumes retained-on-error and must not be read as covering the `consumed_error` or `indeterminate` cases.

## 15. Call-boundary disposition cross-product

[`rt04_return_disposition.py`](PROTOTYPES/RT-04-01/rt04_return_disposition.py) combines one return handle and one local resource across four valid body/timing shapes: successful body with transfer before cleanup, successful body with staged transfer after cleanup, domain error before transfer, and domain error after transfer. It then applies explicit local and pending-handle dispositions, caller release/propagate/ignore action, caller disposition, and the output-owned flag.

The test enumerates `4 × 4 × 4 × 4 × 4 × 2 = 2,048` input combinations over those four compatible body/timing shapes, four dispositions for local cleanup, pending-handle cleanup, and caller cleanup, four caller actions, and both output-carriage values. The explicit fixtures distinguish (1) transfer-first cleanup error where the local resource is consumed but the handle propagates upstream, (2) staged local retained debt plus a consumed pending handle and no returned value, (3) domain error before transfer with one live debt and one indeterminate resource, and (4) domain error after transfer with a consumed local cleanup error while caller still owns the returned handle.


## 16. API-profile source audit

This audit compared official Go package documentation and source, the POSIX Programmer's Manual pages, and the Linux man-pages project. The Open Group POSIX.1-2024 HTML page for `close()` returned HTTP 403 to the web retriever, so its `EINTR` wording is attributed to the Linux `close(2)` caveat. Linux man-pages 6.19 identifies its behavior: the descriptor is released early and a failed `close()` must not be retried because the number may already have been reused; it also notes divergence from POSIX.1-2024 for `EINTR`. POSIX `closedir()` says the `DIR` pointer may no longer identify an accessible object upon return and an implementation descriptor, if used, shall be closed; the listed errors include `EBADF` and `EINTR`. POSIX `fclose()` requires stream disassociation whether or not the call succeeds, then returns `EOF` on error. The Go `os.File.Close` contract makes `File` unusable for I/O and its `Fd` docs warn against separately closing the returned descriptor. The Go `Root.Close` public contract says methods fail after close; the shared `root_openat.go` implementation marks it closed, ignores the syscall close result, and returns nil (while deferring descriptor closure until active operations finish). Thus an API may report success while suppressing an underlying cleanup failure. The focused profile test and full RT-04-01 suite pass on Python 3.12.14; the full suite has **187 tests** (`python -m unittest discover -s . -p 'test_*.py' -v`). Sources: [Linux `close(2)`](https://man7.org/linux/man-pages/man2/close.2.html), [POSIX `closedir()`](https://man7.org/linux/man-pages/man3/closedir.3p.html), [POSIX `fclose()`](https://man7.org/linux/man-pages/man3/fclose.3p.html), [Go `os.File.Close`](https://pkg.go.dev/os#File.Close), [Go `os.Root.Close`](https://pkg.go.dev/os#Root.Close), [Go root implementation](https://go.dev/src/os/root_openat.go).

| API profile / outcome | Resource-capability state after error | Error's remaining obligation | Retry implication | Prototype mapping |
|---|---|---|---|---|
| Abstract retained-on-error contract | Live owner retained | API-specific retry or transfer | Only if explicitly permitted | `retained_error` |
| Linux `close(fd)`, `EIO`/`ENOSPC`/`EDQUOT`/`EINTR` | Descriptor number already released; no retryable ownership of that descriptor | Diagnose or recover possible pending/failed I/O; consider `fsync` before close when durability checking is needed | Do not retry the same numeric fd | `consumed_error` plus a distinct diagnostic/recovery payload (not implemented) |
| Linux `close(fd)`, `EBADF` | Descriptor was not a valid open descriptor at entry | Diagnose an ownership/API invariant violation; this call did not consume a live descriptor | Do not treat it as retained ownership or as successful release | No exact current state; record as invalid-precondition/unknown until modeled |
| POSIX.1-2024 `close`, `EINTR` | May remain open (`EINTR`), be closed (`EINPROGRESS`), or return success per the Linux man-pages summary | Depends on which alternative occurred; error code alone does not identify one disposition | Cannot choose a portable raw-handle retry policy from `EINTR` alone | `indeterminate` for standard-only knowledge |
| Go `os.File.Close`, error | Go `File` object is unusable; do not treat it as a still-usable capability | Preserve and report `Close` error; underlying I/O failure may need separate recovery | Do not retry I/O through that File; docs do not define retrying an exposed raw fd | Wrapper-level consumed capability plus error payload; not a raw-descriptor mapping |
| Go `os.Root.Close`, `root_openat.go` implementation | Root marked closed; later methods fail | Underlying `syscall.Close` result is discarded by this implementation | No close error reaches the caller; outstanding operation refs defer the syscall close | API-level `ok` can hide an underlying close failure; implementation-specific |
| POSIX `closedir`, error | `dirp` may no longer point to an accessible `DIR`; if `DIR` uses an fd, it shall be closed | Preserve the error; do not rely on the same `DIR*` being usable | Do not retry through the old pointer without a platform-specific contract | `indeterminate` at the stream-pointer layer; the fd rule is stated but failure disposition needs finer modeling |
| POSIX `fclose`, error | `FILE` stream is disassociated from the file whether or not the call succeeds | Preserve the error; buffered output/data recovery is separate | Do not reuse the old `FILE*`; underlying close behavior remains separately relevant | `consumed_error` for the stdio capability, underlying descriptor state separate |

The executable profile inputs are in [`rt04_return_disposition.py`](PROTOTYPES/RT-04-01/rt04_return_disposition.py) as `API_PROFILE_OUTCOMES`; the focused test checks each mapping, both state layers, and its retry flag. This is source interpretation for eight named contracts, not a claim that the implementation recognizes errno values, platform versions, or wrapper state. A consumed language-level capability does not establish that its backing kernel resource was consumed. The Go Root source shows another layer: the public method closes the Root while the platform implementation can suppress an underlying close failure from the caller. The mapping remains research input and is not wired to actual errno handling or the static ownership checker. No feature choice or outcome carrier is promoted by this audit.

## 17. Deferred cleanup error carriers in Go

The Go specification separates execution of a deferred call from propagation of its result. Deferred calls run LIFO after explicit return values have been assigned to named result parameters; values returned by the deferred function are discarded. A deferred closure can still mutate named results. Consequently, direct `defer f.Close()` is an implicit **discard** policy. `defer func() { err = f.Close() }()` unconditionally **overwrites** the named result: a close error replaces the body error, while a successful close can erase a body error by assigning `nil`. A guarded closure, `defer func() { if closeErr := f.Close(); err == nil { err = closeErr } }()`, preserves a primary error and reports close failure only when there was no earlier error. A closure using `errors.Join(err, f.Close())` can expose both, with ordering and nil behavior defined by `errors.Join`. These are source-level semantics, not interchangeable spellings. [Go specification: return statements and `defer`](https://go.dev/ref/spec#Defer_statements), [`errors.Join`](https://pkg.go.dev/errors#Join).

The standard library exhibits both unchecked and checked cleanup paths. `os.ReadFile` uses `defer f.Close()` and returns the read result, so a close error is not added to that result. `os.Root.ReadFile` follows the same pattern. In contrast, `os.Root.WriteFile` explicitly calls `f.Close()` and returns its error when the write did not already fail; this preserves the primary write error if both fail. `archive/zip.Writer.Close` explicitly returns errors while finalizing the archive, and its contract states that it does not close the underlying writer. That `Close` is a fallible finalization operation distinct from releasing the output resource. [Go `os.ReadFile`](https://go.dev/src/os/file.go), [Go `os.Root` methods](https://go.dev/src/os/root.go), [Go `archive/zip.Writer.Close`](https://go.dev/src/archive/zip/writer.go).

[`apply_deferred_error_policy`](PROTOTYPES/RT-04-01/rt04_return_disposition.py) enumerates four abstract carriers—discard, overwrite, preserve-primary, and join—for body and cleanup errors. The focused test exhausts all 16 assignments of those policies across primary-error present/absent and cleanup-error present/absent, including the two-error ordering; the full RT-04-01 suite now has **188 passing tests** on Python 3.12.14. The model does not execute Go or infer policy from syntax; it isolates the choice a language's cleanup construct must make visible. In combination with the API-profile table, the evidence distinguishes two independent questions: whether cleanup changes resource capability state, and whether the cleanup error is observable in the function result. Go permits both ignored and propagated close errors by explicit coding choice; a language-level automatic cleanup rule would need to decide the default and the opt-in escape hatch before a result shape could be selected.

## 18. Explicit close versus implicit destruction in Rust, Zig, and C++

The language and library contracts produce distinct combinations of error visibility and resource state. Rust `std::fs::File` closes when dropped, but `Drop` ignores close errors. The documented fallible operation is `sync_all`, which reports synchronization failure while leaving the file handle open; it is not an explicit fallible close. Thus Rust's standard `File` API does not provide an explicit close result. [Rust `File` documentation](https://doc.rust-lang.org/std/fs/struct.File.html) · [Rust `std::fs` source documentation](https://doc.rust-lang.org/src/std/fs.rs.html).

Zig's current `std.posix.close(fd)` returns `void` and documents that it cannot indicate failure; applications needing to verify writes are directed to call `fsync` before close. The `std.fs.Dir.close` wrapper calls this operation and marks its value undefined afterward. The close error is therefore not exposed and the wrapper capability is consumed. `defer` and `errdefer` describe when cleanup code runs, but do not alter this API's failure surface. These observations refer to the current Zig master source, whose platform branches differ in their underlying close operation. [Zig `std.posix.close`](https://github.com/ziglang/zig/blob/master/lib/std/posix.zig) · [Zig `std.fs.Dir.close`](https://github.com/ziglang/zig/blob/master/lib/std/fs/Dir.zig) · [Zig language reference: `defer`](https://ziglang.org/documentation/master/#defer).

The C++ working draft gives `basic_filebuf::close()` a nullable result. It flushes and performs conversion work, attempts close even if preceding work failed, and returns null on failure; its postcondition is that the file is no longer open. `basic_filebuf` destruction calls `close()` but suppresses an exception from it. The higher-level `basic_ofstream::close()` instead returns `void` and sets `failbit`, which may throw `ios_base::failure` if enabled by the exception mask. The explicit and implicit paths thus both consume the stream capability, while exposing different error channels. [C++ draft: `basic_filebuf` members](https://eel.is/c++draft/filebuf.members) · [C++ draft: `basic_ofstream` members](https://eel.is/c++draft/ofstream.members).

The source-derived [`CLEANUP_SURFACE_PROFILES`](PROTOTYPES/RT-04-01/rt04_return_disposition.py) table records seven surfaces across the three ecosystems; its focused test checks both error channel and capability state independently. The relevant design dimensions are therefore: whether cleanup errors are discarded, returned, or represented through stream state/exceptions; whether the resource capability remains usable, is consumed, or has indeterminate underlying state; and whether synchronization/finalization is a separate operation. Rust's `sync_all` and Zig's `fsync` address synchronization, while C++ stream close includes flushing/conversion. These operations should not be conflated with raw descriptor release. This comparison is source interpretation, not a feature selection or proof that all platform implementations behave identically.
