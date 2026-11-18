# Dependency Graph Prototype 01

Experimental content-addressed semantic dependency graph. Python 3.10+, standard library only; Scenario 27's symbolic backend optionally requires a Z3 SMT-LIB executable.

Run from this directory:

```bash
python -m unittest discover -s tests -v
python -m src.semantic_graph
```

The prototype includes deterministic JSON persistence for semantic values, context-scoped relations, and project snapshots (`src/persistence.py`).

## Contract / implementation bindings

`src/binding.py` adds immutable BindingSnapshots. Callers may depend on contract hashes while a snapshot selects concrete implementations. The snapshot hash changes when the implementation selection changes; execution-sensitive verification keys include that root. Binding rows validate semantic kinds and an exact hash-relevant `implements` dependency. Serialization is deterministic and checksummed.

Run the full test suite with the command above. Binding snapshots currently persist as a separate document; atomic integration with project snapshot persistence, dynamic dispatch, compatibility checking, runtime loading, and formal conformance remain unimplemented. See [Research Scenario 10](../../RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md).

## Combined project-state persistence

`src/project_state.py` composes graph and binding-snapshot documents into one deterministic, checksummed envelope. It validates each embedded document on reload. This is not a multi-writer transaction or database. See [Research Scenario 11](../../RESEARCH-SCENARIO-11-ATOMIC-PROJECT-BINDING-PERSISTENCE.md).

## Layered build / deployment / execution identities

`src/execution.py` models BuildSnapshot, BuildArtifact, DeploymentSnapshot, ExecutionSnapshot, ReleaseManifest, and compare-and-swap publication of a mutable release-channel head. See [Research Scenario 12](../../RESEARCH-SCENARIO-12-PROJECT-BUILD-DEPLOYMENT-EXECUTION.md).

## Scoped implementation binding

`src/scoped_binding.py` models project, tenant, and request binding layers with explicit precedence and override permissions. It pins the resolved binding decision. See [Research Scenario 13](../../RESEARCH-SCENARIO-13-MULTI-LEVEL-BUSINESS-RULE-AND-IMPLEMENTATION-BINDING.md).

## Behavioral contract refinement experiment

`src/contract_model.py` defines a finite observable-trace model and checks whether every modeled implementation trace is allowed by a contract. It distinguishes PROVEN, DISPROVEN, and UNKNOWN. PROVEN applies only when both finite models explicitly declare complete semantics; this is an exhaustive proof of the finite model, not a proof that arbitrary source code conforms to that model.

See [Research Scenario 14](../../RESEARCH-SCENARIO-14-FORMAL-BEHAVIORAL-CONTRACTS-AND-REFINEMENT.md).

## Business intent to formal contract experiment

`src/business_intent.py` models immutable intent sources, explicit clarification decisions, caller-scoped business rules, provenance-carrying formal clauses, candidate acceptance gates, effective-date examples/counterexamples, and a two-caller tax-policy evolution scenario. It demonstrates that changing one caller's business rule can change only that caller's selected semantic value while leaving a generic callee contract and another caller unchanged.

Run the focused experiment tests:

```bash
python -m unittest discover -s tests -p 'test_business_intent.py' -v
```

See [Prototype 16 Results](PROTOTYPE-16-RESULTS.md) and [Research Scenario 15](../../RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md). This is not a natural-language parser, authorization system, formal logic engine, or source-code proof.

## Typed Requirement IR experiment

`src/requirement_ir.py` models typed predicates, requirement ownership/scope, source and decision provenance, triggers, actions, temporal metadata, assumptions, unresolved questions, and explicitly required dimensions. It checks types and provenance, detects contradictions and selected underdetermination cases over finite domains, generates satisfying and violating scenarios, and checks caller-policy ownership against explicit callee policy inputs.

Run the focused experiment tests:

```bash
python -m unittest discover -s tests -p 'test_requirement_ir.py' -v
```

See [Prototype 17 Results](PROTOTYPE-17-RESULTS.md) and [Research Scenario 17](../../RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md). The analyzer is finite-domain only; temporal fields are metadata, not evaluated temporal logic. It is not a natural-language parser or implementation proof.

## Requirement evolution and semantic impact experiment

`src/requirement_evolution.py` models immutable requirement revisions, snapshot-local selection keys, hash-relevant semantic dependency edges, separate lineage/provenance records, direct/transitive impact, verification-key changes, split/merge, and three-way concurrent branch merging.

Run the focused experiment tests:

```bash
python -m unittest discover -s tests -p 'test_requirement_evolution.py' -v
```

See [Prototype 18 Results](PROTOTYPE-18-RESULTS.md) and [Research Scenario 18](../../RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md). This is not a semantic-diff engine, complete impact planner, authorization system, or distributed transaction.

## Semantic impact planning and dependency completeness experiment

`src/impact_planning.py` audits whether independently observed dependency identities are covered by declared dependencies within an exact artifact/scope/evidence binding. It distinguishes GAP_FOUND, SUPPORTED_WITHIN_SCOPE, UNKNOWN, and NOT_CHECKED. It maps impacted artifact kinds to typed actions and forces HUMAN_REVIEW + FULL_REVALIDATION when completeness is not supported within scope. A no-action decision requires a matching PROVEN non-interference certificate record; the prototype checks binding only and does not verify the proof.

Run the focused tests:

```bash
python -m unittest discover -s tests -p 'test_impact_planning.py' -v
```

See [Prototype 19 Results](PROTOTYPE-19-RESULTS.md) and [Research Scenario 19](../../RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md). This is not a dependency extractor, runtime tracer, proof checker, or action executor.

## Dependency discovery and semantic classification experiment

`src/dependency_discovery.py` models evidence-bearing dependency candidates from explicit declarations, static analysis, dynamic tracing, sandboxing, and proof analysis. Candidates require explicit semantic classification before entering the hash-relevant dependency set. Unknown candidates block a completeness claim. The module consumes normalized observations; it does not implement the discovery tools.

Run the focused tests:

```bash
python -m unittest discover -s tests -p 'test_dependency_discovery.py' -v
```

See [Prototype 20 Results](PROTOTYPE-20-RESULTS.md) and [Research Scenario 20](../../RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md).

## Counterfactual dependency analysis experiment

src/counterfactual_analysis.py compares normalized repeated baseline/treatment execution records for one declared input factor. It distinguishes reproducible observable effects from trace-only changes, no observed difference, and inconclusive experiments. No observed difference is not proof of irrelevance.

Run focused tests with:
python -m unittest discover -s tests -p 'test_counterfactual_analysis.py' -v

See PROTOTYPE-21-RESULTS.md and Research Scenario 21.

## Coverage-guided dependency discovery experiment

`src/coverage_guided.py` generates typed finite-domain single-factor and t-way interventions, adds integer-extrema and optional static/taint guidance targets, deduplicates candidates by pinned artifact/context/observation-model identity, and schedules candidates with deterministic greedy set cover under a run budget. The coverage ledger preserves uncovered targets. It does not execute the program or prove dependency completeness; multi-factor execution still needs an extension to Scenario 21's single-factor comparison API.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_coverage_guided.py' -v
```

See [Prototype 22 Results](PROTOTYPE-22-RESULTS.md) and [Research Scenario 22](../../RESEARCH-SCENARIO-22-COVERAGE-GUIDED-DEPENDENCY-DISCOVERY.md).


## Multi-factor counterfactual analysis experiment

`src/multifactor_analysis.py` provides separate APIs for repeated paired joint interventions and repeated 2×2 factorial interaction analysis. Numeric outcomes use difference-in-differences; categorical outcomes use limited conditional equality patterns. It consumes normalized run records and does not execute programs or prove dependency completeness.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_multifactor_analysis.py' -v
```

See [Prototype 23 Results](PROTOTYPE-23-RESULTS.md) and [Research Scenario 23](../../RESEARCH-SCENARIO-23-MULTI-FACTOR-COUNTERFACTUAL-ANALYSIS.md).


## Adaptive interaction discovery experiment

`src/adaptive_discovery.py` schedules repeated single-factor interventions first, then complete pairwise 2×2 factorial blocks for selected level pairs. An observed interaction can trigger a higher-order factorial block; inconclusive experiments receive bounded retries. The budget is measured in actual executions (factorial cells × repetitions), and blocks are never split. Executed experiment targets remain separate from observed runtime feedback.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_adaptive_discovery.py' -v
```

See [Prototype 24 Results](PROTOTYPE-24-RESULTS.md) and [Research Scenario 24](../../RESEARCH-SCENARIO-24-ADAPTIVE-INTERACTION-DISCOVERY.md). The planner consumes normalized feedback; it does not execute programs, solve input constraints, or prove dependency completeness.


## Minimal formal semantic core (Scenario 26)

`src/formal_core.py` defines a deterministic finite core with expressions, pure non-recursive calls, local assignment, explicit state regions, ordered events, conditionals, return, and error outcomes. It exhaustively compares input pairs differing in one factor and reports finite-model influence/independence witnesses. Unsupported constructs or a state-space budget limit produce UNKNOWN; fallback edges are hints only, not proof.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_formal_core.py' -v
python -m unittest discover -s tests -p 'test_finite_relational_consistency.py' -v
```

See [Prototype 26 Results](PROTOTYPE-26-RESULTS.md) and [Research Scenario 26](../../RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md). This is not an SMT solver, arbitrary-source verifier, or machine-checked proof of the evaluator.


## Symbolic relational verification (Scenario 27)

src/symbolic_relational.py encodes two executions into SMT-LIB 2. For one selected input factor, the two copies receive independent values while all other inputs are shared. SAT and UNSAT are solver-reported outcomes, not independently checked proofs. A SAT model must be replayed against the reference evaluator; an UNSAT result remains unchecked until a proof artifact is validated by an independent checker. UNKNOWN, timeout, unsupported syntax, or missing solver never count as independence.

Supported fragment: Int/Bool/String, arithmetic and Boolean expressions, pure non-recursive calls, conditionals, explicit initialized locals/state, and a final top-level return. The default solver command is z3 -in -smt2. No Python Z3 package is required.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_symbolic_relational.py' -v
python -m unittest discover -s tests -p 'test_symbolic_finite_differential.py' -v
```

The finite-differential and real-solver integration tests are skipped when the Z3 executable is unavailable. See Prototype 27 Results and Research Scenario 27. This is not yet a full source verifier or independently checked proof system.


## Typed IR and proof boundary (Scenario 28)

`src/typed_ir.py` validates the supported symbolic AST fragment, checks expression/command types, declarations, pure function calls, branch joins, and observation selection. It computes a canonical IR digest and exposes `analyze_typed_symbolically`, which validates before invoking the Scenario 27 encoder.

`src/proof_boundary.py` creates content-addressed evidence records binding the typed IR, semantic/validator/encoder/observation versions, exact SMT query, solver identity/configuration, and optional proof-checker receipt. It distinguishes a solver-reported UNSAT from an independently checked proof. SAT models can be replayed against the Scenario 26 reference evaluator.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_typed_ir.py' -v
python -m unittest discover -s tests -p 'test_proof_boundary.py' -v
```

The proof receipt is currently only a prototype data structure: it is not authenticated and no independent checker is invoked; even a supplied receipt remains labelled UNAUTHENTICATED_CHECKER_RECEIPT_PRESENT. This prototype is not a production proof system. See [Prototype 28 Results](PROTOTYPE-28-RESULTS.md) and [Research Scenario 28](../../RESEARCH-SCENARIO-28-TYPED-IR-AND-PROOF-BOUNDARY.md).


## Verified SMT proof-checker process adapter (Scenario 29)

`src/logos_runner.py` invokes pinned cvc5 and Logos executables, preserves CPC proof bytes, applies timeouts, and fails closed on process or pin errors. A Logos `correct` result remains `CHECKER_REPORTED_CORRECT_UNBOUND`; it is not a program-level proof. The 15 tests use fake executables and do not validate real cvc5/Logos integration.

See [Prototype 29 Results](PROTOTYPE-29-RESULTS.md) and [Research Scenario 29](../../RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md).

## CPC assumption binding audit (Scenario 30)

Scenario 30 audits the pinned Logos parser and soundness API. Logos proves that the conjunction of assumptions parsed from a CPC proof is unsatisfiable; it does not bind those assumptions to LLMLang's original query. The proposed MVP therefore requires exact structural equality between the parsed assumption list and a canonical expected Logos `Term` list. Any mismatch remains UNKNOWN. No Lean wrapper or real proof integration has yet been built.

See [Research Scenario 30](../../RESEARCH-SCENARIO-30-CPC-ASSUMPTION-BINDING.md).


## Strict QF_LIA relational query profile (Scenario 31)

`src/qf_lia_profile.py` and `src/qf_lia_ir.py` form a separate, conservative candidate-query path. The latter defines immutable typed `Term`, `Declaration`, and `RelationalQuery` nodes; the former builds that canonical query IR and passes it to the dedicated SMT-LIB renderer. It accepts only Bool/Int inputs and values, linear integer arithmetic, multiplication with an integer-literal operand, deterministic assignments/conditionals, inlined pure non-recursive functions, and one final top-level return. It emits `(set-logic QF_LIA)`, shares all non-selected inputs between paired executions, and compares return plus explicitly selected state. Results expose profile/validator/encoder versions, the canonical typed query IR, its digest, and a SHA-256 digest of the exact SMT-LIB bytes. The renderer validates declaration closure, sorts, operators, and linear multiplication before emitting text. It deliberately omits the constant outcome string only because this profile rejects non-normal-return constructs.

Unsupported terms are rejected before query output. Function bodies must be reachable from the program and are type-checked when inlined; unused function declarations are rejected rather than silently left unchecked.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_qf_lia_profile.py' -v
```

The output status is `QF_LIA_CANDIDATE_QUERIES`, not `PROVEN`. The version-2 wire envelope explicitly carries factor_left and factor_right; Python validates their unique same-sort _L/_R declaration pair and exact factor-difference AST, while Lean independently constructs and structurally checks not (= left right). The validator and source encoder are still Python code and are not formally verified; source-to-query correspondence and real cvc5/Logos proof checking remain outstanding. See [Research Scenario 32](../../RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md) for the canonical IR design and remaining proof obligations.


## Lean CPC parser-state binding prototype (Scenario 33)

The `logos_binding/` Lake package pins Logos at the audited commit and Lean 4.34.0. It retains the final CPC parser state, checks assumptions against ordinary `Eo.parseProof`, and binds an exact expected declaration set to unambiguous Bool/Int UConst nodes. Its executable tests cover a valid Int declaration, overloaded/repeated declarations, and unexpected declarations.

Run from this directory:

```bash
cd logos_binding
lake build
lake exe testParserBinding
```

A GitHub Actions workflow runs these commands for relevant pushes and pull requests. The pinned Lean build is validated by CI, not by a local build. The current version-2 change is awaiting its Lean CI result. See [Research Scenario 33](../../RESEARCH-SCENARIO-33-CPC-PARSER-STATE-BINDING.md).

## Typed semantic dependency extractor (candidate SPG subset)

`src/semantic_dependency_index.py` defines a strict, version-1 experimental declaration envelope for six object kinds: `function`, `operation`, `type`, `contract`, `implementation`, and `effect`. It accepts only explicit fields; unknown fields and unsupported relations are rejected.

- Function and Operation own explicit `call_sites`; each call site has a stable caller-local `call_site_id` and one or more explicit target alternatives.
- Each target alternative has a stable `target_id`, exact callee Content Hash, and optional condition. This preserves two call sites in one caller and multiple conditional targets at one site.
- Typed references are constrained by source/target kind (e.g. Implementation → Contract and Effect; Function → Type and Contract).
- Publication validates that every target hash exists and has the declared kind before storing the source. Exact target hashes participate in the caller's semantic hash through the existing ContentStore dependency projection.
- The derived `DependencyIndex` exposes deterministic outgoing and incoming edges with source hash, edge ID, relation, exact target hash/kind, and condition.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_semantic_dependency_index.py' -v
```

This is a deliberately small research schema, **not** the canonical LLMLang SPG schema. It does not parse LLMLang source, infer dependencies, prove completeness, model higher-order/dynamic dispatch beyond explicit finite alternatives, define final hash canonicalization, or integrate with the Toolchain Server / shared production Content Store. Unsupported or missing references fail closed. See [Semantic Dependency Index design](../../SEMANTIC-DEPENDENCY-INDEX.md).


### Snapshot-scoped reverse lookup and completeness binding

`src/semantic_dependency_index.py` exposes `query_snapshot_incoming` and `ReverseLookupEvidence`. A reverse query returns exact incoming edges from one Semantic Snapshot plus `GAP_FOUND`, `SUPPORTED_WITHIN_SCOPE`, `UNKNOWN`, or `NOT_CHECKED`. Evidence is bound to the snapshot root, target hash, scope, index schema, extractor identity, and digest of the exact returned edge set. Missing evidence is never interpreted as an empty caller set. The adapter validates bindings only; it does not authenticate evidence or prove that the external observation model is complete. `impact_planning.audit_snapshot_incoming` carries the result into CIP completeness audits without dropping the exact Snapshot root, target, scope, evidence ID, index schema version, extractor identity, or edge-set digest. `plan_impact` requires Snapshot-bound evidence by default: absent evidence is `NOT_CHECKED`, and mismatched Snapshot/target bindings are `UNKNOWN`, both forcing human review and full revalidation. All binding fields participate in plan identity. The explicit `require_snapshot_evidence=False` compatibility mode is only for isolated legacy tests and must not be used for RT-20 CIP approval. See the Snapshot-scoped reverse-query section in [Semantic Dependency Index](../../SEMANTIC-DEPENDENCY-INDEX.md).


## Per-call-site compatibility planning and differential audit

The impact planner now carries exact incoming call-site edges from a Snapshot reverse query. Every discovered call edge must have one decision keyed by `(caller_hash, call_site_id, target_id)` and bound to its exact base callee hash. Resolved decisions (`migrate`, `preserve`, `adapt`, `fork`) require the selected callee hash, resulting caller hash, rationale, and compatibility evidence ID. Missing or unresolved decisions force human review and full revalidation. Decisions and their evidence participate in `plan_id`.

`audit_snapshot_incoming_independently` scans selected declaration payloads separately from the reverse-index builder and compares the exact incoming edge set. This catches projection omissions in the prototype. It shares the Content Store and payload source, so it is not a cryptographically independent or runtime-complete audit. Dynamic dispatch, reflection, and external behavior remain explicit exclusions.
