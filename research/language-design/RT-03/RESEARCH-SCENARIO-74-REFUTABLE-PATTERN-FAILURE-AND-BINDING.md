# Research Scenario 74 — Refutable Pattern Failure and Binding

**Status:** Evidence-linked prior-art comparison; no LLMLang mismatch/control-flow policy selected  
**Research area:** RT-03 control flow, RT-04 typing/definite assignment, RT-09 diagnostics  
**Updated:** 2026-11-19

## 1. Question and scope

When a pattern might not match, how does the language represent that failure and scope any bindings? Separate the pattern's success test from the control-flow form that consumes failure. Scenario 54 compares pattern vocabulary, ordered matching, and exhaustiveness; this report focuses on refutability and failure surfaces: reject at compile time, branch, exit the enclosing scope, return a Boolean test, or produce an optional/result.

## 2. Prior-art comparison

### Rust: irrefutable declaration, conditional match, or mandatory diverging `else`

An ordinary `let` binding requires an irrefutable pattern; a possibly failing destructure is a compile-time error. `if let` and `while let` branch or iterate only when the pattern matches. `let PATTERN = EXPR else { ... }` makes failure handling explicit at a binding site, and its `else` block must diverge (for example, return, break, or panic), ensuring bindings are definitely available after the statement. The failure is control flow and is not implicitly turned into an exception or optional value.

Sources: [Rust Reference — Let statements](https://doc.rust-lang.org/reference/statements.html#let-statements), [Rust Reference — If let expressions](https://doc.rust-lang.org/reference/expressions/if-expr.html#if-let-expressions), [Rust Book — Refutability](https://doc.rust-lang.org/book/ch19-02-refutability.html).

### Swift: optional binding and `guard` with scope-shaped failure handling

Swift optional binding (`if let`, `while let`, and `guard let`) tests an optional and binds its payload only on success. In `if let`, the binding is local to the successful branch. `guard let` requires an `else` body that exits the current scope, leaving the unwrapped binding available afterward. This gives optional extraction explicit failure control flow without general pattern mismatch exceptions; the source form communicates whether success narrows a branch or establishes a value for the remainder of a function.

Sources: [Swift Language Guide — Optional Binding](https://docs.swift.org/swift-book/LanguageGuide/TheBasics.html#Optional-Binding), [Swift Language Guide — Early Exit](https://docs.swift.org/swift-book/LanguageGuide/ControlFlow.html#Early-Exit).

### Go: comma-ok values for selected partial operations

Go does not have general destructuring patterns, but several operations that may fail to find a value have a language-defined comma-ok form: map lookup, type assertion, and channel receive. The second result is a Boolean indicating success; on failure the primary value is the zero value of its type. A one-result assertion may panic on failure, while the two-result form reports it normally. This makes partiality explicit at the operation, but the convention is not a general pattern-matching construct and zero values can be confused with successful payloads unless the `ok` result is checked.

Source: [Go Specification — Assignments and comma-ok forms](https://go.dev/ref/spec#Assignment_statements).

### C#: Boolean pattern test with conditional definite assignment

C# `is` applies a pattern and returns a Boolean. A variable introduced by a declaration pattern is definitely assigned on the successful path, so normal Boolean control flow carries the binding; the value remains unavailable on the failing path. Switch statements/expressions provide multi-arm alternatives. This composes patterns with Boolean operators and guards, though definite-assignment rules and short-circuit structure must remain precise for complex expressions.

Sources: [C# Language Specification — Patterns](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-specification/patterns), [C# Language Specification — Definite assignment and `is`](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-specification/variables).

## 3. Candidate policies

| Candidate | Refutable binding failure | Trade-offs |
|---|---|---|
| PF-A — Irrefutable declarations only | Reject any possibly failing pattern in a declaration; branch forms handle mismatch. | Strong definite-binding invariant and clear diagnostics; optional extraction may require extra nesting. |
| PF-B — Explicit branch binding | Use `if/while let` forms whose bindings exist only in the success branch. | Local, visibly conditional values; nesting can grow for sequential checks. |
| PF-C — Exit-on-failure binding | Permit `let pattern = value else diverge/exit`, then expose bindings after the statement. | Flat success path and explicit failure policy; restricts failure branch to non-returning control flow. |
| PF-D — Boolean pattern test | Pattern test yields Bool and bindings are available only where the true condition is proven. | Composes with Boolean guards and conditions; flow-sensitive definite-assignment analysis grows in complexity. |
| PF-E — Value-level optional/result | Pattern operation returns `Option<Bindings>` or `Result<Bindings, E>`; caller chooses propagation/recovery. | Makes partiality composable as data; can duplicate matching and introduce wrapper/allocations depending on representation. |

These policies may coexist for different contexts; the language must state one canonical binding and failure rule for each syntactic form.

## 4. Discriminating experiments

1. Attempt to destructure `Some(x)`-like and nested product/variant patterns in an unconditional binding. Compare static rejection, runtime assertion, optional result, and branch lowering.
2. Test successful bindings after `if` branches, short-circuit `&&`/`||`, negation, guards, early returns, loops, and labeled exits. Verify definite assignment and scope boundaries.
3. Test sequential extraction of multiple optional/variant values using nested branches, exit-on-failure, Boolean tests, and `Option`/`Result` composition; compare control-flow graph size and diagnostics.
4. Inject failure at each nested subpattern and inspect whether earlier bindings, moves, borrows, or resource cleanups have occurred. Ensure failed matches do not leak partially initialized bindings.
5. Test `else` branches that return, throw, break, continue, panic, diverge, or produce a value; specify which control transfers satisfy exit-on-failure requirements.
6. Compare API ergonomics for recoverable versus fatal mismatch: parse/validation failure, enum dispatch, optional lookup, type test, and user input. Ensure source syntax communicates failure policy rather than silently choosing one.

## 5. Current result

Refutability is not itself a failure policy. Rust and Swift distinguish branch-local extraction from exit-on-failure bindings; Go exposes selected lookup/type/channel failures with explicit status results; C# ties pattern-bound variables to successful Boolean paths. Reusing one bare destructuring declaration for both guaranteed and partial matches would obscure control flow and definite assignment. No LLMLang pattern mismatch policy is selected; ownership/cleanup behavior on partial matches and integration with error propagation remain open.
