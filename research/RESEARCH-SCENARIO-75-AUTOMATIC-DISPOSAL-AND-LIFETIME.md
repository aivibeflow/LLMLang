# Research Scenario 75 — Automatic Disposal and Lifetime

**Status:** Evidence-linked prior-art comparison; no LLMLang automatic-disposal policy selected  
**Research area:** RT-03 scope/termination semantics, RT-04 ownership, RT-09 resource API design  
**Updated:** 2026-11-19

## 1. Question and scope

When does a resource's cleanup action run automatically, and what program construct controls that moment? Separate deterministic scope-exit cleanup from reference-counted object deallocation, garbage-collection cleanup, explicit close/release, async shutdown, and cleanup during fatal termination. Scenarios 35/39 compare cleanup outcomes and fallible release; Scenario 40 covers async cancellation; Scenario 65 covers panic/unwinding. This report isolates lifetime trigger and determinism.

## 2. Prior-art comparison

### Rust: ownership-bound drop scopes

Initialized owned values are dropped when their drop scope exits, in reverse declaration order for locals. Moves transfer the obligation; partially initialized aggregates drop initialized fields. This provides deterministic resource cleanup at scope exit and on unwinding, subject to abort behavior and explicit escape hatches such as `ManuallyDrop`. Drop is synchronous and does not provide an ordinary failure result; code that must observe close failure needs an explicit operation.

Sources: [Rust Reference — Destructors and drop scopes](https://doc.rust-lang.org/reference/destructors.html), [Rust `Drop` trait](https://doc.rust-lang.org/core/ops/trait.Drop.html).

### Zig: explicit lexical `defer`

Zig does not implicitly attach a destructor to each local resource value. `defer` schedules an expression for scope exit; scheduled defer expressions execute in reverse order. `errdefer` runs only on an error return from the block. The programmer makes acquisition/release pairing and success/error cleanup paths explicit, giving lexical predictability without a language-wide ownership destructor mechanism.

Source: [Zig Language Reference — `defer` and `errdefer`](https://ziglang.org/documentation/master/#defer).

### Swift: ARC lifetime for class instances

Swift ARC manages class-instance lifetime from strong references, and a class deinitializer executes immediately before that instance is deallocated. This is not the same trigger as leaving a local lexical scope: retained aliases can keep an instance alive, and a strong reference cycle can prevent deallocation. Lexical cleanup work can instead be registered with `defer`. ARC handles memory lifetime, while deterministic release of scarce external resources still benefits from explicit close/defer patterns and cycle-aware ownership design.

Sources: [Swift Language Guide — Automatic Reference Counting](https://docs.swift.org/swift-book/LanguageGuide/AutomaticReferenceCounting.html), [Swift Language Guide — Deinitialization](https://docs.swift.org/swift-book/LanguageGuide/Deinitialization.html), [Swift Language Guide — Statements (`defer`)](https://docs.swift.org/swift-book/ReferenceManual/Statements.html#Defer-Statement).

### Go: explicit `defer` plus nondeterministic GC cleanup

Go's `defer` runs a call when the surrounding function returns, in last-in-first-out order, including ordinary panic unwinding. This is the deterministic cleanup form. Runtime finalizers and `AddCleanup` callbacks instead run after garbage collection determines that an object is unreachable; their timing is arbitrary and they are not guaranteed to run before program exit or at all. They are fallback mechanisms for associated non-memory resources, not a reliable flush/close contract. `SetFinalizer` also has limitations around cycles; modern documentation recommends `AddCleanup` for many new uses.

Sources: [Go Specification — Defer statements](https://go.dev/ref/spec#Defer_statements), [Go runtime — `AddCleanup` and `SetFinalizer`](https://pkg.go.dev/runtime), [Go GC guide — Finalizers, cleanups, and weak pointers](https://go.dev/doc/gc-guide#Finalizers_cleanups_and_weak_pointers).

## 3. Candidate policies

| Candidate | Automatic disposal trigger | Trade-offs |
|---|---|---|
| AD-A — Ownership-bound destruction | Last ownership obligation is resolved; lexical drop scopes guarantee cleanup for unconsumed owners. | Deterministic and compositional for scarce resources; ownership and drop-order rules add type-checker complexity. |
| AD-B — Explicit scope defers | Only explicitly registered cleanup runs at block/function exit, with defined order. | Simple and visible acquisition/release pairing; easy to forget registration or create control-flow asymmetry. |
| AD-C — ARC plus explicit resource cleanup | Reference-counted memory release when strong references end; external resources use explicit close/defer/with scopes. | Convenient shared object model with clear separation of memory/resource lifetime; cycles and hidden retention delay deinit. |
| AD-D — GC-managed memory plus finalizer fallback | Memory reclamation is automatic; finalizers/cleanups are nondeterministic backup hooks, never required for program correctness. | Low allocation-management burden; unsuitable as the sole contract for file, lock, transaction, or protocol release. |

These policies can combine. In particular, a runtime may use tracing GC for memory and deterministic scope guards for external resources. A `defer` is cleanup scheduling; it does not itself transfer ownership or prove that a resource has one responsible closer.

## 4. Discriminating experiments

1. Acquire nested file/lock/transaction resources; return early, throw/propagate error, break, continue, and move one resource out. Record exactly-once cleanup and order.
2. In an ARC/GC model, retain through aliases and closures, introduce a reference cycle, and force/skip collection; compare memory reclamation with timely external-resource release.
3. Terminate normally, unwind a panic, abort, cancel an async task, and exit the process. Record which cleanup is guaranteed, best-effort, or skipped.
4. Make cleanup reentrant, block forever, panic, or return an error. Define behavior when several cleanups run and when cleanup itself fails during an existing failure.
5. Test async close/shutdown requiring `await`; ensure synchronous destructors do not silently block or launch detached work and specify how parent scopes wait for cleanup.
6. Compare explicit `close`, lexical `defer`, ownership drop, and finalizer fallback for diagnostics when a resource leaks or is used after disposal.

## 5. Current result

“Automatic cleanup” names several distinct lifetime triggers. Rust's owned value drop and Zig/Go lexical defers offer deterministic scope-associated cleanup; Swift ARC deallocation follows strong-reference lifetime and can be delayed by cycles; Go GC cleanups are explicitly not guaranteed to run. Essential external-resource correctness should not depend on nondeterministic finalizers. No LLMLang resource-lifetime policy is selected; exact drop points, async cleanup, cleanup failure, and fatal termination remain separate decisions.
