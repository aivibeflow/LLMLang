# Research Scenario 66 — Copy, Move, and Reference Semantics

**Status:** Evidence-linked prior-art comparison; no LLMLang assignment or parameter policy selected  
**Research area:** RT-03 value/state semantics, RT-04 ownership/aliasing, RT-09 representation, RT-13 ABI  
**Updated:** 2026-11-19

## 1. Question and scope

What does assignment, argument passing, return, and capture do to a value? Separate source-level value semantics from physical copying; ownership transfer from duplication; shallow copies from recursive/deep copies; and references/descriptors from the data they refer to. Aliasing and mutation are the key observations; performance and ABI are separate measurements. This refines the ownership and concurrency studies by comparing ordinary single-threaded value flow.

## 2. Prior-art comparison

### Rust: move by default, `Copy` for trivial duplication, `Clone` when explicit

Assignment and by-value calls move non-`Copy` values; the source place becomes unavailable until reinitialized. `Copy` allows implicit bitwise/trivial duplication for suitable types, while `Clone` is explicit and may execute arbitrary code or duplicate heap data. Borrows pass references without transferring ownership and constrain mutation/access during the borrow. This makes transfer/aliasing statically visible, but generic APIs may need ownership/borrow variants and clone cost can be nontrivial.

Sources: [The Rust Book — What is Ownership?](https://doc.rust-lang.org/stable/book/ch04-01-what-is-ownership.html), [Rust Reference — Move and copy expressions](https://doc.rust-lang.org/reference/expressions.html#move-and-copy-expressions), [Rust `Clone`](https://doc.rust-lang.org/std/clone/trait.Clone.html).

### Go: every parameter and assignment copies the value; reference-bearing values still alias

Go specifies assignment/call passing as copying the stored value. Arrays and structs are self-contained values; pointers, slices, maps, channels, and functions may contain references to shared underlying data, so copying their descriptors does not duplicate the referent. A copied slice header can share an array, while append may allocate and replace only the caller's local header. The rule is simple at the surface but the transitive contents of a value determine whether mutations are visible through aliases.

Sources: [Go Specification — Representation of values and assignments](https://go.dev/ref/spec#Properties_of_types_and_values), [Go FAQ — Everything is passed by value](https://go.dev/doc/faq#pass_by_value), [Go Slices: usage and internals](https://go.dev/blog/slices-intro).

### Swift: value/reference semantics are type-level; copy-on-write preserves value behavior

Structures and enumerations are value types copied on assignment and parameter passing; classes are reference types, so variables share one instance. Standard-library collections and strings can share backing storage until mutation, while preserving value-type isolation (copy-on-write). This separates semantic independence from eager physical duplication. The class/value choice affects identity, mutation visibility, inheritance, and API behavior, not just storage layout.

Sources: [Swift Language Guide — Classes and Structures](https://docs.swift.org/swift-book/LanguageGuide/ClassesAndStructures.html), [Swift Language Guide — Collection Types](https://docs.swift.org/swift-book/LanguageGuide/CollectionTypes.html).

### Zig: values copy; pointer use is explicit

Zig assignments and by-value function parameters work with values; a pointer is an explicit value that provides access to another location, and mutation through one requires the appropriate mutable pointer. Result-location semantics can construct aggregates directly in destination storage, avoiding a temporary physical copy while preserving source-level value rules. This makes address sharing visible but leaves ownership and lifetime discipline largely with the programmer/type conventions.

Sources: [Zig Language Reference — Pointers](https://ziglang.org/documentation/master/#Pointers), [Zig Language Reference — Result Location Semantics](https://ziglang.org/documentation/master/#Result-Location-Semantics), [Zig Language Reference — Values](https://ziglang.org/documentation/master/#Values).

## 3. Candidate policies

| Candidate | Assignment and parameter model | Trade-offs |
|---|---|---|
| CM-A Value copy by default | Assignment/calls create independent value semantics; aggregates may be lowered without physical copies; references are explicit. | Predictable mutation isolation; explicit indirection/ownership is needed for shared mutable state. |
| CM-B Move by default with explicit duplication | Nontrivial values transfer ownership; trivial `Copy`-like types duplicate implicitly; deep/semantic duplication is an explicit operation. | Efficient resource transfer and visible ownership; borrowing/clone decisions add language and API complexity. |
| CM-C Mixed nominal value/reference types | Each type is declared value or reference; copy-on-write may optimize value types. | Familiar value/reference model and selective identity; users must understand category-specific mutation/alias rules. |
| CM-D Uniform descriptor/reference model | Variables copy handles to objects; ownership/lifetime is primarily runtime or convention-managed. | Cheap assignment and flexible graphs; hidden aliasing affects reasoning, equality, concurrency, and reclamation. |

Orthogonal decisions: whether copy is shallow/deep/custom; whether noncopyable types exist; whether move is observable or optimization-only; mutating method and parameter syntax; uniqueness/COW invalidation; reference counting/GC/borrowing; capture and async send rules; and how semantic value identity differs from physical storage identity.

## 4. Discriminating experiments

1. Define nested records containing scalars, arrays, slices, maps, pointers, and mutable resources. Assign, pass, return, capture, and mutate through each alias; compare source-level observations.
2. Add large aggregates, self-referential/cyclic graphs, and resource-bearing values. Record compile-time rejection, moved-from use, deep/shallow duplication, destructor count, and cost separately.
3. Test generic APIs over copyable, movable, borrowed, reference, and noncopyable values; record annotation and overload burden.
4. Exercise COW-like sharing: copy a collection, mutate either side, take addresses/iterators, and test uniqueness invalidation and observable identity.
5. Compare backend lowering and ABI: source value result must remain isolated even if destination passing/NRVO/in-place construction avoids a physical copy.
6. Include async capture and thread transfer, but report data-race/sendability constraints separately from ordinary copy semantics.

## 5. Current result

Prior art exposes at least three axes: source value/reference semantics, ownership transfer/duplication permission, and physical representation/copy elision. Go shows that by-value passing can still preserve aliases through descriptors; Swift shows value semantics can use COW; Rust distinguishes move, trivial copy, explicit clone, and borrow; Zig makes pointers explicit while relying on caller discipline. No LLMLang policy is selected. Nested reference-containing values, noncopyable resources, COW, and ABI-preserving lowering remain open.
