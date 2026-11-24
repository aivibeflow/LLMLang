# Research Scenario 87 — Async/Await Parser and Diagnostic Corpus

**Status:** Proposed conformance corpus; cases are specified but have not been run against an LLMLang parser
**Research area:** RT-03 syntax/diagnostics, RT-04 async effects, RT-11 module boundaries
**Updated:** 2026-11-19

## 1. Question and relation to prior work

What must a shared parser and diagnostic suite distinguish before LLMLang chooses async declaration syntax, await position, context boundaries, or module entry behavior?

[Scenario 86](RESEARCH-SCENARIO-86-ASYNC-AWAIT-SYNTAX-AND-CONTEXTS.md) compares prior-art syntax. [Scenario 58](../RT-10/RESEARCH-SCENARIO-58-ASYNC-FUNCTION-TYPES-AND-SCHEDULING.md) compares function types and task start/scheduling. This scenario turns Scenario 86's open parser/diagnostic fixture gap into a bounded corpus design. It does not choose LLMLang syntax, specify runtime scheduling, or claim that these cases have been implemented.

## 2. Evidence that motivates the corpus

- Rust permits `.await` only in an async context. Async blocks create a new context, so fixtures must test both context entry and the enclosing synchronous scope; the reference error index gives `E0728` for await outside an async context. Sources: [Rust Reference — Await expressions](https://doc.rust-lang.org/reference/expressions/await-expr.html), [Rust error E0728](https://doc.rust-lang.org/stable/error_codes/E0728.html), [Rust Reference — Async blocks](https://doc.rust-lang.org/reference/expressions/block-expr.html#async-blocks).
- Swift uses prefix `await`, restricts it to asynchronous contexts, excludes `defer` bodies and synchronous autoclosures, and specifies how it scopes across infix expressions and combines with `try`. These motivate dedicated precedence and syntactic-context fixtures. Source: [Swift Language Reference — Expressions](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/).
- C# allows `await` in async methods/lambdas, but a nested synchronous local function does not inherit that context; `lock` bodies also reject it. Its compiler diagnostics identify missing async context, while specific restrictions differ by language version (for example, catch/finally restrictions changed after C# 5). Sources: [C# await operator](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/await), [C# async/await compiler diagnostics](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-messages/async-await-errors).
- ECMAScript's grammar parameterizes await availability by syntactic context, distinguishes async function bodies and modules, and has a no-line-terminator restriction between `async` and `function` in function forms. This motivates separating lexical/grammar failures from async-context validation and testing script versus module goals. Source: [ECMAScript 2026 — Async function definitions](https://tc39.es/ecma262/2026/multipage/ecmascript-language-functions-and-classes.html#sec-async-function-definitions).

These are differences in grammar and context rules, not evidence that one rule is best for LLMLang. The proposed corpus records the reference language/version/context rather than copying vendor-specific diagnostic wording.

## 3. Fixture record format

Each fixture should store:

| Field | Purpose |
|---|---|
| `id` | Stable, unique case identifier. |
| `source` | Minimal complete snippet, including enclosing declaration/module context. |
| `language_profile` | Candidate syntax profile and version/goal (for example, ECMAScript script or module). |
| `expected_stage` | Lex, parse, contextual validation, or type/effect check. |
| `expected` | Accept, or one primary diagnostic category; avoid brittle exact wording. |
| `span` | Expected primary span and whether a related declaration span is useful. |
| `recovery` | Whether later declarations should still parse after the error. |
| `rationale` | Prior-art distinction or LLMLang rule being explored. |

The harness should compare normalized diagnostic category, primary source range, and recovery point. Exact message text, color, caret rendering, and editor quick-fix wording are presentation tests and should be versioned separately. A single source snippet may have different results under different language profiles; do not call that disagreement a compiler bug until the profile is fixed.

## 4. Core fixture matrix

The examples below are abstract test intentions. `async fn`, `await expr`, and `expr.await` are placeholders for candidate profiles, not LLMLang syntax.

| ID | Minimal test shape | Expected property under test | Failure category if rejected |
|---|---|---|---|
| AWAIT-001 | `async fn f() { await g() }` | Declaration marker establishes async body context; await form is profile-specific. | Parse or context, depending on profile. |
| AWAIT-002 | `fn f() { await g() }` | A synchronous function cannot use await unless the selected profile allows context inference. | Contextual validation; primary span on await, related span on function header. |
| AWAIT-003 | `async fn f() { fn inner() { await g() } }` | Nested synchronous function does not silently inherit async context. | Contextual validation at inner await. |
| AWAIT-004 | `async fn f() { async fn inner() { await g() } }` | Explicit nested async declaration establishes a fresh async body. | Accept if nested async declarations are in the profile. |
| AWAIT-005 | `async fn f() { let c = || await g(); }` | Anonymous closure context behavior is explicit: inherited, inferred, or requires async marker. | Parse/context, with diagnostic on closure boundary. |
| AWAIT-006 | `async fn f() { let c = async || await g(); }` | Explicit async closure form and its body context are unambiguous. | Accept/reject according to grammar profile; do not infer runtime task behavior. |
| AWAIT-007 | `async { await g() }` inside sync body | Async block enters an async context without changing enclosing function context. | Accept only in profiles with async blocks. |
| AWAIT-008 | `await (a + b)` versus `(await a) + b` | Prefix/postfix placement and precedence are stable and grammar-tested. | Parse or type/effect, not scheduling. |
| AWAIT-009 | `await a + b` | Prefix-await expression extent is specified; parentheses should produce predictable scope. | Parse/precedence or missing-await context, per profile. |
| AWAIT-010 | `try await g()` and `await try g()` | Error propagation operator composition and diagnostic order are explicit. | Parse/context/type-effect according to selected ordering. |
| AWAIT-011 | `defer { await g() }` | Cleanup-body suspension policy is independent of ordinary async context. | Contextual restriction or accept; profile must state cleanup semantics separately. |
| AWAIT-012 | `sync_autoclosure(await g())` in async body | Delayed synchronous closure does not accidentally inherit a suspension context. | Contextual validation at await. |
| AWAIT-013 | `lock { await g() }` or equivalent protected critical section | Suspension restrictions for lock-like constructs are explicit and tied to lock semantics/version. | Contextual restriction or accept only if unlock/reacquire behavior is specified. |
| AWAIT-014 | Top-level `await g()` in script/file versus module | Compilation-unit goal controls top-level await; script/module distinction is represented by metadata. | Parse/context depending on module goal. |
| AWAIT-015 | `async` line break `function f() {}` (ECMAScript reference form) | Newline-sensitive grammar is handled at lex/parse stage, rather than as an async-context error. | Parse/ASI profile diagnostic. |
| AWAIT-016 | `await` in parameter/default initializer of an async declaration | Parameter-evaluation context is explicit and distinct from function body context. | Parse or contextual validation at initializer. |
| AWAIT-017 | Await operand is not awaitable | Parser accepts syntactically valid await; semantic suitability is reported at type/effect stage. | Type/effect diagnostic, not parse failure. |
| AWAIT-018 | Missing operand / malformed postfix chain `value.await.` | Grammar errors identify the smallest useful token range and recover at the next statement/declaration. | Parse with recovery assertion. |

## 5. Cross-case invariants and diagnostic quality

1. **Context is lexical and structural.** Test function, nested function, closure, async closure/block, defer/cleanup, and module boundaries separately. Every accepted context-establishing form needs a paired negative case showing whether it changes only its own body.
2. **Syntax precedes semantic suitability.** An invalid token sequence is a parse diagnostic. A syntactically valid await on an unsupported operand belongs to type/effect checking. An await in a forbidden region is a context diagnostic. Avoid cascades that report all three for one root fault.
3. **Operator scope is observable.** For prefix forms, fixtures must pin operand extent, `try` ordering, grouping, and interaction with infix operators. For postfix forms, pin member/call chaining and parenthesized operands.
4. **Compilation goal is test input.** Source mode (module/script/library/test) must be explicit, not inferred from file suffix without recording that rule.
5. **Recovery is part of conformance.** After a bad await, a later declaration and its diagnostics should remain discoverable. Assert the recovery token and avoid cascades that obscure the primary error.
6. **Runtime behavior is out of scope.** These fixtures do not assert when tasks start, whether awaits run inline, scheduler choice, cancellation, or parallelism; retain those questions in Scenarios 40, 57, and 58.

## 6. Experimental plan and open questions

First implement a language-neutral fixture schema and profile-specific adapters for Rust, Swift, C#, and ECMAScript. Record actual compiler acceptance and normalized diagnostics only when toolchain versions are pinned. Then add candidate LLMLang profiles for marker placement, closure inference, cleanup restrictions, and top-level await. Keep parse acceptance separate from contextual/type checking and run recovery cases independently.

Open decisions include whether closures inherit, infer, or declare async context; whether blocks can create context without a named function; whether cleanup can suspend; whether protected critical sections reject await; whether `await` is a keyword or contextual token; and whether modules support top-level await. The evidence does not select answers. No LLMLang grammar, diagnostic wording, or execution model is chosen here.

## 7. References

- [Rust Reference — Await expressions](https://doc.rust-lang.org/reference/expressions/await-expr.html)
- [Rust error E0728](https://doc.rust-lang.org/stable/error_codes/E0728.html)
- [Rust Reference — Async blocks](https://doc.rust-lang.org/reference/expressions/block-expr.html#async-blocks)
- [Swift Language Reference — Expressions](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/)
- [C# await operator](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/await)
- [C# async/await compiler diagnostics](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-messages/async-await-errors)
- [ECMAScript 2026 — Async function definitions](https://tc39.es/ecma262/2026/multipage/ecmascript-language-functions-and-classes.html#sec-async-function-definitions)
