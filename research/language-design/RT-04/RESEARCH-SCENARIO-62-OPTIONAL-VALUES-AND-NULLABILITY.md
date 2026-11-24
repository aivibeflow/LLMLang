# Research Scenario 62 — Optional Values and Nullability

**Status:** Evidence-linked prior-art comparison; no LLMLang absence/nullability policy selected  
**Research area:** RT-03 value/error semantics, RT-04 algebraic types and references, RT-13 FFI  
**Updated:** 2026-11-19

**Follow-up:** [Scenario 109](../../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-109-OPTIONAL-PRESENCE-ROUND-TRIP.md) adds a bounded JSON round-trip fixture showing the information loss/preservation choices for omitted, null, and present fields. It does not change this comparison's open status or select an LLMLang policy.

## 1. Question and scope

How is the absence of a value represented, checked, composed, and exposed at API/FFI boundaries? Separate: (1) optional values from nullable pointers, (2) absence from failure and uninitialized state, (3) type-level propagation/checking from runtime null checks, (4) optional nesting and flattening, (5) default initialization, (6) ABI/layout guarantees, and (7) interoperability with null-bearing foreign APIs. Scenarios 41 and 54 cover typed errors and sum-type matching; this study focuses on absence as a value-level contract.

## 2. Prior-art comparison

### Rust: explicit `Option<T>`; references themselves are non-null

Rust represents possible absence with the algebraic type `Option<T>` (`Some(T)` or `None`); an ordinary reference must point to a valid location. Callers must handle or explicitly transform the optional case through matching and combinators. This makes absence visible in signatures for any payload type, not only pointers. For selected payload types Rust specifies niche-based representation guarantees: `Option<T>` can match `T` in size/alignment/ABI, but those guarantees are limited to documented cases and should not be generalized to every `T` or external ABI.

Sources: [The Rust Programming Language — Option and null](https://doc.rust-lang.org/book/ch06-01-defining-an-enum.html), [Rust std::option — Representation](https://doc.rust-lang.org/std/option/).

### Swift: `Optional<T>` syntax and checked unwrapping

Swift's `T?` is syntactic sugar for `Optional<T>`, which can contain a wrapped value or `nil`. `nil` represents absence of a value of the optional's type; it is not restricted to pointers. Optional binding, pattern matching, chaining, and coalescing provide structured propagation. Swift also has implicitly unwrapped optionals (`T!`) that permit implicit access and can fail at runtime if `nil`; documentation reserves these for particular initialization/interoperability patterns and advises ordinary optionals for values that may become nil during normal lifetime.

Sources: [Swift Language Guide — Optionals](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/), [Swift Types — Optional types](https://docs.swift.org/latest/documentation/the-swift-programming-language/types/), [Swift Optional Chaining](https://docs.swift.org/latest/documentation/the-swift-programming-language/optionalchaining/).

### Go: typed nil is the zero value for reference-bearing type categories

Go's predeclared `nil` is a zero value for pointers, channels, functions, interfaces, maps, and slices—not for arbitrary `T`. Different nil-capable types have different operational meanings (for example, nil channels block; nil maps can be read but not written; nil functions panic when called). Interface values also combine a dynamic type and dynamic value, so an interface containing a typed nil pointer is itself non-nil. The broad built-in nil accommodates idiomatic zero initialization but creates type-specific behavior and traps at generic/interface boundaries.

Sources: [Go specification — The zero value](https://go.dev/ref/spec#The_zero_value), [Go specification — Interface types](https://go.dev/ref/spec#Interface_types), [Go FAQ — Why is my nil error value not equal to nil?](https://go.dev/doc/faq#nil_error).

### Zig: explicit optional type with explicit unwrap/fallback operators

Zig spells an optional as `?T`; an optional may contain a `T` or `null`. The language provides explicit unwrap (`.?`) and fallback/control-flow (`orelse`) operations. `orelse` extracts a non-optional value on the continuing path or executes a chosen alternative/early return. This keeps the optional boundary and the handling branch visible. The language reference demonstrates optionals at C interop boundaries, such as an allocator returning a nullable pointer; representation depends on the payload/type and target, so do not assume every optional is ABI-equivalent to a nullable pointer.

Source: [Zig Language Reference — Optionals](https://ziglang.org/documentation/master/#Optionals).

## 3. Candidate models and trade-offs

| Candidate | Model | Benefits | Costs/risks |
|---|---|---|---|
| N-A Algebraic optional for every payload | `Option<T>`/`Optional<T>` is a distinct sum type; no nullable references. | Absence visible and uniformly matchable; nested absence is representable. | More syntax/constructors; foreign null pointers require explicit conversion; layout needs stated ABI policy. |
| N-B Nullable reference types plus optional value types | References may be `T?`; non-reference values use `Option<T>` or dedicated nullable forms. | Maps naturally to object-oriented and C APIs; pointer-specific optimization. | Two concepts/operators/checking rules; nullability metadata and erased/legacy boundaries complicate guarantees. |
| N-C Typed null for nil-capable categories | A universal-looking `nil` is accepted for a defined set of pointer/container/callable types. | Convenient zero initialization and foreign API mapping. | Meaning depends on type; typed nil/interface ambiguity and operations on nil values require special rules. |
| N-D Explicit `Nullable<T>` separate from `Result<T,E>` | Absence and failure are separate algebraic cases; APIs may combine them explicitly. | Prevents conflating “not found” with “failed”; exhaustive handling composes. | Nested layers can be verbose; convenience propagation must preserve which case occurred. |

Regardless of candidate, specify: optional-of-optional representation; equality/order/hash behavior; default value policy; forced-unwrap behavior; propagation/flattening rules; serialization; and C/Objective-C/LLVM ABI conversion. A missing database row, a field omitted from input, an explicit JSON `null`, an uninitialized local, and a failed lookup are not necessarily the same semantic case.

## 4. Discriminating experiments

1. Compile matched APIs for optional integer, pointer, function, enum, generic payload, and nested optional values. Record type inference, exhaustive match diagnostics, default initialization, and unwrap behavior.
2. For Go-like nil categories, test every operation on nil map/slice/channel/function/interface and typed nil through interfaces, generics, error returns, reflection, and equality.
3. For Rust/Swift/Zig-style optional sums, test `Option<Option<T>>`, map/and_then/flatten, optional chaining, coalescing, and error combinations to ensure absent-vs-failure cases remain distinguishable.
4. Measure layouts and call ABI only for declared targets and payloads; probe C pointer arguments/returns, sentinel encodings, nullable annotations, and serialization/JSON presence/null distinctions.
5. Compare API evolution when an always-present field becomes optional, when absence is added to a return type, and when an existing null sentinel is replaced by a tagged type. Track source compatibility, ABI, schema, and diagnostics separately.

## 5. Current result

Prior art distinguishes tagged optional values, nullable references, and category-specific nil zero values. It also shows that representation optimization is payload- and ABI-specific, and that “no value,” “not initialized,” and “operation failed” need not be interchangeable. LLMLang still needs an explicit absence model and foreign-boundary rules; no candidate is selected.
