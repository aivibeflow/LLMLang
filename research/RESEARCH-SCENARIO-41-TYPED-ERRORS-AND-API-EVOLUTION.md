# Research Scenario 41 — Typed Errors and API Evolution

**Status:** Evidence-linked comparison; no LLMLang error model selected
**Research area:** RT-03/04 error outcomes, type contracts, and compatibility
**Updated:** 2026-11-19

## 1. Question

How should a function communicate recoverable failure, how much of its error space is part of its static type, and what happens to callers when that space changes or is wrapped with context?

Separate at least four dimensions: the control-flow mechanism (returned sum, thrown value, or additional return); the static precision of the error set/type; the caller's obligation to handle or propagate; and the compatibility policy when new failure cases are introduced. Panic, abort, cancellation, and divergence remain distinct terminal outcomes unless a profile deliberately converts them.

## 2. Prior-art comparison

### Rust: explicit `Result<T, E>` sum and propagation conversion

Rust's standard `Result` is an enum with `Ok(T)` and `Err(E)`. The `?` operator propagates an `Err` from the enclosing function; its conversion behavior lets callers compose functions with different error types when the target error supports conversion. The value is explicit in the function type and can carry arbitrary typed payloads, including owned data, but the two standard variants do not express an outcome that simultaneously carries success-shaped `T` and `E`; that requires a custom sum/product constructor such as the COR-13 error-with-value case.

Sources: [Rust `Result`](https://doc.rust-lang.org/std/result/), [Rust Book — recoverable errors](https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html).

### Zig: finite error sets and error unions

Zig combines an error-set type with a payload type as an error union, written `E!T`. The compiler can infer error sets, and `||` merges sets. Its reference says inferred sets act generically and are incompatible with recursion, can complicate function pointers, and may vary across build targets; explicit error sets are recommended in those cases. A broad `anyerror` is available but generally discouraged because it hides the statically known possibilities and weakens generated documentation and exhaustive handling.

This is a compact, statically inspectable outcome model. Error-set closure can force a choice between changing a public signature as callees evolve and widening/erasing the set; the language reference's recursion and target limits matter for generic APIs and reproducible interface identity.

Source: [Zig language reference — error sets and error unions](https://ziglang.org/documentation/master/#Error-Union-Type).

### Swift: typed throws with an explicit erasure boundary

Swift 6.0 implemented SE-0413 typed throws. A signature such as `throws(ParseError)` constrains the function to one concrete thrown type; untyped `throws` uses `any Error`. The proposal explicitly chooses one error type per function and recommends `any Error` when multiple error types must escape. A `do` block that sees different thrown types can infer an erased `any Error`, while a typed `do throws(E)` can pin a shared error type. Typed throws is part of function types and can be erased to untyped throws; the proposal notes source-compatibility considerations for references to generic typed-throwing functions.

This allows narrow APIs to keep error identity without requiring every API to use closed enums. Composition across independently typed subsystems can require explicit mapping or deliberate erasure. Swift's proposal also says type-inference changes originally planned behind `FullTypedThrows` were not implemented in Swift 6.0; current behavior should be checked against the selected compiler release.

Source: [Swift Evolution SE-0413 — Typed throws](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0413-typed-throws.md).

### Go: open error interface, contextual wrapping, and stable classification

Go returns errors as ordinary `error` interface values, commonly as an additional result. Wrapping can add context while preserving an underlying error through `Unwrap`; callers use `errors.Is` and `errors.As` to classify through the chain. The official Go 1.13 guidance makes wrapping a deliberate API choice: wrapping exposes underlying error details to callers, while not wrapping avoids exposing implementation details. The `errors` package also supports joined trees of errors.

This model keeps local implementation changes flexible, but static function signatures do not enumerate all possible errors or force exhaustiveness. Public error behavior relies on documented classification guarantees and on callers inspecting through the provided API rather than concrete representation.

Sources: [Go 1.13 — Working with Errors](https://go.dev/blog/go1.13-errors), [Go `errors` package](https://pkg.go.dev/errors), [Go Error Values FAQ](https://go.dev/wiki/ErrorValueFAQ).

## 3. Discriminating dimensions

| Dimension | Rust `Result` | Zig error union | Swift typed throws | Go error value |
|---|---|---|---|---|
| Error in function type | `E` generic parameter | Error-set member(s) in `E!T` | One thrown type, or erased `any Error` | Only broad `error` result type |
| Main control flow | Explicit pattern/value propagation (`?`) | Explicit union propagation (`try`) | Throw/`try`/`catch` control flow | Ordinary return and explicit checks |
| Composition | Convert `E` to enclosing error type | Merge/infer sets, with recursion/function-pointer limitations | Map to common type or erase to `any Error` | Wrap/unwarp and classify with `Is`/`As` |
| Exhaustive caller handling | When caller matches a closed enum it chooses | `switch` can cover known set | Typed closed error enum can be exhaustively matched where required | No static exhaustiveness over concrete errors |
| Context without losing cause | Custom error constructor/source chain | Explicit payload/context constructors | Wrap/map into a chosen error type or erase | `Unwrap` / `%w`; deliberate exposure choice |
| Extension pressure | New enum case can affect matches and conversions | Error-set signature and inferred closure can change | Narrow typed signature cannot throw a new unrelated type without mapping/widening | Implementation error can change while `errors.Is`/`As` behavior remains contractual |

This table compares affordances, not total soundness or ergonomics. All four can be supplemented with domain types and runtime checks.

## 4. Shared API evolution fixture

Consider `load_config(path)`: initially it can return `Missing` or `Malformed`; a later implementation adds `PermissionDenied`, wraps an OS error with path/context, and may fail after producing partial content.

Check the following independently for each representation:

1. Does a caller need to change when a new case is introduced?
2. Can the caller branch on a stable domain classification while retaining diagnostic detail?
3. Can the implementation wrap a private OS error without making it part of the public contract?
4. Is the error set inferred from transitive callees, explicitly declared, or hidden behind a broad type?
5. Can a single outcome carry both partial value/ownership and the error, as in COR-13?
6. How do dynamic dispatch, FFI, plugins, and platform-specific failures affect the claimed closed set?

Useful variants include a private error wrapped under a public `LoadError`, a new public variant, widening `throws(ParseError)` to `throws(any Error)`, adding a platform-specific error set, and a cleanup failure concurrent with the primary error. Record source compatibility, binary/interface identity, catch/match behavior, and caller-visible classification for each.

## 5. Cross-area implications and next probe

- Static error precision is not the same as full effect information: error types alone do not describe successful I/O, ordering, blocking, partial effects, or authority requirements.
- Closed error sets improve exhaustiveness but couple the producer's evolution to caller branch coverage; open/wrapped errors improve implementation flexibility but shift obligations to documented stable classification and tests.
- Broad erasure (`any Error`, `anyerror`, or an open interface) is an API boundary decision. Record where precision is intentionally lost and whether it can be recovered.
- Error constructors must be tested together with resource payloads and cleanup debt; `Result<Owned<T>, E>` cannot by itself encode both `E` and an owned `T` in one ordinary variant.
- Error aggregation needs specified ordering, deduplication, primary-error precedence, and inspectability. A joined error tree and an error-with-value constructor answer different questions.

Next, extend the shared corpus with matched API evolution fixtures across calls, branch matches, effectful operations, resource ownership, and FFI. Define observable success/error/cancel/panic outcomes independently of surface syntax and test exactly which public signature/hash changes when the implementation adds a failure mode. This report selects no LLMLang error representation.

## 6. References and limits

The linked sources are official language or project documentation consulted 2026-11-19. Zig's `master` reference is moving; pin a release before relying on details. Swift typed throws is described by a language-evolution proposal implemented in Swift 6.0, with some originally proposed inference changes explicitly deferred. These are design comparisons, not compatibility experiments in LLMLang.

## 7. Versioning policy for a public error contract

Static error shape and compatibility policy are related but distinct. A language/library can expose a closed type and still reserve the right to extend it by requiring callers to handle unknown cases from the start.

| Ecosystem mechanism | Policy before adding a new public error | Effect of adding a new error case/type |
|---|---|---|
| Rust `#[non_exhaustive]` | Downstream code must include a wildcard arm; only the defining crate can match exhaustively | Adding variants does not break downstream exhaustive matches because they were disallowed; adding this attribute later changes downstream usage and is a semver-major change per Cargo guidance |
| Swift resilient enum | In library-evolution mode, non-`@frozen` public enums are compiled to tolerate member additions; clients use `@unknown default` to account for future cases | Adding a case can preserve ABI compatibility; marking the enum `@frozen` opts out and disallows adding, removing, or reordering cases without breaking ABI |
| Java checked exception | Callers must catch or declare checked exceptions exposed by source signatures | JLS says changing `throws` clauses does not break existing binaries because checked only at compile time; adding a checked exception can require source callers to handle/redeclare it on recompilation |
| Zig explicit error set | Error set is stated in the return type and callers can switch on known members | Extending the set changes the public return/error type and can require callers or function-pointer types to be updated |
| Zig inferred error set | Error set is derived from implementation and transitive calls | A body/callee change can change inferred API type; inference is incompatible with recursion and can complicate function pointers and cross-target consistency |
| Go `error` interface | Function type does not close the set; stable behavior is documented via wrapping/classification conventions | A new concrete error can preserve the signature, but callers only retain stable behavior if `errors.Is`/`As` classification contracts are documented and preserved |

The table separates source compatibility, binary compatibility, and error-classification compatibility. “Binary compatible” does not mean old callers handle a newly thrown condition correctly; “open” does not mean callers have a reliable classification contract; and a wildcard fallback does not make a newly added condition semantically equivalent to prior cases.

Sources: [Rust `non_exhaustive`](https://doc.rust-lang.org/std/attribute.non_exhaustive.html) and [Cargo SemVer guidance](https://doc.rust-lang.org/cargo/reference/semver.html); [Swift library evolution](https://www.swift.org/blog/library-evolution/) and [`@frozen`](https://docs.swift.org/latest/documentation/the-swift-programming-language/attributes/); [Java Language Specification §13.4.21](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-13.html); [Zig error sets](https://ziglang.org/documentation/master/#Error-Set-Type); [Go error wrapping](https://go.dev/blog/go1.13-errors).
