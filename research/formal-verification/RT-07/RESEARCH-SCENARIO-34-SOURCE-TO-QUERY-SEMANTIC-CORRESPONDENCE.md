# Research Scenario 34 — Source-to-Query Semantic Correspondence

**Status** — In progress. Lean proves that the canonical relational formula is satisfiable exactly when paired executions of the checked Int/Bool fragment witness dependence. The lowered formula fits the strict QF_LIA profile, and each symbol has a unique declaration of the correct sort. JSON correspondence and source-derived CPC binding remain open.

**Date:** 2026-11-17  
**Depends on:** Scenarios 26–33.  
**Question:** What must be defined and proved before a QF_LIA relational query generated from an LLMLang program can be treated as a faithful encoding of that program's semantics?

## 1. Objective and trust boundary

The outstanding gap is not another serialization check. It is a semantic theorem connecting:

1. a well-formed source program in a precisely delimited deterministic fragment;
2. its execution under an explicit input and initial state;
3. the paired executions used for a counterfactual dependency query;
4. the Boolean formula represented by the canonical relational query IR.

The theorem must be independent of Python tests and independent of the SMT solver. Python may remain the current query producer, but Lean must define the source-fragment semantics and validate or reconstruct the query in a way that does not trust Python's claim that the query is correct.

The proof is staged. A theorem about expressions is not a theorem about commands; a theorem about one execution is not a theorem about paired execution; a theorem about a Lean query evaluator is not yet a theorem about SMT-LIB or CPC.

## 2. Initial source fragment

The first formal fragment is intentionally smaller than the Python prototype's accepted syntax.

### 2.1 Values and types

- Values are mathematical integers and Booleans.
- Types are exactly `Int` and `Bool`.
- Integer arithmetic is unbounded mathematical arithmetic, not machine-word arithmetic.
- Boolean operators have ordinary two-valued semantics.
- Equality is type-preserving; ordering is defined only for integers.

This is the same arithmetic model required by QF_LIA. Machine overflow, floating point, strings, pointers, and memory aliasing are outside this fragment.

### 2.2 Expressions

The initial expression grammar contains:

- integer and Boolean literals;
- typed input/local/state variable references;
- unary integer negation and Boolean negation;
- integer addition, subtraction, and multiplication by a literal integer constant;
- integer and Boolean equality;
- integer less-than and less-than-or-equal;
- Boolean conjunction and disjunction;
- typed conditional expressions (`ite`).

The source typing relation must be explicit. The query IR's result-sort index is not a substitute for proving that the source expression is well typed.

Multiplication is accepted only when at least one operand is syntactically an integer literal after the source fragment's specified normalization. No algebraic simplification or constant folding may be silently assumed by the proof.

### 2.3 Commands and program shape

The initial command grammar contains:

- assignment to a local;
- assignment to an explicitly declared observable or internal state region;
- conditional with two command sequences;
- one top-level final return.

The initial program has:
- an explicit finite declaration context for inputs, locals, and state regions;
- a fully specified initial state;
- no uninitialized reads;
- no loops, recursion, exceptions, events, I/O, external calls, concurrency, nondeterminism, or pointer/alias operations;
- no early return from a nested branch; control flow is normalized so every path reaches the single final return.

The prototype may accept a wider set than the first theorem. The theorem's accepted grammar is authoritative for the proof milestone; unsupported constructs must be rejected rather than approximated.

## 3. Source operational semantics

A configuration consists of the current scope and runtime slots. Every initialized declaration has a slot of its declared sort, keyed by stable ID. Uninitialized declarations have no value. The source evaluator uses big-step rules for the initial fragment without loops. A command takes one configuration to another. The final expression is evaluated in the resulting configuration.

The rules must specify:

- expression evaluation against the current locals and state;
- assignment evaluation before updating the target;
- branch selection using the evaluated Boolean condition;
- sequential command execution;
- final return evaluation after all preceding commands.

State writes are sequential and visible to later commands. Observable state is selected by an explicit observation contract; internal state must not become observable merely because it exists in the implementation.

The semantics must be deterministic. Prove determinism before using a single-valued execution function in the relational theorem.

## 4. Relational semantics

For a selected input factor (p), construct two initial input environments (
ho_L) and (
ho_R) with these constraints:

- the selected factor may differ;
- every other declared input is equal on both sides;
- initial state is identical;
- any already initialized local also has the same entry value on both sides;
- no other environmental source exists in this fragment.

Run the same source program on both sides from the same initial state. Define the observation as a typed tuple containing:

- returned value;
- values of exactly the state regions named by the observation contract.

The contract supplies an ordered list of distinct declaration IDs and their sorts. Each ID must name a visible, initialized state region at the return point. A field outside this list has no observation slot. The contract can select an empty state tuple when the return value is the only output.

The initial fragment has only normal termination. The outcome discriminator can therefore be omitted, but this omission is justified only by the source grammar and a proof that every accepted program returns normally. It must not be generalized to a language with exceptions or divergent execution.

Define:

`FactorDiff := inputL[p] ≠ inputR[p]`

`ObservationDiff := observe(run(P, ρL, σ0)) ≠ observe(run(P, ρR, σ0))`

The query's intended proposition is:

`FactorDiff ∧ ObservationDiff`

A satisfying assignment is a concrete counterexample witness that changing only factor (p) can change an observed result. Unsatisfiability establishes independence only under the stated fragment, input model, and observation contract.

## 5. Required correspondence theorems

The proof must be split into independently reviewable lemmas.

### SC-1 — Expression typing preservation

If a source expression is well typed with result sort (s), its translation is a well-typed QueryTerm of sort (s).

### SC-2 — Expression evaluation preservation

For every well-typed source expression (e) and well-formed environment (
ho):

`evalSource(e, ρ) = evalQuery(translateExpr(e), ρ)`

This theorem covers all accepted expression constructors, including Boolean operations, comparisons, conditional expressions, and literal multiplication.

### SC-3 — Command-sequence preservation

For every accepted command sequence and initial local/state environment, source execution and translated symbolic execution produce equivalent final locals and state.

The symbolic execution result must retain path conditions. Conditional branches may be represented by guarded updates or by `ite`; the proof must show that the chosen representation is equivalent to operational branch selection.

### SC-4 — Program observation preservation

For every accepted program and input/state environment, the observation extracted from source execution equals the observation extracted from the translated execution.

### SC-5 — Paired-execution preservation

For every pair of input environments satisfying the shared-input and shared-initial-state constraints, the two translated executions preserve both source observations. This must be proved for arbitrary left/right values, not only finite test domains.

### SC-6 — Relational-query correctness

The canonical query formula evaluates to true exactly when:
- the selected factor differs between the two inputs; and
- the source observations differ.

This is the core source-to-query correspondence theorem.

### SC-7 — QF_LIA admissibility

Every admitted program, contract and factor yields a quantifier-free Boolean formula over `Int` and `Bool` in the strict QF_LIA term profile. Each multiplication has an integer literal operand. Each conjunction or disjunction has at least two operands. Solver-facing declaration closure must preserve the sort and source role of every referenced symbol (SCW-30).

## 6. Lean implementation architecture

Do not put all semantics into the existing Logos binding module. Split the proof core from the external checker integration.

Proposed modules:

- `SourceSyntax.lean` — declaration contexts, well-formed scopes, and access checks.
- `CheckedSourceSemantics.lean` — scope checking for the indexed expression AST, typed runtime slots, and expression-level correspondence with the independent query IR.
- `SourceCommandSemantics.lean` — command syntax, static initialization checking, concrete execution and its proofs.
- `SourceSemantics.lean` — expression evaluation and deterministic command/program execution.
- `SymbolicCommandSemantics.lean` — typed substitution, guarded path states and command-sequence preservation.
- `ProgramObservationSemantics.lean` — observation admission, typed output tuples and their preservation.
- `PairedObservationSemantics.lean` — admissible input pairs, shared entry slots and preservation of both observations.
- `CanonicalQuerySymbols.lean` — stable declaration keys, typed symbol bindings and conversion between canonical and paired valuations.
- `ProgramRelationalQuery.lean` — compilation of the relational formula and proof of equivalence to concrete dependence.
- `QfLiaQuery.lean` and `QfLiaAdmissibility.lean` — the solver term profile and proof that every compiled formula lowers into it.
- `SolverRelationalQuery.lean` — the lowered formula, its declaration table and the proof that symbol lookups preserve source bindings.
- `Correspondence.lean` — SC-1 through SC-7 theorems.
- `LogosBinding.lean` — existing CPC parser bridge, JSON decoder, and Eo.Term renderer.

The Lean proof core must not import cvc5, invoke a solver, or trust Python-generated proof claims. The external Logos binding can consume a query only after Lean has validated its source/query correspondence certificate or independently reconstructed the expected query.

Avoid introducing a generic compiler framework prematurely. The first formalization should use a small inductive syntax and explicit functions.

## 7. Fine-grained implementation plan

The work is split into small reviewable tasks. A task is complete only when its artifact exists, the relevant theorem is kernel-checked, and CI exercises the module. Python tests and finite examples are regression evidence, not substitutes for Lean theorems.

### 7.1 Baseline and proof boundary

- [x] **SCW-01 — Record the exact QF_LIA source subset.** Keep the initial source grammar and exclusions explicit (Sections 2 and 10).
- [x] **SCW-02 — Record the current expression-level proof boundary.** `SourceQuerySemantics.lean` contains an independent typed source/query expression AST and `translateExpr_preserves_eval`.
- [x] **SCW-03 — Record the existing relational-expression prototype.** `RelationalSourceQuerySemantics.lean` contains per-side expression translation, selected-factor renaming, shared non-factor names, and expression-level factor/observation difference lemmas.
- [x] **SCW-04 — Audit the current modules against the intended trust boundary.** The audit is recorded in [SCW-04-MODULE-BOUNDARY-AUDIT.md](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SCW-04-MODULE-BOUNDARY-AUDIT.md). It records the pre-SCW-15 source graph: `SourceQuerySemantics.QueryTerm` existed independently, but relational proofs still used `LogosBinding.QueryTerm`. This was a historical dependency finding; SCW-15 later implemented the independent relational core and separate preservation adapter, as recorded below and in the audit's current-source addendum. The audit itself did not upgrade a theorem.

**Outputs:** reviewed baseline inventory; explicit list of proved expression claims and unproved command/program claims; module dependency diagram.

### 7.2 Source syntax, typing, and environments

- [x] **SCW-05 — Define declaration contexts. The seven-task [SCW-05 breakdown](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SCW-05-DECLARATION-CONTEXT-BREAKDOWN.md) is now marked complete; its scope does not include SCW-06 context-wide validation.** `SourceSyntax.lean` represents input, local, and state declarations with stable IDs and `Int`/`Bool` sorts. [Pinned CI](https://github.com/aivibeflow/LLMLang/actions/runs/44508142320/job/135505028634) built the module and passed identity-lookup tests. Context-wide uniqueness and scope checks belong to SCW-06.
- [x] **SCW-06 — Define source well-formedness.** Require unique IDs and spellings, constrain visibility and initialization, and check read, write and observation eligibility. [Scope model](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceSyntax.lean)
- [x] **SCW-07 — Prove expression typing preservation.** `translateExpr_symbols` preserves the reference list and its sorts. `checkedTranslate_binds_symbol` binds each symbol in an accepted query to the source declaration and its stable ID.
- [x] **SCW-08 — Define typed runtime environments.** Runtime slots are keyed by stable ID. `RuntimeEnv.Satisfies` checks that every initialized declaration has a value of its declared sort and that the other declared slots are absent.
- [x] **SCW-09 — Prove expression evaluation totality and determinism.** `evaluation_total` and `evaluation_deterministic` give existence and uniqueness under the scope, expression and environment checks. `evaluateChecked_eq_some` connects that relation to the executable evaluator.

The fragment has one namespace, with visible inputs and state regions initialized and locals explicitly marked as initialized after assignment. Reads require a visible initialized declaration. Writes can initialize locals and update state. The observation contract can select initialized state regions. Static checking visits both conditional arms, including an arm the evaluator never takes.

`checkedTranslate_preserves_evaluation` proves that the query has the unique source result whenever the query environment agrees with actual values for the checked reads. The evaluator can adapt the runtime slots to the existing mathematical evaluator with arbitrary defaults for other names, since `evalExpr_agrees_on_reads` proves those defaults cannot change the result. This theorem covers the indexed Int/Bool AST and its named references. Later phases extend the result to state transitions and whole-program symbol binding. [Checked semantics and proofs](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CheckedSourceSemantics.lean)

`lake build LLMLangLogosBinding` on Lean 4.34.0 kernel-checks the two modules and `SourceCoreTests.lean` in Required CI. The examples cover duplicate names and IDs, invalid scope and initialization, rejected accesses, missing and wrong-sort slots, and preservation of an expression mixing Int and Bool. The theorem axiom audit reported only Lean's `propext`, `Classical.choice`, and `Quot.sound`. [Checked examples](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceCoreTests.lean)

### 7.3 Expression translation and semantic preservation

- [x] **SCW-10 — Prove pure expression evaluation preservation.** Existing `translateExpr_preserves_eval` proves the deliberately small typed Int/Bool expression fragment.
- [x] **SCW-11 — Prove per-side relational expression translation.** Existing `translateRelationalExpr_correct` relates relational query terms to source evaluation under side-specific environments.
- [x] **SCW-12 — Prove canonical input-symbol mapping for expressions.** Existing `translateCanonicalRelationalExpr_correct` covers indexed `i_N`, `i_N_L`, and `i_N_R` naming at expression level.
- [x] **SCW-13 — Prove selected-factor split and non-selected-input sharing.** Existing left/right binding and `nonFactorInputsAreShared` lemmas establish these symbol-level facts.
- [x] **SCW-14 — Prove expression-level factor and observation difference formulas.** Existing `factorDifference_correct`, `observationDifference_correct`, and `relationalAssumptions_correct` cover expression results, not whole programs.
- [x] **SCW-15 — Remove accidental dependency on the external Logos AST from the semantic proof core.** `RelationalSourceQuerySemantics.lean` imports only `SourceQuerySemantics` and uses its independent `QueryTerm`. `LogosQueryAdapter.lean` maps that IR to `LogosBinding.QueryTerm` with the kernel-checked theorem `toLogosQueryTerm_preserves_eval`. The pinned Lean build and semantic correspondence checks passed on [PR #41](https://github.com/aivibeflow/LLMLang/actions/runs/44386169159), [Required CI for PR #43](https://github.com/aivibeflow/LLMLang/actions/runs/44508142320/job/135505028634), and the later [Logos-binding CI run for PR #94](https://github.com/aivibeflow/LLMLang/actions/runs/44766546452).

**Outputs:** expression-level theorem suite; canonical symbol map; independent query semantics; a small separately verified Logos adapter.

### 7.4 Command and program semantics

- [x] **SCW-16 — Define the command AST.** Support local and state writes, sequencing, Boolean branches, and one typed final return. `Program.check` checks write roles and sorts, and derives the definite initialization set before the return.
- [x] **SCW-17 — Define source big-step execution.** `Executes` evaluates the right-hand side before storing, threads slots through sequences, and runs the selected branch. `Program.execute_eq_some` proves that the executable evaluator agrees with the big-step program rules.
- [x] **SCW-18 — Prove source execution determinism.** `Program.Executes.deterministic` proves uniqueness of the final configuration and value. `Program.checked_execution_exists` proves a normal return for each program that passes the static check and starts with a satisfying runtime environment.
- [x] **SCW-19 — Define symbolic execution state.** A symbolic path has typed query-term slots keyed by declaration ID, its current initialization set and its branch tests.
- [x] **SCW-20 — Define symbolic assignment and conditional translation.** Substitute the current slot terms into the right-hand side before writing. At a join, keep the alternatives with their accumulated guards. Both alternatives must pass the source checker, including definite initialization.
- [x] **SCW-21 — Prove command-sequence preservation (SC-3).** `translateCommands_preserves` proves that for each initial valuation exactly one path is active and it denotes the concrete final configuration, including current state values and locals initialized only on that path.
- [x] **SCW-22 — Define the observation contract.** `checkObservedProgram` admits a program and a distinct, ordered list of state slots at their declared sorts. The typed output contains the final return and exactly the selected slots.
- [x] **SCW-23 — Prove program observation preservation (SC-4).** `translateProgramObservations_exists` constructs a translation for every admitted program and contract. `translateProgramObservations_preserves` proves that for every initial valuation the unique active symbolic observation evaluates to the concrete observation.

Declarations and visibility are fixed during execution. The static checker intersects definite initialization at a branch join. Concrete execution keeps any additional locals initialized on the selected path. `Command.check_has_execution` proves that the concrete path maintains the initialization required by the checker. `Executes.preserves_validity` keeps the typed runtime invariant across every command. [Command semantics and theorems](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceCommandSemantics.lean)

The required Lake build compiles 22 kernel-checked examples for concrete commands. [Command examples](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceCommandTests.lean)

`SymbolicState.initial_represents` shows that every well-typed runtime store is represented on declared slots under a suitable initial valuation. Symbolic execution starts with declared source spellings. SCW-28 replaces them with canonical keys when it builds the relational formula. The preservation proof evaluates guards against their terms at the branch point, so a later write cannot retroactively change an earlier branch. Guarded alternatives can grow exponentially with the number of branches. [Symbolic semantics and theorems](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SymbolicCommandSemantics.lean)

The required Lake build also compiles 17 kernel-checked symbolic examples. They cover nested branches, a flag changed before a subsequent branch, write-then-read after a join, path-local initialization, and rejected accesses. The two main symbolic theorems use only Lean's standard axioms `propext`, `Classical.choice`, and `Quot.sound`. [Symbolic examples](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SymbolicCommandTests.lean)

SC-4 projects the same return and state sorts on both sides. On the symbolic side each path retains its guards and the terms for contract outputs. The proof uses command preservation to select the concrete final state, then proves that each selected slot is present and denotes the corresponding value. Observations can use any declared initial values represented by `SymbolicState.initial_represents`. The result applies to a single run and the independent query IR. [Observation model and theorem](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ProgramObservationSemantics.lean)

The required Lake build compiles 18 observation examples. They cover both branches, different field orders, a return-only contract, and two executions with different writes to an unselected state slot and identical observations. Rejection cases exercise duplicates, undeclared or hidden state, input and local slots, and sort mismatches. The admission, translation and preservation theorems use only Lean's standard axioms `propext`, `Classical.choice`, and `Quot.sound`. [Observation examples](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ProgramObservationTests.lean)

### 7.5 Paired execution and relational query

- [x] **SCW-24 — Define paired input environments.** `PairedValuations.check` accepts two typed valuations when the selected ID is a visible, initialized input and all other initialized declarations agree. `shared_slot` and `shared_state` prove equality of the corresponding concrete entry slots. `factor_values` ties the chosen inputs to the selected declaration.
- [x] **SCW-25 — Prove paired execution preservation (SC-5).** `pairedObservations_preserved` proves that executing the program twice and evaluating the compiled observations on the two valuations produce the same ordered pair of typed observations. Both valuations range over arbitrary mathematical Int and Bool values.
- [x] **SCW-26 — Define the complete relational proposition.** `compileRelationalQuery` constructs `FactorDiff ∧ ObservationDiff` over the checked program and observation contract. `compileRelationalQuery_exists` proves that admitted programs, contracts and factors yield a formula.
- [x] **SCW-27 — Prove relational-query correctness (SC-6).** `compileRelationalQuery_correct` proves the equivalence for every canonical valuation. `compileRelationalQuery_satisfiable_iff` proves that the formula is satisfiable exactly when an admitted pair of source executions has different factor values and observations.
- [x] **SCW-28 — Bind formula symbols to source declarations.** `RelationalQuery.symbol_binding` binds every reference by name and sort. `symbolBindings_names_nodup` proves declaration uniqueness. `sideValuation_slot` and `sideValuation_forPair_slot` establish exact left, right and shared identity in both directions.

The pair checker permits equal factor values. The formula requires them to differ and compares the return and each contract-selected state slot. The compiler merges guarded paths with typed `ite` terms for each observation slot, using the unique active path proved by SC-4. The fallback at the end of the conditional chain is unreachable for a checked program. [Paired semantics](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/PairedObservationSemantics.lean) · [Relational compiler and proofs](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ProgramRelationalQuery.lean)

The internal Lean symbol names use `i_` followed by the decimal value of `3 × stableID + role`. Role 0 is shared, 1 is left, and 2 is right. Only the selected input has separate left and right symbols. Every other initialized entry slot shares one symbol. Encoding an admitted source pair and decoding its valuation restores both concrete initial configurations. SCW-31 connects these internal keys to the version-2 wire envelope. [Canonical symbol bindings](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CanonicalQuerySymbols.lean)

The Lake build includes 16 relational examples covering Int and Bool factors, both branch directions, equal factors, return-only and state-only differences, a source spelling that collides with a canonical name, replay of a concrete pair, and rejected factors and contracts. [Relational examples](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ProgramRelationalQueryTests.lean)

### 7.6 QF_LIA admissibility and external wire/checker boundary

- [x] **SCW-29 — Prove QF_LIA admissibility (SC-7).** `compileRelationalQuery_qfLia` proves that each admitted program, contract and factor compiles to a formula whose lowered term passes the strict QF_LIA check.
- [x] **SCW-30 — Prove declaration closure for the solver-facing query.** Every symbol has exactly one declaration with its sort, and lookup recovers its original stable source declaration and shared, left or right role.
- [x] **SCW-31 — Define the canonical JSON correspondence boundary.** An accepted decode uses the exact source-generated bytes and yields the same declarations and typed terms as the corresponding Lean-owned query. [Typed JSON correspondence](RT-07-TYPED-JSON-CORRESPONDENCE.md)
- [x] **SCW-32 — Connect the proved formula to Logos terms.** For the admitted Int/Bool fragment, the adapter preserves sort and interpretation and retains the exact parser-state bindings. The [concrete-pair theorem](RT-07-LOGOS-CONCRETE-PAIR-LIFTING-2026-11-24.md) proves both valuation directions in combination with SCW-33 after validation of the parser binding table shape. The public verdict soundness application remains under SCW-34.
  - The typed renaming stage used by the source envelope preserves evaluation under a related valuation. The JSON gate ties the decoder output to those renamed terms. [Wire symbol renaming](RT-07-WIRE-SYMBOL-RENAMING.md)
  - The [finite scalar comparison](RT-07-LOGOS-SCALAR-DENOTATION-2026-11-24.md) checks the values of 1,536 rendered expressions and the assumptions for 96 concrete pairs through the pinned SMT translation.
  - The [scalar preservation theorem](RT-07-LOGOS-SCALAR-PRESERVATION-2026-11-24.md) extends the expression result to all typed source expressions under related valuations in a restricted evaluator.
  - The [valuation binding theorem](RT-07-LOGOS-VALUATION-BINDING-2026-11-24.md) discharges the expression theorem's constant relation for successfully constructed tables.
- [x] **SCW-33 — Bind exact CPC assumptions to the proved source-derived formula.** The [program bridge theorem](RT-07-LOGOS-PROGRAM-ASSUMPTIONS-2026-11-24.md) connects the two ordered parsed assumptions with the Lean-reconstructed source conjuncts and relates their values to source dependence under every successfully interpreted wire valuation.
- [ ] **SCW-34 — State the solver/checker trust boundary.** Document which theorem is Lean-kernel checked, which result is Logos-checked, and what remains trusted or assumed.
  - A bounded wire fixture distinguishes source reconstruction, exact assumption binding and a complete Logos verdict. [Source-to-wire acceptance](RT-07-SOURCE-WIRE-LOGOS-ACCEPTANCE.md)
  - The [upstream scalar model proof](RT-07-LOGOS-UPSTREAM-SCALAR-MODEL-2026-11-24.md) checks semantic agreement for every successful restricted evaluation with related constants.
  - The [single-kernel program theorem](RT-07-LOGOS-SINGLE-KERNEL-PROGRAM-2026-11-24.md) proves the accepted program assumptions' meaning in an upstream model that agrees at the resolved constants. Applying full Logos verdict soundness remains open.
  - The [model extension proof](RT-07-LOGOS-MODEL-EXTENSION-2026-11-24.md) supplies a well-formed agreeing model for each scalar valuation. Its unconditional form uses the upstream existence theorem and inherits a native computation axiom, which the audit records separately from the conditional overlay proof.

`QueryTerm.isQfLia` checks the typed term tree shared by the adapter, JSON decoder and Logos renderer. Its constructors fix the operators and their Int/Bool sorts. The check descends through all operands, including both branches of a conditional. `toLogosQueryTerm_qfLia` proves admissibility by induction on the independent query IR. In particular, `mulConst` lowers to a multiplication with an explicit integer literal, and each binary Boolean connective lowers to a two-element operand list. [Term profile](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/QfLiaQuery.lean) · [Adapter theorem](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/LogosQueryAdapter.lean) · [Program theorem](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/QfLiaAdmissibility.lean)

Seven Lean examples exercise signed literal multiplication, rejected nonlinear multiplication even inside an inactive conditional branch, and rejected short Boolean operand lists. The admissibility proof builds independently of CPC. [Lean examples](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ProgramRelationalQueryTests.lean)

`toLogosQueryTerm_symbols` proves that lowering preserves the list of symbol occurrences with their sorts. `RelationalQuery.lower` combines the lowered term with the canonical bindings and projects the solver's name and sort table from those bindings. `symbol_declared_once` proves that each referenced name occurs exactly once in that table and has the required sort. `lower_symbol_binding` recovers the original binding by name, preserving the source ID and role. The examples cover a source spelling that matches another symbol's canonical name and a Boolean factor with distinct left and right entries. [Adapter proof](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/LogosQueryAdapter.lean) · [Declaration proofs](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SolverRelationalQuery.lean) · [Lean examples](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ProgramRelationalQueryTests.lean)

**Outputs:** admissibility theorem; canonical wire/Logos adapter; exact source-derived CPC binding; explicit trusted computing base.

### 7.7 Adversarial validation and CI

- [ ] **SCW-35 — Add expression-level differential fixtures.** Compare source and query evaluators over generated bounded Int/Bool environments; these are regression tests, not proofs.
- [ ] **SCW-36 — Add command-level edge cases.** Cover write-then-read, both conditional branches, nested conditionals, scope errors, and invalid uninitialized reads.
- [ ] **SCW-37 — Add relational adversarial fixtures.** Cover wrong selected factor, accidentally split shared inputs, swapped left/right names, missing observed state, and wrong initial-state sharing.
- [ ] **SCW-38 — Add QF_LIA negative fixtures.** Reject nonlinear multiplication, unsupported sorts/operators, undeclared symbols, duplicate declarations, and malformed source programs.
- [ ] **SCW-39 — Add kernel/axiom audit.** CI must fail on `sorry`, `admit`, project-local axioms, or an unapproved trust escape in new proof modules.
- [ ] **SCW-40 — Add a dedicated proof CI gate.** Build each proof module in dependency order and run executable adversarial fixtures under the pinned Lean toolchain.
- [ ] **SCW-41 — Publish milestone evidence.** Record exact commit, CI run, toolchain/dependency pins, theorem names, and remaining proof boundary.

**Outputs:** repeatable CI gate and evidence record for the first program-level source-to-query milestone.

### 7.8 Execution order and gates

SCW-04 completed the dependency and trust boundary audit. SCW-05 and SCW-15 passed pinned Lean CI. SCW-06–09 cover the typed expression core. SCW-16–25 preserve command execution and observations through paired runs. SCW-26–28 establish equivalence between the canonical formula and concrete dependence witnesses. SCW-29 and SCW-30 prove admissibility and declaration closure for the lowered solver term. SCW-31–34 carry that result through serialization and the proof checker.

| Gate | Required tasks | Exit condition |
|---|---|---|
| G0 — Baseline | SCW-01–SCW-04 | Trust boundary and theorem inventory reviewed |
| G1 — Typed source core | SCW-05–SCW-09 | Context, well-formedness, and typed environment invariants compile |
| G2 — Expressions | SCW-10–SCW-15 | Expression preservation proved without Logos dependency in semantic core |
| G3 — Commands | SCW-16–SCW-21 | Deterministic command execution and SC-3 pass |
| G4 — Program observations | SCW-22–SCW-23 | SC-4 passes for return and selected state |
| G5 — Paired runs | SCW-24–SCW-25 | SC-5 passes for arbitrary related input environments |
| G6 — Relational formula | SCW-26–SCW-28 | SC-6 and source-symbol binding invariants pass |
| G7 — Wire and checker | SCW-29–SCW-34 | SC-7 and source-derived JSON/CPC/Logos binding pass |
| G8 — Acceptance | SCW-35–SCW-41 | Theorems, adversarial tests, axiom audit, and CI acceptance pass |

This decomposition targets only the stated deterministic QF_LIA fragment, not the entire LLMLang language. Each gate is reported separately; expression-level success must never be described as program-level correctness.

At each stage, add executable examples and negative tests, but do not label tests as proofs. Each theorem must be kernel-checked with no `sorry`, admitted axiom, or unreviewed custom axiom.

## 8. Important semantic hazards

- **Integer model:** QF_LIA uses mathematical integers. If LLMLang later uses bounded machine integers, overflow semantics require a different encoding or explicit range proof.
- **Evaluation order:** source expressions and symbolic rewrites must preserve evaluation order. This fragment has pure expressions, so reordering is safe only after purity is part of the grammar.
- **Short-circuit Boolean operators:** decide whether `and`/`or` are short-circuiting or total pure operators. With pure, total expressions their values agree, but this must not be generalized to effectful expressions.
- **State:** reads after writes must observe the updated state. A translation that reads only the initial state is invalid.
- **Branching:** both branches must be translated under the correct path condition; merging branch results with `ite` must preserve the operational semantics.
- **Observations:** only contract-selected state and the return value are compared. Trace, events, errors, and termination are absent by construction, not silently ignored.
- **Declarations:** a name-to-symbol map must be injective and sort-correct. Query variable identity must distinguish left and right copies and shared inputs.
- **Source/query binding:** matching a query's declarations to parser-assigned Logos UConst identifiers is necessary but does not prove that the query describes the source program.

## 9. Acceptance criteria for the first proof milestone

The milestone is complete only when:

- the Lean source grammar exactly documents the accepted fragment;
- a Lean validator rejects malformed or unsupported source programs;
- SC-1 and SC-2 are proved for every accepted expression constructor;
- SC-3 and SC-4 are proved for assignment, conditional, and return;
- SC-5 and SC-6 are proved for paired execution and the relational query;
- SC-7 is proved for the generated formula;
- all theorem modules compile in CI;
- the theorem modules contain no `sorry`, `admit`, or project-local axioms;
- adversarial tests demonstrate rejection of loops, recursion, effects, unsupported sorts, uninitialized state, and nonlinear multiplication;
- the existing Logos binding tests continue to pass.

A proof of only SC-2 is a valuable intermediate result, but must be reported as expression-level correspondence only.

## 10. Non-goals

This scenario does not prove:
- correctness of the Python parser or validator;
- that the formal fragment captures all intended LLMLang semantics;
- correctness of LLVM/native code generation;
- correctness of the cvc5 solver;
- correctness of the Logos parser (its checker soundness theorem is a separate boundary);
- absence of bugs in the Lean kernel or trusted compiler;
- that a formal requirement matches human intent.

The formal result is always conditional on the declared source semantics, input assumptions, and observation contract.
