# Research Scenario 36 — Recursion, Termination, and Execution Budgets

**Status:** evidence collected; comparison open; no vector selected  
**Updated:** 2026-11-19  
**Aspect:** RT-03 semantics × RT-04 effects/types × RT-07 verification × RT-10 runtime

## Question

How should LLMLang distinguish a recursive computation that returns, one that diverges, and one stopped by a resource limit? What guarantees should the type checker, verifier, and runtime make about termination and resource budgets?

This is an open semantic question: the current executable A/D evaluators and typed-call experiment have no recursive calls. Their finite test coverage does not define the behavior of general recursion or exhaustion.

## Candidate vectors

| Vector | Rule | Benefits | Costs and risks |
|---|---|---|---|
| **T — Total-by-default recursion** | Every recursive definition must pass structural or well-founded termination checking. Nontermination is rejected statically. | Termination claims compose with total-function reasoning; proofs can reduce recursive definitions when the termination evidence is accepted. | Some useful searches, servers, interpreters, and reactive loops are naturally nonterminating; termination analysis is incomplete and may require annotations/proofs. Requires a distinct model for productive co-recursion. |
| **P — General recursion with partiality** | General recursion is allowed; divergence is part of program behavior. Static proofs must distinguish partial code or treat it opaquely. | Directly expresses long-running and potentially nonterminating computations; familiar systems-language model. | Termination cannot be inferred from a return type; equivalence and proof are harder; stack, time, and memory failures may vary with implementation. |
| **D — Typed divergence effect** | A function that may diverge carries an explicit `div`/`Dv` effect, inferred or declared and propagated through calls. The effect classifies termination behavior; it need not be a user-catchable handler operation. | Callers and effect-polymorphic combinators can distinguish total computations from potentially divergent ones without rejecting all general recursion. The effect can coexist with exception and I/O effects. | Sound inference relies on call-graph/effect completeness; a `div` label does not prove nontermination, bound time, or provide a runtime recovery mechanism. Proof rules must say which properties hold conditionally on termination. |
| **F — Explicit fuel/budget semantics** | Evaluation receives a declared step or cost budget; exhaustion is a distinct outcome. Recursion may be total or partial inside that envelope. | A bounded run has a reproducible stopping criterion if the cost model is specified; useful for verifiers, sandboxed execution, and deterministic replay. | Fuel measures abstract language steps, not wall time or exact machine cost; instrumenting and preserving the count through optimization is a semantic and compiler obligation. Caller/callee ownership and cleanup at exhaustion must be defined. |
| **E — External runtime limits** | Source semantics permits unbounded computation; implementation or embedder may terminate it on stack, memory, or execution limits. | Fits native/VM deployment and operational limits without imposing one source-level cost model. | Result may depend on implementation, host, and configuration; exact error class and cleanup behavior may not be portable. Evidence must record runtime/limit identity and must not treat timeout as semantic divergence or success. |

These vectors can be combined. A particularly plausible comparison is total-by-default for proof-facing pure functions, explicit partial/effectful boundaries for servers and interpreters, and an external runtime budget for operational safety. That combination remains a hypothesis, not a recommendation.

## Prior-art observations

Lean requires recursive definitions either to be justified to its kernel by a termination strategy or made opaque using `partial`; the reference describes several structural and well-founded strategies. Lean's `partial` declarations are completely opaque to the logic, while `partial_fixpoint` supports a more explicit partial-function account. This makes the proof boundary visible rather than pretending that an unproved recursive function is total. [Lean Reference: recursive definitions](https://lean-lang.org/doc/reference/latest/Definitions/Recursive-Definitions/) · [Lean Reference: definitions](https://lean-lang.org/doc/reference/latest/Definitions/Definitions/).

Koka tracks possible nontermination as a `div` effect, separate from `exn`, nondeterminism, state, and console effects; it also infers and propagates effects polymorphically. Its documentation calls the no-effect case `total` and the combination `<div, exn>` `pure`, which shows that purity and termination are distinct properties. F* has a primitive `Dv` effect: `Tot` has total-correctness semantics, while `Dv` permits divergence and retains partial-correctness guarantees (“if it terminates, the result satisfies the type”). F* says `Dv` disables termination checking and is outside its logical core, so extrinsic proofs cannot assume evaluation yields a value. These systems show that tracking divergence in a type/effect boundary is distinct from proving termination or adding fuel. [Koka effect types](https://koka-lang.github.io/koka/doc/book.html#effect-types) · [F* divergence effect](https://fstar-lang.org/tutorial/book/part4/part4_div.html).

Rust permits general recursion but does not make stack exhaustion an ordinary `Result` value. The Rust RFC error conventions classify stack overflow and out-of-memory as catastrophic errors; it states that stack overflow currently aborts the process. Rust panic strategy is separately configurable: `unwind` walks the stack and may be recoverable, while `abort` does not unwind and permits different optimization assumptions. These behaviors demonstrate that recoverable panic, catastrophic runtime failure, and domain `Result` are separate outcome classes. [Rust RFC 236: error conventions](https://rust-lang.github.io/rfcs/0236-error-conventions.html) · [Rust Reference: panic](https://doc.rust-lang.org/reference/panic.html).

WebAssembly defines traps for certain instruction conditions, while its implementation-limits appendix permits an implementation to terminate computation when runtime limits are exceeded and report an embedder-specific error. The spec states concrete limits may depend on implementation or embedder circumstances. A runtime budget can therefore be an execution boundary without being a portable source-level step count. [WebAssembly Core Specification 3.0: implementation limitations](https://webassembly.github.io/spec/core/appendix/implementation.html).

## Observable outcome model to compare

For one computation, record `(value, terminal outcome, trace, final store/resources, budget/runtime identity)`:

| Case | Candidate terminal observation |
|---|---|
| Recursive function returns | `Returned(value)` |
| Domain failure is returned | `ResultError(error)` |
| Declared budget is exhausted | `FuelExhausted(remaining=0)` or another explicitly chosen budget outcome |
| Runtime limit stops execution | `RuntimeLimit(kind, implementation/configuration)` or host-level failure |
| No finite result exists absent a stop limit | `Diverges` as a semantic classification; an actual executor may only observe that it has not returned yet |
| Unrecoverable runtime fault | `Aborted(fault-class)` with explicit cleanup/trace guarantees |

The table is a candidate vocabulary. In particular, a timeout observed by a test harness cannot prove divergence, and a runtime interruption cannot be silently converted into a domain error.

## Compatibility conditions and risks

- RT-03 evaluation, RT-04 effects and result types, RT-07 proof claims, and RT-10 runtime limits must agree on the terminal outcome vocabulary.
- A divergence effect is a static possibility summary, not a dynamic error result: handlers must not imply they can catch an infinite computation unless cancellation/termination is separately specified.
- Effect inference must propagate divergence through higher-order calls and recursive strongly connected components; incomplete call graphs must remain unknown rather than infer `total`.
- A proof over a potentially diverging function must state whether it is total correctness, partial correctness conditional on return, or an intrinsic property of a computation representation.
- If fuel becomes a source-visible input, it affects function behavior, semantic identity, cache keys, and verification inputs. If it is only a verifier parameter, the verifier must not claim an unbounded source theorem from a bounded run.
- If compiler optimizations change the number of abstract steps, either the fuel semantics must be preserved by the lowering or the language must identify the execution layer whose steps are counted.
- Budget exhaustion during cleanup or after ownership transfer must preserve the resource-state and error-with-value invariants from COR-13.
- Co-recursion, lazy structures, asynchronous waits, and actor liveness require separate productivity/fairness questions; structural termination of a pure call does not establish scheduler progress.
- Wall-clock deadlines and memory caps are environment/runtime inputs, not substitutes for a portable cost semantics.

## Falsification and discriminating experiment

A total-by-default vector is weakened if representative RT-01 workloads require unbounded service loops and cannot isolate them behind an explicit partial/effectful boundary without unacceptable complexity. A general-recursion vector is weakened if the required proof and cache-reuse claims depend on termination that cannot be established modularly. A typed-divergence vector is weakened if higher-order or mutually recursive effect inference marks a potentially diverging path as total, or if the `div` effect is mistaken for a catchable exception. A source-level fuel vector is weakened if two conforming evaluators or a semantics-preserving optimization disagree on fuel exhaustion. An external-limit-only vector is weakened if identical verification inputs can produce incompatible terminal observations across supported runtimes.

Next experiment: add small mutually recursive and self-recursive functions to the shared source semantics corpus. Include a terminating structural case, a terminating non-structural case, a divergent case, explicit budget exhaustion at several boundaries, an effect before exhaustion, and exhaustion while a resource scope is active. Compare a fuel-counting reference interpreter with a small-step evaluator; separately record what a host runtime limit can and cannot establish. Add type/checker projections only after the observation contract is stated. Source syntax, runtime correspondence, and independent review are required before treating the result as evidence about LLMLang source programs.

## Machine-readable summary

| Decision | Vectors | Current evidence | Status |
|---|---|---|---|
| Recursive partiality and termination | T total-by-default; P general recursion; D typed divergence effect; F explicit fuel; E external runtime limits; compatible combinations remain open | Lean distinguishes termination-checked definitions and logic-opaque partial definitions; Koka and F* track divergence as a distinct effect; Rust and WebAssembly distinguish language behavior from runtime failure/limits | Evidence collected; no LLMLang vector selected |

This report records the design space and prior-art constraints. It selects no LLMLang semantics.
