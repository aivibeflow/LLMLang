# Research Scenario 78 — Floating-Point Reproducibility and IEEE Edge Cases

**Status:** Evidence-linked prior-art comparison; no LLMLang floating-point profile selected
**Research area:** RT-03 arithmetic semantics and observable behavior, RT-04 numeric types, RT-07 proof model, RT-09 backend preservation
**Updated:** 2026-11-19

## 1. Question and boundary

What does a floating-point type promise about value representation, rounding, exceptional values, comparisons, fused operations, and optimized execution—and which of those promises survive target changes?

Scenario 45 already lists floating-point axes and a discriminating fixture. This report expands the prior-art comparison rather than claiming a completed conformance experiment. It focuses on distinctions that affect reproducibility: IEEE value behavior versus exact NaN bits, source-level operation rounding versus fused execution, strict versus fast modes, and arithmetic values versus serialization/bit inspection. It does not survey decimal/fixed-point arithmetic, interval arithmetic, vector lane semantics, or establish correct rounding of transcendental functions across targets.

## 2. Prior-art comparison

### Rust: IEEE binary formats and detailed, non-identical NaN guarantees

Rust documents `f32`/`f64` as IEEE binary32/binary64 formats. Ordinary comparisons follow IEEE-like NaN behavior: NaN is unequal to itself and neither less nor greater, so the type does not implement total `Eq`/`Ord`. Signed zeros compare equal although arithmetic can retain their sign. Basic arithmetic uses round-to-nearest, ties-to-even. The primitive documentation also explicitly says arithmetic need not preserve NaN bit patterns; it specifies only constrained portions of resulting NaN encoding. Bit-conversion APIs can preserve representation, but that is a different contract from arithmetic value semantics.

This separates a useful language guarantee for numeric results from a stronger and usually unavailable guarantee that every arithmetic operation preserves NaN payload/signaling bits. Applications using floats as canonical serialized identities must define their own normalization or bitwise policy.

Sources: [Rust `f32` documentation](https://doc.rust-lang.org/core/primitive.f32.html), [Rust Reference — floating-point operations and numeric casts](https://doc.rust-lang.org/reference/expressions/operator-expr.html#numeric-cast).

### Go: IEEE comparisons, FMA freedom, explicit rounding barriers

Go specifies floating-point comparison according to IEEE 754 and states that floating/complex division by zero must follow IEEE 754 result rules, while whether it panics is implementation-specific. Implementations may fuse floating-point operations (including across statements) and produce a result different from individually rounded operations. An explicit conversion to the same destination precision forms a rounding barrier that prevents fusion which would discard that rounding. This permits optimization while retaining a source-level way to demand an intermediate precision boundary.

The specification's constants are exact at compile time subject to documented implementation minimums, but there are no constants denoting negative zero, infinity, or NaN; runtime/library construction is required for those values. Thus literal semantics and runtime IEEE values are separate.

Source: [Go specification — Floating-point operators](https://go.dev/ref/spec#Floating_point_operators), [Go specification — Constants](https://go.dev/ref/spec#Constants).

### Swift: IEEE-oriented protocol surface; target behavior needs a pinned conformance study

Swift's standard library provides `Float` and `Double` conforming to `FloatingPoint`; the documentation describes these operations in terms of IEEE 754 behavior and exposes classification, rounding, and bit-pattern-oriented APIs. Its generic protocol surface is useful for numeric abstractions, but a claim of bit-identical arithmetic across target architectures, compiler versions, or math libraries requires separate validation. `Float80` availability itself depends on target ABI, demonstrating that a named extended format can be target-dependent.

Sources: [Swift `FloatingPoint` protocol](https://docs.swift.org/swift/latest/documentation/swift/floatingpoint/), [Swift `Float80`](https://docs.swift.org/swift/latest/documentation/swift/float80/), [Swift Language Guide — The Basics](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/).

### Zig: strict default and locally scoped optimized semantics

The current Zig language reference offers binary16/32/64/128 plus extended formats, with float literals evaluated as `comptime_float` at the precision/operations of `f128`. Runtime operations default to `.strict`, described as strict IEEE compliance. A scope may opt into `.optimized`, where transformations can assume away NaN/infinity significance, treat signed zero as insignificant, use reciprocal approximations, contract multiply-add, or reassociate operations. The documented example produces different outputs in strict and optimized functions for the same input.

This makes the relaxed behavior explicit and scoped. It also means float mode becomes a semantic input for validation and reproducible artifacts. Master documentation is rolling and must be pinned to a Zig release before a formal comparison.

Source: [Zig language reference — Floats and Floating Point Operations](https://ziglang.org/documentation/master/#Floating-Point-Operations), [Zig `@setFloatMode`](https://ziglang.org/documentation/master/#setFloatMode).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Zig |
|---|---|---|---|---|
| Common binary types | `f32`, `f64` | `float32`, `float64` | `Float`, `Double`; `Float80` target-dependent | `f16/f32/f64/f80/f128`, target C long double |
| NaN equality/order | NaN unequal to itself and unordered; no default total `Eq`/`Ord` | Comparisons follow IEEE 754 | IEEE-oriented floating-point comparison APIs | Strict mode IEEE; optimized scope relaxes NaN assumptions/observations |
| NaN arithmetic payload | Arithmetic need not preserve exact bit patterns | No general cross-target payload-preservation guarantee stated in cited rule | Bit-pattern APIs exist; arithmetic portability requires target measurement | Strict/optimized mode changes which observations can be relied upon |
| Signed zero | `+0 == -0`; sign may persist in operations | IEEE behavior | IEEE-oriented API; verify operation/ABI details on targets | Strict mode; optimized may ignore sign |
| FMA/contraction | Must assess language/target and optimization contract for each profile | Permitted unless explicit rounding boundary prevents fusion | Needs pinned compiler/target experiment for exact guarantees | Strict vs optimized explicitly controls contraction permission |
| Rounding guarantees documented here | Basic arithmetic roundTiesToEven | Target precision and explicit conversions round; fusion may remove intermediate round | Protocol exposes rounding operations; arithmetic bitwise cross-target scope open | strict IEEE mode; compile-time float has `f128` precision/operations |
| Special values as source literals | Use constants/APIs or operations; NaN bits have separate caveats | No literal constants for `-0`, infinity, NaN | API construction/classification available | No syntax; standard library constructs special values |

This matrix is documentation-based. Rows with “needs experiment” are open questions, not evidence that an implementation is non-conforming.

## 4. Discriminating corpus and measurement record

For each format and target, include exact decimal and hexadecimal inputs plus raw bit patterns:

1. `+0`/`-0`: equality, reciprocal, sign inspection, min/max, hashing, text formatting, serialization round trip.
2. Quiet/signaling NaNs with multiple signs/payloads: equality, classification, comparisons, `min`/`max`, arithmetic, casts, FFI, and byte serialization.
3. Infinities, overflow, subnormals, underflow, and halfway rounding cases; record result bits and exception/trap behavior.
4. A well-known FMA discriminator for `a*b+c`, with and without an explicit intermediate-rounding conversion/store; test optimized and strict modes.
5. Reassociation cases such as `(x + large) - large`, cancellation, and reductions with multiple legal tree shapes.
6. Conversion edges among binary16/32/64/extended formats and integer conversions, including NaN/infinity/out-of-range values.
7. `sqrt`, `sin`, `cos`, `exp`, and `log` near hard-to-round inputs; classify whether the contract promises correctly rounded result, bounded error, or platform-library behavior.
8. Compare native, interpreter/VM, and each backend; rerun with compiler upgrades and architecture changes.

Record compiler version, target triple, CPU features, math library, optimization and float modes, exact source, input/output bits, text formatting, exceptions/traps, and whether the output is an allowed result or required unique result. Keep numeric equality, total-ordering policy, hash identity, and wire-format canonicalization separate.

## 5. Candidate vectors and cross-area consequences

- **F-A Strict reproducible default:** fix per-operation rounding and observable special-value behavior; relax only through an explicit, hash-visible region/profile. Stronger proofs and replay are easier; some targets may incur performance cost.
- **F-B IEEE value semantics with target latitude:** preserve specified numeric outcomes but leave selected payloads, exception flags, and math library results target-dependent. Portable source remains possible, while bitwise reproducibility requires a narrower target contract.
- **F-C Fast by default with explicit strict operations:** optimizers gain freedom but users and verifiers need to recognize every strict boundary; accidental scientific/financial misuse is a major API concern.
- **F-D Multiple named formats/profiles:** e.g. deterministic core floats, target-native math, and approximate/vector modes. This makes trade-offs explicit but multiplies types, APIs, test matrix, and proof obligations.

These are research vectors, not recommendations. Float mode, target features, backend math library, and any relaxed-math scope must be included in artifact identity and proof/cache inputs if they affect outputs. A source-level “deterministic” promise must say whether it covers only primitive operations, all transcendental functions, NaN bits, text rendering, or cross-machine serialized bytes.

## 6. Open decisions and falsifiers

- Should standard equality remain IEEE partial equality, with a separate total-order key for sorting/maps? How do collections treat NaN and signed zero?
- Should semantic hashing use numeric equality, normalized IEEE bits, or exact payload bits? Those choices differ for `+0/-0` and multiple NaNs.
- Which effects from floating operations are observable: only result values, exception flags, traps, timing, and generated diagnostics?
- Can an explicit cast/store act as a required rounding point across every backend?
- Is determinism required across optimization levels, target CPUs, runtime implementations, and math libraries, or only within a pinned execution profile?
- Are strict primitives sufficient for proofs, or must a verifier model IEEE floating-point theory and bounded formats rather than real arithmetic?

No LLMLang float format, equality/order rule, relaxed mode, serialization normalization, or deterministic-math guarantee is selected. F-A is weakened if measured workloads require broad relaxed math; F-C is weakened if its relaxed assumptions routinely invalidate user expectations or proof portability; target-latitude vectors are weakened if reproducibility requirements frequently demand pinning every environment detail.

## 7. Evidence quality and limits

Official references were opened on 2026-11-19. Rust primitive docs and Swift documentation are rolling; Go's specification may evolve; Zig master is especially time-sensitive. Pin language and toolchain editions/releases and run the corpus across a target matrix before writing normative claims. This report does not present compiler measurements or prove complete IEEE 754 conformance.
