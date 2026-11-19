# Research Scenario 67 — Mutability and Immutability Depth

**Status:** Evidence-linked prior-art comparison; no LLMLang mutability model selected  
**Research area:** RT-03 state semantics, RT-04 aliasing/ownership, RT-06 dependencies, RT-17 diagnostics  
**Updated:** 2026-11-19

## 1. Question and scope

What does it mean for a binding or value to be immutable? Separate (1) rebinding a name, (2) mutating a value directly, (3) mutating through an alias/reference, (4) transitive/deep immutability of reachable data, (5) interior mutability, and (6) compile-time constants. Mutability and concurrency safety are related but distinct: a uniquely accessed mutable object can be race-free, while logically immutable APIs can still hide synchronized state.

## 2. Prior-art comparison

### Rust: immutable bindings/references by default, explicit mutable access, interior mutability exceptions

Bindings are immutable unless declared `mut`; mutable borrows require an appropriate mutable place and exclusive `&mut` access. A shared `&T` normally prevents mutation through that reference and enables compiler assumptions. Interior-mutability types such as `Cell`/`RefCell` deliberately allow mutation through a shared reference, using restricted APIs and, for `RefCell`, runtime borrow checks. Atomic types provide a separate synchronization-aware form. This is a capability/access model with explicit exceptional types, not universal deep constness over every object in the graph.

Sources: [Rust Book — Variables and Mutability](https://doc.rust-lang.org/stable/book/ch03-01-variables-and-mutability.html), [Rust Reference — Interior Mutability](https://doc.rust-lang.org/reference/interior-mutability.html), [Rust `std::cell`](https://doc.rust-lang.org/std/cell/).

### Go: reassignable variables plus compile-time constants; alias mutation remains available

Go `const` declarations represent compile-time constant expressions and are restricted to supported constant values; ordinary mutable aggregate variables use `var`/short declarations. Mutability is not a qualifier that recursively freezes an object. A copied pointer, slice, map, channel, or function value can reference shared state, so another alias may mutate the referent even if a particular binding is not reassigned. The language separates constant expression values from runtime object mutability rather than offering a general deep-const type qualifier.

Sources: [Go Specification — Constant declarations](https://go.dev/ref/spec#Constant_declarations), [Go Specification — Representation of values](https://go.dev/ref/spec#Properties_of_types_and_values), [Go FAQ — Pass by value](https://go.dev/doc/faq#pass_by_value).

### Swift: `let` constrains value instances differently from reference instances

For value types such as structs and enums, a `let` instance cannot have its variable properties changed; this acts across the value's stored properties. For a class instance, `let` makes the reference binding constant, but the referred object's `var` properties may still change. `mutating` marks value-type methods that modify `self`. Thus the practical depth of immutability depends on the type's value/reference category; it does not automatically freeze a reference graph.

Sources: [Swift Language Guide — Properties](https://docs.swift.org/swift-book/LanguageGuide/Properties.html), [Swift Language Guide — Classes and Structures](https://docs.swift.org/swift-book/LanguageGuide/ClassesAndStructures.html), [Swift Protocols — Mutating methods](https://docs.swift.org/swift-book/LanguageGuide/Protocols.html).

### Zig: `const` values and pointer qualification are explicit

Zig distinguishes `const` and `var` declarations and generally recommends `const` where reassignment is unnecessary. Pointer type qualifiers independently determine whether mutation through a pointer is permitted; a pointer binding and the pointed-to object are separate. This exposes alias paths more directly than a deep-const keyword but makes correct lifetime, ownership, and discipline the programmer's responsibility.

Sources: [Zig Language Reference — Pointers](https://ziglang.org/documentation/master/#Pointers), [Zig Language Reference — Variables](https://ziglang.org/documentation/master/#Variables).

## 3. Candidate policies

| Candidate | Meaning of immutable binding/value | Trade-offs |
|---|---|---|
| MU-A Binding-only constness | A binding cannot be reassigned; pointed-to/reachable objects remain mutable through permitted aliases. | Simple and familiar; local `const` does not imply stable observations or deep purity. |
| MU-B Access-capability constness | Mutation requires an explicit mutable binding/reference; shared references block ordinary mutation, with explicit interior-mutability types. | Makes aliasing and mutation capability visible; borrow rules and special cell/atomic APIs add complexity. |
| MU-C Value-category constness | Immutable values are deeply frozen by value semantics; reference types freeze only the reference unless declared otherwise. | Strong local reasoning for value types; behavior depends on value/reference taxonomy and reference graphs. |
| MU-D Deep/transitive immutability qualifier | An immutable type/binding forbids mutation of the full reachable object graph, except declared synchronized cells. | Useful for deterministic reasoning and sharing; hard with cycles, foreign objects, lazy caches, and mutable external state. |

Orthogonal decisions: default mutability; reassignment versus in-place mutation; field-level mutability; interior-mutable APIs and runtime checks; deep versus shallow freeze; mutable method receiver syntax; const propagation through generic types; foreign/unsafe boundaries; and whether immutability is a type property, binding property, or borrow capability.

## 4. Discriminating experiments

1. Build a nested record with immutable binding, mutable fields, a pointer/reference field, shared array/map, and a synchronized cache. Attempt direct mutation, alias mutation, rebinding, and mutation through generic APIs.
2. Separate unique ownership from shared aliasing. Check whether each profile accepts mutation in the unique case and rejects or synchronizes the shared case.
3. Test closures, async capture, actor/task transfer, and FFI handles; report mutation access separately from sendability/data-race checks.
4. Add cyclic graphs, lazy memoization, COW values, and foreign references to test deep-freeze closure, cache behavior, identity, and invalidation.
5. For each rejected mutation, record whether the diagnostic points to the binding, field, alias-creation site, or missing capability; measure edit stability when a type changes from value to reference semantics.
6. Compare optimizer/evidence reuse under mutable aliases, interior-mutability cells, and deep immutable values. Do not infer purity from a local `const` spelling alone.

## 5. Current result

`const` is not a common semantic contract across these languages. Rust emphasizes mutation capabilities and controlled interior mutability; Go's constants are compile-time values while runtime aliases remain mutable; Swift's `let` depth differs for value versus class instances; Zig makes declaration and pointer qualifiers explicit. Binding immutability, object immutability, graph immutability, and race safety should be evaluated as separate axes. No LLMLang policy is selected; deep-freeze behavior, generic propagation, cache exceptions, and foreign boundaries remain open.
