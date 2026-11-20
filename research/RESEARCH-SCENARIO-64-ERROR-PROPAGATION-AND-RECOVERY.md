# Research Scenario 64 — Error Propagation, Context, and Recovery

**Status:** Evidence-linked prior-art comparison; no LLMLang error policy selected  
**Research area:** RT-03/04 recoverable failure, effects, typed errors, API boundaries  
**Updated:** 2026-11-19

## 1. Question and scope

When an operation fails, how does the error move across calls, gain context, get classified, and become handled or recovered? Separate error values from control-flow propagation; propagation from transformation; diagnostic context from public cause identity; expected failure from defects/panics; and local recovery from top-level reporting. Scenario 41 compares error type/API evolution, while this scenario compares propagation and recovery behavior.

## 2. Prior-art comparison

### Rust: explicit `Result` values and `?` with conversion

Recoverable failure is conventionally returned in `Result<T, E>`. Pattern matching or combinators make recovery explicit. `?` returns the success value or exits the current function with the error; where the destination error type differs, `From` conversion can map it. The caller chooses whether to retry, default, report, or propagate. Panics represent unrecoverable failure, not a typed recoverable channel. This yields visible call signatures and a value-level error channel, though generic composition and conversion policy can widen/erase distinctions.

Sources: [The Rust Book — Recoverable Errors with `Result`](https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html), [The Rust Book — To `panic!` or Not to `panic!`](https://doc.rust-lang.org/book/ch09-03-to-panic-or-not-to-panic.html), [Rust `Result`](https://doc.rust-lang.org/std/result/index.html).

### Swift: typed throws, propagation, and typed catch/rethrow

Throwing is part of a function type; `try` marks a potentially throwing call. A thrown error propagates through the current scope until caught by `do`/`catch`, and handlers may rethrow a different error. Typed throws can constrain the error type, while untyped `throws` erases to `any Error`; composition can require a shared type or explicit erasure. `rethrows` provides a static relation between callback throwing and the enclosing function. This separates error control flow from ordinary return values while retaining an explicit throwing effect in signatures.

Sources: [Swift Language Guide — Error Handling](https://docs.swift.org/swift-book/LanguageGuide/ErrorHandling.html), [Swift Declarations — throwing function types](https://docs.swift.org/swift-book/ReferenceManual/Declarations.html), [Swift Evolution SE-0413 — Typed throws](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0413-typed-throws.md).

### Go: explicit return checks and opt-in cause exposure

Functions conventionally return `error` as an ordinary result, and callers check it at the point of use. Wrapping with `%w`/`Unwrap` creates an inspectable chain; `errors.Is`/`As` traverse it. Whether to wrap is an API choice: wrapping makes the underlying cause observable to callers and may couple them to implementation details. The convention keeps control flow explicit and supports added context, but the compiler does not require a returned error to be checked or propagated.

Sources: [Go 1.13 — Working with Errors](https://go.dev/blog/go1.13-errors), [Go 1.13 Release Notes — Error wrapping](https://go.dev/doc/go1.13#error_wrapping), [Go Error Values FAQ](https://go.dev/wiki/ErrorValueFAQ).

### Zig: inferred error sets, `try`, and locally exhaustive handling

An error union carries either a value or an error. `try` propagates an error to the caller; a function's error set can be inferred or stated, making the propagation boundary part of the type. `catch` handles an error locally and can provide a fallback or branch on its identity. Error-return traces can preserve the path through propagated errors for diagnostics, with build-mode-dependent availability. Inference reduces annotation burden but makes signature visibility and inferred closure behavior important compatibility questions.

Sources: [Zig Language Reference — Errors](https://ziglang.org/documentation/master/#Errors), [Zig Language Reference — Error Return Traces](https://ziglang.org/documentation/master/#Error-Return-Traces).

## 3. Candidate policies

| Candidate | Propagation and recovery | Trade-offs |
|---|---|---|
| ER-A Explicit error value | `Result<T,E>` returned and matched; propagation is a desugared early return. | Uniform value semantics and easy local recovery; signatures may become nested/noisy and callers can ignore values absent lint/type effects. |
| ER-B Typed throwing effect | A function declares/infers an error effect; propagation follows call control flow to typed handlers. | Concise call-site propagation and statically visible effect; call composition, async interaction, and handler scope need precise rules. |
| ER-C Explicit checks with extensible error values | Error is an ordinary return plus explicit classification/wrapping API; no language-enforced propagation. | Simple interoperability and flexible diagnostics; unchecked failures and inconsistent wrapping conventions are easy. |
| ER-D Hybrid typed propagation with explicit boundary erasure | Closed or constrained errors internally, explicit conversion to open diagnostic/error value at selected API boundaries. | Balances exhaustive recovery with interop; requires rules for mapping, cause exposure, and compatibility. |

Cross-cutting axes: whether propagation can convert error types implicitly; whether wrapping exposes the cause contractually; whether errors form a chain or tree; whether catches must be exhaustive; default handling for unknown future cases; interaction with cleanup failures and owned return values; whether cancellation is an error; async/task aggregation; and whether panic/defect is distinct from recoverable failure.

## 4. Discriminating experiments

1. Use one call graph with two independent error types, a contextual annotation, retry/default recovery, and a top-level reporter. Record which signatures change under explicit value, typed effect, and inferred error-set profiles.
2. Add a new error case in a dependency and measure source compatibility, exhaustiveness diagnostics, dynamic classification, and API/interface hash changes.
3. Compare identity-preserving propagation, mapping/conversion, single-cause wrapping, multi-cause aggregation, and redaction. Test which underlying causes callers can inspect and which are promised API.
4. Inject cleanup failure while another error is pending; include transferred/owned results. Record primary-error precedence, both-error preservation, and ability to continue recovery.
5. Add cancellation, panic/defect, foreign errors, async child failures, and a non-exhaustive fallback. Compare type-check acceptance and runtime observations.
6. Capture diagnostics separately from semantic cause values: source locations, stack/error-return traces, allocation/latency, and debug/release behavior.

## 5. Current result

Prior art offers materially different boundaries: Rust makes recoverable errors ordinary typed values and uses a conversion-capable propagation operator; Swift models throwing as a function effect with scoped catching and optional type erasure; Go uses explicit result checks and treats cause-chain exposure as API policy; Zig couples propagated error sets to function types and supplies explicit local catches. All distinguish local recovery from propagation, but differ in compile-time enforcement, conversion/wrapping, and signature evolution. No LLMLang policy is selected. Typed async/task errors, cleanup composition, unknown future cases, and cause privacy remain open.
