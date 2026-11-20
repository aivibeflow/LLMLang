# Research Scenario 60 — Type Inference Scope and Annotations

**Status:** Evidence-linked prior-art comparison; no LLMLang inference boundary selected  
**Research area:** RT-03 determinism/diagnostics, RT-04 type system and generics, RT-09 compiler behavior  
**Updated:** 2026-11-19

## 1. Question and scope

How much type information should a compiler infer, across which syntactic scope, and where should authors state types explicitly? Distinguish: (1) local variable inference, (2) generic type-argument inference, (3) contextual/backward inference from expected types, (4) inference across statements/functions/modules, (5) ambiguity/fallback policy, (6) diagnostic localization and compile-time bounds, and (7) source/API signature explicitness. Scenario 42 studies generic abstraction and dispatch; this scenario concerns inference scope, explainability, and separate compilation.

## 2. Prior-art comparison

### Rust: strong inference within bodies and calls, explicit public item signatures

Rust infers a `let` binding when surrounding constraints determine one type, and errors when information is insufficient. `_` can request inference in selected type arguments but is prohibited in item signatures. This gives concise local code while function/item boundaries still expose explicit types. Inference failures can be resolved with a local annotation or explicit generic argument. The clear boundary aids interface readability and separate compilation, though it sometimes requires annotations where a more context-directed system could infer further.

Sources: [Rust Reference — Let statements](https://doc.rust-lang.org/reference/statements.html#let-statements), [Rust Reference — Inferred type](https://doc.rust-lang.org/reference/types/inferred.html).

### Go: inference primarily solves generic instantiation equations from call/assignment context

Go's specification defines generic type inference in terms of equations derived from argument/parameter relationships, type constraints, and certain assignment contexts. It infers omitted type arguments when enough information exists, then separately checks instantiation constraints and assignability. The staged rule gives a specified failure boundary instead of choosing among arbitrary candidates. Go also has ordinary declaration inference from initializer values, but generic inference is deliberately described as a bounded operation rather than unrestricted whole-program Hindley–Milner inference.

Sources: [Go specification — Type inference](https://go.dev/ref/spec#Type_inference), [Go blog — Type inference](https://go.dev/blog/type-inference).

### Swift: expression/statement-level contextual inference

Swift's reference documentation states that type inference operates at the level of a single expression or statement. Context can flow into an expression: function parameter types, expected result types, literals, and implicit member syntax can jointly determine omitted type information. This enables concise closures and collection literals, but enlarges the constraint-solving problem and means an annotation or expression split can affect compiler work and error localization. Type inference does not imply inferred public declarations or arbitrary cross-module solving.

Sources: [Swift Types — Type inference](https://docs.swift.org/latest/documentation/the-swift-programming-language/types/), [Swift Language Guide — The Basics](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/), [Swift Language Guide — Closures](https://docs.swift.org/latest/documentation/the-swift-programming-language/closures/).

## 3. Candidate boundaries

| Candidate | Inference scope | Trade-offs |
|---|---|---|
| I-A Local forward inference | Infer from initializer/arguments and local constraints; require explicit public signatures and use-site generic arguments when not determined. | Predictable boundaries and localized diagnostics; more annotations, especially for empty literals and result-only type parameters. |
| I-B Bidirectional expression inference | Solve each bounded expression/statement with both operand and expected-context information; keep declarations/signatures explicit at API boundaries. | Concise closure/literal code and strong local context; constraint complexity, overload ambiguity, and diagnostics need explicit limits. |
| I-C Function-body constraint inference | Solve constraints across a function body, including later uses and returns; declarations still define the external signature. | Reduces local annotations; errors may surface far from their source and edits can perturb distant inferred types. |
| I-D Global/module inference | Infer across declarations or modules, potentially generalizing unannotated definitions. | High brevity and polymorphism; weak separate-compilation boundaries, larger invalidation, harder interface identity and diagnostics, and risk of inference-dependent API changes. |

These choices are independent of generic constraint/dispatch semantics, overload resolution, defaulting of numeric literals, and whether local `let` bindings are polymorphic. An inference algorithm must say when it reports ambiguity, which defaults (if any) apply, and whether source order affects the selected type.

## 4. Decision-relevant consequences

- **Reproducibility:** A deterministic solver with specified tie-break/default rules avoids tool-version drift. Prefer an explicit ambiguity diagnostic over silently selecting a type unless the defaulting rule is part of the language.
- **Diagnostics:** Compare annotation at declaration, call, or expression split. Track both the true source of contradiction and the location shown to users. Preserve a principled bound on search/solver work.
- **Separate compilation and APIs:** Explicit declaration signatures give stable interface artifacts and limit dependency invalidation. Inferred public signatures can make unrelated body edits alter API types unless the language constrains inference and checks interface stability.
- **AI-agent edits:** Measure whether local inference lets an agent change one expression without cascading edits, and whether compiler suggestions identify a minimal annotation that resolves ambiguity.
- **Tooling:** IDE completion, formatting, semantic diffs, and code review need stable inferred types and provenance from source/context, not only a final type string.

## 5. Discriminating experiments

1. A matched corpus covering empty collections, numeric literals, overloaded operators, nested generics, associated types, closures, optional/member syntax, recursive calls, and higher-order generic functions.
2. For each candidate boundary, record accepted/rejected programs, inferred types, minimum annotations, solver time/steps, ambiguity behavior, and diagnostic span. Include adversarially nested overload choices and deliberately conflicting constraints.
3. Edit one statement or overload and measure inferred-type changes outside the edited expression, downstream interface hash changes, dependency invalidation, and diagnostic stability.
4. Compare separate-module compilation with inferred private and public signatures; verify that interface extraction and rebuild behavior match the declared boundary.
5. Run controlled human/agent repair tasks. Measure successful completion, number and placement of annotations, repair iterations, diagnostic usefulness, and whether the inferred API changed unintentionally.

Pin language/compiler versions and solver limits. Report inference acceptance separately from runtime or performance claims; this prior-art survey has no LLMLang compiler measurements.

## 6. Current result

The references support three distinct practical boundaries: body-local inference with explicit item interfaces (Rust), rule-based generic instantiation inference (Go), and expression/statement contextual inference (Swift). They do not establish one universally best policy. LLMLang must decide its inference scope jointly with generics, overloads, API/interface hashing, diagnostics, compile-time budgets, and incremental invalidation. No candidate is selected.
