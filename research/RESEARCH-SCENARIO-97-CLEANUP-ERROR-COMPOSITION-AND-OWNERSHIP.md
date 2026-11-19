# Research Scenario 97 — Cleanup Error Composition and Ownership

**Status:** Evidence-linked comparison and discriminator corpus; no outcome or cleanup policy selected  
**Research areas:** RT-03 core outcomes, RT-04 ownership/effects, RT-08 evidence, RT-18 evolution  
**Updated:** 2026-11-19

## 1. Question and relation to prior work

When a computation is already returning a value, reporting a domain error, being cancelled, exhausting its execution budget, or unwinding after a panic, how should failures from one or more cleanup actions affect the caller-visible outcome? Which resource owner and cleanup obligations survive that composition?

[Scenario 39](RESEARCH-SCENARIO-39-CLEANUP-FAILURE-AND-OWNERSHIP-TRANSFER.md) compares cleanup triggers and owned returns in Zig, Rust, Swift, and Go. [Scenario 36](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) adds fuel exhaustion and bounded cleanup reserves. [COR-13](RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md) shows that transfer-first cleanup failure may require an error-with-owned-value result; [COR-07](RT-03-04-SHARED-SEMANTICS-CORPUS.md) models a bounded nested cleanup-error rule. This scenario isolates a missing cross-cutting axis: the *algebra that composes a primary outcome with ordered secondary cleanup failures*.

This is not one generic “error precedence” choice. Trigger, execution order, failure visibility, primary-cause selection, catchability, and resource capability state can vary independently. The comparison uses documented language/runtime mechanisms to define discriminators; it does not infer a preferred LLMLang rule.

## 2. Prior-art comparison

### Java try-with-resources: preserve a primary exception and suppress close failures

The Java Language Specification says resources initialize left-to-right and close in reverse order. Closing continues if one close action throws. If an initializer, the body, or an earlier close already threw, a later close exception is suppressed on that primary exception. If the body completed normally, the first close exception becomes the thrown outcome and further close failures are suppressed on it. This gives a built-in, ordered secondary-failure channel while preserving a distinguishable primary cause.

Source: [Java Language Specification §14.20.3 — try-with-resources](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-14.html#jls-14.20.3).

### Go defer: LIFO execution is specified; result composition is explicit code

Go specifies that deferred calls execute LIFO immediately before a function returns or while its goroutine is panicking. The return expression assigns result parameters before deferred calls run, and a deferred function may modify named result parameters. The language therefore specifies cleanup timing but does not choose a universal cleanup-error precedence rule: code may discard a close error, overwrite the named result, preserve an earlier error, or explicitly combine errors. Since Go 1.20, [`errors.Join`](https://pkg.go.dev/errors#Join) returns an error wrapping the non-nil input errors, preserving inspectability of multiple causes; it does not automatically make every deferred error part of a function's returned error.

Sources: [Go specification — return statements](https://go.dev/ref/spec#Return_statements) and [defer statements](https://go.dev/ref/spec#Defer_statements); [Go `errors.Join`](https://pkg.go.dev/errors#Join).

### Rust Drop: implicit destruction has no ordinary error result

Rust's `Drop::drop` method returns `()`, so implicit destruction cannot directly return a typed cleanup error through the ordinary function result. The standard-library documentation warns that a destructor may run during unwinding and that a second panic in that situation will likely abort the process. Explicit fallible operations must expose their own result before ordinary drop; destructor panic and recoverable API error are different failure channels.

Sources: [Rust `Drop` documentation](https://doc.rust-lang.org/stable/core/ops/trait.Drop.html) and [Rust Reference — destructors](https://doc.rust-lang.org/reference/destructors.html).

### Swift defer: scope-exit execution has a control-transfer boundary

Swift documents `defer` as scope-exit cleanup and states that statements inside it cannot transfer control outside the defer body. That is a useful boundary for testing whether cleanup failure participates in an in-flight return or throw. The cited rule establishes cleanup control flow, not a general aggregation rule for multiple cleanup failures.

Source: [The Swift Programming Language — Statements](https://docs.swift.org/swift-book/ReferenceManual/Statements.html).

These mechanisms are not interchangeable. Java provides a language-level suppression rule; Go exposes a programmable result boundary; Rust's implicit destructor has no `Result` channel; and Swift's cited defer rule constrains control transfer. Each leaves the resource's post-failure state to its own API contract.

## 3. Independent semantic dimensions

| Dimension | Alternatives to distinguish |
|---|---|
| Cleanup trigger | Always at scope exit; only on error; explicit close; cancellation-specific cleanup; runtime teardown only. |
| Attempt order | LIFO; declaration order; explicit sequence; stop on first failure; continue after failure. |
| Primary outcome | Preserve body/return/cancel/fuel/panic cause; first cleanup error; last cleanup error; aggregate without a distinguished primary. |
| Secondary failure carrier | Ordered suppressed list; flat multi-error; nested `CleanupFailed`; overwrite; discard; abort/trap. |
| Catchability | Domain error; uncatchable cancellation/fuel/runtime fault; panic/unwind; process abort. Do not merge these tags merely because all carry diagnostic data. |
| Ownership state | Caller-owned transferred value; callee-owned pending return; released; consumed-with-error; live cleanup debt; unknown underlying state. |
| Resource state on failed cleanup | Still usable; consumed; indeterminate; runtime-specific. Error aggregation cannot decide this state. |

For each path, record an outcome tuple such as `(primary kind, primary payload, ordered secondary failures, cleanup trace, owner map, resource states, remaining budget)`. Result tags alone do not encode all of these observations.

## 4. Candidate composition vectors

These are mutually distinguishable policies for comparison, not recommendations:

- **P — Preserve-primary with ordered suppression.** Keep the in-flight outcome as primary; append cleanup failures in actual attempt order. Java try-with-resources is a concrete prior-art example for exceptions.
- **A — Flat aggregate with primary identity.** Store a primary cause plus an ordered list of additional causes; consumers can inspect all causes without traversing nested wrappers. Go `errors.Join` shows inspectable multi-cause errors, but selecting the primary and wiring deferred failures remains explicit application policy.
- **N — Nested cleanup wrapping.** Each failure wraps the preceding outcome, as in the bounded COR-07 fixture. This preserves causal nesting but can make the original stop reason harder to inspect.
- **R — Replace with cleanup failure.** A cleanup failure becomes the visible outcome, replacing a pending return or prior error. This is easy to express in a `finally`-like or overwritten named-result pattern, but may hide the original failure and transfer obligation.
- **D — Discard implicit-cleanup failure.** Cleanup is attempted but its failure is not part of the caller-visible result. This can be compatible with infallible/void destructor contracts; it is unsafe as an unstated assumption when cleanup failure is observable or resource state matters.
- **X — Abort on secondary fatal failure.** A panic/trap during already-active unwinding ends ordinary recovery. Rust's documented double-panic behavior motivates testing this boundary; it is not a typed aggregate outcome.

Primary identity and secondary ordering are separate from ownership. Under any vector, transferring a handle before cleanup means the caller remains its owner even if the terminal outcome is an error, cancellation, or fuel exhaustion. A plain `Result<T,E>` cannot express both `E` and an owned `T`; an explicit product/sum envelope or a rule rejecting/staging that transfer is needed.

## 5. Discriminator corpus

Run each fixture in candidate reference semantics with a unique event label per cleanup attempt. Keep cause order and owner maps as separate expected observations.

| ID | Body outcome | Cleanup sequence in execution order | Main discriminator |
|---|---|---|---|
| CLEANUP-OUT-001 | Return scalar | Inner close fails; outer close succeeds | Does cleanup failure replace an otherwise successful return? Does outer cleanup still run? |
| CLEANUP-OUT-002 | Return scalar | Inner and outer close both fail | First, last, nested, flat, or aggregate primary; exact secondary order. |
| CLEANUP-OUT-003 | Domain error `E0` | Inner `E1`, outer `E2` | Preserve `E0` and order `[E1,E2]`, nest, replace, discard, or abort. |
| CLEANUP-OUT-004 | Transfer owned handle, return success | Local temporary cleanup fails | Is caller ownership preserved with the cleanup error, staged, rejected, or lost by a plain error? |
| CLEANUP-OUT-005 | Transfer owned handle, return domain error `E0` | Local cleanup fails `E1` | Require `(E0, E1, owned handle)` or another explicit outcome; verify exactly one owner. |
| CLEANUP-OUT-006 | Pending owned return, staged until cleanup | Local cleanup fails | Does the value remain callee-owned, get disposed, or become a cleanup debt? Is rollback of the pending value fallible? |
| CLEANUP-OUT-007 | Cancellation requested | Two cleanup failures | Preserve cancellation as primary while reporting ordered cleanup causes, or transform it? Is task completion distinct from request? |
| CLEANUP-OUT-008 | Source fuel exhausted | Reserved cleanup runs, one release fails | Preserve `FuelExhausted` and attach cleanup failure, or turn it into a catchable domain error? Preserve prior effects. |
| CLEANUP-OUT-009 | Source fuel exhausted | Cleanup reserve depleted before inner close | Record blocked inner/outer obligations, define whether later frames may be skipped, and retain any transferred owner. |
| CLEANUP-OUT-010 | Panic/unwind active | Cleanup panics or traps | Continue aggregation, replace the panic, or enter abortive behavior; pin runtime profile and unwind boundary. |
| CLEANUP-OUT-011 | Any abrupt body exit | Inner close fails, outer close succeeds | Verify a failed inner close does not implicitly suppress later cleanup unless the candidate says stop-on-failure. |
| CLEANUP-OUT-012 | Any outcome | Close reports failure after consuming or invalidating the resource | Distinguish the error carrier from resource state: usable, consumed, or indeterminate. |

For every accepted path assert: each acquired resource has exactly one owner or an explicit debt/state; no transferred handle is duplicated or silently dropped; the trace records attempted, failed, completed, and blocked cleanup in order; and the primary terminal kind is not silently reclassified. Mark unsupported aliasing, divergence in cleanup, asynchronous release, and unknown resource state as `UNKNOWN` rather than passing them.

## 6. Validation plan, falsifiers, and limits

The corpus is a proposed experiment and has not been run against LLMLang semantics or language compilers. The next bounded prototype should reuse one typed call/resource fixture across an operational trace model and a separate caller-obligation checker, then cross primary outcomes (return, domain error, cancellation, fuel, panic), cleanup success/failure/blocking, return timing, and the six composition policies. Keep the outcome algebra, actual resource state, and ownership checker as separate projections. Exhaustively enumerate the finite subset and independently review the candidate table before updating confidence.

Falsify a policy if it masks a declared primary cause without an explicit rule; loses or duplicates ownership; drops a cleanup failure that its contract says is observable; skips a required outer cleanup after an inner failure; claims cleanup completion when fuel/divergence prevented it; or lets a `Result` handler catch cancellation/fuel/abort without an explicit boundary.

This study does not choose destructor behavior, exception syntax, cancellation guarantees, source-fuel semantics, `ErrorWithValue`, error ordering, or ownership transfer timing. Java's exception suppression is not evidence that its exact carrier is appropriate for cancellation or fuel. Go's join API does not create automatic defer-result propagation. Rust's double-panic abort is runtime behavior, not a model for all fatal failures. Cleanup failure also does not establish whether an underlying OS resource remains open; API-specific state transitions remain necessary.

## 7. References

- [Java Language Specification §14.20.3 — try-with-resources](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-14.html#jls-14.20.3)
- [Go specification — return statements](https://go.dev/ref/spec#Return_statements)
- [Go specification — defer statements](https://go.dev/ref/spec#Defer_statements)
- [Go `errors.Join`](https://pkg.go.dev/errors#Join)
- [Rust `Drop` documentation](https://doc.rust-lang.org/stable/core/ops/trait.Drop.html)
- [Rust Reference — destructors](https://doc.rust-lang.org/reference/destructors.html)
- [Swift Language Reference — Statements](https://docs.swift.org/swift-book/ReferenceManual/Statements.html)
- [LLMLang Scenario 36 — recursion, termination, and fuel](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md)
- [LLMLang Scenario 39 — cleanup failure and ownership transfer](RESEARCH-SCENARIO-39-CLEANUP-FAILURE-AND-OWNERSHIP-TRANSFER.md)
- [COR-13 — typed ownership across calls](RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md)
