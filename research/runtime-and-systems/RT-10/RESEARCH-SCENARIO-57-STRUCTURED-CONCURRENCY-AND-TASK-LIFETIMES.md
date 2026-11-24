# Research Scenario 57 — Structured Concurrency and Task Lifetimes

**Status:** Evidence-linked prior-art comparison; no LLMLang task hierarchy or spawn policy selected  
**Research area:** RT-03 concurrency semantics, RT-04 effects/capabilities/ownership, RT-16 runtime safety  
**Updated:** 2026-11-19

## 1. Question and scope

How are concurrent computations created, supervised, canceled, joined, and related to the lifetime of the code that starts them? Keep these independent:

1. Structured child tasks versus unstructured/detached tasks.
2. Parent scope exit behavior: join, cancel-and-join, detach, or error.
3. Cancellation propagation, masking, and cooperative response.
4. Result/error aggregation and ordering.
5. Task-local values, priority, capabilities, and deadline inheritance.
6. Task handle ownership and authority to cancel/join.
7. Scheduler/runtime as language-level or library-level semantics.
8. Resource cleanup when children fail, block, or ignore cancellation.

Scenario 40 compares cancellation and cleanup outcomes; this scenario focuses on task tree structure, scope exit, and supervision policy. It does not recommend one universal model for servers, background daemons, and bounded parallel computations.

## 2. Prior-art comparison

### Swift: structured task groups and `async let` by default within their scope

Swift task groups and `async let` create child tasks whose lifetimes do not exceed the parent scope. The scope waits for all children before returning, even if the body has already selected one result. Cancellation propagates through descendants, but tasks must cooperatively observe it; cancellation is a signal rather than forced termination. Unstructured `Task` and detached tasks are also available and have different inheritance behavior.

This makes ordinary scoped concurrency easier to audit for leaks and resource lifetime, but a slow or cancellation-ignoring child can delay scope exit. Detached tasks remain an escape hatch requiring explicit lifetime/supervision discipline.

Sources: [Swift TaskGroup — Structured concurrency](https://docs.swift.org/latest/documentation/swift/taskgroup/), [Swift Language Guide — Concurrency](https://docs.swift.org/swift-book/LanguageGuide/Concurrency.html), [Swift TaskLocal](https://docs.swift.org/latest/documentation/swift/tasklocal/).

### Go: cheap unstructured goroutine launch; synchronization and cancellation are explicit conventions/APIs

The Go `go` statement starts a function call independently and does not wait for completion; its result values are discarded. The language does not return a task handle. Completion, joining, and cancellation are expressed through channels, `sync.WaitGroup`, and context APIs. Goroutines can outlive the initiating function, and leaks are possible when a goroutine remains blocked without a cancellation or communication path.

This makes concurrent launch concise and leaves lifecycle policy to program structure and libraries. It places the burden on developers to arrange joins and cancellation, and the compiler does not generally enforce that a parent waits for its children.

Sources: [Go specification — Go statements](https://go.dev/ref/spec#Go_statements), [Go Concurrency Patterns: Context](https://go.dev/blog/context), [Go code review comments — Goroutine lifetimes](https://go.dev/wiki/CodeReviewComments#goroutine-lifetimes).

### Rust: structured OS-thread scopes exist; async task supervision is runtime/ecosystem dependent

Rust's standard `thread::scope` allows child threads to borrow non-`'static` data and guarantees outstanding scoped threads are joined before the scope returns. In contrast, a regular `JoinHandle` owns permission to join, and dropping it detaches the thread. Async/await defines futures and suspension syntax, while executors/runtimes and task-spawn APIs coordinate their execution; task-group structure depends on the chosen runtime/library.

This provides a statically enforced structured option for OS threads and permits explicit unstructured ownership where wanted. It also means lifecycle guarantees differ between scoped threads and asynchronous tasks and may not be uniform across runtime ecosystems.

Sources: [Rust std::thread::scope](https://doc.rust-lang.org/std/thread/fn.scope.html), [Rust JoinHandle](https://doc.rust-lang.org/std/thread/struct.JoinHandle.html), [The Rust Programming Language — Async runtimes](https://doc.rust-lang.org/book/ch17-00-async-await.html).

## 3. Comparison matrix

| Dimension | Swift structured tasks | Go goroutines | Rust scoped threads / async runtimes |
|---|---|---|---|
| Spawn surface | Task groups, `async let`, plus unstructured `Task` | `go` statement | `thread::scope`/`spawn`; async executor/library APIs |
| Default parent-child guarantee | Structured APIs join children at scope exit | None in language; explicit sync needed | Scoped threads join; ordinary thread handle drop detaches; async varies by runtime |
| Capturing parent state | Sendability/isolation checks and task semantics | Closures share variables; lifetime extends as needed | Scoped threads borrow; unscoped threads/tasks usually need owned/`'static` values |
| Cancellation | Propagates in task tree; cooperative | Context/channel conventions | Thread cancellation is typically cooperative/user-defined; async runtime-specific |
| Results | Group iteration/async-let values; errors can be thrown | Channels/shared state; goroutine returns discarded | Join handles/results; runtime-specific join/task results |
| Scope-exit latency | Waits for all children; ignoring cancellation can delay exit | Parent can continue/return; children may remain running | Scope waits for scoped threads; detached/unstructured work may outlive scope |
| Main risk | Hidden long wait from structured child | Goroutine leaks and manual lifecycle | Different lifecycle rules across thread and async APIs/runtimes |

## 4. Discriminating fixtures

1. Spawn three children; one succeeds, one errors/panics, one blocks forever; return early from parent and record join/cancel/error behavior.
2. Cancel the parent while children are CPU-bound, awaiting I/O, blocked on a channel, and running cleanup; measure cancellation observation and scope exit.
3. Drop/lose a handle and compare detached execution, automatic cancellation, and enforced join.
4. Capture a stack-local borrowed resource in a child; verify whether the type system prevents escape or scope exit guarantees the borrow ends safely.
5. Add nested child/grandchild scopes and verify cancellation, priority, deadline, task-local context, and capability propagation.
6. Race multiple child failures and specify deterministic versus scheduler-dependent error aggregation and result order.
7. Test an early-result algorithm that returns the first successful child while remaining children are slow, irreversible, or uncooperative.
8. Drop a child-owned file/socket/transaction and aggregate cleanup failure when parent cancellation or sibling failure occurs.
9. Run the same abstract workload through a structured API and a detached API; compare observable traces and leaks.
10. Confirm observability tooling can reconstruct task parentage and explain which scope owns each live task.

Record task tree, spawn authority, result/join state, cancellation cause/timing, cleanup trace, retained resources, sibling failure policy, and source scope that keeps each task alive.

## 5. Cross-area implications and open hypotheses

- Structured concurrency gives a default lifetime invariant: no child outlives its owning scope. It does not guarantee termination, prompt cancellation, deadlock freedom, or bounded runtime.
- Waiting for all children improves resource/accounting correctness but can make “return first result” wait for irrelevant work. A policy must specify whether remaining children are canceled, joined, or detached and how cancellation-unresponsive children affect exit.
- Cancellation and task supervision are different: cancellation requests work to stop; supervision decides what failures do to siblings and parents and how results/errors are collected.
- Unstructured tasks support services, event loops, and background maintenance, but need an explicit supervisor/owner, shutdown hook, and capability budget.
- Task handles are authority-bearing resources. Owning a handle may permit joining, canceling, or detaching; handle copyability and drop behavior should be typed and documented.
- Borrowed captures can be safe when a scope guarantees join; requiring `'static`-like captures is simpler for detached tasks but pushes clones/ownership transfers to callers.
- Inherited task-local context, deadline, priority, and capabilities affect behavior and security. Detached tasks need an explicit inherit/clear policy to avoid ambient-authority leakage.
- Error aggregation must define ordering and precedence under nondeterministic completion; a deterministic language profile may need stable source/spawn order rather than completion order.
- Runtime scheduling is separate from source-level structuredness. The semantics should state guarantees without promising a specific scheduler algorithm unless reproducibility requires it.

No LLMLang default task structure, task handle/drop semantics, cancellation propagation, supervision strategy, or detached-task capability policy is selected.

## 6. Next research and falsifiers

Prototype a small task tree with `scope`, spawn, await/join, cancel, and detach operations. Compare (A) structured-only tasks, (B) structured by default with explicit supervised detach, and (C) unstructured spawn with mandatory task handles. Inject child failures, noncooperative tasks, cancellation at every suspension point, and cleanup failure. Measure orphan/leak rate, early-result latency, task-tree comprehension, deterministic error replay, type/authority complexity, and runtime overhead.

Structured-only tasks are weakened if long-lived service work becomes awkward or uncooperative children can indefinitely block parent scopes. Unstructured tasks are weakened if common control-flow paths lose handles or leak resources. Structured-by-default is weakened if escape policies become more complex than the workloads they support or if the compiler cannot provide actionable supervision diagnostics.

## 7. Sources and temporal limits

Official documentation was consulted 2026-11-19. Swift concurrency and Rust runtime guidance are evolving; Rust async task supervision is library-specific, and Go cancellation is typically built from package APIs. Keep language guarantees separate from library contracts and pin runtime versions in experiments.
