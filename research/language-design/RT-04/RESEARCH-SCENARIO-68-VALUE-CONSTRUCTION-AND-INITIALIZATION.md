# Research Scenario 68 — Value Construction and Initialization Invariants

**Status:** Evidence-linked prior-art comparison; no LLMLang construction policy selected  
**Research area:** RT-03 value formation, RT-04 type/resource invariants, RT-09 representation, RT-18 evolution  
**Updated:** 2026-11-19

## 1. Question and scope

How are values created, and when are they considered valid for ordinary use? Separate complete field initialization from defaults/zero values; structural aggregate literals from controlled constructors; object allocation from readiness; fallible initialization from post-construction mutation; and constructor failure from fatal failure. The critical safety property is that no invalid/partially initialized value escapes through `self/this`, callbacks, references, or concurrent publication.

## 2. Prior-art comparison

### Rust: complete aggregate construction, with constructors as ordinary functions

Rust structs can be formed by struct literals when fields are visible; construction requires all fields not supplied through the supported update syntax. The language does not impose a special constructor method; associated functions can establish domain invariants, while private fields can restrict direct construction. This makes defaults explicit and composes with ownership/drop behavior, but API authors must decide which types allow literal construction and which invariants require controlled functions.

Sources: [Rust Book — Defining and Instantiating Structs](https://doc.rust-lang.org/stable/book/ch05-01-defining-structs.html), [Rust Reference — Struct Expressions](https://doc.rust-lang.org/reference/expressions/struct-expr.html), [Rustonomicon — Constructors](https://doc.rust-lang.org/nomicon/constructors.html).

### Go: recursively initialized zero value as a universal creation path

Declared variables and allocated values receive the zero value recursively: numeric zero, false, empty string, nil for reference-bearing categories, and zero-initialized fields/elements for aggregates. This permits creation without explicit constructors and encourages types whose zero values are useful. Invariants that cannot hold at zero need methods/state checks or an explicit constructor convention; the language does not prevent a caller from constructing a struct literal that bypasses that convention.

Sources: [Go Specification — The zero value](https://go.dev/ref/spec#The_zero_value), [Effective Go — Data](https://go.dev/doc/effective_go#data), [Go FAQ — zero values and `new`](https://go.dev/doc/faq).

### Swift: definite initialization and two-phase class construction

Swift value types require stored properties to receive values before initialization completes. Class initialization has two phases: each class initializes the properties it introduces before delegating upward; once all stored properties across the hierarchy are initialized, later customization proceeds. Before phase one completes, the initializer cannot use `self` as an ordinary value, call instance methods, or read instance properties. This prevents use/publication of a partially valid object while supporting inheritance. Failable initializers add an explicit failure path.

Sources: [Swift Language Guide — Initialization](https://docs.swift.org/swift-book/LanguageGuide/Initialization.html), [Swift Declarations — Initializers](https://docs.swift.org/swift-book/ReferenceManual/Declarations.html#Initializers).

### Zig: aggregate literals, comptime defaults, and runtime init functions

Zig allows struct fields to declare default expressions evaluated at compile time, permitting omission of those fields in literals. Its language reference cautions that defaults should not allow the struct's invariants to be violated; if runtime-known data is required, use an initialization method that fills the remaining fields. The distinction makes compile-time defaults convenient but does not replace domain validation. Zig's `undefined` is explicitly not a valid initialized value and may represent arbitrary data, so any use needs a tightly controlled write-before-read discipline.

Sources: [Zig Language Reference — Default Field Values](https://ziglang.org/documentation/master/#Default-Field-Values), [Zig Language Reference — Values / `undefined`](https://ziglang.org/documentation/master/#undefined).

## 3. Candidate policies

| Candidate | Construction model | Trade-offs |
|---|---|---|
| IN-A Complete explicit aggregates | Every field required absent an explicitly declared valid default; constructors are ordinary functions. | Transparent values and easy invariants; verbose construction and deliberate API encapsulation required. |
| IN-B Useful zero/default value | Every type has a recursively initialized default, plus optional constructors. | Simple allocation and low ceremony; many domain types have no valid neutral zero and invalid states are easy to represent. |
| IN-C Controlled construction with definite initialization | All fields must be initialized along every successful path; methods/self use is restricted until complete; constructors may fail. | Strong validity and safe failure boundary; constructor/checker complexity rises for inheritance, recursion, and conditional initialization. |
| IN-D Aggregate plus validated builder | Public aggregate fields/defaults for simple types; explicit builder/finalize API for invariant-bearing types. | Flexible and evolvable; permits invalid intermediate builder states unless the API/type-state model constrains them. |

Cross-cutting axes: public field visibility and literal construction; default-expression phase/purity; partial initialization/drop on failure; move/ownership of initialized fields; recursive and cyclic values; `self` capture/callback/async escape; inheritance/delegation; lazy fields; and whether runtime `undefined`/uninitialized storage is exposed.

## 4. Discriminating experiments

1. Model a type with required fields, optional defaults, cross-field invariant, and runtime validation. Try literal/default/constructor/builder creation and record which invalid values are representable.
2. Add constructors with multiple early returns and injected failures after each field/resource acquisition. Record cleanup, dropped fields, and whether any partial object escapes.
3. Attempt `self` publication to a callback, global, task, or superclass before all fields are valid; test compiler rejection and runtime race outcomes.
4. Add a recursive structure and a mutually dependent field invariant; compare ability to construct a valid root without exposing intermediate invalid states.
5. Change a public field to private/add a field/alter a default. Measure client source compatibility, API hashes, serialization behavior, and migration options.
6. Compare compile-time defaults, runtime constructor checks, debug assertions, and unchecked `undefined` under optimized builds; ensure required validation cannot disappear silently.

## 5. Current result

Prior art offers distinct validity contracts: Go makes every allocation initialized through a recursive zero value; Rust requires structurally complete construction but delegates domain invariants to visibility and ordinary functions; Swift statically enforces definite initialization and restricts partially initialized class `self`; Zig supports compile-time field defaults but warns against defaults that violate invariants and leaves `undefined` as arbitrary data. No LLMLang policy is selected. Useful zero values, fallible constructors, partial-resource cleanup, escape prevention, and API evolution remain open.
