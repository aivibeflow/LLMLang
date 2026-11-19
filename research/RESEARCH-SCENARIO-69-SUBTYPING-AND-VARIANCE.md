# Research Scenario 69 — Subtyping and Variance

**Status:** Evidence-linked prior-art comparison; no LLMLang subtyping or variance policy selected  
**Research area:** RT-03 type compatibility, RT-04 generics/dispatch, RT-09 type checking  
**Updated:** 2026-11-19

## 1. Question and scope

When is a value of one static type usable where another is expected, especially through generic constructors and function types? Separate nominal inheritance/interface implementation from structural compatibility; subtyping from assignability/coercion; and the variance of each generic parameter from the type's name. A sound covariance rule must not permit writes that violate the narrower element type; function inputs and outputs have different substitution directions. Behavioral substitutability (contracts/history) is stronger than signature compatibility and is covered separately in Scenario 14.

## 2. Prior-art comparison

### Rust: narrow subtype relation; variance inferred from type structure

Rust's Reference restricts subtyping to lifetime variance and higher-ranked lifetime cases; after erasing lifetimes, ordinary types are related by equality. Variance describes how a subtype relationship in a parameter affects a generic type. The compiler derives variance from field/type structure rather than requiring user annotations for ordinary generic types. Mutable references and invariant interior types constrain safe substitutions; lifetime covariance is useful for shortening borrows. This gives a relatively small subtype relation while keeping lifetime substitution expressive.

Sources: [Rust Reference — Subtyping and Variance](https://doc.rust-lang.org/reference/subtyping.html), [Rustonomicon — Subtyping and Variance](https://doc.rust-lang.org/nomicon/subtyping.html).

### Java: invariant generic instantiations with use-site wildcards and capture

Java's JLS states that `C<T>` is not a subtype of `C<S>` merely because `T` is a subtype of `S`; ordinary parameterized types are invariant. Wildcards express bounded views such as `? extends T` and `? super T`, while capture conversion gives an unknown wildcard a fresh type variable for safe local reasoning. This retains mutable generic containers without unsound covariance, at the cost of wildcard/capture complexity and more involved inference diagnostics.

Sources: [Java Language Specification §4.10 — Subtyping](https://docs.oracle.com/javase/specs/jls/se24/html/jls-4.html#jls-4.10), [Java Tutorials — Wildcards and Subtyping](https://docs.oracle.com/javase/tutorial/java/generics/subtyping.html).

### Go: exact type identity/assignability plus interface implementation

Go specifies type identity and assignability with detailed rules: generic instantiations must match their type arguments; an interface destination accepts a value whose type implements that interface, with method signatures matching exactly. Assignability is not general variance through nested types. This favors explicit interfaces and straightforward type equality over implicit hierarchy-wide substitution, but does not offer a general read-only covariant view of a mutable container.

Sources: [Go Specification — Type identity](https://go.dev/ref/spec#Type_identity), [Go Specification — Assignability](https://go.dev/ref/spec#Assignability), [Go FAQ — Why no covariance in method return types?](https://go.dev/doc/faq#covariant_types).

### Swift: generic abstraction and constrained existentials, with variance boundaries

Swift uses generics and protocol constraints for parametric polymorphism rather than treating every generic relationship as a subtype. The constrained existential types proposal states that constrained existentials behave invariantly with respect to their type arguments. This demonstrates that existential boxing and generic substitution are separate rules; class inheritance conversions and function type conversions must be evaluated independently rather than inferred from the generic syntax. Where invariance prevents a useful conversion, APIs can use another generic parameter, explicit mapping, or an existential boundary.

Sources: [Swift Language Guide — Generics](https://docs.swift.org/swift-book/LanguageGuide/Generics.html), [Swift Evolution SE-0353 — Constrained Existential Types](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0353-constrained-existential-types.md), [Swift Language Reference — Types](https://docs.swift.org/swift-book/ReferenceManual/Types.html).

## 3. Candidate policies

| Candidate | Subtyping/variance policy | Trade-offs |
|---|---|---|
| SV-A Equality-only except explicit interfaces | No general subtype relation for concrete/generic types; explicit interface constraints and conversions mediate reuse. | Small relation and predictable diagnostics; more adapters and repeated conversions. |
| SV-B Invariant nominal generics | Generic arguments invariant by default; explicit read/write abstractions or existential/wildcard views handle variance needs. | Sound mutable containers and stable API reasoning; more type syntax and capture/inference burden. |
| SV-C Declaration-site variance | Generic declarations mark parameters `out`/covariant, `in`/contravariant, or invariant; checker validates declaration use. | Cleaner call sites for safe producer/consumer abstractions; annotations constrain implementation evolution and higher-order positions. |
| SV-D Inferred structural variance | Infer variance from field/method use, with explicit escape hatches for invariance or erased views. | Less annotation for immutable APIs; adding a consuming use can break clients, inference and incremental interface identity become more complex. |

Function types are a separate rule: a safe subtype relation generally permits a function that accepts a broader input and returns a narrower output where the original function is expected. Test thrown/effect bounds, asyncness, ownership, and calling convention as additional dimensions. Arrays and mutable references need invariance or a restricted write interface unless runtime checks mediate writes.

## 4. Discriminating experiments

1. Use `Animal <: Cat` plus immutable producer, mutable vector, write-only sink, callback, and function result types. Check substitutions and reject any path that allows a Dog to enter a Cat-only storage location.
2. Add nested generic types, higher-order callbacks, nullable/optional and error/effect wrappers, existential/interface values, and generic methods. Record subtyping, assignability, coercion, and inference as separate outcomes.
3. Mutate a generic API from read-only to consuming/storing a parameter. Measure downstream compatibility under invariant, declaration-site, and inferred variance.
4. Compare wildcard/capture or existential views with explicit mapping/adapters: annotations, diagnostic locality, runtime boxing, and code generation.
5. Combine lifetime/borrow/ownership variance with reference mutability and interior-mutability cells. Verify that lifetime shortening cannot create aliasing or mutation unsoundness.
6. Record which type relationships enter public interface hashes and dependency invalidation; a variance change can alter accepted callers even when representation and function bodies stay fixed.

## 5. Current result

Subtyping scope is an independent design choice from generic constraints. Rust keeps ordinary concrete subtyping narrow and derives lifetime variance; Java uses invariant mutable generics plus use-site wildcard/capture; Go specifies identity/assignability and interface implementation without nested generic variance; Swift separates generic abstraction from existential and other conversion rules. No LLMLang rule is selected. Function variance, effect/error/async dimensions, mutable container views, and variance evolution need matched fixtures before RFC synthesis.
