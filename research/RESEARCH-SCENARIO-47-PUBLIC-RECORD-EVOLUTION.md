# Research Scenario 47 — Public Record and Variant Evolution

**Status:** Evidence-linked compatibility comparison; no LLMLang public data-type policy selected  
**Research area:** RT-04 data types, RT-05 semantic/interface identity, RT-18 source and ABI evolution  
**Updated:** 2026-11-19

## 1. Question and scope

When a library exposes a product type or sum type, which later changes remain compatible with old clients? Focus on adding struct/record fields, enum cases, and fields inside a case. Distinguish:

1. Source compatibility after recompilation.
2. Binary/ABI compatibility for already-compiled clients.
3. Pattern-match exhaustiveness and construction syntax.
4. Layout, serialization, and foreign-function representation.
5. Whether a type was designed as closed/frozen or open/resilient from its first release.

The comparison uses Rust/Cargo, Swift library evolution, and Go package compatibility guidance. It does not cover wire-format evolution in depth; source-level data types and serialized schema compatibility need separate contracts.

## 2. Prior-art comparison

### Rust: reserve extensibility up front with non-exhaustive APIs

Rust's non_exhaustive attribute may apply to structs, enums, and enum variants. Outside the defining crate, a non-exhaustive struct cannot be constructed with a literal, and enum matching requires a wildcard fallback. Cargo's compatibility guidance treats adding a public field to an all-public-field struct, adding an enum case to an exhaustive enum, adding fields to a case, or adding non_exhaustive later as breaking changes. Its mitigation is to reserve room at initial API introduction and prefer constructors/accessors where future evolution is intended.

This puts source-level obligations up front: clients accept incompleteness and cannot rely on exhaustive construction/matching. The language can then preserve extension room, but the fallback arm may hide meaningful new cases unless clients handle the wildcard deliberately.

Sources: [Rust Reference — non_exhaustive](https://doc.rust-lang.org/reference/attributes/type_system.html#the-non_exhaustive-attribute), [Cargo SemVer Compatibility](https://doc.rust-lang.org/cargo/reference/semver.html).

### Swift: resilient versus frozen layout in library evolution mode

Swift library evolution allows public non-frozen structs and enums to retain resilience across module boundaries; a library can add stored properties or enum cases without requiring clients to know the complete layout/case set. The frozen attribute opts out of that resilience and promises a fixed public layout/case set; future stored-property or case changes are ABI-breaking. Enabling library evolution is a build/distribution decision, so source declarations alone do not determine the compatibility promise.

This can support binary-compatible library updates at the cost of indirection or less layout knowledge for clients. Frozen public types can enable stronger client optimization but spend the evolution budget. Changing frozen/resilient status itself can break ABI, so it is a release-time decision.

Sources: [Swift.org — Library Evolution](https://www.swift.org/blog/library-evolution/), [Swift attributes — frozen](https://docs.swift.org/latest/documentation/the-swift-programming-language/attributes/).

### Go: keyed literals support many field additions, but not all clients

Go's compatibility guidance notes that adding fields to exported structs is usually source-compatible, because keyed composite literals can omit fields and receive zero values. Unkeyed composite literals enumerate fields positionally, so adding a field breaks those clients. Go's compatibility policy explicitly calls out unkeyed literals as a risk, and tooling can flag them for public structs.

Go's policy is an ecosystem compatibility guideline rather than a language prohibition on positional construction. This reduces friction for common keyed use but relies on library maintainers and clients following conventions. Zero-value behavior also becomes part of the compatibility story: a newly added field must behave correctly when left at its zero value.

Sources: [Go blog — Keeping Your Modules Compatible](https://go.dev/blog/module-compatibility), [Go compatibility guide](https://go.dev/doc/go1compat), [Go blog — Backward Compatibility](https://go.dev/blog/compat).

## 3. Comparison matrix

| Change | Rust default public exhaustive type | Rust reserved non-exhaustive type | Swift resilient type | Swift frozen type | Go exported struct |
|---|---|---|---|---|---|
| Add product field | Source-breaking when clients use struct literal; major per Cargo guidance | Allowed while clients cannot construct/match exhaustively | ABI-resilient in library-evolution mode; source/API behavior still must be checked | ABI-breaking even for private stored property | Usually source-compatible for keyed literals; breaks unkeyed literals |
| Add sum case | Breaks exhaustive matches; major | Allowed; downstream wildcard required | ABI-resilient when non-frozen under library evolution | Breaks fixed case/layout promise | Not directly applicable to Go's open interface/pseudo-sum patterns |
| Add fields within case | Constructors and patterns break | Can reserve fields with non-exhaustive variant | Associated payload enum evolution follows resilience rules | ABI-breaking | Not directly applicable |
| Evolution setting timing | Adding non-exhaustive later is itself major | Must be present at initial API boundary | Library mode and frozen status must be established before release | Frozen promise constrains future layout/cases | Convention/tooling can be adopted, but language does not reserve layout automatically |
| Main compatibility axis | Source/semver | Source extensibility with caller fallback | Binary ABI and client resilience | Client optimization versus ABI commitment | Source compatibility conventions and zero-value defaults |

“Compatible” always needs a named consumer model. Source-compatible, binary-compatible, layout-compatible with FFI, and behavior-compatible are different claims.

## 4. Discriminating fixture

Publish a library with:

- A public Config product type with two fields and a constructor/default.
- A public Error sum with two cases, one case carrying a product payload.
- A client that uses keyed construction, positional construction where supported, field reads, exhaustive matching, wildcard matching, serialization, and FFI layout.

Release 1, then mutate one axis at a time: add a product field with a default; add a variant; add a payload field; reorder fields; change a public type from open/resilient to frozen; switch representation or serialization. For each step, test old client source recompilation, old binary with new library where supported, and the serialized/FFI boundary separately. Record compiler diagnostics, runtime interpretation, layout, and migration burden.

## 5. Cross-area implications and open hypotheses

- Extensibility is bought before the change: constructors, accessors, wildcards, or resilience metadata make future changes possible by limiting what clients may assume.
- A wildcard/fallback can preserve compilation while silently routing a new semantically important variant through generic handling. Compatibility therefore does not prove behavior remains correct.
- Default values are a compatibility mechanism only if they preserve invariants and have explicit meaning; zero initialization is not automatically a valid domain default.
- Source-level records and enums may have separate serialized and FFI representations. Changing a source field is not safe for a wire schema or C ABI unless that contract explicitly permits it.
- Interface identity and cache keys may need to include openness/frozen status, visible fields/cases, representation, and library-evolution mode. This is an RT-05/RT-11 hypothesis; the cited ecosystems do not establish LLMLang's exact hash projection.

## 6. Next research and falsifiers

Build the same client/library fixture in all three ecosystems, pin compiler versions and ABI settings, and run source and binary compatibility checks. Add a serialized form and a C-facing view to expose the places where source-level resilience ends. Record exact API-diff tool behavior and whether it catches unkeyed construction, missing wildcard, layout, and behavior changes.

Reserved openness is weakened if callers must write boilerplate fallbacks that undermine exhaustive safety. Frozen types are weakened if required API evolution causes repeated major releases or ABI breaks. Convention-based compatibility is weakened if ordinary language syntax allows common client patterns to break on field additions without clear tooling. Any approach is weakened if it confuses successful recompilation with safe interpretation of new states.

No LLMLang record/enum openness attribute, field visibility policy, defaulting rule, or ABI promise is selected.

## 7. Sources and temporal limits

Official documentation was consulted 2026-11-19. Rust Cargo semver guidance is policy guidance, Go compatibility documents describe the Go 1 promise and common source-compatibility patterns, and Swift's behavior depends on library-evolution compiler mode and frozen annotations. Validate with pinned compilers before making ABI claims.
