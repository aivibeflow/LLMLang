# Research Scenario 42 — Generics, Constraints, and Dispatch

**Status:** Evidence-linked prior-art comparison; no LLMLang generic mechanism selected  
**Research area:** RT-04 type abstraction, RT-09 specialization/lowering, RT-11 interface identity  
**Updated:** 2026-11-19

## 1. Question and scope

How should reusable code express operations available on type parameters, how are implementations selected, and when can a value cross an abstraction boundary without exposing its concrete type?

These are related but separate decisions:

1. Parametric polymorphism: a definition is checked against type variables and instantiated at uses.
2. Constraint model: required operations and type relationships are expressed by nominal traits/protocols, structural interfaces/type sets, or class predicates.
3. Associated types: a constraint may name types related to its implementing type.
4. Dispatch and representation: calls may specialize statically, pass dictionaries/witness tables, or use existential/trait objects with dynamic dispatch.
5. Coherence: the language must determine whether zero, one, or multiple implementations apply, and whether selection can vary by module/import context.

This report compares Rust, Go, Swift, and Haskell/GHC documentation. It does not benchmark generated code or type-checker performance, prove semantic equivalence, prescribe syntax, or cover higher-kinded/dependent polymorphism in depth.

## 2. Prior-art comparison

### Rust: nominal traits, bounds, and explicit dynamic boundary

Generic Rust items use trait bounds to state which operations are available. A trait implementation attaches behavior to a type. Coherence rejects overlapping implementations and the orphan rule restricts who may implement a trait for a type; this constrains downstream extension while preventing independently selected conflicting implementations. Generic use can be monomorphized, while a dyn Trait value gives a dynamic-dispatch boundary and is restricted to dyn-compatible traits. These mechanisms make static and dynamic abstraction explicit, but they are distinct type forms with different constraints.

The design pressure is not just inference: a public trait and its implementation ownership rules shape ecosystem extensibility, semver, and which crate controls behavior. A trait with associated types or generic methods may not be usable as a trait object under the dyn-compatibility rules.

Sources: [Rust Reference — Traits](https://doc.rust-lang.org/reference/items/traits.html), [Rust Reference — Implementations and coherence](https://doc.rust-lang.org/reference/items/implementations.html), [Rust Reference — Trait objects](https://doc.rust-lang.org/reference/types/trait-object.html).

### Go: type-parameter constraints as interfaces and type sets

Go generic type parameters are constrained by interface types. A constraint defines the admissible type set and the operations available for a parameter; interfaces can describe method sets and, in constraint position, unions and underlying-type terms. Ordinary interfaces also support runtime values and dynamic method dispatch, while a type parameter is a compile-time abstraction. Go documentation distinguishes these concepts: using an interface as a constraint is not the same as storing an interface value.

This gives one interface syntax distinct roles while keeping the supported type-set rules intentionally bounded. The language specification's special rules for comparable, union terms, and operations on type parameters are part of the design cost; structural matching does not mean every arbitrary structural constraint is expressible.

Sources: [Go specification — Interface types and type parameters](https://go.dev/ref/spec), [Go tutorial — Generics](https://go.dev/doc/tutorial/generics), [Go FAQ — Type parameters](https://go.dev/doc/faq#Type_Parameters).

### Swift: protocols, associated types, opaque and existential types

Swift generic constraints use protocols, with where clauses expressing same-type and associated-type requirements. Protocol associated types name relationships that are not naturally represented as a fixed list of methods alone. Opaque some P types preserve one specific hidden conforming type identity at compile time; existential any P packages a value behind a protocol abstraction and has different identity and use constraints. Generic parameters, opaque results, and existentials therefore offer different abstraction contracts rather than interchangeable spellings.

The expressive relationships help model collection-like and builder APIs, but the user must choose whether concrete type identity is preserved, hidden-but-fixed, or erased. Associated types and protocol composition also interact with whether an existential can represent a protocol value.

Sources: [Swift Language Guide — Generics](https://docs.swift.org/latest/documentation/the-swift-programming-language/generics/), [Swift Language Guide — Protocols](https://docs.swift.org/latest/documentation/the-swift-programming-language/protocols/), [Swift Language Guide — Opaque Types](https://docs.swift.org/latest/documentation/the-swift-programming-language/opaquetypes/).

### Haskell/GHC: type classes, dictionaries, associated families, and overlap

Haskell type-class constraints express predicates over types; class instances supply implementations, typically elaborated through dictionary passing. GHC also supports associated type and data families, which express type-level relationships and may be open or closed depending on family form. Instance resolution has admissibility, overlap, and orphan-module rules; enabling overlap can affect coherence and separate compilation. This model gives powerful abstraction and type-level computation but expands instance resolution and interface-dependency complexity.

GHC documentation warns that orphan instances require proactively reading orphan-module interfaces because they may affect resolution, while overlapping instances can create incoherence or conservative resolution behavior. This connects generic abstraction to dependency extraction, build invalidation, and reproducibility.

Sources: [GHC User's Guide — Instance declarations and resolution](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/instances.html), [GHC User's Guide — Type families](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/type_families.html), [GHC User's Guide — Separate compilation](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/separate_compilation.html).

## 3. Comparison matrix

| Dimension | Rust traits | Go constraints/interfaces | Swift protocols | Haskell/GHC classes |
|---|---|---|---|---|
| Constraint attachment | Nominal trait bounds | Interface constraints and type sets | Nominal protocol conformance | Class predicates resolved by instances |
| Implementation discovery | Explicit impl; coherence and orphan rules | Implicit method-set satisfaction; type terms constrain type parameters | Explicit conformance | Instance declarations discovered from imported interfaces |
| Related type outputs | Associated types | No general associated type member in constraints | Associated types and same-type where constraints | Associated types/families |
| Static abstraction | Generic functions/types, normally statically specialized | Generic functions/types | Generic functions/types; opaque result preserves hidden identity | Constrained polymorphic functions |
| Dynamic abstraction | dyn Trait when dyn-compatible | Interface values | any Protocol existential | Dictionary passing is an implementation model; not the same as Rust/Swift existential syntax |
| Extension/coherence pressure | Orphan and overlap restrictions are explicit | Structural satisfaction avoids explicit instance overlap selection; type-set rules bound expressiveness | Explicit conformance ownership; protocol evolution and existential constraints matter | Flexible instance/type-family system; overlap and orphan handling affect coherence and module dependencies |
| Dependency/build implication | Bounds, impl selection, and specialization inputs may affect interface or generated code | Constraint and type-set changes affect admissibility; implementation body may not change generic signature | Protocol requirements, associated-type witnesses, and existential/generic boundary affect clients | Imported instance/orphan interfaces can influence resolution even when source imports look unrelated |

Dictionary passing describes a common compilation strategy for type classes; the GHC language documentation specifies source and resolution behavior, not one universal runtime cost. Static specialization is an implementation choice whose code-size and compile-time impact must be measured per compiler and target.

## 4. Discriminating fixture

Use a generic fold_map(source, map, combine) and a heterogeneous PluginRegistry:

- fold_map should accept a type with an associated output type and a constraint on that output, then instantiate for arrays and a user-defined streaming source.
- PluginRegistry should hold multiple unrelated implementations discovered at runtime, return an opaque implementation from a constructor, and expose a stable client-facing interface.
- Add a third-party implementation for two dependencies the application does not own; attempt a duplicate/conflicting implementation in a downstream package.
- Add one protocol/trait requirement and one associated type after the client is compiled.
- Change only one implementation body, then only one constraint/instance relation; record compile, link, runtime dispatch, cache invalidation, and API compatibility effects.

Record separately: type-checking success/failure, diagnostics and ambiguity, source and binary compatibility, chosen implementation identity, code size, compile time, runtime dispatch cost, and whether dependency extraction found every resolution input. Do not let a benchmark of one monomorphized loop stand in for existential use or instance-resolution behavior.

## 5. Cross-area implications and open hypotheses

- Generic constraints are part of RT-04 semantics; dispatch and specialization are RT-09 backend choices. The surface construct alone does not determine runtime representation.
- A change to an associated type, protocol requirement, instance, or overlap set can affect callers even if a function's printed signature is unchanged. This suggests an RT-05/RT-11 invalidation question, but cited documentation does not prove LLMLang's required hash boundary.
- Structural constraints can reduce explicit conformance boilerplate, while globally selected instances can make behavior predictable at a cost to downstream extension. This is a trade-off, not a total ranking.
- Dynamic values are useful for heterogeneous collections and plugin boundaries, but should not silently erase ownership, effects, error contracts, or authority requirements.
- A trait/class dictionary can be treated as an explicit semantic input in a canonical representation, or selection can be represented by an implementation binding. Which is correct depends on whether specialization/dispatch choice is observable and what evidence/cache result is being reused.

## 6. Next research and falsifiers

Build the shared fixture in at least two compiler implementations per candidate model, pinning compiler versions and flags. Inspect emitted representations for representative static and dynamic cases; measure build time and code size only after semantic outcomes and chosen implementation are checked. Add the fixture to dependency extraction and change-impact analysis.

The Rust-style coherence advantage is weakened if downstream users cannot implement essential foreign abstractions without repeated wrapper types or upstream changes. The structural Go-style advantage is weakened if common abstractions require verbose unions/type terms or cannot state important relationships. Associated-type approaches are weakened if existential/plugin boundaries require pervasive boxing or type erasure. Instance-based approaches are weakened if module/import changes alter resolution unexpectedly or force broad rebuilds. Any candidate that cannot make implementation selection deterministic under package composition fails the shared reproducibility requirement.

No LLMLang syntax, dispatch strategy, or coherence policy is selected by this report.

## 7. Sources and temporal limits

Primary references were consulted 2026-11-19. Go specification and Swift documentation are rolling documents; compiler behavior should be checked against pinned releases before experiments. GHC User's Guide pages include versioned documentation, but implementation-resolution details still require a pinned GHC build for reproducible probes. This is documentation-based prior-art analysis, not a performance or conformance experiment.
