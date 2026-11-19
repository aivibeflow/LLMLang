# Research Scenario 56 — Closure Capture, Callability, and Escape

**Status:** Evidence-linked prior-art comparison; no LLMLang closure/capture model selected  
**Research area:** RT-03 function/value semantics, RT-04 ownership and concurrency, RT-06 dependencies  
**Updated:** 2026-11-19

## 1. Question and scope

How do anonymous/nested functions retain access to surrounding state, and how do capture mode, invocation behavior, and lifetime interact? These are separate choices:

1. Capture by shared reference, mutable reference, copy, or move.
2. Inferred capture versus explicit capture list/mode.
3. Callable cardinality and receiver behavior: reusable immutable, reusable mutable, or consuming/once.
4. Escaping versus nonescaping closure lifetime.
5. Heap/environment allocation and closure identity.
6. Shared mutable cell semantics and concurrency safety.
7. Reference cycles and cleanup/resource lifetime.
8. Closure type, inference, ABI, and function-pointer conversion.

This report compares Rust, Go, and Swift references. It does not assume that one capture policy answers lifetime, ownership, or thread-safety questions.

## 2. Prior-art comparison

### Rust: inferred minimal borrowing/moving, callable traits reflect use

Rust closures infer how each outer variable is captured, preferring shared borrow when possible and using mutable borrow or by-value capture as required by body use. `move` forces captured values to be copied or moved into the closure environment, but a move closure may still implement reusable call traits. Every closure implements `FnOnce`; closures that do not move values out can implement `FnMut`, and those that neither mutate nor move out can implement `Fn`. This encodes whether calls borrow immutably, borrow mutably, or consume the closure.

The model integrates capture and ownership with static callability and lifetime checks. It can produce precise but non-obvious inferred closure types/capture paths; return types and public APIs often need explicit trait bounds or opaque types.

Sources: [Rust Reference — Closure expressions](https://doc.rust-lang.org/reference/expressions/closure-expr.html), [Rust Reference — Closure types and call traits](https://doc.rust-lang.org/reference/types/closure.html).

### Go: closures share captured variables, lifetime extends as needed

Go function literals may refer to variables in a surrounding function. The outer function and closure share those variables, and the variables survive as long as accessible references remain. This gives closures direct access to mutable local state; implementation may extend storage lifetime when the closure outlives the stack frame. The language specifies shared-variable behavior rather than a value-snapshot capture list.

This is compact and intuitive for local callbacks but means mutation is shared and lifetime/aliasing are less visible in source. Concurrency can make shared captures race-prone unless synchronized; loop-variable semantics have also changed by language version to give per-iteration variables in modern Go.

Source: [Go specification — Function literals](https://go.dev/ref/spec#Function_literals).

### Swift: lexical capture with escape annotations and explicit capture lists

Swift closures capture constants and variables from their enclosing scope. Closure parameters can be marked `@escaping` when stored or called after the function returns; nonescaping contexts enable stronger lifetime/access checks. Capture lists explicitly control how values are captured, including value snapshots and weak/unowned class references. Capturing `self` in an escaping closure can form a strong reference cycle, so source-level lifetime intent matters.

This makes escape and some capture behavior part of API/type context and provides syntax for cycle management. It adds annotations and ownership conventions, and inference may depend on whether a function parameter is escaping.

Sources: [Swift Language Guide — Closures and escaping closures](https://docs.swift.org/latest/documentation/the-swift-programming-language/closures/), [Swift Language Reference — Closure expressions](https://docs.swift.org/swift-book/ReferenceManual/Expressions.html#Closure-Expression).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift |
|---|---|---|---|
| Default capture | Inferred borrow/mutable borrow/value as needed | Shared outer variable binding | Lexical capture of outer constants/variables |
| Explicit capture | `move` forces by-value capture | No per-variable capture list | Capture list supports explicit values/weak/unowned |
| Repeated call contract | `Fn`, `FnMut`, `FnOnce` | Function value; no capture-based callable trait lattice | Function type; mutation/access rules and escape context checked |
| Escape/lifetime | Borrow checker proves references valid; move can own environment | Captured variables live as long as accessible | Non-escaping by default for closure parameters; `@escaping` marks extended lifetime |
| Shared mutation | Requires mutable borrow/ownership discipline | Shared variable by language semantics | Captured mutable variable semantics; access exclusivity applies |
| Cycle management | Ownership graph/Arc/Weak patterns | GC reclaims cycles | ARC; `weak`/`unowned` capture choices matter |
| Thread safety | Trait bounds (`Send`/`Sync`) based on captures | Shared state requires synchronization; data races possible | Sendability/concurrency checks can constrain captured values |
| Main cost | Inference and lifetime/type complexity | Hidden aliasing/lifetime and synchronization | Escape annotations, capture lists, ARC-cycle management |

## 4. Discriminating fixtures

1. Capture an immutable scalar, mutate an outer variable, and move an owned resource out; test inferred and explicit modes.
2. Invoke each closure repeatedly, concurrently, and after the outer function returns; record allowed calls and lifetime.
3. Store closures in a field/container, return them, pass them to synchronous callbacks, and pass them to async task APIs.
4. Use nested closures where an inner closure captures a variable used by the outer closure; test capture precision and lifetime shortening.
5. Test value snapshot versus shared mutable cell after outer mutation; document expected observable traces.
6. Build a reference cycle between object and escaping callback; test strong, weak, and unowned capture policies and cleanup timing.
7. Capture a file/socket/lock/task handle and test drop/cleanup when closure is dropped, called once, called repeatedly, canceled, or leaked.
8. Send captured closures across threads/tasks with immutable, mutable, non-sendable, and actor-isolated state.
9. Test loop-created closures across iterations under versioned loop semantics and delayed invocation.
10. Compare closure equality/identity, hashing, serialization, debug output, function-pointer coercion, and ABI representation where relevant.

Record environment layout abstraction, capture edges, callable capability, escape proof/annotation, ownership transfer, allocation, lifetime end, cleanup trace, and concurrency diagnostics.

## 5. Cross-area implications and open hypotheses

- Capture mode and escape lifetime must remain separate. A closure can own copied/moved captures and still escape, or borrow captures and be restricted to a local lifetime.
- Callable cardinality (`Fn`/`FnMut`/`FnOnce`-like) is an API contract for callbacks and tasks, not merely an implementation detail. It affects whether a caller may invoke more than once or retain a closure.
- Shared-variable closures simplify callbacks but create implicit aliasing and synchronization obligations. Snapshot/move capture makes state transfer clearer but can duplicate data or prevent intended shared updates.
- Capture precision affects incremental dependency edges and ownership scope. Capturing one field versus a whole object can change invalidation, borrow conflicts, and retained memory.
- Escape analysis can optimize stack allocation, but a semantic guarantee should not depend on optimizer success. Explicit lifetime annotations improve API clarity at the cost of annotation burden.
- Closure environment destruction is part of resource and cleanup semantics, especially when the closure is dropped without invocation or canceled while queued.
- Reference cycles are possible when closures retain owners and are stored by those owners. Weak/unowned references address different semantics and failure behavior and should not be treated as one generic weak mode.
- Concurrent closures must state whether captured mutable state is shared, isolated, copied, or transferred; runtime scheduling does not make mutation safe by itself.
- Closure identity and ABI matter for semantic hashing, dynamic linking, serialization, and deterministic replay even if surface syntax treats closures as ordinary values.

No LLMLang closure capture default, escape syntax, callable-cardinality type, closure identity, or concurrency-safety rule is selected.

## 6. Next research and falsifiers

Build a bounded closure type/lifetime prototype with immutable and mutable captures, move capture, an escaping callback, and a once-only resource capture. Compare (A) borrow/use-inferred capture with call traits, (B) shared-cell capture and runtime lifetime extension, and (C) explicit capture/escape annotations. Add async sendability and cancellation/drop paths. Measure inference stability under small edits, diagnostics, allocation/lifetime behavior, source boilerplate, ownership correctness, and blind refactor safety.

Implicit shared capture is weakened if callback mutation/escape causes frequent hidden aliasing or concurrency defects. Explicit capture lists are weakened if ordinary callbacks become verbose and edits routinely forget required captures. Callability traits are weakened if users struggle to understand whether callbacks are consumed; a uniform function type is weakened if it cannot express safe once-only or mutable callbacks without dynamic checks.

## 7. Sources and temporal limits

Official references were consulted 2026-11-19. Rust and Swift references are rolling; Go's specification is versioned and loop-variable semantics depend on language version. Record compiler/runtime versions and test allocation/lifetime behavior separately from normative source semantics.
