# LLMLang Research State — 2026-11-19

**Updated:** 2026-11-20; the register now includes Scenario 107 while retaining its original dated filename.

**Status:** Research state and next-work register; not a language decision or normative specification.  
**Branch:** `codex/save-research-state-2026-11-19`  
**Purpose:** Preserve an evidence-linked snapshot that makes the current research corpus reviewable and identifies the gates before integrated candidate scoring and an RFC.

[Scenario 77](RESEARCH-SCENARIO-77-CALL-ARGUMENT-EVALUATION-ORDER.md) compares general expression/call sequencing beyond Boolean short-circuiting: Rust's recursive left-to-right operand rule, Go's narrower event ordering, Java's left-to-right arguments and abrupt-completion behavior, and C++'s unspecified but non-interleaved parameter initialization. A shared trace/optimizer corpus remains open; no LLMLang order is selected.

[Scenario 78](RESEARCH-SCENARIO-78-FLOATING-POINT-REPRODUCIBILITY-AND-IEEE-EDGES.md) expands Scenario 45's floating-point checklist into a prior-art comparison of IEEE special values, non-total NaN comparisons, NaN payload guarantees, FMA/rounding boundaries, and strict versus optimized execution. A cross-target bit corpus, transcendental accuracy contract, and proof alignment remain open; no LLMLang float profile is selected.

[Scenario 79](RESEARCH-SCENARIO-79-STRING-LITERAL-SYNTAX-AND-INTERPOLATION.md) compares escaped, raw, multiline, byte-oriented, and interpolated source literals across Rust, Go, Swift, and Zig. It separates literal decoding from Scenario 46's runtime text model and flags interpolation as possible effectful typed code, not automatic context escaping. Lexer/formatter/source-emitter fixtures and context-safe template behavior remain open; no syntax is selected.

[Scenario 80](RESEARCH-SCENARIO-80-COMMENTS-DOCS-AND-LEXICAL-TRIVIA.md) compares nested and line-only comments, newline effects, doc-comment attachment, tool directives, and trivia retention across Rust, Go, Swift, and Zig. Lexer/parser fixtures, doc extraction, directive trust/placement, source-map preservation, and comment/hash policy remain open; no syntax or tooling policy is selected.

[Scenario 81](RESEARCH-SCENARIO-81-IMPORT-BINDING-SYNTAX-AND-NAMESPACE-POLLUTION.md) isolates import declarations from Scenario 43 module/package semantics, comparing qualification, direct binding, aliases, wildcard/on-demand imports, relative paths, and re-exports across Rust, Go, Swift, Java, and Python. Resolver provenance, duplicate-name behavior, path moves, and exact build invalidation remain open; no syntax is selected.

[Scenario 82](RESEARCH-SCENARIO-82-SOURCE-FILE-STRUCTURE-AND-TOP-LEVEL-CODE.md) compares the file grammar and compilation-unit roles of Go, Rust, Java, Swift, and Kotlin: headers, package membership, imports, declarations, and entry-point code. File movement, order sensitivity, generated sources, and single versus multi-file build boundaries remain to be tested; no grammar is selected.

[Scenario 83](RESEARCH-SCENARIO-83-NUMERIC-LITERAL-LEXICAL-SYNTAX.md) isolates token grammar from Scenario 73 literal typing and Scenario 78 runtime float semantics. It compares integer/float spellings, separators, exponents, suffixes, sign boundaries, and malformed tokens across Rust, Go, Swift, and Zig; the shared lexer corpus remains unrun and no syntax is selected.

[Scenario 84](RESEARCH-SCENARIO-84-FUNCTION-SIGNATURE-AND-CALL-SURFACE.md) separates signature/caller syntax from Scenario 77 evaluation order. It compares parameter names versus argument labels, result forms, defaults, variadics, and method receivers in Rust, Go, Swift, and Java. API compatibility fixtures for renaming, defaults, labels, and overload interactions remain open; no syntax is selected.

[Scenario 85](RESEARCH-SCENARIO-85-LOCAL-BINDING-DECLARATION-SYNTAX.md) compares local binding syntax and declaration-versus-assignment forms in Rust, Go, Swift, and Zig. This extends Scenarios 50, 67, 68, and 74 without selecting their scope, mutability, initialization, or pattern-failure semantics. A common same-scope redeclaration/destructuring/definite-initialization fixture remains open.

[Scenario 86](RESEARCH-SCENARIO-86-ASYNC-AWAIT-SYNTAX-AND-CONTEXTS.md) isolates async/await grammar from Scenario58 runtime and scheduling choices. It compares marker placement, prefix/postfix await, closure/context boundaries, error-operator composition, and top-level module await across Rust, Swift, C#, and ECMAScript. Parser and diagnostic fixtures remain open; no syntax is selected.

[Scenario 87](RESEARCH-SCENARIO-87-ASYNC-AWAIT-PARSER-DIAGNOSTIC-CORPUS.md) turns Scenario86's parser/diagnostic gap into an 18-case proposed corpus for context boundaries, precedence, error-operator order, cleanup/critical regions, module goal, malformed syntax, recovery, and parse-versus-type diagnostics. The fixture schema and cases are designed, not executed; no LLMLang syntax or diagnostic wording is selected.

[Scenario 88](RESEARCH-SCENARIO-88-DEFAULT-ARGUMENT-EVALUATION-AND-API-COMPATIBILITY.md) compares Swift, Kotlin, Python, and C++ defaults across evaluation epoch, argument ordering, name/source environment, and dispatch/version selection. It specifies nine discriminating cases for side effects, mutable defaults, failures, async/effects, and source/binary evolution; no LLMLang policy or implementation result is asserted.

[Scenario 89](RESEARCH-SCENARIO-89-ECMASCRIPT-AUTOMATIC-SEMICOLON-INSERTION.md) extends Scenario53's Go/Rust/Swift comparison with ECMAScript 2026's three parser/grammar-driven insertion rules, restricted productions, and empty-statement/for-header exceptions. It proposes parse-tree and formatter discriminators; no LLMLang newline or terminator rule is selected.

[Scenario 90](RESEARCH-SCENARIO-90-RUNTIME-HASHING-DETERMINISM-AND-PERSISTENT-IDENTITY.md) separates runtime collection hashes, iteration order, stable fingerprints, and cryptographic digests. It compares Rust, Swift, Python, Go, and NIST digest guidance, proposing reproducibility and collision-resistance discriminators; no LLMLang policy is selected.

[Scenario 91](RESEARCH-SCENARIO-91-VERSIONED-CONTENT-ADDRESSES-AND-DIGEST-MIGRATION.md) extends persistent-address research with Git's verified bidirectional compatibility mapping, OCI's algorithm-tagged digest plus media type/size, and CIDv1's version/content codec/multihash fields. It separates digest suite, canonical representation, semantic domain, lineage, and trust; specifies migration and recursive-group discriminators for LL-004/005; no LLMLang address or migration strategy is selected.

[Scenario 92](RESEARCH-SCENARIO-92-OPERATION-IDENTITY-AND-IMPLEMENTATION-BINDING.md) compares interface/contract identity with concrete implementation selection. WIT contracts, Bazel Action digests, Nix derivation/output addressing, and OCI content digests illustrate different identity claims; no OpHash envelope is selected. It identifies a key open semantic question: whether an OpHash promises contract-permitted behavior or one exact implementation behavior.

[Scenario 93](RESEARCH-SCENARIO-93-CACHE-SOUNDNESS-RESULT-ENVELOPES-AND-TRUST.md) isolates cache-validity conditions beyond the existing Action Key proposal. REAPI separates action-result lookup from content-addressed outputs and commits timeout/platform into action identity; Nix ties content-addressed outputs to declared inputs/sandbox assumptions; GitHub Actions illustrates prefix restoration for dependency material and trust-scoped cache writers. The study proposes exact-result, validated-material, trust-boundary recomputation, and attested-result candidates plus falsifiers; it selects none and leaves LL-021 open.

[Open Questions Research Program](RESEARCH-PROGRAM-OPEN-QUESTIONS-2026-11-19.md) inventories 24 uniquely identified LL questions and taxonomy-wide research gates, sequences the remaining work into four dependency-led waves, and records the duplicate LL-022 correction as LL-024 for Toolchain Server. This is a planning artifact, not a closure claim.

Since the previous snapshot, [Scenario 58](RESEARCH-SCENARIO-58-ASYNC-FUNCTION-TYPES-AND-SCHEDULING.md) compared Rust future construction/polling, Swift async function types/task APIs, and Go goroutine launch. The async type/effect, call-start policy, task creation, and scheduler are separate research axes; no LLMLang choice is selected. Runtime traces, blocking behavior, sync/async interop, and target parallelism remain open.

[Scenario 59](RESEARCH-SCENARIO-59-BOOLEAN-SHORT-CIRCUIT-AND-EVALUATION-ORDER.md) now distinguishes intrinsic short-circuit operators (Rust/Go), Swift's standard autoclosure-backed Boolean operator, and partially specified general expression ordering. Effectful/error/diverging operands show why value-only algebra is insufficient to validate optimizer rewrites. An executable multi-compiler trace corpus remains open; no LLMLang policy is selected.

[Scenario 60](RESEARCH-SCENARIO-60-TYPE-INFERENCE-SCOPE-AND-ANNOTATIONS.md) compares Rust's body-local inference with explicit item signatures, Go's rule-based generic-instantiation inference, and Swift's expression/statement contextual inference. The option matrix now treats inference scope as distinct from generic dispatch. Solver bounds, diagnostics, interface hashing, edit stability, and annotation burden need a matched corpus; no inference policy is selected.

[Scenario 61](RESEARCH-SCENARIO-61-CONCURRENT-MUTABLE-STATE-AND-MEMORY-MODEL.md) compares Rust ownership/atomics, Go's shared-memory DRF-SC model and race detector, and Swift actor isolation/Sendable. It separates data races from logical race conditions and records language-specific trust gaps; a shared litmus suite, unsafe/FFI boundary tests, and backend memory-model validation remain open. No LLMLang model is selected.

[Scenario 62](RESEARCH-SCENARIO-62-OPTIONAL-VALUES-AND-NULLABILITY.md) compares Rust `Option<T>`, Swift `Optional<T>`, Go's typed `nil` categories and interface edge case, and Zig `?T`. It separates absence from failure, uninitialized state, and omitted external fields. Nested optionality, representation/ABI guarantees, and FFI/schema behavior remain untested; no absence model is selected.

[Scenario 63](RESEARCH-SCENARIO-63-EQUALITY-IDENTITY-AND-HASHING.md) compares Rust `PartialEq`/`Eq`/`Hash`, Go's type-directed comparability and dynamic interface panic, Swift `Equatable`/`Hashable` with separate `===`, and Zig's fixed operator semantics. It distinguishes structural/domain equality, reference identity, equivalence laws, comparability, ordering, and hash compatibility. NaN, cyclic values, mutable keys, Unicode canonical equality, and portable hashes remain open; no LLMLang policy is selected.

[Scenario 64](RESEARCH-SCENARIO-64-ERROR-PROPAGATION-AND-RECOVERY.md) compares Rust `Result`/`?`, Swift typed throws and scoped catches, Go explicit checks plus opt-in wrapping/cause inspection, and Zig error sets with `try`/`catch`. It separates propagation from transformation, diagnostic context from public cause identity, and local recovery from boundary reporting. Async/task error aggregation, cleanup composition, future error cases, and cause privacy remain open; no LLMLang policy is selected.

[Scenario 65](RESEARCH-SCENARIO-65-FATAL-FAILURE-AND-UNWINDING.md) compares Rust's unwind/abort strategies, Go's goroutine-scoped panic/recover, Swift's recoverable throws versus assertions/preconditions/fatal errors, and Zig safety-mode-dependent `unreachable`. Cleanup, task/process isolation, FFI unwinding, and build-profile effects on terminal behavior remain open; no LLMLang policy is selected.

[Scenario 66](RESEARCH-SCENARIO-66-COPY-MOVE-AND-REFERENCE-SEMANTICS.md) compares Rust move/`Copy`/`Clone`/borrow, Go value copies with aliases through reference-bearing values, Swift value/reference types with copy-on-write collections, and Zig values with explicit pointers. Source-level isolation, ownership transfer, duplication, and physical copy elimination are distinct; nested aliases, noncopyable resources, COW and ABI lowering remain open. No LLMLang policy is selected.

[Scenario 67](RESEARCH-SCENARIO-67-MUTABILITY-AND-IMMUTABILITY-DEPTH.md) compares Rust mutable-access capabilities/interior mutability, Go compile-time constants versus runtime aliases, Swift `let` for values versus class instances, and Zig `const`/pointer qualifiers. Binding immutability, object immutability, graph immutability, and race safety remain separate; deep-freeze behavior, generic propagation, caches, and foreign objects remain open. No LLMLang policy is selected.

[Scenario 68](RESEARCH-SCENARIO-68-VALUE-CONSTRUCTION-AND-INITIALIZATION.md) compares Rust complete aggregate construction and ordinary constructor functions, Go recursive zero values, Swift definite/two-phase initialization, and Zig comptime field defaults with runtime init methods. Invariant preservation, failed construction cleanup, early `self` escape, recursive initialization, and public field evolution remain open. No LLMLang policy is selected.

[Scenario 69](RESEARCH-SCENARIO-69-SUBTYPING-AND-VARIANCE.md) compares Rust's narrow lifetime/high-ranked subtype relation, Java invariant generic instantiations with wildcard/capture views, Go identity/assignability/interface implementation, and Swift generic/existential conversion boundaries. Mutable-container safety, function variance, inference interaction, and API evolution remain open; no LLMLang policy is selected.

## 1. Current position

The research corpus has moved from broad proposals toward bounded, evidence-bearing comparisons. [Scenario 42](RESEARCH-SCENARIO-42-GENERICS-CONSTRAINTS-AND-DISPATCH.md) adds a documentation-based comparison of generic constraints, associated types, coherence, and static/dynamic dispatch; performance and dependency-invalidation effects remain unmeasured. [Scenario 43](RESEARCH-SCENARIO-43-MODULES-IMPORTS-AND-INITIALIZATION.md) adds a documentation-based module/package comparison focused on re-exports, visibility, initialization order, and dynamic discovery; incremental build behavior remains to be prototyped. [Scenario 44](RESEARCH-SCENARIO-44-COMPTIME-AND-MACRO-BOUNDARIES.md) adds a prior-art comparison of syntax macros and compile-time evaluation; expansion safety, reproducibility, and resource bounds remain unvalidated. [Scenario 45](RESEARCH-SCENARIO-45-NUMERIC-SEMANTICS-AND-OVERFLOW.md) adds a prior-art comparison of integer widths/overflow, division, and floating-point modes; cross-target and backend outcomes remain unmeasured. [Scenario 46](RESEARCH-SCENARIO-46-STRINGS-UNICODE-AND-INDEXING.md) adds a Unicode text prior-art comparison; encoding validity, normalization/hash policy, and Unicode-version behavior remain to be prototyped. [Scenario 47](RESEARCH-SCENARIO-47-PUBLIC-RECORD-EVOLUTION.md) adds a source-versus-ABI compatibility comparison for public product and sum types; no compiler or binary-compatibility experiment has been run. [Scenario 48](RESEARCH-SCENARIO-48-CLOCKS-TIME-AND-DEADLINES.md) adds a clock prior-art comparison; suspend, timer, and replay behavior remain to be tested on target platforms. [Scenario 49](RESEARCH-SCENARIO-49-OPERATORS-CONVERSIONS-AND-PRECEDENCE.md) adds an operator/conversion comparison; parser and type-checker behavior remain to be prototyped. [Scenario 50](RESEARCH-SCENARIO-50-NAMES-IDENTIFIERS-AND-SCOPE.md) compares lexical scope, shadowing, namespaces, imports, runtime lookup, loop captures, and macro name provenance; a resolver fixture and edit-invalidation experiment remain to be run. [Scenario 51](RESEARCH-SCENARIO-51-ACCESS-CONTROL-AND-API-BOUNDARIES.md) compares Rust, Go, and Swift access control and exported API boundaries; interface compatibility and downstream invalidation remain to be prototyped. [Scenario 52](RESEARCH-SCENARIO-52-UNICODE-IDENTIFIERS-AND-SOURCE-SAFETY.md) compares identifier repertoire, NFC/NFKC identity, Unicode versioning, confusables, and source rendering; the lexer corpus and multilingual review study remain to be run. [Scenario 53](RESEARCH-SCENARIO-53-STATEMENT-TERMINATION-AND-NEWLINES.md) compares semicolon insertion, explicit terminators, newline continuation, and expression-valued blocks; parser and formatter fixtures remain to be prototyped. [Scenario 54](RESEARCH-SCENARIO-54-PATTERN-MATCHING-AND-EXHAUSTIVENESS.md) compares Rust, Swift, and Go on destructuring, exhaustive coverage, guards, and open variant evolution; matcher and ownership fixtures remain to be run. [Scenario 55](RESEARCH-SCENARIO-55-LOOP-RESULTS-LABELS-AND-CONTROL-TRANSFER.md) compares loop forms, value-producing exits, labeled transfers, and cleanup across Rust, Go, and Swift; CFG and ownership fixtures remain to be prototyped. [Scenario 56](RESEARCH-SCENARIO-56-CLOSURE-CAPTURE-AND-ESCAPE.md) compares closure capture, callable cardinality, escaping lifetimes, cycles, and concurrency safety across Rust, Go, and Swift; a closure type/lifetime prototype remains open. [Scenario 57](RESEARCH-SCENARIO-57-STRUCTURED-CONCURRENCY-AND-TASK-LIFETIMES.md) compares task-tree structure, scope exit, join/cancel, and detached work across Swift, Go, and Rust; task-tree and failure-injection prototypes remain open. The [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md) is the current integration point. It compares candidate bundles but deliberately selects none. The [Research Taxonomy](RESEARCH-TAXONOMY.md) remains the coverage register; neither is normative.

The strongest evidence is concentrated in language semantics, type/resource boundaries, identity/change lifecycle, package/build behavior, and bounded authorization:

| Area | Evidence available | Establishes | Does not establish |
|---|---|---|---|
| RT-01 workloads | Reference workload catalogue and executable CLI pilot with Python/C references | Shared concrete workloads and host-level observable behavior | LLMLang usability, workload weights, or performance versus candidate language profiles |
| RT-03/04 semantics | [Shared corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md), bounded evaluators and fixture families COR-01–13, including [Scenarios 36–41](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md), [Scenarios 97–107](RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md) | Distinguishing observations for errors, effects, state, cancellation, cleanup, typed calls, actor schedules, and one resource-return boundary; prior-art on effect rows/handlers versus traces, effect permission versus runtime authority, cleanup triggers and failure channels across Zig/Rust/Swift/Go, cancellation signaling versus task termination and cleanup completion, typed error sets/throws versus open error values and API evolution, recursion, higher-order and heap-hidden divergence propagation, recursive-group termination, runtime limits, abstract source-fuel and cleanup probes, fuel × owned-return outcome projection and independent audit, COR-07 cleanup aggregation, shared versus per-scope cleanup reserve, Scenario 97's bounded six-policy composition/obligation audit, Scenario 98's finite AST-path witnesses, Scenario 99's identical-marker path correlation, Scenario 100's finite predicate feasibility/witness comparison, Scenario 101's pinned DPLL2 route/model cross-check and one-family timing, Scenario 102's conservative UNKNOWN/UNSAT policy comparison with 128 fixed-seed generated formulas, Scenario 103's real timed worker isolation/reaping, Scenario 104's exhaustive mutation-identity counterexample, Scenario 105's call-summary state-transition comparison, and Scenario 106's exact/may-alias call-site transition comparison plus Scenario 107's bounded AST-derived alias summary and join-precision counterexample | Complete source semantics, parser/extractor correspondence, scalable solver trust/performance, broader timeout/failure behavior and negative-result verification, general source-derived alias- and call-aware mutation summaries beyond the bounded AST fixture, source/CFG completeness and path-sensitive alias precision, sound surface type system, general ownership model, LLMLang recursive evaluator/effect inference, effect-row/trace and capability-boundary conformance, closure/heap divergence conformance, source-level cleanup fuel/divergence/error-composition semantics across outcomes, integrated typed owned-value caller boundary, async cancellation/cleanup conformance, typed error/API evolution conformance, or validated concurrency runtime |
| RT-05 identity | Lifecycle, call-site refactoring, recursive group identity experiments | Counterexamples and trade-offs for continuity, call obligations, symmetric members, and change propagation | Canonical identity envelopes, authenticated lineage, import/merge completeness, or final Stable ID/value model |
| RT-06/20 dependencies | Scenario 15–34 studies and dependency/impact prototypes | Bounded dependency classification, counterfactual analysis, symbolic proof boundary, and plan/change lifecycle structures | Complete source dependency extraction, graph-completeness proof, or end-to-end accepted change correctness |
| RT-07/08 evidence | Lean/Logos CPC parser binding, strict QF_LIA relational query, source-to-query correspondence work | Exact binding and kernel-checked results for a declared narrow integer/boolean relational fragment | Proof of arbitrary LLMLang programs, complete evidence trust chain, or coverage of effects/resources/concurrency |
| RT-09/10/13 execution | Compiler/backend, LLVM, POSIX and runtime architecture proposals | Candidate boundaries and hazards worth testing | Selected execution model, backend equivalence, ABI, or measured feasibility |
| RT-11 incremental build | [Binding invalidation benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md) | In its synthetic C fixture, separate stable-ABI linkage reduces caller recompilation on an implementation-only edit | General LLMLang cache safety, real-language speedup, or validated action-key projection |
| RT-12 package/reuse | Package identity, manifest/index models, merge/closure/archive prototypes | Deterministic logical-index and exact-hash dependency behavior within prototype fixtures | Normative wire/archive format, multi-provider behavior, production store snapshot guarantees, or registry trust |
| RT-14/16/19/20–23 workflow/security | Toolchain/workflow proposals, Toolchain prototype, RT-16 threat model and authorization fixtures | Lifecycle boundaries, scoped authorization properties, replay cases, bounded workspace/change-set behavior | Production concurrency, sandbox security, signed evidence, full recovery, or final approval policy |

The latest bounded type/semantics results include a counterexample: transfer-first cleanup failure can require returning both an error and a still-owned value. The current typed-call/checker boundary cannot express that envelope. Effect summaries also lose ordering and payload details, and an open-row marker does not implement row unification or handler-coverage analysis. See COR-13 and the cross-profile comparison in the shared corpus and option matrix.

[Scenario 94](RESEARCH-SCENARIO-94-SCHEDULER-FAIRNESS-AND-LIVENESS.md) adds a prior-art comparison of conditional/runtime-specific scheduling fairness and keeps it distinct from protocol progress and task termination. [Scenario 95](RESEARCH-SCENARIO-95-DIAGNOSTICS-FOR-HUMANS-AND-AGENTS.md) extends the diagnostics work from Scenario 87 to structured diagnostic contracts, editor transport, repair proposals, and evidence-based human/agent evaluation. Both studies remain analytical: neither selects a language policy nor reports a new LLMLang prototype result.

[Scenario 96](RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md) extends LL-020 with a source-to-IR preservation comparison: LLVM poison/UB promises must be justified by source semantics, while source wrapping, checked failure, and memory-bound rules require explicit lowering. The source-to-IR corpus and target validation remain unrun; LLVM's backend role is unselected.

[Scenario 97](RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md) separates cleanup order, primary-cause selection, secondary-error carriage, catchability, and resource ownership. Java suppression, Go's explicit deferred-result composition and `errors.Join`, Rust's unreturnable `Drop` failure/double-panic boundary, and Swift's defer control-transfer rule provide distinct prior-art mechanisms. A bounded outcome model now runs 12 discriminators across six policies (72 observations) and a 13,230-case valid-input product; all pass a separately implemented owner/debt projection. Cause-carrier alternatives are distinguishable while cleanup traces and resource ownership remain independent projections. The result is finite implementation cross-checking only: no policy is selected, and source completeness, async/divergent cleanup, and independent review remain open.

[Scenario 98](RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) closes one bounded AST-path coverage gap: a seven-condition tree has 128 concrete Boolean assignments and eight unique feasible paths, each with a concrete witness. Recursive and small-step evaluators agree on every assignment's full event sequence and resource map, and their projections match the structural path model. This is not parser/source-to-AST completeness evidence; correlated predicates, symbolic feasibility, and human/formal review remain open.

[Scenario 99](RESEARCH-SCENARIO-99-REPEATED-PATH-PREDICATES.md) narrows the repeated-condition gap. Two sequential branches using the same fixture marker now produce only the two consistent paths (`TT`, `FF`), and both concrete assignments agree with both evaluators and distinct resource witnesses. This relies on test-assigned marker identity; equivalence/contradiction between different predicates, mutation-aware identity, symbolic feasibility, and source correspondence remain open.

[Scenario 100](RESEARCH-SCENARIO-100-FINITE-BOOLEAN-PATH-FEASIBILITY.md) adds an exhaustive truth-table analyzer over immutable Boolean variables with `not`, `and`, and `or`. For `x` followed by `x or y`, all four assignments induce three feasible branch vectors (`TT`, `FT`, `FF`); `TF` is impossible. Every vector has a concrete witness, and both evaluators plus the resource path projection agree. The analyzer is exponential in variable count and does not address effects, mutation, source extraction, or unbounded domains; solver performance and trust remain open.

[Scenario 101](RESEARCH-SCENARIO-101-SOLVER-VS-TRUTH-TABLE-PATHS.md) cross-checks the same path constraints using SymPy 1.14.0's explicit `dpll2` backend and compares witness routes with the exact truth-table result. It agrees on all three routes for `x` then `x or y`; a separate contradiction fixture confirms the impossible arm is excluded. A local median-of-three benchmark on one conjunction family shows near parity at 8 variables and lower solver times at 12–18 variables. This is a narrow easy-formula result, not a general SAT performance or soundness claim. Solver trust, difficult formulas, a real timeout boundary, parser/source correspondence, and effects/mutation remain open; Scenario 102 separately records the result-policy behavior for UNKNOWN.

[Scenario 102](RESEARCH-SCENARIO-102-SOLVER-UNKNOWN-AND-SOUND-PATH-PRUNING.md) compares exact finite, tri-state solver, hybrid, and proof-carrying path pruning. SMT-LIB defines `unknown` as inconclusive, Z3 exposes a timeout and `reason_unknown()`, and SymPy's pinned satisfiability API has no documented per-query timeout. Eight result-policy fixtures show that only a replayed witness proves feasibility and only an explicitly supported UNSAT basis prunes a may-path; timeout, unsupported/error, invalid model, and untrusted UNSAT remain unknown. A fixed-seed CI fixture cross-checks 128 random depth-four Boolean formulas against exact enumeration; a separate 300-formula run also agreed on route sets and replayed witnesses. The timeout case was injected at the policy boundary, not forced in a real backend. Hard formulas, actual worker termination/recovery, proof checking, mutation-aware identity, and source correspondence remain open.

[Scenario 103](RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md) adds a one-request POSIX worker around pinned SymPy DPLL2. A 12-pigeon/11-hole UNSAT query hit a real 0.5-second wall-clock deadline after worker startup; the parent killed and reaped the worker, reported UNKNOWN with no model, and the existing result mapper retained the route. Small 2/2 SAT and 3/2 UNSAT instances completed; the latter still did not qualify to prune because the backend is untrusted and emits no checked certificate. This closes only the actual-timeout/worker-isolation slice. Repeated performance distributions, crash/protocol fault cases, memory and concurrency bounds, checked UNSAT, and source/CFG correspondence remain open.

[Scenario 104](RESEARCH-SCENARIO-104-MUTABLE-PREDICATE-IDENTITY.md) exhausts both initial Boolean states for two sequential branches separated by `x := not x`. Name-conflated analysis reports only `FF`/`TT` and drops the concrete `FT`/`TF` routes; independent `x@0`/`x@1` versions admit all four routes; adding the explicit toggle transition recovers exactly the concrete set. This demonstrates why path predicates must refer to state versions and write transitions; aliasing, effectful calls, loops, and source extraction remain open.

[Scenario 105](RESEARCH-SCENARIO-105-CALL-MUTATION-SUMMARIES.md) exhausts the four Boolean state pairs around a call. A complete pure summary preserves `x`; a complete toggle summary yields only crossed routes; an incomplete/may-write summary allows all post-call values. Reusing the source name across the call drops possible routes when mutation/aliasing is unknown. These are hand-supplied abstract transitions, not source-derived effect analysis; alias sets, dynamic dispatch, call-graph completeness, and provenance remain open.

[Scenario 106](RESEARCH-SCENARIO-106-CALL-ALIAS-SETS-AND-FIELD-SENSITIVE-PATHS.md) exhausts exact and uncertain call-site targets for a callee that toggles one referenced field. Exact `flag` and exact disjoint `other` targets produce distinct route pairs; a may-alias set or unknown target set unions them and retains all routes. Treating a possible alias as disjoint drops reachable behavior.

[Scenario 107](RESEARCH-SCENARIO-107-SOURCE-DERIVED-CALL-ALIASES.md) extracts the toggle summary and call targets from a bounded Python-shaped AST subset, then compares its alias-based route relation with exhaustive fixture execution. It preserves all routes in the tested cases, but non-relational branch joins can add infeasible routes when alias targets correlate with predicate state. Eight tests reject unsupported mutations/fields. This is a bounded source adapter, not LLMLang parsing or source/CFG completeness; general path-sensitive alias, call, loop, heap, and concurrency analysis remain open.

## 2. Candidate vectors still open

The current matrix keeps these integrated candidates for comparison:

- **C1 — Verifiable pure-first language:** pure strict core, explicit effects/capabilities, reference semantics first, later native backend.
- **C2 — Systems language with explicit ownership:** ordered mutation and ownership/borrowing, with a conservative verification boundary.
- **C3 — Isolated concurrent language:** message/protocol types with trace and model-checking evidence.
- **C4 — Effectful functional language:** immutable functional core with explicit handlers and effectful runtime boundaries.

These are candidate bundles, not exhaustive specifications. No vector has passed the complete compatibility gates.

## 3. Cross-area constraints supported by current evidence

1. **RT-03 and RT-04 must be compared together.** Equal scalar outputs do not imply equal observable traces. State-handler logging/rejection and actor delivery order provide counterexamples.
2. **Effects need more than a set of effect names.** Ordering, payloads, handler behavior, terminal outcomes, and environmental inputs can change observations and evidence reuse.
3. **Resource cleanup and ownership cross call boundaries.** Cleanup precedence, failure, transfer, and retained values need one outcome model before ownership or error constructors can be frozen.
4. **Identity, compatibility, and behavior are distinct.** Contract conformance does not imply equivalence suitable for inlining; recursive group identity creates caller invalidation; continuity requires explicit lifecycle evidence.
5. **Proof claims must name their exact fragment and inputs.** The QF_LIA/Lean work validates a narrow relational-query pipeline, not general source programs.
6. **Runtime/backend claims need a shared preservation gate.** Architecture proposals and C compiler experiments do not establish that multiple LLMLang backends preserve one source semantics.
7. **Content integrity is not trust.** Hashes do not identify an authorized publisher, verifier, approver, or trusted evidence producer.
8. **Unknown is a research result, not a numeric failure score.** Candidate scoring must expose unknowns and test sensitivity to workload weights.

These refine existing dependency hypotheses; they do not add normative rules. See [Research Dependency Map](RESEARCH-DEPENDENCY-MAP.md), especially the RT-03/04, RT-05/06/07/08, RT-09/10/13, RT-11/12, and RT-14/16/19/20 edges.

## 4. Research gates before RFC synthesis

### Gate A — Shared source-level semantics and type/resource boundary

- Define source-level rules for calls, branches, Result/error propagation, cancellation, resource acquire/use/release, transfer/return, and cleanup failure.
- Make ordered effects and payloads visible to type/dependency summaries.
- Add a typed owned-value return scenario for COR-13.
- State where profiles differ and what equivalence means for results, traces, resource state, and divergence.
- Compare total recursion, general partiality, typed divergence, source fuel, VM operator gas, and external limits; define how exhaustion interacts with effects, rollback, and cleanup.
- Record independent review; parallel evaluators against one hand-authored contract are implementation checks, not independent specification validation.

### Gate B — Identity and dependency completeness

- Compare R-A/R-B/R-C on common import, rename, move, duplicate, split/merge, recursive, call-site edit, and branch-conflict cases.
- Specify exact call/contract/implementation bindings and which observations each artifact hash commits to.
- Validate dependency extraction against source mutations, including negative and fallback lookups.
- Preserve conservative UNKNOWN wherever completeness or provenance is absent.

### Gate C — Evidence and backend preservation

- For each evidence class, record proposition, assumptions, exact source/tool/target inputs, producer identity, trust boundary, soundness claim, and reuse rule.
- Extend the two-backend gate to an executable shared workload; compare outputs, effects, errors, resources, diagnostics, and rejected constructs against reference semantics.
- Keep proof coverage narrow and explicit; unsupported constructs must not inherit proof status.

### Gate D — Workload and human/agent evaluation

- Run reference workloads on candidate implementations when available.
- Define workload weights before aggregate scoring. Publish sensitivity results.
- Measure authoring success, repair attempts, diagnostics, context/token use, and scope violations in controlled agent tasks.
- Keep usability and correctness evidence separate.

### Gate E — Security and operational lifecycle

- Exercise authorization with persistent concurrent clients and crash injection around apply/accept/commit/push/publication.
- Establish sandbox behavior for filesystem, network, credentials, process lifetime, and resource exhaustion.
- Define authenticated evidence and package provenance separately from content hashing.
- Validate worktree isolation and recovery on interrupted operations.

## 5. Suggested next sequence

1. Close Gate A with a narrow source-level owned-resource call boundary, ordered effect summary, and recursive termination/budget semantics; continue path feasibility with timeout distributions, worker fault/resource bounds, hard formula families, checked negative-result evidence, and source/IR-bound mutable versions and field-sensitive effects across aliases, calls, and loops.
2. In parallel only where independent, continue Gate B with identity/import completeness and Gate E with persistent authorization/sandbox experiments.
3. Select a small cross-profile executable slice only after Gate A rules are explicit; keep RT-03 alternatives separate in the harness.
4. Run reference semantics and a second implementation/backend against that slice.
5. Update the option matrix with measured outcomes and confidence; do not score candidates while major criteria remain unknown.
6. Draft an RFC only after candidate vectors have explicit compatibility results, failed/unknown cases, and workload-weight sensitivity.

This is planning, not approval of a semantic profile. A scoped RFC may be possible earlier if it labels unresolved parts and does not imply a complete language selection.

[Scenario 70](RESEARCH-SCENARIO-70-TYPE-ALIASES-NEWTYPE-AND-OPAQUE-ABSTRACTIONS.md) separates identity-preserving aliases, fresh nominal wrappers, hidden implementation, and explicit representation/ABI guarantees across Rust, Go, Swift, and Zig. Assignment, invariants, separately compiled API evolution, serialization, opaque client operations, and target ABI behavior remain open; no LLMLang policy is selected.

[Scenario 71](RESEARCH-SCENARIO-71-INTERFACE-IMPLEMENTATION-OWNERSHIP-AND-COHERENCE.md) compares owner-local explicit coherence (Rust), implicit structural satisfaction (Go), explicit/retroactive conformance (Swift), and global type-class instances with orphan/overlap rules (Haskell). Cross-package conflict scenarios, API evolution, deterministic lookup, and dependency invalidation remain untested; no LLMLang policy is selected.

[Scenario 72](RESEARCH-SCENARIO-72-SUM-TYPE-LAYOUT-ABI-AND-INTEROPERABILITY.md) separates sum-case semantics from storage layout, calling conventions, resilience, and foreign representation across Rust, Zig, Swift, and C. Cross-target ABI probes, unknown/invalid tag handling, version-skew behavior, and bridge costs remain open; no LLMLang representation policy is selected.

[Scenario 73](RESEARCH-SCENARIO-73-NUMERIC-LITERAL-TYPING-AND-CONVERSIONS.md) expands Scenario 45's literal/coercion axis: Rust infers/defaults literal types, Go retains exact untyped constants, Swift uses contextual literal protocols, and Zig exposes comptime-only literal types. Runtime conversions and mixed-operand peer typing remain separate and untested; no LLMLang policy is selected.

[Scenario 74](RESEARCH-SCENARIO-74-REFUTABLE-PATTERN-FAILURE-AND-BINDING.md) extends Scenario 54 from pattern vocabulary/exhaustiveness to mismatch handling: Rust/Swift branch or exit bindings, Go comma-ok results, and C# Boolean pattern tests. Definite assignment, nested partial cleanup, and error propagation remain open; no LLMLang rule is selected.

[Scenario 75](RESEARCH-SCENARIO-75-AUTOMATIC-DISPOSAL-AND-LIFETIME.md) separates scope-bound deterministic cleanup (Rust drop, Zig/Go defer), Swift ARC object lifetime, and Go GC cleanup/finalizers that may not run before exit. Async close, aliases/cycles, cleanup failure, and process abort remain open; no LLMLang resource-lifetime policy is selected.

[Scenario 76](RESEARCH-SCENARIO-76-REGULAR-EXPRESSION-SEMANTICS-AND-RESOURCE-BOUNDS.md) fills an explicit gap left by Scenario 46: regex dialect and runtime bounds. Rust/Go use bounded engines with deliberate syntax limits, .NET exposes backtracking and nonbacktracking modes, and Swift Foundation documents ICU compatibility without the cited same complexity bound. Adversarial inputs, Unicode versioning, capture semantics, and cancellation remain open; no LLMLang policy is selected.

## 6. Evidence quality and traceability

For each new result, retain exact branch/commit, files, command and tool versions, fixture selection, assumptions, positive/negative cases, limitations, evidence class, and the vector it could falsify. Update the taxonomy and option matrix when scope changes. Keep decisions in [TODO and open decisions](../TODO.md) open until explicitly accepted.

## 7. References

- [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md)
- [Research Taxonomy](RESEARCH-TAXONOMY.md)
- [Shared Semantics Corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md)
- [RT-05 Identity Lifecycle Experiment](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md)
- [RT-05/RT-20 Call Site Refactoring Experiment](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md)
- [RT-05 Recursive Identity Experiment](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md)
- [RT-11 Binding Invalidation Benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md)
- [RT-16 Threat Model 01](RT-16-THREAT-MODEL-01.md)
- [TODO and open decisions](../TODO.md)
