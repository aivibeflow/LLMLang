# Research Scenario 63 — Equality, Identity, and Hashing

**Status:** Evidence-linked prior-art comparison; no LLMLang equality or identity policy selected  
**Research area:** RT-03 value semantics, RT-04 operator/typeclass contracts, RT-12 collections  
**Updated:** 2026-11-19

## 1. Question and scope

What does equality mean for each type, how is identity distinguished from value equality, and when can a value be used as an ordered or hash key? Keep separate: (1) structural/value equality, (2) reference identity, (3) partial versus equivalence relations, (4) type-level comparability, (5) user-defined equality, (6) equality/hash compatibility, and (7) ordering. Scenarios 45 and 46 cover numeric and textual values; this scenario focuses on contracts and collection semantics.

## 2. Prior-art comparison

### Rust: `PartialEq` for equality, stronger `Eq` marker for total equivalence

Rust's `PartialEq` trait defines `==`/`!=` and can express non-equivalence relations; floating-point NaN is not equal to itself. `Eq` marks types claiming reflexive equality, and float types therefore do not implement it. These are semantic contracts implemented by libraries; the compiler does not prove arbitrary implementations obey their laws. Hash collections require `Eq` and `Hash`, with the law `a == b` implies equal hash output. Pointer identity is explicit through pointer APIs rather than being the meaning of structural equality for every type.

Sources: [Rust `PartialEq`](https://doc.rust-lang.org/core/cmp/trait.PartialEq.html), [Rust `Eq`](https://doc.rust-lang.org/core/cmp/trait.Eq.html), [Rust `Hash` and `Eq`](https://doc.rust-lang.org/std/hash/trait.Hash.html).

### Go: built-in comparability rules determine `==` and map-key eligibility

Go defines comparability structurally for primitive, pointer, channel, array, and struct types, with some dynamic checks for interface values. Slices, maps, and functions are not comparable except to `nil`; a comparison of interface values with an identical dynamic type that is not comparable can panic at runtime. Pointers compare by address/pointed-to variable identity. The built-in map key contract follows these equality rules, so comparability affects the type system and collection eligibility rather than being an independently declared protocol. Floating-point comparisons follow IEEE behavior, including NaN inequality.

Sources: [Go specification — Comparison operators](https://go.dev/ref/spec#Comparison_operators), [Go specification — Comparable types](https://go.dev/ref/spec#Comparison_operators), [Go FAQ — Slices and equality](https://go.dev/doc/faq#why_does_go_not_have_a_==_operator).

### Swift: explicit `Equatable`/`Hashable`; class identity uses `===`

Swift's equality operator is available for types conforming to `Equatable`; simple structs/enums can receive synthesized implementations. Hash-based collections require `Hashable`, whose hash must be consistent with equality. For reference types, `===` tests whether two references point to the same instance; `==` is a separate value/domain relation if the class implements `Equatable`. String equality uses canonical equivalence of extended grapheme clusters, which is distinct from byte-for-byte equality. `Hasher` guarantees repeatability for the same input sequence during one program execution, not a stable persisted hash across executions.

Sources: [Swift Language Guide — Classes and Structures](https://docs.swift.org/latest/documentation/the-swift-programming-language/classesandstructures/), [Swift Advanced Operators — Equatable](https://docs.swift.org/latest/documentation/the-swift-programming-language/advancedoperators/), [Swift Hashable](https://docs.swift.org/latest/documentation/swift/hashable/), [Swift Hasher](https://docs.swift.org/latest/documentation/swift/hasher/), [Swift Strings and Characters](https://docs.swift.org/latest/documentation/the-swift-programming-language/stringsandcharacters/).

### Zig: built-in operator meaning, with representation-specific exceptions

Zig documents a fixed operator set and associated behavior rather than allowing arbitrary operator overloads. Equality behavior is therefore tied to the language's supported types and explicit operations. Some specialized representations have their own semantics: equating `bitpack struct`/`bitpack union` values compares the backing integer. This avoids an open-ended equality dispatch surface, but any representation-specific rule must be visible and documented. Hash-based collection use is a library/API design issue distinct from the equality operator itself.

Source: [Zig Language Reference — Operators and bitpack types](https://ziglang.org/documentation/master/).

## 3. Candidate policies

| Candidate | Equality policy | Trade-offs |
|---|---|---|
| E-Q Structural only | Built-in equality recursively compares fields/elements of supported types; no overloads. Identity uses an explicit operator/API. | Predictable and easy to reason about; excludes domain equality (case-insensitive IDs, normalized values) from `==`. Cycles/recursive structures need defined treatment or exclusion. |
| E-P Protocol/trait equality | Types explicitly implement a `PartialEq`-like operation; a stronger lawful equivalence marker gates sets/maps. | Expressive and supports domain equality; laws are largely programmer obligations and can be violated. |
| E-C Comparability constraints | A type is comparable only if all constituents satisfy built-in structural rules; collections constrain keys accordingly. | Static eligibility and predictable runtime; dynamic/interface cases may still panic unless restricted to strictly comparable types. |
| E-I Split equality and identity | `==` means value/domain equality; explicit identity operation compares references/entities. Hashing and ordering each require separate capabilities. | Clarifies intent; adds operators/concepts and requires API authors to choose semantics deliberately. |

These policies are not mutually exclusive: an intrinsic structural operator can coexist with a user-defined named `equivalent` method, and reference identity can remain separate. Specify float NaN behavior, signed zero, recursive/cyclic values, generic constraints, order laws, hash key mutability, and whether hash values may persist across runs. Never promise stable content hashes from a process-randomized table hasher.

## 4. Discriminating experiments

1. Build a matched corpus for primitive values, nested products/sums, mutable references, aliased graphs, recursive/cyclic graphs, NaNs (multiple payloads), signed zero, and canonically equivalent Unicode strings.
2. For user-defined equality, test reflexivity, symmetry, transitivity, `!=` consistency, cross-type comparison, and behavior after mutable state changes. Report violations separately from compiler rejection.
3. Check map/set membership under equal-but-distinct values, identity-equal-but-domain-unequal values, NaN keys, mutable keys, collisions, and changed equality/hash state after insertion.
4. Compare type-level rejection with runtime panic/false outcomes for containers, interface/dynamic types, and generic key parameters.
5. Pin the contract for portable hashes, persisted hashes, and ABI equality; verify that backend lowering preserves distinctions between byte equality, normalized text equality, structural equality, and pointer identity.

## 5. Current result

Prior art separates at least four concepts: structural equality, domain-defined equality, reference identity, and hash-key compatibility. Comparability may be built-in/type-directed (Go/Zig) or a library trait/protocol contract (Rust/Swift). NaN and canonical Unicode equivalence demonstrate that bitwise identity, mathematical equality, and language equality are not interchangeable. No LLMLang policy is selected; graph-cycle behavior, lawful custom equality, stable hashing, and collection constraints remain open.
