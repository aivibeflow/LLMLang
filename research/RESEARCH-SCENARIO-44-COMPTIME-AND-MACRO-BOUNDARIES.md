# Research Scenario 44 — Compile-Time Execution and Macro Boundaries

**Status:** Evidence-linked prior-art comparison; no LLMLang metaprogramming model selected  
**Research area:** RT-03 phase semantics, RT-04 type-level computation, RT-09 compiler pipeline, RT-16 build security  
**Updated:** 2026-11-19

## 1. Question and scope

How can programmers generate repetitive declarations and compute with compile-time values without making ordinary code's meaning opaque, build behavior non-reproducible, or compilation an uncontrolled execution environment?

Keep four mechanisms distinct:

1. Declarative syntax macros that match token or syntax patterns.
2. Procedural macros that execute host code to transform syntax.
3. Typed syntax-tree macros with constrained input/output positions.
4. Compile-time evaluation of ordinary language functions and values.

Compare hygiene, stage separation, access to type information, expansion ordering, diagnostics/source maps, termination/resource limits, build caching, and trust. This study covers Rust, Swift, and Zig documentation, with C-style preprocessing as a contrast only. It does not specify LLMLang syntax, a macro sandbox, or a verified metaprogramming semantics.

## 2. Prior-art comparison

### Rust: declarative rules plus procedural token transforms

Rust macro_rules is declarative pattern matching over token trees. It can expand into expressions, statements, items, types, and patterns. Its mixed-site hygiene means some names resolve at the definition site and others at the invocation site. This makes the macro system more structured than plain text substitution, while still requiring users to understand name-resolution rules and expansion diagnostics.

Procedural macros are host-language functions operating on token streams. Rust documentation explicitly describes them as unhygienic: their output behaves as if written at the call site and can interact with imports and names there. This gives substantial transformation freedom, but macro authors must manage paths and generated names carefully. The proc-macro crate executes during compilation, so macro dependencies belong to the build trust and reproducibility boundary.

Sources: [Rust Reference — Macros by example](https://doc.rust-lang.org/reference/macros-by-example.html), [Rust Reference — Procedural macros](https://doc.rust-lang.org/reference/procedural-macros.html), [Rust Reference — Macros overview](https://doc.rust-lang.org/reference/macros.html).

### Swift: typed syntax-tree transformations with additive expansion

Swift macros operate on compiler-provided syntax representations. The language documentation states that expansion is additive: macros add code without deleting or modifying existing source. Input and generated output must parse as Swift, generated values must type-check, and expansion failures become compile errors. This creates a more bounded transform shape than arbitrary textual rewriting and provides a structured expansion stage.

The compiler may run macro implementations in an external process and reuse that process for expansions. That process boundary supports tooling but does not by itself establish a security sandbox or deterministic execution. Macro output, implementation versions, compiler version, and any permitted environment inputs can affect compiled artifacts and therefore cache keys.

Sources: [Swift Language Guide — Macros](https://docs.swift.org/latest/documentation/the-swift-programming-language/macros/), [Swift Language Reference — Macro expansion expressions](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/), [Swift declarations — Macro implementation](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/).

### Zig: compile-time evaluation of ordinary code

Zig makes compile-time evaluation explicit for values and function calls. Compile-time-known parameters and expressions can drive type construction and computation, with compile-time execution sharing much of ordinary language syntax rather than adding a separate token-rewriting language. The reference describes compile-time-known code as eliminated from runtime output and rejects runtime side effects or runtime-dependent values in compile-time evaluation.

This reduces the distinction between metaprogramming and ordinary computation, but increases the importance of phase distinction: whether a value is compile-time known affects what operations are legal and what code is generated. Resource limits, deterministic inputs, and expansion/type-generation diagnostics remain compiler contract questions that must be evaluated for a pinned Zig release.

Sources: [Zig Language Reference — comptime](https://ziglang.org/documentation/master/#comptime), [Zig overview — comptime](https://ziglang.org/learn/overview/).

### C preprocessor: textual substitution as a lower-bound contrast

C preprocessing performs token-oriented preprocessing before C parsing and type checking. Macro expansion can change token sequences without being constrained by C expression or declaration structure, so parentheses, name collisions, repeated argument evaluation, and diagnostics after expansion are design hazards. It remains widely useful for conditional compilation and portable declarations, but should not be treated as equivalent to a syntax-tree macro or typed compile-time evaluator.

Source: [C standard draft N1570 — Translation phases and preprocessing](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf).

## 3. Comparison matrix

| Dimension | Rust declarative | Rust procedural | Swift macros | Zig comptime | C preprocessor |
|---|---|---|---|---|---|
| Input abstraction | Token-tree patterns/fragments | Token streams | Syntax representation | Typed values, types, and ordinary expressions | Preprocessing tokens/text |
| Transform freedom | Rule-based structural expansion | Arbitrary host-code transform | Additive syntax generation | Compile-time execution; no general token rewriting | Broad token substitution and conditional inclusion |
| Hygiene | Mixed-site rules | Unhygienic | Structured syntax model; name behavior follows Swift macro API | Ordinary language name/type rules | No language-level hygiene |
| Type awareness | Fragments identify syntax categories, not arbitrary inferred types | Token-level API; semantic queries are constrained | Compiler checks generated syntax and types after expansion | Compile-time evaluator uses language types and known values | Runs before C semantic analysis |
| Trust boundary | Compiled as part of source toolchain | Host code executes in compiler build pipeline | Macro implementation is executable build input, potentially separate process | Compile-time code executes in compiler | Preprocessor/compiler executes directives and includes |
| Cache inputs | Macro definition/dependencies and invocation tokens | Implementation, dependencies, environment, invocation | Implementation/toolchain/input syntax | Evaluated code and all compile-time values/dependencies | Macro definitions, includes, flags, environment |
| Main advantage | Concise structural syntax extension | Broad derive/custom transformation power | Typed syntax and constrained additive expansion | One language for compile-time and runtime computation | Portability and conditional compilation |
| Main risk | Expansion complexity and mixed-site lookup | Name capture, build-time execution, hidden behavior | External executable macro and opaque generated code | Phase complexity and compile-time resource use | Textual hazards and weak semantic diagnostics |

The table compares documented mechanisms, not a ranking. Macro hygiene and sandboxing are separate properties: hygienic name resolution does not restrict file, process, or network access.

## 4. Discriminating fixture

Use a declaration generator that receives a record definition and generates serialization code, a compile-time lookup table from a constant schema, and a conditional platform binding.

For each mechanism, measure and inspect:

- Can the generator use syntax only, typed syntax, or fully resolved types?
- Can it add declarations, modify existing declarations, remove declarations, or only return a value?
- Which identifiers resolve at definition and call sites? Can two expansions collide?
- Can errors point to the original input span and generated output span?
- Does the result depend on filesystem, environment variables, network, clock, random state, compiler version, or dependency version?
- Can expansion be cached by a complete manifest, and does a macro implementation edit invalidate all affected outputs?
- What are the recursion, fuel, memory, and wall-clock limits? How does limit exhaustion report?
- Does generated code pass the same type/effect/ownership checks as handwritten code?
- Can a package author inspect or reproduce the exact expansion used by CI?

Also create a malicious or accidental expansion case that attempts an undeclared external read or writes outside its output area. This checks the security boundary; it is not a substitute for testing ordinary macro correctness.

## 5. Cross-area implications and open hypotheses

- Syntax transformation and compile-time evaluation are independent axes. A language can provide compile-time functions without macros, or macros without general compile-time execution.
- Type-aware generators may remove boilerplate but couple macro execution to type resolution and compiler phase ordering. Syntax-only transforms are easier to stage but cannot directly branch on inferred semantics.
- Any executable macro mechanism enlarges the trusted build input. Hermeticity requires explicit environment inputs, controlled filesystem/process/network access, resource limits, provenance, and cache invalidation.
- Deterministic expansion does not imply safe expansion; sandboxing does not imply deterministic output. Both properties need separate claims and evidence.
- Generated declarations must retain source provenance and semantic identity so dependencies, diagnostics, approvals, and cache keys can refer to the expansion and its inputs.

## 6. Next research and falsifiers

Prototype syntax-only, typed syntax-tree, and ordinary comptime versions of the fixture, using pinned toolchains. Compare diagnostics, expansion inspectability, type information available, generated artifact size, incremental invalidation, and capability-denied behavior. Record every environment input and test whether builds reproduce when only the declared manifest is present.

The typed syntax-tree approach is weakened if it forces excessive boilerplate or cannot express common safe generation. The general host-code macro approach is weakened if compilation requires ambient privileges or produces unreliable diagnostics and untraceable dependencies. The ordinary comptime approach is weakened if phase errors and compile-time resource behavior are too difficult to explain or bound. The syntax-only approach is weakened if essential generators must duplicate the compiler's parser or type resolver.

No LLMLang macro syntax, compile-time evaluator, trust model, or expansion order is selected.

## 7. Sources and temporal limits

Primary documentation was consulted 2026-11-19. Swift documentation describes version 6.4; Rust online reference and Zig master are rolling, so experiments must pin toolchain releases. N1570 is a C committee draft, not the final publication text. This report is prior-art analysis, not a security audit or compiler benchmark.
