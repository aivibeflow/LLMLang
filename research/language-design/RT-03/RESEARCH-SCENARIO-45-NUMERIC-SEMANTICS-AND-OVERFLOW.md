# Research Scenario 45 — Numeric Semantics, Overflow, and Floating-Point Modes

**Status:** Evidence-linked prior-art comparison; no LLMLang numeric profile selected  
**Research area:** RT-03 arithmetic semantics, RT-04 numeric types/refinements, RT-07 proof model, RT-09 backend preservation  
**Updated:** 2026-11-19

## 1. Question and scope

Which numeric values and operations should LLMLang define, and how should behavior remain predictable across debug/release modes, architectures, compilers, and proof boundaries?

Separate these questions:

1. Integer widths: fixed-width signed/unsigned, platform-sized integers, arbitrary precision, or combinations.
2. Overflow: trap/panic, defined wrapping, saturating, checked result, or mode-dependent behavior.
3. Division: zero behavior, signed minimum divided by -1, and truncation/floor/exact variants.
4. Literals and coercion: untyped/exact constants versus immediately typed literals; implicit numeric conversion and casts.
5. Floating point: IEEE 754 behavior, NaN/signed-zero semantics, contraction/reassociation, strict versus fast modes.
6. Execution profiles: whether optimization flags may change program-visible outcomes or only performance.

This report compares Rust, Go, Swift, and Zig references. It does not specify decimal/fixed-point types, vector/SIMD semantics, transcendental library accuracy, or a full IEEE conformance suite.

## 2. Prior-art comparison

### Rust: checked behavior depends on compiler configuration

The Rust Reference documents integer overflow checks in debug mode and describes compiler flags that control checks more directly. This means the ordinary arithmetic operator's behavior is coupled to build configuration unless a program uses explicit checked, wrapping, overflowing, or saturating APIs. Rust's type system offers fixed-width integers, while usize/isize are target-width-dependent.

The key design question is whether a build profile may change observable arithmetic results or only whether a fault is detected. Debug-only detection can expose bugs early, but a language-level contract should specify release behavior and reproducible flags if profiles differ.

Sources: [Rust Reference — Operator expressions and overflow](https://doc.rust-lang.org/reference/expressions/operator-expr.html#overflow), [Rust primitive integer documentation](https://doc.rust-lang.org/std/primitive.i32.html).

### Go: fixed-width integer overflow is defined and signed division is truncating

Go specifies unsigned addition, subtraction, multiplication, and left shift modulo 2^n. Signed integer overflow produces a deterministic value defined by the signed representation and operands, and does not panic. Integer division truncates toward zero, with a specified special case for the minimum signed value divided by -1. Division by zero at runtime panics.

Go also has int/uint types whose width is implementation-dependent, so fixed-width types are required when the number of bits is part of an external format or proof. Floating-point and complex behavior follows IEEE 754 in relevant respects, while division by zero panic behavior for floating/complex values is implementation-specific according to the specification.

Sources: [Go specification — Integer overflow and operators](https://go.dev/ref/spec#Integer_overflow), [Go specification — Integer operators](https://go.dev/ref/spec#Integer_operators), [Go specification — Floating-point operators](https://go.dev/ref/spec#Floating_point_operators).

### Swift: trapping default with explicit wrapping operators

Swift's basic fixed-width integer arithmetic traps on overflow. Separate ampersand-prefixed operators explicitly opt into wrapping behavior; standard integer APIs also expose reporting-overflow operations. Integer literals that cannot fit the chosen type are rejected. Int is the platform's native word size, while fixed-width integer types are available for stable representation.

This makes wrapping intent visible at each operation and keeps accidental overflow detectable in normal builds. It can make low-level modular arithmetic more syntactically explicit, and callers must choose a checked-result API when they need to handle overflow rather than trap or wrap.

Sources: [Swift Language Guide — Advanced Operators](https://docs.swift.org/latest/documentation/the-swift-programming-language/advancedoperators/), [Swift Language Guide — The Basics](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/), [Swift UInt API](https://docs.swift.org/latest/documentation/swift/uint/).

### Zig: explicit overflow operator families and safety modes

Zig has fixed-width integer types and distinct operator forms for ordinary, wrapping, and saturating arithmetic. Integer overflow can trigger safety behavior depending on runtime-safety configuration; the documentation distinguishes safety-enabled and optimized modes. Zig also offers checked overflow builtins. Floating-point mode may be strict or optimized at scope, with optimized mode permitting transformations analogous to fast-math.

This gives low-level programmers explicit control over arithmetic intent and safety checking, but build mode and floating-point mode become semantic inputs if they change observable behavior. A compiler/runtime profile must state them to make execution and evidence reproducible.

Sources: [Zig Language Reference — Operators](https://ziglang.org/documentation/master/#Operators), [Zig Language Reference — Floating-point operations](https://ziglang.org/documentation/master/#Floating-Point-Operations), [Zig Language Reference — Runtime safety](https://ziglang.org/documentation/master/#setRuntimeSafety).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Zig |
|---|---|---|---|---|
| Integer widths | Fixed-width plus target-width usize/isize | Fixed-width plus target-dependent int/uint | Fixed-width plus target-width Int/UInt | Fixed-width integer types |
| Ordinary overflow | Checks/panic in debug; flags control behavior | Deterministic fixed-width result; unsigned modulo | Traps | Safety checks may detect; ordinary operators distinguish from wrapping/saturating forms |
| Explicit modular arithmetic | Wrapping methods/APIs | Defined unsigned modulo; signed overflow defined by representation | Dedicated wrapping operators | Dedicated wrapping operators |
| Saturation/checked result | Standard APIs | Usually explicit library logic | Reporting-overflow APIs; saturation via APIs | Saturating operator family and overflow builtins |
| Signed division | Truncating; overflow edge must be specified by operation/configuration | Truncates toward zero; minimum / -1 has defined special result | Truncates toward zero; traps on overflow/divide-by-zero | Several explicit division operations; ordinary signed division is restricted to avoid ambiguous rounding |
| Floating optimization | Compiler/target semantics require profile review | IEEE 754-style rules; some division-by-zero panic behavior implementation-specific | IEEE 754 types and operations; optimizer/toolchain behavior still needs target validation | Strict and optimized modes, including fast-math-like transformations |
| Build profile impact | Overflow-check settings can affect detection/result | Integer results specified; implementation profile still matters elsewhere | Default trap plus explicit wrap operators | Runtime-safety and float modes can affect behavior |

The matrix separates arithmetic value semantics from error-reporting APIs and optimizer freedom. “Checked” can mean compile-time rejection, runtime trap, or an explicit returned overflow flag; these are different contracts.

## 4. Discriminating fixture

Use fixed-width signed and unsigned 8-bit and 64-bit values and exercise:

- max + 1, min - 1, multiplication overflow, unary negation of min, and left shift beyond width;
- min / -1, negative / positive division and remainder, and division by zero;
- checked, wrapping, and saturating versions of each supported operation;
- decimal and hexadecimal literals at type boundaries, narrowing casts, signed/unsigned conversion, and integer-to-float rounding;
- float overflow, subnormal values, positive and negative zero, NaNs, infinity, division by zero, and fused multiply-add/reassociation under strict and optimized modes;
- a host-sized integer compiled for 32-bit and 64-bit targets.

For each case, record compile-time result/rejection, runtime result/trap, exact output bits, diagnostic, build flags, compiler version, target triple, and whether a proof/query projection produces the same outcome. Include optimization-on and optimization-off builds. Compare two backends against one source-level expected-result table.

## 5. Cross-area implications and open hypotheses

- Mode-dependent overflow behavior can make debug/release executions observably different; LLMLang must decide whether build profiles are semantic inputs or merely diagnostic/performance profiles.
- Wrapping, saturating, trapping, and checked operations should be distinct in the semantic model if they produce different outcomes. A generic arithmetic operator should not silently select among them by target or optimization mode.
- Platform-sized integers weaken cross-target reproducibility when their width enters serialization, hashing, protocol layout, or proof propositions.
- Floating-point reproducibility requires more than naming an IEEE format: contraction, reassociation, denormal handling, rounding mode, NaN payloads, and library functions may vary by target or mode.
- Exact arithmetic and SMT integer reasoning do not automatically validate bounded machine arithmetic. The verification model must preserve width, signedness, overflow mode, and floating-point assumptions.

## 6. Next research and falsifiers

Create the fixture as a language-neutral outcome table first. Run it under two compiler/backend configurations per candidate model with pinned targets and flags. Link each observation to a typed semantic operation and to a proof encoding. Measure only after the expected semantics are fixed.

The trap-by-default vector is weakened if routine low-level code requires pervasive checked-result plumbing or makes performance/ABI contracts unusable. Defined wrapping is weakened if users repeatedly assume mathematical integers or if overflow bugs become difficult to detect. Build-mode-dependent semantics are weakened if the same source silently behaves differently in production. Strict floating-point defaults are weakened if target workloads cannot meet their performance needs without explicit optimized regions; fast modes are weakened if they make cross-target results unsuitable for required verification.

No LLMLang numeric representation, overflow rule, coercion policy, or floating-point mode is selected.

## 7. Sources and temporal limits

Official language references were consulted 2026-11-19. Rust, Swift, and Go references are rolling; Zig master is moving rapidly. Run the fixture against pinned releases and targets. This report does not claim full cross-platform conformance.
