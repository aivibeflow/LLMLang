# Research Scenario 73 — Numeric Literal Typing and Conversions

**Status:** Evidence-linked prior-art comparison; no LLMLang literal typing or conversion policy selected  
**Research area:** RT-03 expression semantics, RT-04 numeric typing/inference, RT-09 diagnostics  
**Updated:** 2026-11-19

## 1. Question and scope

At what point does a numeric spelling become a typed runtime value, and which conversions may occur implicitly between numeric types? Separate literal typing from runtime variable conversion, exact constant evaluation from machine arithmetic, operand peer-type resolution from assignment conversion, and implicit conversion from an explicit cast that may lose range or precision. Scenario 45 compares overflow and numeric representation; this report expands its literal/conversion dimension. Scenario 49 compares syntax and operator semantics.

## 2. Prior-art comparison

### Rust: context-inferred numeric literal with defaults; explicit numeric casts

An unsuffixed integer or float literal gets its type from the surrounding inference context when constrained, otherwise it defaults to `i32` or `f64`. Once a value has a runtime numeric type, Rust does not implicitly convert between primitive numeric types as an arithmetic promotion rule; casts use `as` and have specified but sometimes lossy behavior. Literal overflow and float literal representability are compile-time checks/lints distinct from runtime arithmetic overflow. Coercion sites exist, but numeric casts are not general coercions.

Sources: [Rust Reference — Literal expressions](https://doc.rust-lang.org/reference/expressions/literal-expr.html), [Rust Reference — Type coercions](https://doc.rust-lang.org/reference/type-coercions.html), [Rust Reference — Numeric casts](https://doc.rust-lang.org/reference/expressions/operator-expr.html#numeric-cast).

### Go: exact untyped constants; typed values require explicit conversion

Go numeric constants are exact values of arbitrary precision within implementation minimums and do not overflow during constant evaluation. Untyped constants keep that status through constant expressions, and can be used in a typed context when representable; without context they receive default types such as `int` or `float64`. By contrast, distinct typed numeric values cannot be mixed without explicit conversion. The split gives literal expressions more flexibility than runtime variables while preserving explicit type movement between values.

Sources: [Go Specification — Constants](https://go.dev/ref/spec#Constants), [Go Specification — Representability](https://go.dev/ref/spec#Representability), [Go Specification — Conversions](https://go.dev/ref/spec#Conversions), [Go FAQ — Why no implicit numeric conversions?](https://go.dev/doc/faq#convert).

### Swift: contextual literal protocols; explicit value conversion

Swift literals do not begin as ordinary typed runtime values: inference uses context and literal-conformance protocols such as `ExpressibleByIntegerLiteral` or `ExpressibleByFloatLiteral`; unconstrained integer and floating literals default to `Int` and `Double`. This supports user-defined literal-compatible types while retaining exact contextual checks for integer range. Numeric variables of different widths are not implicitly promoted to a common type; conversion is expressed through an initializer/API, which may trap, fail, or otherwise document its policy.

Sources: [Swift Language Reference — Integer and floating-point literals](https://docs.swift.org/swift-book/ReferenceManual/LexicalStructure.html#Integer-Literals), [Swift Language Guide — Numeric type conversion](https://docs.swift.org/swift-book/LanguageGuide/TheBasics.html#Numeric-Type-Conversion).

### Zig: compile-time literal types and explicit runtime boundaries

Zig integer and floating literals have compile-time-only types (`comptime_int` and `comptime_float`) until context or evaluation requires a runtime type. Integer literals have no fixed size limitation at compile time, while conversion to a runtime integer type must satisfy that type's constraints. Zig has explicit coercion rules, including peer type resolution, and rejects ambiguous or unsafe conversions rather than generally promoting runtime numeric variables. This makes the comptime/runtime boundary central to literal ergonomics and diagnostics.

Sources: [Zig Language Reference — Integer literals and runtime integers](https://ziglang.org/documentation/master/#Integer-Literals), [Zig Language Reference — Type coercion](https://ziglang.org/documentation/master/#Type-Coercion), [Zig Language Reference — Peer type resolution](https://ziglang.org/documentation/master/#Peer-Type-Resolution).

## 3. Candidate policies

These are independent axes rather than mutually exclusive bundles.

| Axis | Candidate | Trade-offs |
|---|---|---|
| Literal model | NL-A Immediately typed literals with fixed defaults; NL-B exact/unbounded constant values until context; NL-C compile-time-only literal pseudo-types; NL-D literal protocols allowing user-defined destination types. | More context and exactness reduce suffix/cast noise but enlarge inference and overflow diagnostics; literal protocols improve extensibility but make literal behavior depend on imported conformances. |
| Runtime conversion | NC-A No implicit numeric conversion; NC-B only proven range/precision-safe widening; NC-C a conventional peer-type promotion table; NC-D explicit checked/saturating/wrapping casts per operation. | Explicit conversions are visible but verbose; widening is convenient but must define signedness/precision; promotion tables risk target-dependent or surprising results. |
| Mixed-expression typing | NP-A Require identical operand types except literals; NP-B compute a specified common peer type; NP-C infer from expected result context where unambiguous. | Local rules aid reading and diagnostics; contextual/bidirectional rules can make expression meaning depend on distant context. |

## 4. Discriminating experiments

1. Type `1`, `255`, `256`, the largest supported integer spelling, `0.1`, and a very small/large exponent in unconstrained, narrow-integer, wide-integer, float, generic, and user-defined literal contexts. Record exactness, defaulting, and failure phase.
2. Compare `1 + x` where `x` is each signed/unsigned width, arbitrary-width integer, float, and user-defined numeric type against `x + 1`; determine whether literal inference is symmetric and whether order affects overload/peer resolution.
3. Mix typed `i8` with typed `u8`, `i32` with `f32`, and `f32` with `f64`. Record implicit accept/reject, chosen result type, overflow/precision loss, and explicit-conversion spelling.
4. Pass constants and runtime values through function arguments, generic bounds, arrays, compile-time evaluation, and FFI declarations. Ensure constant representability does not accidentally grant runtime-variable conversions.
5. Test negative minimum literals and unary minus, shifts, division, and integer-to-float conversion around precision boundaries; distinguish lexical literal formation, compile-time folding, and runtime operator behavior.
6. Add overloads or generic numeric interfaces and test ambiguity, diagnostic locality, import sensitivity, inferred signature changes, and semantic hash/invalidation effects.

## 5. Current result

The surveyed languages all reduce routine literal verbosity, but draw different lines between untyped/exact compile-time constants and runtime numeric values. Go separates exact untyped constants from explicitly converted variables; Zig exposes a comptime-only literal type; Swift uses contextual literal protocols; Rust uses inference/defaulting followed by explicit primitive casts. None implies a general rule for runtime promotion. Literal typing, conversion safety, and peer-type resolution should be compared independently for LLMLang. No LLMLang choice is selected; precision boundaries, diagnostics, target widths, and generic/overload interactions remain open.
