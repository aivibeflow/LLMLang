# Research Scenario 39 — Cleanup Failure and Ownership Transfer

**Status:** Evidence-linked comparison; no cleanup, exception, or ownership rule selected
**Research area:** RT-03/04 resource lifecycle, error handling, ownership, and effects
**Updated:** 2026-11-19

## 1. Question

When a function returns an owned value while a local cleanup action can fail, which event occurs first, which outcome reaches the caller, and where does the outstanding ownership obligation live? This scenario extends [COR-13](RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md) with language mechanisms that choose different cleanup triggers or make cleanup failure unrepresentable as an ordinary return.

The fixture is deliberately small: acquire a resource to return, acquire a local temporary, then return the first resource while releasing the temporary may fail. Record result tag, ordered cleanup events, owner map, and any cleanup debt independently.

## 2. Comparative mechanisms

### Zig: success transfer plus error-path rollback

Zig's official language reference distinguishes unconditional `defer` from `errdefer`. A successful `return foo` in its `createFoo` example suppresses `errdefer` for the resource being transferred and runs unconditional `defer` for a temporary. Error exits run error-path cleanup in reverse order. The reference also specifies that control cannot `return` from inside a defer expression. An error union `E!T` represents either an error or a `T`, so it does not itself encode an error and the `T` together.

This gives a useful construction/rollback pattern, but the documented example's deallocator is not fallible. Zig's trigger rule does not settle what LLMLang should do if cleanup itself reports an ordinary error; the owner/debt and primary-error policy still need a separate contract.

Source: [Zig language reference — `errdefer` and error unions](https://ziglang.org/documentation/master/#errdefer).

### Rust: ownership transfer and cleanup during unwinding

Rust's return rules transfer the return operand to the caller while local drop scopes run as the function exits. Its `Drop` method has no ordinary `Result` return channel. Rust's standard-library documentation advises destructors not to panic: a second panic from `Drop` while already unwinding will likely abort. This makes ordinary fallible cleanup a poor fit for implicit destruction; code that must observe failure needs an explicit fallible close/release operation before scope exit.

This design separates ordinary ownership cleanup from recoverable cleanup failure, but leaves explicit close ordering and the state of the resource after a failed close to the API contract.

Sources: [Rust Reference — return expressions](https://doc.rust-lang.org/reference/expressions/return-expr.html), [Rust Reference — destructors and drop scopes](https://doc.rust-lang.org/reference/destructors.html), [Rust `Drop` documentation](https://doc.rust-lang.org/stable/core/ops/trait.Drop.html).

### Swift: scope-exit cleanup runs across throws

Swift specifies that `defer` executes when its scope exits, including when an error is thrown, and that the body cannot transfer control outside itself. The construct therefore ensures cleanup execution but does not by itself return a cleanup error alongside the pending thrown error or owned result. A fallible operation that must affect the function's outcome needs to be performed and handled explicitly in ordinary control flow.

Source: [The Swift Programming Language — statements (`defer`)](https://docs.swift.org/latest/documentation/the-swift-programming-language/statements/).

### Go: deferred code can recover panic and mutate named results

The Go specification runs deferred calls immediately before the surrounding function returns or while its goroutine is panicking, in reverse registration order. A deferred function that calls `recover` may stop the panic sequence; deferred closures may also modify named result parameters before return. This is a dynamic recovery mechanism, distinct from an affine ownership checker or a typed `ErrorWithValue` result. The language rule alone does not prove resource conservation or constrain which error takes precedence.

Source: [Go specification — defer and recover](https://go.dev/ref/spec#Defer_statements).

## 3. What the mechanisms do and do not establish

| Mechanism | Cleanup trigger | Ordinary cleanup failure channel | Ownership + error together | Main unresolved obligation |
|---|---|---|---|---|
| Zig `defer` / `errdefer` | Scope exit / error exit | Not specified as a separate cleanup-result protocol | Not in `E!T` by itself | Define fallible cleanup and retained owner/debt |
| Rust `Drop` | Scope exit and unwinding | No `Result` return from `Drop`; panic during unwinding may abort | No ordinary return result from implicit `Drop` | Expose fallible release explicitly before exit |
| Swift `defer` | Scope exit, including throw | Body cannot transfer control outside the defer | No automatic combined result | Decide how explicit cleanup errors compose with an in-flight throw |
| Go `defer` / `recover` | Return and panic | Dynamic panic recovery, not a typed cleanup result | Named results can be changed procedurally | Track owner exactly once and define error precedence |
| COR-13 transfer-first fixture | Transfer precedes local cleanup | Explicit modeled cleanup outcome | `error_with_value` required when cleanup fails | Type and checker must carry caller obligation |

The mechanisms are not directly equivalent: the languages differ in exception model, destruction guarantees, and ownership systems. The comparison is about the observable dimensions each mechanism forces a design to specify.

## 4. Discriminating outcome matrix

For each policy, run these cases and preserve separate result and resource-state observations:

| Returned value | Local cleanup | Candidate observations that must be distinguished |
|---|---|---|
| owned handle | success | success plus caller ownership; temporary released once |
| owned handle | failure after transfer | error-with-value, explicit cleanup debt, or a policy that rejects/stages transfer |
| no value, primary error | success | original error preserved; temporary release ordered and recorded |
| no value, primary error | cleanup also fails | precedence, aggregation/suppression, and every remaining owner/debt visible |
| panic/throw | cleanup succeeds | unwind/throw outcome and exact cleanup trace |
| panic/throw | cleanup fails or panics | secondary-failure behavior, including suppression, replacement, continued unwind, or abort |

For every terminal case assert: no owner is duplicated; no live resource disappears; cleanup attempts and outcomes are ordered; and any retained obligation is represented to the caller or runtime. A success/error tag alone is insufficient evidence.

## 5. Cross-area implications and next probe

- “Cleanup runs” is not the same claim as “cleanup succeeded.” Implicit cleanup mechanisms often make failure unreturnable or treat it as panic/abort; explicit close operations expose an ordinary error path.
- A rollback hook such as `errdefer` needs a distinct trigger from unconditional scope cleanup, while both need explicit ordering.
- If transfer is committed before fallible local cleanup, the caller may need an error-with-owned-value outcome. If transfer is staged, the callee needs a defined second cleanup path and a result for failure of that cleanup.
- If unwinding or cancellation can invoke cleanup, the semantic contract must specify what happens when cleanup itself fails while another terminal outcome is in flight.
- Cache/evidence summaries must retain cleanup ordering and failure policy wherever they affect caller obligations or observable outcomes.

The next bounded prototype should feed the same typed call tree to the operational trace model and ownership checker for a Cartesian matrix over return/error/panic, transfer timing, local cleanup success/failure, pending-result cleanup success/failure, and caller propagation/release. Keep language comparisons as hypotheses until source-to-model correspondence and independent review exist. This scenario selects no LLMLang rule.

## 6. References and limits

All references above are official language documentation, consulted 2026-11-19. Zig's `master` documentation is moving; pin a language release/toolchain before relying on syntax. This is a rules comparison, not executable conformance evidence. It does not evaluate asynchronous cancellation, destructor reentrancy, process abort recovery, or ownership across FFI and actor boundaries.
