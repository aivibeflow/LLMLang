# Research Scenario 59 — Boolean Short-Circuit and Evaluation Order

**Status:** Evidence-linked prior-art comparison; no LLMLang Boolean operator/effect-order policy selected  
**Research area:** RT-03 expression semantics, RT-04 effects and operator typing, RT-09 optimization  
**Updated:** 2026-11-19

## 1. Question and scope

How do logical operators control operand evaluation, and which evaluation order is observable when expressions can call effectful, diverging, blocking, or failing code? Keep separate: (1) truth-table result, (2) whether the right operand is evaluated, (3) operand order for strict operators, (4) whether operators can be overloaded, (5) exception/error/divergence propagation, and (6) compiler freedom to reorder or eliminate expressions. Scenario 49 surveys operators generally; this scenario isolates conditional evaluation and its interaction with effects and optimization.

## 2. Prior-art comparison

### Rust: language-defined lazy Boolean operators, not overloadable

Rust defines `&&` and `||` as lazy Boolean operators. The right operand runs only if the left operand does not determine the answer (`true && rhs`, `false || rhs`). Bitwise `&` and `|` are distinct strict operators. Rust explicitly documents that `&&` and `||` cannot be overloaded; their conditional behavior needs semantics beyond an ordinary binary trait method. This keeps the skip condition language-defined even when other operators dispatch through traits.

Sources: [Rust Reference — Lazy Boolean operators](https://doc.rust-lang.org/reference/expressions/operator-expr.html#lazy-boolean-operators), [Rust `core::ops` guidance](https://doc.rust-lang.org/stable/core/ops/index.html).

### Go: conditional logical operands plus a bounded left-to-right rule

Go defines `p && q` as `if p then q else false` and `p || q` as `if p then true else q`; the left operand is evaluated first and the right only when required. Its order-of-evaluation rule guarantees lexical left-to-right order for function calls, method calls, channel receives, and binary logical operations, but does not specify an order for every subexpression or composite literal component. Therefore, the logical operator has a clear conditional rule while unrelated expression details can remain nondeterministic when they interact through state or effects.

Sources: [Go specification — Logical operators](https://go.dev/ref/spec#Logical_operators), [Go specification — Order of evaluation](https://go.dev/ref/spec#Order_of_evaluation).

### Swift: standard logical operators express laziness through `@autoclosure`

Swift's standard `Bool.&&` interface takes the right-hand Boolean as an `@autoclosure`, and the closure is evaluated only when called. Swift documentation describes `@autoclosure` as a way to defer evaluating an argument expression without requiring closure syntax at the call site. This places a key part of short-circuit behavior in the standard operator implementation and its function type. The trade-off is that library-defined laziness becomes possible but readers must inspect the operator's signature/implementation to know when a deferred expression runs.

Sources: [Swift Bool operator declaration](https://docs.swift.org/latest/documentation/swift/bool/), [Swift Language Guide — Closures and autoclosures](https://docs.swift.org/latest/documentation/the-swift-programming-language/closures/), [Swift Types — Function types](https://docs.swift.org/latest/documentation/the-swift-programming-language/types/).

## 3. Candidate models and consequences

| Candidate | Definition | Consequences |
|---|---|---|
| B-A Intrinsic lazy Boolean operators | `and`/`or` (or `&&`/`||`) are syntax with specified left-to-right conditional evaluation and cannot be overloaded. | Stable control-flow/effect semantics and easy compiler modeling; domain-specific truth-like values need named methods or explicit combinators. |
| B-B Strict Boolean operators | Both operands always evaluate left-to-right; conditional logic uses `if` or a dedicated lazy form. | Uniform strict-expression rule; unsafe/expensive right sides cannot be guarded with the operator and source can be more verbose. |
| B-C Library-defined lazy operators | Operator receives a deferred right operand (autoclosure/thunk) and decides whether/when to evaluate it. | Flexible abstractions; operator meaning depends on selected overload, effect behavior is less apparent, and generic reasoning/tooling is harder. |
| B-D Mixed rule with distinct strict and lazy tokens | Reserve separate tokens for strict Boolean combination and short-circuit control flow. | Makes skip behavior visible at syntax; adds operator vocabulary and precedence/formatter surface. |

These models are compatible with different strict-operator order guarantees. Independently choose: define every operand left-to-right; define only a subset of evaluation events (as Go does); or leave order unspecified only for proven-pure operands. If effectful order is unspecified, observable behavior may differ across compilers/targets; if optimization can reorder only pure expressions, purity must be soundly available to the compiler.

## 4. Interaction with effects and failures

With `false && write_log()`, a short-circuit rule suppresses the write; with strict evaluation it occurs even though the final Boolean is false. With `true || fail()`, lazy evaluation suppresses the failure; with strict evaluation, the failure is observable. Similar witnesses cover divergence, blocking receives, resource acquisition, authorization checks, and cancellation. Thus a Boolean operator is a control-flow construct whenever operands are effectful; it cannot be modeled as an ordinary truth-table function over two already-evaluated values.

Optimization must preserve the selected observable semantics. Reordering or eliminating an expression is safe only if the language's effect/purity guarantees show that it cannot alter values, errors, I/O traces, state, resource outcomes, divergence, or synchronization. Algebraic identities (for example `false && x = false`) cannot justify evaluating `x`; eager evaluation would change behavior.

## 5. Discriminating experiments

1. Use right operands that append a trace marker, return an error, diverge, block on a channel, acquire a resource, or fail authorization. Cover all four left truth values and assert which events occur.
2. Put effectful calls in both operands of strict arithmetic/comparison operators and in aggregate literals/assignments; compile with two compilers and optimization levels to detect unspecified order.
3. Compare intrinsic lazy operators with overloaded/autoclosure forms. Test generic constraints, nested operators, error propagation, and evaluation exactly-once behavior.
4. Run optimizer differential tests on equivalent expression rewrites and compare full observations (value, error, trace, resource state, and termination) rather than result values only.
5. Test guard patterns such as `ptr != null && ptr.field > 0`, checked indexing, optional values, and authorization predicates to ensure the evaluation guarantee supports intended idioms.

Record language/compiler versions, optimization flags, traces, and which events are normative versus implementation-dependent. Keep unspecified cases explicitly marked; do not infer a full left-to-right guarantee from one operator's rule.

## 6. Current result

Prior art distinguishes built-in lazy control-flow operators, strict value operators, and library-level deferred operands. It also shows that a language may specify short-circuiting precisely while leaving other expression ordering partially unspecified. LLMLang still needs a coherent rule linking expression evaluation, effect summaries, error/divergence behavior, and optimizer legality; no candidate is selected.
