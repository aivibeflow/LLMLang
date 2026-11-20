# Research Scenario 86 — Async/Await Syntax and Contexts

**Status:** Evidence-linked prior-art comparison; no LLMLang async syntax selected  
**Research area:** RT-03 expression and declaration grammar, RT-04 async typing/effects, RT-11 module/build boundaries  
**Updated:** 2026-11-19

## 1. Question and scope

How is asynchronous code marked syntactically, where may suspension syntax occur, and how does async context propagate through closures, local functions, and module entry points? This report compares grammar and placement rules only.

Scenario58 studies async function types, call start behavior, task creation, executors and scheduling; Scenario40 and Scenario57 cover cancellation/cleanup and task lifetime. Here those runtime choices are held apart from syntax: declaration marker placement, await operator position/scope, async closure/block forms, propagation, and top-level await.

## 2. Prior-art comparison

### Rust: prefix `async`, postfix `.await`, explicit async blocks/closures

Rust writes `async fn f()` and `operand.await`. The await expression is postfix and is legal only in an async context. Async blocks and async closures create such a context; the outer function does not become async merely because it contains a nested async block. `await` binds to the future operand, while its result is the output value. Top-level await is not a general module/file form in the cited language reference; callers use an async entry/runtime strategy.

Sources: [Rust Reference — Await expressions](https://doc.rust-lang.org/reference/expressions/await-expr.html), [Rust Reference — Async blocks](https://doc.rust-lang.org/reference/expressions/block-expr.html#async-blocks), [Rust `async` keyword](https://doc.rust-lang.org/stable/core/keyword.async.html).

### Swift: `async` in the signature, prefix `await` over an expression

Swift places `async` after the parameter clause in the function signature: `func f() async -> T`. Calls to async functions must be in the scope of an `await` expression. The `await` operator is a prefix and marks potential suspension points. Its expression coverage matters: for an infix expression, `await` may apply across the expression unless parenthesized; `try` must precede `await` when both occur. `await` is restricted in contexts such as `defer` bodies and synchronous autoclosures.

Sources: [Swift Language Reference — Function declarations and asynchronous functions](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/), [Swift Language Reference — Await operator](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/).

### C#: `async` modifier and prefix `await` inside async methods/lambdas

C# uses the `async` modifier on methods, lambdas, and anonymous methods; `await expression` suspends evaluation of the enclosing async method when needed. The context rule is structural: a synchronous local function nested inside an async method is still synchronous and cannot contain `await`. Async methods execute synchronously until an await that cannot complete immediately. The `async` keyword is contextual rather than globally reserved.

Sources: [C# reference — `async` keyword](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/async), [C# reference — `await` operator](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/await), [C# reference — Lambda expressions](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/lambda-expressions).

### JavaScript/ECMAScript: `async function`, prefix `await`, and module top-level await

ECMAScript places `async` immediately before `function` (with a no-line-terminator restriction); async methods and arrow functions have their own forms. `await` is a prefix expression recognized in async function bodies and modules. In script parsing contexts it can instead be an identifier. Top-level await is therefore tied to the module syntactic goal, making module evaluation asynchronous for dependents. Async function bodies return promises, but this report does not compare their runtime scheduling with other models.

Source: [ECMAScript 2026 Language Specification — Async Function Definitions and Await expressions](https://tc39.es/ecma262/2026/multipage/ecmascript-language-functions-and-classes.html#sec-async-function-definitions).

## 3. Comparison matrix

| Dimension | Rust | Swift | C# | ECMAScript / JavaScript |
|---|---|---|---|---|
| Async declaration spelling | `async fn f()` | `func f() async` | `async Task<T> F()` | `async function f()`; async arrow/method forms |
| Await position | Postfix `future.await` | Prefix `await expression` | Prefix `await expression` | Prefix `await expression` |
| Permitted context | Async fn/block/closure | Async context | Async method/lambda/anonymous method | Async body or module goal |
| Async closure/block | Async closure and `async {}` block | Async closure/context-sensitive closure use | Async lambda/anonymous method | Async arrow/function expression |
| Nested sync closure behavior | Async context boundary follows async closure/block syntax | Closure context/type can constrain await validity | Sync local function cannot await, even inside async method | Nested function body has its own async marker/context |
| Top-level await | Not general source-file syntax in cited reference | Requires async entry/context; no general module TLA in cited syntax | Async `Main` method rather than arbitrary file-level await | Allowed in modules, not classic scripts |
| Contextual keyword details | `async`/`.await` lexical forms | `async` and `await` declaration/expression keywords | `async` is contextual; await is an operator token | Grammar parameters make await contextual to async/module goal |
| Mixed error + await spelling | `?` propagation may compose with `.await` | `try await expr` order is constrained | `await` plus `try/catch` statement/expression control | Rejection propagates as abrupt completion in async body |

## 4. Discriminating syntax fixtures

1. Declare async functions, methods, closures, anonymous functions, and blocks. Compare marker position, omitted return types, generic/type annotations, and parser ambiguity.
2. Test await placement: `await f()`, `f().await`, `await (a + b)`, `(await a) + b`, chained member/call/index expressions, and await on a non-async value.
3. Place await inside an outer async function but nested synchronous local function/closure, async closure, `defer`/cleanup, autoclosure, lock/critical-section body, and macro expansion. Record context inheritance and diagnostic spans.
4. Combine async suspension and error propagation: `try await f()`, `await try f()`, `f().await?`, `await? f()`, `await` inside `catch`, and cleanup/defer bodies.
5. Test top-level await in script, module, library, package initializer, test file, and executable entry unit. Determine whether imports/dependents become async and how cycles report.
6. Check line breaks after `async`, before `function`, around postfix `.await`, and between `await` and its operand; test semicolon/newline insertion interactions under Scenario53 rules.
7. Test async calls in default arguments, property initializers, constructors, getters, protocol/interface declarations, and function types.

Record parse tree, async-context boundary, suspension-point spans, required call-site markers, source maps, module evaluation dependencies, and diagnostics. Keep this corpus separate from execution traces that determine when tasks start or which thread runs them.

## 5. Candidate axes and implications

- **Declaration marker placement:** prefix modifier, signature effect after parameters, or an explicit wrapper/task return type. Placement affects readability and type syntax but does not itself determine eager/lazy execution.
- **Await position:** postfix attaches suspension to one operand; prefix may mark a wider expression unless precedence/parentheses are precise.
- **Required versus optional await:** mandatory marker makes possible suspension reviewable; optional/implicit await reduces annotation but hides interleaving points.
- **Async context propagation:** explicit async on every function/lambda boundary is locally visible; inherited context reduces syntax but can make nested callbacks change behavior unexpectedly.
- **Async blocks/closures:** first-class localized async regions support composition; they require clear capture, return, error and identity rules.
- **Top-level await:** improves scripts and module initialization ergonomics; it makes module graph evaluation async and can complicate dependency cycles and startup failures.
- **Error operator ordering:** integrating `try`/`?` with await can be concise, but grammar and diagnostic order should be stable and unambiguous.
- **Keyword reservation:** reserved words simplify contextual parsing; contextual keywords ease evolution but require explicit lexical context rules.

Surface syntax choices influence parser errors, formatter rules, async propagation diagnostics, code generation and source-to-IR mapping. They do not select task scheduling, cancellation, executor affinity or parallelism.

## 6. Open questions and falsifiers

- Should async be a declaration modifier/effect, a return wrapper, or both at explicit boundaries?
- Should suspension use postfix operand syntax or prefix `await` expression syntax?
- Must every suspension be marked, including calls hidden under operators and convenience APIs?
- Can an async context flow into ordinary closures/local functions, or must each boundary opt in?
- Are async blocks necessary if async closures and functions exist?
- Does top-level await belong in modules, only executable entry points, or neither?
- How does await compose grammatically with checked/recoverable errors and cleanup constructs?
- Should `async` be reserved globally or contextual to a declaration form?

Postfix await is weakened if generated or nested fluent expressions become hard to scan and parse. Prefix await is weakened if its operator scope changes across infix expressions or requires frequent parentheses. Mandatory markers are weakened if they produce noisy code and authors routinely bypass them; optional markers are weakened if suspension becomes invisible in code review. Top-level await is weakened if asynchronous module graphs make startup ordering and cycles hard to reason about.

No async declaration syntax, await operator position, context-propagation rule, or top-level await policy is selected.

## 7. Sources and temporal limits

Primary references were consulted on 2026-11-19: Rust Reference (rolling), Swift language docs 6.4, current C# language reference, and ECMAScript 2026. Pin language versions for conformance tests. This is grammar/context analysis, not a runtime performance or scheduling comparison.
