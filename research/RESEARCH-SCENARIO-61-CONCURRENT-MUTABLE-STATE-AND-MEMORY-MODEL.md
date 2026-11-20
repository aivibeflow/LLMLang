# Research Scenario 61 — Concurrent Mutable State and Memory Model

**Status:** Evidence-linked prior-art comparison; no LLMLang concurrency-safety or memory-order model selected  
**Research area:** RT-03 concurrency observations, RT-04 ownership/effects/memory model, RT-10 runtime  
**Updated:** 2026-11-19

## 1. Question and scope

Which concurrent programs may share mutable state, how are conflicting accesses synchronized, and what does the language promise about the resulting observations? Separate: (1) memory data races from higher-level race conditions, (2) ownership transfer from shared access, (3) actor/isolation domains, (4) lock/channel/atomic synchronization, (5) memory order and compiler/CPU reordering, (6) unsafe/foreign escape hatches, and (7) static checking from dynamic race detection. Scenario 57 treats task hierarchy/lifetime; this scenario studies shared-state safety and visibility between tasks.

## 2. Prior-art comparison

### Rust: safe ownership prevents data races; atomics expose memory ordering

Rust's safe type rules prevent data races through ownership/borrowing and thread-transfer/share bounds (`Send`/`Sync`); shared mutable access normally requires synchronization primitives or atomics. A data race in Rust is undefined behavior, but ordinary safe code is designed to make such races impossible; unsafe code can violate those guarantees. Atomics are shareable and each operation takes an explicit ordering that participates in the happens-before relation. The Rust Reference says parts of the overall memory model remain incomplete, a material specification risk for low-level unsafe/compiler work. Rust prevents memory-unsafety from a data race but does not prevent all logical race conditions, deadlocks, or schedule-dependent outcomes.

Sources: [Rustonomicon — Data Races and Race Conditions](https://doc.rust-lang.org/nomicon/races.html), [Rust atomic types — Memory model](https://doc.rust-lang.org/core/sync/atomic/), [Rust Reference — Memory model](https://doc.rust-lang.org/reference/memory-model.html).

### Go: shared memory is allowed; synchronization and DRF-SC define portable outcomes

Go defines reads/writes across goroutines using a formal memory model. A data race is a concurrent write/read or write/write conflict without synchronization, unless all conflicting accesses are atomic. Data-race-free programs have sequentially consistent outcomes (DRF-SC). For programs that do race, Go constrains implementation outcomes more than C/C++'s fully undefined-race approach, while still treating races as errors; its race detector can find races on executed paths. The programming model permits shared mutable memory and makes synchronization APIs and programmer discipline central rather than enforcing exclusive ownership at the type level.

Sources: [Go Memory Model](https://go.dev/ref/mem), [Go Race Detector](https://go.dev/doc/articles/race_detector), [Effective Go — Concurrency](https://go.dev/doc/effective_go#concurrency).

### Swift: isolation and Sendable restrict cross-domain sharing

Swift models concurrent access with actor/global-actor isolation and `Sendable` constraints. Actors serialize access to actor-isolated mutable state; Sendable values can cross concurrency domains without introducing a data-race risk. Types may satisfy Sendable through immutable/value semantics, internal locking, or actor isolation. An `@unchecked Sendable` declaration transfers responsibility to the author and suppresses compiler checking. Swift's concurrency checker can be enabled in stages for migration, and unchecked/legacy interoperability remains a trust boundary. Actor isolation addresses data races, not every logical race: Swift's actor design permits reentrancy when an actor-isolated function suspends, so another operation can run before it resumes; invariants spanning suspension points need their own protocol.

Sources: [Swift Sendable](https://docs.swift.org/latest/documentation/swift/sendable/), [Swift Declarations — Actor isolation](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/), [SE-0306 Actors — Reentrancy](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0306-actors.md), [Swift concurrency migration strategy](https://docs.swift.org/main/documentation/swift-6-concurrency-migration-guide/migrationstrategy/).

## 3. Candidate models and trade-offs

| Candidate | Shared-state rule | Consequences |
|---|---|---|
| C-S Ownership/transfer first | Mutable state is owned by one task/thread at a time; sharing immutable data or synchronized shared handles is explicit. | Strong static prevention and compositional safety; borrowing/transfer rules and FFI boundaries add type-system complexity. |
| C-A Actor/isolation first | Mutable state belongs to an isolation domain; crossing domains requires safe transfer (`Sendable`) or an explicit isolated call. | Makes authority and serialization visible; actor hops, reentrancy, and interop need precise semantics. |
| C-M Shared memory with synchronization | Any reference may be shared; races are errors with a formal DRF-SC guarantee, plus locks/channels/atomics and optional race detection. | Flexible and familiar systems model; safety depends on programmer discipline, dynamic tooling misses unexecuted paths, and the memory model is complex. |
| C-H Hybrid | Safe high-level code uses ownership/isolation; explicit low-level modules can use shared memory under documented unsafe/atomic obligations. | Balances safety and systems access; boundary soundness, capability control, and proof/diagnostic integration become central. |

These are compatible with several behaviors for racy programs: reject statically where provable; define bounded outcomes; make races undefined; or treat them as runtime-detected errors. Define the memory model and compiler contract separately from the ergonomic synchronization API. Define atomic orders (for example relaxed/acquire/release/sequentially consistent), atomicity/width availability, and whether mixed atomic/non-atomic accesses are permitted.

## 4. Discriminating experiments

1. A shared litmus corpus: message publication, store buffering, load buffering, read-modify-write counters, lock release/acquire, channel transfer, and atomic/non-atomic mixed access. Record allowed outcomes on each target and under each optimizer. [Scenario 113](RESEARCH-SCENARIO-113-STORE-BUFFERING-MEMORY-ORDERS.md) now provides the first bounded store-buffering comparison; it remains an abstract profile rather than a complete language model.
2. For static candidates, test aliasing, task capture, mutable borrows crossing spawn, transferred values, actor hops, non-Sendable references, generic APIs, global state, unsafe/unchecked assertions, and FFI callbacks.
3. Distinguish data races from logic races: atomic counter with lost invariant, check-then-act, actor reentrancy across `await`, deadlock, starvation, and cancellation while holding a lock/resource.
4. Compare static acceptance/rejection, diagnostics, race-detector coverage, runtime overhead, and portability; report which bugs each mechanism prevents and which it cannot.
5. Test optimizer litmus results against a formal model or independent reference interpreter. Pin language/compiler version, target architecture, memory-order operations, and sanitizer/runtime.

## 5. Current result

Prior art offers distinct safety centers: exclusive ownership and explicit atomic order (Rust), a specified shared-memory model with DRF-SC plus runtime race detection (Go), and cross-domain isolation/sendability (Swift). These mechanisms solve data races to different degrees and leave logical race conditions in scope. The Rust reference's stated incompleteness, Go's limited guarantees for racy programs, and unchecked/interop escapes in Swift identify different evidence and trust obligations. No LLMLang model is chosen; memory-model completeness, high-level ergonomics, FFI, and backend optimizer conformance remain open.
