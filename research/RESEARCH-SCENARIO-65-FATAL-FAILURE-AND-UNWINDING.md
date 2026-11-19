# Research Scenario 65 — Fatal Failure, Unwinding, and Process Boundaries

**Status:** Evidence-linked prior-art comparison; no LLMLang fatal-failure policy selected  
**Research area:** RT-03/04 failure semantics, cleanup, resource safety, execution profile  
**Updated:** 2026-11-19

## 1. Question and scope

What happens when execution reaches a condition the program does not treat as recoverable? Distinguish recoverable error values/effects (Scenario 64), assertion failures, language/runtime panic, process abort, undefined/illegal behavior, and external termination. For each, specify stack unwinding, deferred/finalizer cleanup, resource invariants, handler scope, concurrency behavior, diagnostics, and build-profile differences. A process crash does not imply transactions roll back or external I/O is undone.

## 2. Prior-art comparison

### Rust: panic usually unwinds and drops, but can abort

The Rust Book describes panic as an unrecoverable failure distinct from `Result`. By default, panic unwinds the stack and cleans up values; profiles may instead abort immediately, without running destructors. The Reference describes unwind strategy and ABI boundaries, where an unwind crossing a non-unwinding boundary aborts; exact cleanup at that boundary has constraints. Thus panic is not ordinary recoverable error propagation, and cleanup guarantees depend on panic strategy and ABI.

Sources: [Rust Book — Unrecoverable Errors with `panic!`](https://doc.rust-lang.org/stable/book/ch09-01-unrecoverable-errors-with-panic.html), [Rust Reference — Panic](https://doc.rust-lang.org/stable/reference/panic.html), [Rust Reference — Function ABI and unwinding](https://doc.rust-lang.org/reference/items/functions.html).

### Go: goroutine-scoped panic unwinds `defer`; constrained recovery

`panic` stops ordinary control flow and runs deferred functions while unwinding the current goroutine. `recover` only intercepts a panic when called from a deferred function during that goroutine's panic; it resumes normal execution in the recovering function. An uncaught panic reaching the goroutine boundary terminates the program. Go's own guidance treats panic/recover as exceptional within a package and commonly restores an explicit error-valued public API at a boundary. This provides recovery, but recovery scope and goroutine boundaries are semantically important.

Sources: [Go Blog — Defer, Panic, and Recover](https://go.dev/blog/defer-panic-and-recover), [Go Specification — Handling panics](https://go.dev/ref/spec#Handling_panics), [Effective Go — Recover](https://go.dev/doc/effective_go#recover).

### Swift: recoverable throws are separate from assertions and fatal errors

Swift's throwing functions propagate typed or erased errors to `catch`; this is the recoverable channel (Scenario 64). The language guide separately documents `assert`, `precondition`, and `fatalError` for failed assumptions, programmer errors, and unrecoverable termination. Assertions may be omitted in optimized configurations, while preconditions retain a different runtime contract; these are distinct from `throw`. Code must not use a debug-only assertion to enforce input validation or security invariants.

Sources: [Swift Language Guide — Error Handling](https://docs.swift.org/swift-book/LanguageGuide/ErrorHandling.html), [Swift Language Guide — The Basics: Assertions and Preconditions](https://docs.swift.org/swift-book/LanguageGuide/TheBasics.html), [Swift Control Flow](https://docs.swift.org/swift-book/LanguageGuide/ControlFlow.html).

### Zig: safety checks, panic, and unreachable vary by build mode

Zig distinguishes error unions and propagated errors from panic/safety failures. Its reference states that `unreachable` triggers a safety panic by default in Debug and ReleaseSafe, while Fast/Small builds permit the optimizer to assume the path cannot occur. Error-return traces record propagated error paths where enabled, and default trace availability varies by build mode. This puts profile choice directly into failure behavior: an invalid assumption can be a diagnostic trap in one mode and optimizer-dependent illegal behavior in another.

Sources: [Zig Language Reference — `unreachable`](https://ziglang.org/documentation/master/#unreachable), [Zig Language Reference — Safety](https://ziglang.org/documentation/master/#Safety), [Zig Language Reference — Error Return Traces](https://ziglang.org/documentation/master/#Error-Return-Traces).

## 3. Candidate policies

| Candidate | Fatal failure behavior | Trade-offs |
|---|---|---|
| FF-A Always unwind within process | Run registered cleanup and destructors, then terminate the current task/process unless an explicit boundary converts failure. | Better resource cleanup and local diagnostics; runtime cost, cleanup itself can fail/diverge, and external effects remain irreversible. |
| FF-B Always abort | Terminate immediately; no language cleanup guarantee. | Small/simple runtime and avoids inconsistent continuation after invariant failure; loses cleanup and in-process recovery. |
| FF-C Explicit profile strategy | Select unwind/abort at module or executable profile boundary with restrictions on cross-boundary unwinding. | Supports targets with different requirements; builds may differ observably, so profile identity and FFI constraints must be explicit. |
| FF-D No user-catchable panic; isolated task/process boundary | Fatal failure kills only a supervised task/process; supervisor observes a terminal status and may restart. | Fault containment and simple semantics within task; resource ownership, partial external effects, restart loops, and lost diagnostic state need contracts. |

Orthogonal axes: which checks may be removed by optimization; whether bounds/division/assert checks are always-on; cleanup order and double-fault policy; whether panic payloads are typed; handler/recovery scope (function, task, goroutine, process); behavior during cancellation; cross-language ABI rules; and representation of terminal failure in traces/proofs.

## 4. Discriminating experiments

1. Trigger explicit panic, bounds violation, arithmetic trap, assertion, failed precondition, and `unreachable` in debug/optimized/safe builds. Record termination, diagnostic location, and whether observable behavior changes.
2. Install nested cleanup actions that log order, release resources, and fail, then inject a fatal failure. Compare complete, skipped, duplicated, or secondary-failure cleanup under each policy.
3. Trigger failure in a child task/thread/goroutine and test parent/supervisor outcome, sibling cancellation, process survival, restart, and deterministic trace capture.
4. Cross an FFI boundary during unwind; verify permitted propagation, abort behavior, cleanup guarantees, and ABI/profile identity.
5. Introduce partial writes/commits before failure. Verify that termination evidence reports effects already committed and never implies rollback.
6. Measure code size/runtime cost of always-on checks, unwind tables, stack traces, and profile-specific failure paths; retain semantic conformance separately from cost results.

## 5. Current result

The main design distinction is between recoverable failure and invariant/defect failure. Prior art ranges from Rust's configurable unwind/abort, through Go's narrowly scoped `recover`, Swift's separate throws/assert/precondition/fatalError channels, to Zig's safety-mode-sensitive `unreachable`. Build profile, task boundary, and ABI can therefore affect cleanup and terminal observations. No LLMLang behavior is selected; optimization profiles, double-fault cleanup, child-task supervision, and FFI unwind policy remain open.
