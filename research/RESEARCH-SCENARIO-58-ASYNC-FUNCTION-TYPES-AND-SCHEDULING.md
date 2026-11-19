# Research Scenario 58 — Async Function Types and Scheduling

**Status:** Evidence-linked prior-art comparison; no LLMLang async type or execution policy selected  
**Research area:** RT-03 execution semantics, RT-04 effects/types, RT-16 runtime  
**Updated:** 2026-11-19

## 1. Question and scope

What does declaring/calling an asynchronous function mean, when does its body start, how is it scheduled, and what causes actual parallel execution? Keep distinct: (1) async as a function type/effect, (2) call evaluation and eager/lazy start, (3) suspension and resumption, (4) task creation and scheduling, (5) concurrency versus parallelism, and (6) executor/runtime selection. Scenario 40 covers cancellation/cleanup and Scenario 57 task hierarchy; this scenario concerns the boundary between async functions and runnable tasks.

## 2. Prior-art comparison

### Rust: async call constructs a future; polling drives it

The Rust Reference specifies that calling an `async fn` produces a future, and the body runs when that future is polled. Awaiting polls the operand; a pending result suspends the enclosing future until it is woken and polled again. The language defines the future interface and suspension behavior, while an executor/runtime supplies polling and task scheduling. Constructing or awaiting one future alone does not imply parallel execution; explicit spawning and a capable executor are separate.

Sources: [Rust Reference — Functions](https://doc.rust-lang.org/reference/items/functions.html), [Rust Reference — Await expressions](https://doc.rust-lang.org/reference/expressions/await-expr.html), [Rust Future trait](https://doc.rust-lang.org/core/future/trait.Future.html).

### Swift: async is part of function type; concurrency is introduced by task constructs

Swift marks async function types with `async`, and calls must occur in an async context under `await`. The Swift Tour distinguishes a simple awaited call from `async let`, which starts work in parallel with other async code; `Task` starts async work from synchronous code, while task groups structure concurrent children. The reference manual describes `await` as a potential suspension point and says concurrent code does not suspend at other points. Thus async typing/suspension and task creation are distinct language constructs; actual execution placement is a runtime/executor concern.

Sources: [Swift Declarations — Asynchronous functions](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/), [Swift Expressions — Await expressions](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/), [A Swift Tour — Concurrency](https://docs.swift.org/latest/documentation/the-swift-programming-language/guidedtour/), [Swift TaskGroup](https://docs.swift.org/latest/documentation/swift/taskgroup/).

### Go: `go` launches a goroutine; ordinary function types stay synchronous

Go's `go` statement starts a function call as an independent goroutine and does not return a task/future handle. This launch operation is distinct from function declaration and call: a normal call runs synchronously in the current goroutine, while prefixing it with `go` asks the runtime scheduler to execute it independently. Goroutines enable concurrency; CPU parallel execution depends on the problem and runtime resources/configuration, and is not guaranteed merely by launching goroutines.

Sources: [Go specification — Go statements](https://go.dev/ref/spec#Go_statements), [Effective Go — Goroutines](https://go.dev/doc/effective_go#goroutines), [Go FAQ — Goroutine scheduler](https://go.dev/doc/faq#goroutines).

## 3. Option axes and trade-offs

| Axis | Candidate forms | Evidence-derived consequence |
|---|---|---|
| Async declaration/type | A: async is distinct function type/effect; B: ordinary function returning explicit Future/Task; C: ordinary functions with suspension introduced by call context | A makes suspension visible at API boundaries; B exposes the computation value and composition; C reduces declaration syntax but hides suspension contracts. |
| Invocation | L: cold/lazy future starts when polled/awaited; E: call eagerly starts a task; X: call is synchronous unless explicit spawn | L enables composition/cancellation before work begins but can surprise by doing no work; E simplifies fire-and-forget but makes construction effectful; X makes the launch boundary explicit. |
| Suspension | Explicit `await` points vs implicit runtime suspension | Explicit points make reentrancy/interleaving reviewable; implicit suspension reduces syntax but can hide state observation boundaries. Neither alone guarantees fairness or safety. |
| Scheduling | Executor/runtime selected by platform/library vs specified language scheduler | Runtime choice broadens portability and ecosystem integration but varies scheduling guarantees; language scheduler may improve uniformity while constraining deployment and ABI. |
| Parallelism | Async/task semantics guarantee only concurrency; parallelism is runtime/resource dependent vs expose parallel execution guarantees | Guarantees require target/resource assumptions; otherwise parallelism is an implementation/runtime property, not a consequence of `async` or `await`. Go explicitly distinguishes concurrency from parallelism; Swift separately provides `async let` and task APIs for creating concurrent children. |

## 4. Decision-relevant questions and discriminating experiments

1. Does calling an async function execute its body up to the first suspension, create a dormant value, or enqueue a task immediately? Trace observable side effects before and after await.
2. Can a future be dropped before first poll? Can an already-started task be canceled, and which effects/resources have begun? Relate outcomes to Scenario 40.
3. Compare sequential `await f(); await g()` with Swift-like async binding/group launch and Go-like explicit spawn. Record event traces and assert whether each body can begin before its result is awaited; repeat on single-thread and multi-thread runtimes to separate concurrency from parallelism.
4. Test blocking calls inside async functions, executor affinity, fairness, starvation, and wakeup correctness. Define which properties are language-level, runtime contracts, or unspecified.
5. Test async function subtyping/coercion, generic bounds, callback storage, FFI, and diagnostics when async/sync contexts are mixed.

Record exact runtime/tool versions, traces, target parallelism, and cancellation points. Do not infer parallel execution from syntax alone.

## 5. Current result

Prior art establishes materially different separations between function declarations, future construction, task creation, and scheduler participation. This scenario narrows the choice set; it does not select LLMLang syntax, runtime, or scheduling guarantee. Cross-cutting dependencies include task lifetime/supervision (Scenario 57), cancellation/cleanup (Scenario 40), function and closure types (Scenario 56), effects/capabilities (Scenarios 37–38), and ABI/backend choice.
