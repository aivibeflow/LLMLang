# Research Scenario 116 — Atomic Contracts and Backend Lowering

**Status:** Official LLVM backend contract comparison; no LLMLang atomic profile selected  
**Research area:** RT-04 ownership/effects/memory model; RT-09 compiler; RT-10 runtime; RT-13 backends  
**Updated:** 2026-11-20

## Question

What must a compiler preserve when lowering source-level atomics and fences into an intermediate representation and target instructions, and which source guarantees may become target-dependent?

## Evidence from LLVM

LLVM's Language Reference defines a happens-before partial order and atomic orderings with explicit constraints. It says the atomic semantics implement Java or C++ memory models, but directs frontends to the source language contract when those descriptions are not precise enough. Its `monotonic` ordering provides a per-object total modification order and coherence constraints compatible with happens-before; it expressly does not promise that these per-object orders can be combined into one global order. Acquire/release and sequentially consistent orderings add stronger synchronization constraints. Fences are special because they have no address and synchronize only through specified atomic operations.

LLVM's frontend guide also makes a target contract explicit: atomic instructions are guaranteed lock-free in LLVM IR, so operations wider than a target's native support may be impossible to generate. The guide advises frontends to be target-aware; if an operation is unsupported, code generation may fail and a frontend needing it should use explicit locking. The exact supported widths and lowering behavior are target-dependent and need version-pinned validation.

| Layer | Contract/evidence | Obligation for LLMLang implementation |
|---|---|---|
| Source semantics | Defines data-race classification, read-from, modification order, happens-before, release sequences, fences, and `SeqCst` as source-observable rules. | Do not define source behavior by incidental LLVM IR behavior. Specify the source contract first. |
| IR mapping | LLVM orderings encode partial/global constraints; `monotonic` has per-object modification order/coherence but no global order, while `seq_cst` participates in a constrained total order. | Establish a sound source-order-to-IR mapping for each supported construct and forbid transformations that widen allowed source outcomes. |
| Target lowering | LLVM atomic instructions are required to be lock-free, and width/target support can make lowering unavailable. | Choose and document an unavailable-width policy: reject/type-gate, runtime fallback with a separate contract, or constrain the supported target set. Never silently strengthen or weaken semantics. |
| Optimization | Atomic/fence semantics constrain reordering, invented accesses, and access width/overlap. | Validate optimized IR and final machine code against the formal source model, not only against single-threaded outputs. |

## Design consequences

The backend choice affects the source contract before code generation starts. A language that promises lock-free atomics at a stated width must constrain eligible target/width combinations. A language that promises portable atomic behavior may choose a runtime lock fallback, but that changes progress, reentrancy, signal/interrupt, and possibly async-safety properties; it cannot be presented as lock-free. A compile-time “supported atomic width” capability makes availability explicit but can make generic APIs target-dependent. Each option needs measured costs and conformance tests.

Scenario 113's finite outcome enumerators are not compiler validation: they establish a hand-authored relation only. The next validation stage should compile the same version-pinned litmus corpus through a reference interpreter and at least two independent backends/targets, inspect optimized IR and machine-code observations where feasible, and test unsupported atomic widths. A passing unit test for the model cannot establish backend preservation.

## Open questions

- Is lock-freedom part of LLMLang's semantic guarantee, a per-type capability, or only an implementation property?
- Which widths/types are guaranteed atomic on the minimum target set?
- Is lock fallback allowed, and what are its interaction guarantees with async cancellation, signals, process-shared memory, and runtime callbacks?
- How are mixed-order and fence litmus outcomes checked after optimization and lowering?
- What artifact identity pins source memory model, compiler version, target triple/features, LLVM version, and atomic lowering runtime?

## Sources

- [LLVM Language Reference — Atomic Memory Ordering Constraints](https://llvm.org/docs/LangRef.html#atomic-memory-ordering-constraints)
- [LLVM Atomic Instructions and Concurrency Guide](https://llvm.org/docs/Atomics.html)
- [C++ draft — atomic orderings and fences](https://eel.is/c++draft/atomics)
