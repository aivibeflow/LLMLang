# Research Scenario 40 — Async Cancellation and Resource Cleanup

**Status:** Evidence-linked comparison; no cancellation or async-cleanup semantics selected
**Research area:** RT-03/04 cancellation, task lifecycle, ownership, and cleanup
**Updated:** 2026-11-19

## 1. Question

When cancellation arrives while a task owns a resource and is awaiting an operation, does cancellation merely request termination, does it stop execution, and does it guarantee that cleanup has completed before the caller observes termination?

Keep these events separate:

1. cancellation requested;
2. task observes the request or its computation is dropped;
3. task reaches a terminal outcome;
4. synchronous cleanup runs;
5. asynchronous cleanup completes;
6. parent/joiner observes completion and any cleanup outcome.

“Canceled” alone cannot stand for all six. A resource-safe contract must state what remains owned or live at every externally observable boundary.

## 2. Official prior-art comparison

### Rust async: dropping a future is cancellation; async destruction remains experimental

Tokio describes cancellation of an async computation as dropping its future. Synchronous `Drop` can release resources held by the future, but it cannot await asynchronous shutdown. Rust's standard library documents `AsyncDrop` and `async_drop_in_place` as nightly-only experimental APIs in the current documentation consulted for this report.

This makes cancellation responsive and deterministic at the future drop boundary, but a future that requires protocol-level asynchronous close/flush needs a separate explicit shutdown protocol or a runtime task that owns and completes that protocol. A dropped future does not prove that a remote peer observed rollback or that buffered output was not partially sent.

Sources: [Tokio tutorial — `select!` cancellation](https://tokio.rs/tokio/tutorial/select#cancellation), [Rust `AsyncDrop`](https://doc.rust-lang.org/stable/std/future/trait.AsyncDrop.html), [Rust async-drop function](https://doc.rust-lang.org/stable/std/future/fn.async_drop_in_place.html).

### Swift: cooperative task cancellation plus a synchronous handler boundary

Swift's `withTaskCancellationHandler` runs its `onCancel` closure when cancellation occurs, even if the operation is executing code that never checks cancellation. If cancellation arrives while the operation is running, the synchronous handler may run concurrently with it; shared state and resource ownership therefore need synchronization. Swift also specifies that `await` cannot appear in a `defer` body. Cancellation signaling and asynchronous cleanup therefore require a separate task/owner and explicit coordination if the caller must wait for cleanup.

Structured task groups add another boundary: the group waits for its child tasks before returning, while signaling cancellation does not interrupt their execution automatically. This is useful for reasoning about parent lifetime, but a child that ignores cancellation can delay group completion.

Sources: [Swift `withTaskCancellationHandler`](https://docs.swift.org/latest/documentation/swift/withtaskcancellationhandler%28operation%3Aoncancel%3A%29/), [Swift await expressions](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/), [Swift task groups](https://docs.swift.org/latest/documentation/swift/taskgroup/).

### Go: cancellation signal and cleanup completion are separate

Go's `context.CancelFunc` tells an operation to abandon work but does not wait for it to stop. The operation must observe `Done()` and return. A deferred `cancel()` releases resources associated with a derived context, but it does not join child goroutines. `context.AfterFunc` runs its callback in its own goroutine, and its stop function does not wait for that callback to complete.

The Go model makes signal propagation explicit and supports cooperative cleanup, but callers need a separate join/acknowledgment protocol when completion matters. Returning after sending a cancel signal is not evidence that the task stopped or released its resources.

Sources: [Go `context` package](https://pkg.go.dev/context), [Go context concurrency patterns](https://go.dev/blog/context).

## 3. Lifecycle comparison

| Runtime model | Cancellation action | Cleanup behavior | Does cancellation call itself imply cleanup completion? | Caller evidence needed |
|---|---|---|---|---|
| Rust future / Tokio | Drop future | Synchronous destructors for values still held by it | No for async shutdown; `AsyncDrop` is experimental | Join/owner protocol or explicit async close result |
| Swift task | Cooperative cancellation state plus optional synchronous handler, potentially concurrent with operation | `defer` is synchronous; handler can run despite unchecked operation | No | Synchronize handler/operation state; await task/group completion and separately await cleanup owner if delegated |
| Go context | Close `Done` signal / cancel context | Goroutine chooses when to return and run defers | No; `CancelFunc` and `AfterFunc` stop do not join work | Wait channel/WaitGroup/other acknowledgment plus resource result |

The mechanisms differ in execution model and cannot be ranked on this table alone. The shared discriminator is whether the caller can establish terminal completion and final resource state, not merely whether a cancellation signal was delivered.

## 4. Shared discriminator fixture

An async `send_then_close(socket, payload)` operation owns a socket and a temporary buffer. Cancellation can arrive at any of these points: before the first write, during a partial write, after the peer receives all bytes but before local acknowledgment, or during asynchronous close/flush.

For each point, record an ordered trace containing `cancel_requested`, bytes sent/acknowledged, task terminal event, cleanup started/completed/result, final local owner, and peer-visible protocol state. Compare four contracts:

- immediate future/task drop with synchronous resource release;
- cooperative cancellation followed by task return;
- cancellation handler delegates cleanup to a separate owner;
- structured scope signals child cancellation and waits for completion.

Falsify a candidate if it reports cancellation completion while required cleanup is still outstanding and has no live owner/join handle; loses or duplicates the socket owner; or claims rollback when bytes may already have reached the peer. `cleanup_pending` is a distinct state from `canceled_and_cleaned`.

## 5. Cross-area implications and follow-up

- **RT-03:** cancellation, divergence, failure, and normal return are different terminal/control outcomes; external effects may already have occurred before cancellation.
- **RT-04:** resource ownership must say whether the task, parent, or cleanup worker owns a resource while async cleanup is pending.
- **RT-10/13:** a runtime must define task scheduling, cancellation observation points, synchronous destructor behavior, async shutdown, and process shutdown ordering.
- **RT-16/20:** cancellation and joins can cross authorization/workspace lifetimes; cleanup that outlives a request must not retain authority accidentally.

Next compare cancellation at each await point against the same event/ownership model as COR-11/12 and COR-13. Include ignored cancellation, repeated cancellation, cleanup failure, caller timeout while joining, and runtime shutdown. Preserve unknown behavior for foreign calls and operations that do not specify cancellation safety. No LLMLang cancellation or cleanup rule is selected.

## 6. References and limits

The sources above are official language/runtime documentation consulted on 2026-11-19. Rust `AsyncDrop` is explicitly experimental; its present API is not a stable-language guarantee. Tokio's cancellation description is runtime guidance, not a Rust language rule. The Go source specifies cooperative cancellation APIs, not a universal runtime cancellation semantic. This is an analytical comparison, not executable cross-runtime evidence.
