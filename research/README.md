# LLMLang Research Index

Research documents are exploratory evidence and do not change the candidate or normative language specification unless a decision is explicitly accepted.

Start with [Research State 2026-11-19](RESEARCH-STATE-2026-11-19.md) for the current evidence map, open integrated vectors, synthesis gates, and recommended next work. Use the [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md) to compare cross-area candidate bundles; no bundle is selected.

## Core semantic and type research

- [Core language semantics](CORE-LANGUAGE-SEMANTICS.md) compares pure, imperative, actor, and effectful-functional profiles.
- [RT-04 type/effect/ownership/capability alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) records checker vectors and limits.
- [Scenario 36 — recursion, termination, and fuel](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md), [Scenario 37 — effect rows, handlers, and traces](RESEARCH-SCENARIO-37-EFFECT-ROWS-HANDLERS-AND-OBSERVATION.md), and [Scenario 38 — effects, capabilities, and authority](RESEARCH-SCENARIO-38-EFFECTS-CAPABILITIES-AND-AUTHORITY.md) extend the RT-03/04 comparison without selecting language rules.
- [Scenario 39 — cleanup failure and ownership transfer](RESEARCH-SCENARIO-39-CLEANUP-FAILURE-AND-OWNERSHIP-TRANSFER.md) compares Zig, Rust, Swift, and Go cleanup/error mechanisms against COR-13's owned-return boundary.
- [Scenario 40 — async cancellation and resource cleanup](RESEARCH-SCENARIO-40-ASYNC-CANCELLATION-AND-CLEANUP.md) distinguishes cancellation requests, task termination, and completed cleanup across Rust, Swift, and Go.
- [Scenario 94 — scheduler fairness and liveness](RESEARCH-SCENARIO-94-SCHEDULER-FAIRNESS-AND-LIVENESS.md) separates runnable-task fairness, preemption, protocol/resource progress, and structured joining across Go, Tokio, Erlang/OTP, Rust async, and Swift task groups; no LLMLang guarantee is selected.
- [Scenario 95 — diagnostics for humans and coding agents](RESEARCH-SCENARIO-95-DIAGNOSTICS-FOR-HUMANS-AND-AGENTS.md) compares compiler diagnostic records, LSP/editor transport, repair suggestions, test corpora, and human/LLM explanation studies; no diagnostic format or repair authority is selected.
- [Scenario 96 — LLVM UB, poison, and semantic preservation](RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md) compares LLVM IR poison/UB with Rust source behavior and WebAssembly wrapping/traps, and proposes a source-to-IR preservation corpus; no backend or source behavior is selected.
- [Scenario 97 — cleanup error composition and ownership](RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md) separates cleanup ordering, primary-cause selection, secondary-error carriers, catchability, and resource ownership across Java, Go, Rust, and Swift; a bounded model runs 12 discriminators across six policies plus a 13,230-case valid outcome/ownership product, with no policy selected.
- [Scenario 98 — finite AST-to-path coverage](RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) exhausts 128 concrete assignments for a seven-condition AST tree, compares them with eight structural paths and two evaluators, and records the remaining parser/source-extraction gap.
- [Scenario 99 — repeated path predicates](RESEARCH-SCENARIO-99-REPEATED-PATH-PREDICATES.md) constrains repeated identical Boolean markers to one per-path choice, eliminating two of four impossible structural combinations in a finite fixture; different-predicate satisfiability and source identity remain open.
- [Scenario 100 — finite Boolean path feasibility](RESEARCH-SCENARIO-100-FINITE-BOOLEAN-PATH-FEASIBILITY.md) exhausts a two-variable predicate space, finds three feasible branch vectors for `x` then `x or y`, and cross-checks witnesses against both RT-03 evaluators; solver scalability and source correspondence remain open.
- [Scenario 101 — solver versus truth-table path feasibility](RESEARCH-SCENARIO-101-SOLVER-VS-TRUTH-TABLE-PATHS.md) cross-checks SymPy DPLL2 route models against Scenario 100 and measures one conjunction family; the result does not generalize to difficult SAT instances or establish solver trust.
- [Scenario 102 — solver UNKNOWN and sound path pruning](RESEARCH-SCENARIO-102-SOLVER-UNKNOWN-AND-SOUND-PATH-PRUNING.md) compares exact, tri-state, hybrid, and proof-carrying pruning; witnesses must replay and inconclusive routes remain possible.
- [Scenario 103 — real solver timeout and worker isolation](RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md) forces an actual SymPy DPLL2 pigeonhole query to its external deadline and checks that the worker is reaped and the route remains UNKNOWN.
- [Scenario 104 — mutable values and predicate identity](RESEARCH-SCENARIO-104-MUTABLE-PREDICATE-IDENTITY.md) exhaustively shows how reusing a variable name across a write can prune reachable paths, while independent versions overapproximate unless the write transition is encoded.
- [Scenario 105 — call mutation summaries and path feasibility](RESEARCH-SCENARIO-105-CALL-MUTATION-SUMMARIES.md) compares pure, known mutation, and incomplete/may-write call summaries; unknown effects require conservative post-call state havoc in the bounded model.
- [Scenario 106 — call-site alias sets and field-sensitive paths](RESEARCH-SCENARIO-106-CALL-ALIAS-SETS-AND-FIELD-SENSITIVE-PATHS.md) exhausts exact, disjoint, may-alias, and incomplete points-to cases for a call that writes through a reference.
- [Scenario 41 — typed errors and API evolution](RESEARCH-SCENARIO-41-TYPED-ERRORS-AND-API-EVOLUTION.md) compares Rust, Zig, Swift, and Go error contracts and their evolution pressure.
- [Scenario 64 — error propagation, context, and recovery](RESEARCH-SCENARIO-64-ERROR-PROPAGATION-AND-RECOVERY.md) compares Rust `Result`/`?`, Swift typed throws/catch, Go wrapping and inspection, and Zig error sets/`try`/`catch`.
- [Scenario 65 — fatal failure, unwinding, and process boundaries](RESEARCH-SCENARIO-65-FATAL-FAILURE-AND-UNWINDING.md) compares Rust panic strategies, Go panic/recover, Swift fatal checks, and Zig safety-mode behavior.
- [Scenario 66 — copy, move, and reference semantics](RESEARCH-SCENARIO-66-COPY-MOVE-AND-REFERENCE-SEMANTICS.md) compares Rust ownership transfer, Go value copies with reference-bearing descriptors, Swift value/reference types and copy-on-write, and Zig values with explicit pointers.
- [Scenario 67 — mutability and immutability depth](RESEARCH-SCENARIO-67-MUTABILITY-AND-IMMUTABILITY-DEPTH.md) compares Rust mutable-access capabilities and interior mutability, Go constants versus runtime aliases, Swift `let` across value/reference types, and Zig `const`/pointer qualifiers.
- [Scenario 68 — value construction and initialization invariants](RESEARCH-SCENARIO-68-VALUE-CONSTRUCTION-AND-INITIALIZATION.md) compares complete aggregate construction, Go zero values, Swift definite/two-phase initialization, and Zig comptime defaults.
- [Scenario 69 — subtyping and variance](RESEARCH-SCENARIO-69-SUBTYPING-AND-VARIANCE.md) compares Rust lifetime variance, Java invariant generics with use-site wildcards, Go assignability/interface implementation, and Swift generic/existential boundaries.
- [Scenario 70 — type aliases, nominal wrappers, and opaque abstractions](RESEARCH-SCENARIO-70-TYPE-ALIASES-NEWTYPE-AND-OPAQUE-ABSTRACTIONS.md) separates alias identity, fresh nominal identity, hidden implementation, and representation/ABI guarantees across Rust, Go, Swift, and Zig.
- [Scenario 71 — interface implementation ownership and coherence](RESEARCH-SCENARIO-71-INTERFACE-IMPLEMENTATION-OWNERSHIP-AND-COHERENCE.md) compares owner-local impls, implicit structural satisfaction, retroactive conformance, and scoped/overlapping instances across Rust, Go, Swift, and Haskell.
- [Scenario 72 — sum-type layout, ABI, and interoperability](RESEARCH-SCENARIO-72-SUM-TYPE-LAYOUT-ABI-AND-INTEROPERABILITY.md) separates semantic variants from memory layout, calling conventions, resilience, and C interoperability across Rust, Zig, Swift, and C.
- [Scenario 73 — numeric literal typing and conversions](RESEARCH-SCENARIO-73-NUMERIC-LITERAL-TYPING-AND-CONVERSIONS.md) compares literal defaults, exact compile-time values, runtime numeric casts, and mixed-operand typing across Rust, Go, Swift, and Zig.
- [Scenario 74 — refutable pattern failure and binding](RESEARCH-SCENARIO-74-REFUTABLE-PATTERN-FAILURE-AND-BINDING.md) compares compile-time rejection, conditional binding, exit-on-failure, Boolean pattern tests, and explicit status values across Rust, Swift, Go, and C#.
- [Scenario 75 — automatic disposal and lifetime](RESEARCH-SCENARIO-75-AUTOMATIC-DISPOSAL-AND-LIFETIME.md) compares ownership-bound drop, lexical defer, ARC deinitialization, and nondeterministic GC cleanup across Rust, Zig, Swift, and Go.
- [Scenario 76 — regular-expression semantics and resource bounds](RESEARCH-SCENARIO-76-REGULAR-EXPRESSION-SEMANTICS-AND-RESOURCE-BOUNDS.md) compares bounded automata, backtracking, dual engines, Unicode behavior, and timeout policies across Rust, Go, .NET, and Swift Foundation.
- [Shared semantics corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md) maps COR-01–13 fixtures and their evidence boundaries.
- [COR-13 typed ownership follow-up](RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md) records the bounded policy comparison and preliminary action-list/CFG caller model for owned-resource results; integration with typed call trees remains open.

## Integration and foundations

- [Research taxonomy](RESEARCH-TAXONOMY.md) tracks areas, coverage, and required report fields.
- [Research dependency map](RESEARCH-DEPENDENCY-MAP.md) records cross-area hypotheses and sequencing.
- [Formal verification architecture](LLMLang-FORMAL-VERIFICATION.md) describes proof and trusted-boundary questions.
- [Semantic artifact store](GLOBAL-SEMANTIC-ARTIFACT-STORE.md), [identity studies](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md), and [semantic merge research](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) cover representation, identity, and change.
- [Runtime and backend proposals](POSIX-RUNTIME-ARCHITECTURE.md), [translation/backends](TRANSLATION-AND-TARGET-BACKENDS.md), and [LLVM architecture](LLVM-BACKEND-ARCHITECTURE.md) are analytical until tested against shared semantics.
- [RT-16 threat model](RT-16-THREAT-MODEL-01.md) covers agent authority and bounded authorization experiments.
- [TODO](../TODO.md) remains the authoritative register of unresolved project decisions.

Keep conclusions scoped to the fixtures and assumptions actually checked. A passing test suite, prototype, or proof in a restricted fragment is not evidence that the full language profile is complete or selected.
