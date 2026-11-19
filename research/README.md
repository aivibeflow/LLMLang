# LLMLang Research Index

Research documents are exploratory evidence and do not change the candidate or normative language specification unless a decision is explicitly accepted.

Start with [Research State 2026-11-19](RESEARCH-STATE-2026-11-19.md) for the current evidence map, open integrated vectors, synthesis gates, and recommended next work. Use the [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md) to compare cross-area candidate bundles; no bundle is selected.

## Core semantic and type research

- [Core language semantics](CORE-LANGUAGE-SEMANTICS.md) compares pure, imperative, actor, and effectful-functional profiles.
- [RT-04 type/effect/ownership/capability alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) records checker vectors and limits.
- [Scenario 36 — recursion, termination, and fuel](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md), [Scenario 37 — effect rows, handlers, and traces](RESEARCH-SCENARIO-37-EFFECT-ROWS-HANDLERS-AND-OBSERVATION.md), and [Scenario 38 — effects, capabilities, and authority](RESEARCH-SCENARIO-38-EFFECTS-CAPABILITIES-AND-AUTHORITY.md) extend the RT-03/04 comparison without selecting language rules.
- [Scenario 39 — cleanup failure and ownership transfer](RESEARCH-SCENARIO-39-CLEANUP-FAILURE-AND-OWNERSHIP-TRANSFER.md) compares Zig, Rust, Swift, and Go cleanup/error mechanisms against COR-13's owned-return boundary.
- [Scenario 40 — async cancellation and resource cleanup](RESEARCH-SCENARIO-40-ASYNC-CANCELLATION-AND-CLEANUP.md) distinguishes cancellation requests, task termination, and completed cleanup across Rust, Swift, and Go.
- [Scenario 41 — typed errors and API evolution](RESEARCH-SCENARIO-41-TYPED-ERRORS-AND-API-EVOLUTION.md) compares Rust, Zig, Swift, and Go error contracts and their evolution pressure.
- [Scenario 64 — error propagation, context, and recovery](RESEARCH-SCENARIO-64-ERROR-PROPAGATION-AND-RECOVERY.md) compares Rust `Result`/`?`, Swift typed throws/catch, Go wrapping and inspection, and Zig error sets/`try`/`catch`.
- [Scenario 65 — fatal failure, unwinding, and process boundaries](RESEARCH-SCENARIO-65-FATAL-FAILURE-AND-UNWINDING.md) compares Rust panic strategies, Go panic/recover, Swift fatal checks, and Zig safety-mode behavior.
- [Scenario 66 — copy, move, and reference semantics](RESEARCH-SCENARIO-66-COPY-MOVE-AND-REFERENCE-SEMANTICS.md) compares Rust ownership transfer, Go value copies with reference-bearing descriptors, Swift value/reference types and copy-on-write, and Zig values with explicit pointers.
- [Scenario 67 — mutability and immutability depth](RESEARCH-SCENARIO-67-MUTABILITY-AND-IMMUTABILITY-DEPTH.md) compares Rust mutable-access capabilities and interior mutability, Go constants versus runtime aliases, Swift `let` across value/reference types, and Zig `const`/pointer qualifiers.
- [Scenario 68 — value construction and initialization invariants](RESEARCH-SCENARIO-68-VALUE-CONSTRUCTION-AND-INITIALIZATION.md) compares complete aggregate construction, Go zero values, Swift definite/two-phase initialization, and Zig comptime defaults.
- [Scenario 69 — subtyping and variance](RESEARCH-SCENARIO-69-SUBTYPING-AND-VARIANCE.md) compares Rust lifetime variance, Java invariant generics with use-site wildcards, Go assignability/interface implementation, and Swift generic/existential boundaries.
- [Scenario 70 — type aliases, nominal wrappers, and opaque abstractions](RESEARCH-SCENARIO-70-TYPE-ALIASES-NEWTYPE-AND-OPAQUE-ABSTRACTIONS.md) separates alias identity, fresh nominal identity, hidden implementation, and representation/ABI guarantees across Rust, Go, Swift, and Zig.
- [Shared semantics corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md) maps COR-01–13 fixtures and their evidence boundaries.
- [COR-13 typed ownership follow-up](RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md) records the bounded policy comparison and preliminary action-list/CFG caller model for owned-resource results; integration with typed call trees remains open.

## Integration and foundations

- [Research taxonomy](RESEARCH-TAXONOMY.md) tracks areas, coverage, and required report fields.
- [Research dependency map](RESEARCH-DEPENDENCY-MAP.md) records cross-area hypotheses and sequencing.
- [Formal verification architecture](LLMLANG-FORMAL-VERIFICATION.md) describes proof and trusted-boundary questions.
- [Semantic artifact store](GLOBAL-SEMANTIC-ARTIFACT-STORE.md), [identity studies](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md), and [semantic merge research](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) cover representation, identity, and change.
- [Runtime and backend proposals](POSIX-RUNTIME-ARCHITECTURE.md), [translation/backends](TRANSLATION-AND-TARGET-BACKENDS.md), and [LLVM architecture](LLVM-BACKEND-ARCHITECTURE.md) are analytical until tested against shared semantics.
- [RT-16 threat model](RT-16-THREAT-MODEL-01.md) covers agent authority and bounded authorization experiments.
- [TODO](../TODO.md) remains the authoritative register of unresolved project decisions.

Keep conclusions scoped to the fixtures and assumptions actually checked. A passing test suite, prototype, or proof in a restricted fragment is not evidence that the full language profile is complete or selected.
