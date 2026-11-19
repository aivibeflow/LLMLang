# Research Scenario 70 — Type Aliases, Nominal Wrappers, and Opaque Abstractions

**Status:** Evidence-linked prior-art comparison; no LLMLang type identity or representation policy selected  
**Research area:** RT-03 type compatibility, RT-04 types and abstraction, RT-09 interfaces/ABI  
**Updated:** 2026-11-19

## 1. Question and scope

Which declarations merely give an existing type another name, which introduce a distinct nominal identity, and which hide a concrete implementation behind an abstract contract? Separately, can a distinct type promise the same representation or ABI as its underlying value? These axes are often conflated: opaque does not necessarily mean layout-compatible, and a nominal wrapper need not guarantee layout.

## 2. Prior-art comparison

### Rust: aliases, newtype structs, and explicit representation

Rust type aliases introduce another name for an existing type. A tuple or braced struct wrapper instead introduces a distinct nominal type, commonly called the newtype pattern, useful for preventing accidental interchange and attaching traits or APIs. Representation is a separate declaration concern: `repr(transparent)` guarantees the same layout and ABI as the single non-zero-sized field (subject to its constraints); default Rust representation does not provide a stable layout contract. Thus a wrapper can have fresh type identity without promising FFI representation.

Sources: [Rust Reference — Type aliases](https://doc.rust-lang.org/reference/items/type-aliases.html), [The Rust Programming Language — Advanced Types](https://doc.rust-lang.org/book/ch19-04-advanced-types.html), [Rust Reference — Type layout](https://doc.rust-lang.org/reference/type-layout.html).

### Go: alias identity versus a defined type

Go alias declarations bind another spelling to a type and preserve identity. A type definition creates a distinct defined type with the same underlying type; it does not inherit methods of the source type, though conversions and assignability follow explicit specification rules. This cleanly separates a compatibility/migration alias from a domain-specific type. The language's type identity rules do not by themselves establish a general stable ABI guarantee.

Sources: [Go Specification — Type declarations](https://go.dev/ref/spec#Type_declarations), [Go Specification — Type identity](https://go.dev/ref/spec#Type_identity), [Go Specification — Conversions](https://go.dev/ref/spec#Conversions).

### Swift: aliases, nominal value wrappers, and opaque results

Swift `typealias` creates an alternative name, not a new type. A struct wrapper has distinct nominal identity and can establish its own API and invariants. Opaque result types (`some P`) hide a function's concrete result type while preserving a statically known underlying type for that declaration and exposing protocol constraints; they are an abstraction boundary, not simply a representation-transparent wrapper. Public API resilience and ABI stability are related but separately governed concerns.

Sources: [Swift Language Guide — The Basics: Type Aliases](https://docs.swift.org/swift-book/LanguageGuide/TheBasics.html#Type-Aliases), [Swift Language Guide — Opaque and Boxed Protocol Types](https://docs.swift.org/swift-book/LanguageGuide/OpaqueTypes.html), [Swift ABI Stability Manifesto](https://github.com/swiftlang/swift/blob/main/docs/ABIStabilityManifesto.md).

### Zig: aliases, nominal containers, and incomplete opaque types

Zig `const Alias = T` provides another declaration name for the same type. A single-field struct is a distinct container type and can be used as a type-safe wrapper. Zig `opaque` declares a type with unknown size/alignment and no visible fields, commonly used for C types whose layout is unavailable; it is not equivalent to a fully sized value wrapper with private fields. The distinction matters for pointer-only APIs, allocation, and FFI.

Sources: [Zig Language Reference — Containers](https://ziglang.org/documentation/master/#Containers), [Zig Language Reference — opaque](https://ziglang.org/documentation/master/#opaque).

## 3. Candidate policies

| Candidate | Type and abstraction policy | Trade-offs |
|---|---|---|
| TI-A — Alias plus ordinary nominal declarations | Aliases are identity-preserving; records/enums create fresh nominal types. | Small conceptual model; wrapper syntax may be more verbose. |
| TI-B — First-class newtype | Dedicated wrapper declaration creates fresh identity, with explicit construction and projection/conversion rules. | Strong domain separation and invariant boundary; requires clear ergonomics and generic/trait forwarding rules. |
| TI-C — Opaque public type | Public interfaces may expose an abstract identity and operations while hiding fields and implementation. | Supports representation change and encapsulation; complicates separate compilation, construction, serialization, and debugging. |
| TI-D — Independent representation guarantee | A nominal wrapper may separately request transparent layout/ABI under stated structural constraints. | Useful for FFI and zero-cost interop; constrains future representation evolution and target portability. |

The candidates are composable dimensions, not mutually exclusive whole-language choices. Specify alias identity, nominal identity, abstraction visibility, and representation guarantees independently.

## 4. Discriminating experiments

1. Compare alias and wrapper behavior in assignment, overload resolution, generic inference, pattern matching, reflection/type names, and serialization schemas.
2. Attempt to bypass constructor invariants through literals, defaults, deserialization, FFI, unsafe operations, and generic APIs.
3. Change the wrapped representation across separately compiled library versions; record source, binary, and serialized-data compatibility independently.
4. Test transparent wrappers across primitives, zero-sized fields, nested wrappers, alignment, calling conventions, and each target ABI; require explicit evidence for every guarantee.
5. Exercise opaque values in client modules: permitted operations, pointer/value use, allocation/destruction, debug formatting, and dependency invalidation when hidden implementation changes.
6. Measure method/trait/interface forwarding, conversions, optimizer elimination, and whether type identity participates in semantic artifact keys.

## 5. Current result

Aliases, distinct nominal wrappers, hidden implementations, and layout/ABI guarantees solve different problems. Rust, Go, Swift, and Zig each expose useful distinctions but attach different constraints to them. The evidence supports testing the dimensions separately; it does not select a LLMLang design. Cross-module evolution, target ABI behavior, serialization, and invariant enforcement remain open.
