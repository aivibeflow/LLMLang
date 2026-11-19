# Research Scenario 72 — Sum-Type Layout, ABI, and Interoperability

**Status:** Evidence-linked prior-art comparison; no LLMLang sum-type layout or FFI policy selected  
**Research area:** RT-03 data representation, RT-09 ABI and interoperation, RT-20 public API evolution  
**Updated:** 2026-11-19

## 1. Question and scope

How should a language represent algebraic sum types in memory and across function boundaries, and which guarantees can a library expose while retaining room to add cases or optimize layout? Separate source-level case identity/exhaustiveness from physical tag and payload layout, calling convention, foreign representation, and evolution guarantees. Scenario 47 covers source/API evolution of variants; Scenario 54 covers matching and exhaustiveness. This scenario focuses on representation and ABI.

## 2. Prior-art comparison

### Rust: unspecified default layout and explicit C-compatible forms

Rust's default representation for enums does not promise a stable layout. With `repr(C)`, a field-carrying enum is represented as a C-layout struct containing a tag and a union of payload structs. A primitive representation for an enum with fields is a different representation, described as a union whose variant structs each begin with the tag. The language also permits niche-based optimizations under the default representation, but code must not treat those optimizations as a general ABI promise. Explicit representation is therefore a separate choice from the semantic fact that enum cases are disjoint.

Sources: [Rust Reference — Type layout and enum representations](https://doc.rust-lang.org/reference/type-layout.html#reprc-adt), [Rust Reference — Enumerated types](https://doc.rust-lang.org/reference/types/enum.html), [Rust Reference — FFI](https://doc.rust-lang.org/nomicon/ffi.html).

### Zig: tagged unions for safe switching, extern unions for layout

Zig can associate a union with an enum tag, making it a tagged union usable in `switch` and allowing the active field to be checked through the tag. A plain union does not carry that safety information automatically. When a foreign or exact in-memory layout is needed, Zig documents `extern union` and `bitpack union` as layout-guaranteed forms; an ordinary tagged union's optimized representation should not be assumed to match an external C struct-union pattern. This keeps source-level safety and ABI control distinct.

Sources: [Zig Language Reference — Tagged unions](https://ziglang.org/documentation/master/#Tagged-union), [Zig Language Reference — extern unions](https://ziglang.org/documentation/master/#extern-union), [Zig Language Reference — Unions](https://ziglang.org/documentation/master/#union).

### Swift: resilient versus frozen enums and ABI resilience

Swift library evolution distinguishes non-frozen public enums, whose case set/layout remain hidden so a library can add cases, from `@frozen` enums, whose case set becomes exhaustive and cannot later change without source and ABI breakage. Non-frozen enum layout is not exposed to clients; clients must account for future unknown cases in switches. `@objc` enums have a C-compatible/trivial representation category, distinct from general Swift enums with associated payloads. This makes resilience a contract about client assumptions as well as storage.

Sources: [Swift Library Evolution — Frozen enums](https://github.com/swiftlang/swift/blob/main/docs/LibraryEvolution.rst#frozen-enums), [Swift Evolution SE-0192 — Non-exhaustive enums](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0192-non-exhaustive-enums.md), [Swift ABI Stability Manifesto](https://github.com/swiftlang/swift/blob/main/docs/ABIStabilityManifesto.md).

### C: tagged-union convention rather than a native payload sum type

C commonly models a closed variant value using a struct containing an enum discriminator and a union payload. The programmer must preserve the invariant that the discriminator agrees with the active union member; the representation itself does not provide Rust/Swift-style algebraic case checking. Foreign interfaces therefore need explicit tag width/value assignments, alignment, payload layout, and ownership/lifetime rules. C23 fixed-underlying-type enums provide additional control for enum types, but do not create an automatic tagged payload union.

Sources: [WG14 N3096 — C23 draft, enumerated types and unions](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf), [Rust Reference — `repr(C)` enum mapping example](https://doc.rust-lang.org/reference/type-layout.html#reprc-adt).

## 3. Candidate policies

| Candidate | Representation and evolution | Trade-offs |
|---|---|---|
| SA-A — Optimized private representation | Default representation is compiler-chosen; no public ABI promises. FFI uses explicit bridge structs/functions. | Best optimization and evolution freedom; direct aggregate FFI is verbose and may allocate/copy. |
| SA-B — Stable tagged-union representation | Public sum types use fixed tag plus C-layout payload union. | Straightforward C interop and inspection; tag/padding/case changes constrain ABI and may waste space. |
| SA-C — Resilient opaque ABI | Public non-exhaustive sum values cross ABI through opaque handles or resilient calling conventions; consumers use accessors/matches. | Allows case/layout evolution; runtime and accessor overhead and limited foreign ergonomics. |
| SA-D — Explicit per-type representation controls | Each sum type declares private, resilient, C-tagged, or fixed primitive/tagged ABI representation; incompatible cases are rejected. | Makes contracts visible and supports targeted FFI; increases language/tooling surface and cross-target validation burden. |

Case evolution and storage are related but separate. A fixed tag may still leave payload padding rules, indirect cases, calling convention, and valid-value invariants unspecified. A resilient source API does not imply a stable C ABI.

## 4. Discriminating experiments

1. For the same zero-payload, single-payload, multi-payload, nested, and large-payload variants, record size/alignment, tag placement, invalid encodings, and register/indirect passing on each target ABI.
2. Compile producer and consumer separately, then add a case or change payload fields. Record source, binary, and wire-format compatibility independently for frozen, resilient, and explicit C-tagged profiles.
3. Round-trip values across C and the language for every tag and payload; inject unknown tags, invalid tag/payload combinations, null/invalid pointers, and version-skewed values. Specify safe rejection behavior.
4. Compare exhaustive and future-proof switch lowering: unknown-case handling, optimizer assumptions, and behavior when a newer library sends a case unknown to the client.
5. Measure niches, explicit tags, payload unions, boxing/indirect cases, and FFI bridges for memory, call cost, code size, and optimizer stability without inferring ABI from one build.
6. Specify fixed tag width/signedness, discriminant assignment, padding/alignment, endianness when serialized, ownership of payloads, and whether invalid bit patterns are representable at any unsafe boundary.

## 5. Current result

Safe sum-type semantics do not dictate a single layout or ABI. Rust exposes a detailed explicit C representation alongside an unspecified optimized default; Zig separates tagged unions from extern layout forms; Swift makes exhaustiveness/layout flexibility an explicit resilience contract; C relies on manual tag/payload invariants. The evidence supports independent per-type ABI and evolution decisions, but no LLMLang representation profile is selected. Matched cross-target ABI probes and version-skew tests remain necessary.
