# RT-00 B-02b.2 — Python prototype and test-evidence audit

**Audit snapshot:** `c35ba93c031684100dcdbc06a34b0e14696c37ab`  
**Date:** 2026-11-20  
**Scope:** Python implementation and test modules under `research/PROTOTYPES/DEPENDENCY-GRAPH-01/{src,tests}/`, family README, prototype result records, and Required CI workflows.  
**Method:** source/test inventory, module docstrings/imports, test-method inventory, result-record review, CI workflow inspection, and current-head check evidence. No local Python test suite was run during this audit.

## 1. Executive result

The family is not one monolithic prototype. It contains several related research lines: semantic graph and identity models; requirement/business-intent models; dependency discovery and impact planning; finite and symbolic relational analysis; QF_LIA query generation; and a process adapter for cvc5/Logos.

The Python implementations are useful executable research models and regression targets. They do **not** establish that arbitrary LLMLang source is parsed, faithfully translated, or formally verified. The formal source-to-query proof is the separate Lean work in Scenario 34.

At this snapshot:
- `src/` contains 32 Python files;
- `tests/` contains 32 Python test modules;
- those modules contain 376 methods named `test_*`;
- Required CI compiles all `src` and `tests` modules, but executes only 12 of the 32 test modules (177 `test_*` methods by source inventory).

## 2. Prototype and module classification

### 2.1 Semantic graph, identity, persistence, and binding

| Module | Role / relationship |
|---|---|
| `semantic_graph.py` | Base content-addressed semantic values, explicit dependencies, snapshots, and verification keys |
| `persistence.py` | Deterministic graph serialization and reload; explicitly not a database |
| `binding.py` | Immutable contract-to-implementation binding snapshots |
| `project_state.py` | Composes graph and binding snapshots into one checksummed document |
| `execution.py` | Build, deployment, execution, release identities and compare-and-swap channel head |
| `scoped_binding.py` | Project/tenant/request implementation-binding precedence |
| `identity_lifecycle.py` | RT-05 continuity and lineage comparisons |
| `recursive_identity.py` | Bounded recursive declaration-graph identity |
| `binding_build_benchmark.py` | Benchmark driver for call-site binding invalidation; not a semantic implementation test |

These are supporting identity and lifecycle models. Their existence should not be interpreted as a source parser or production storage/runtime implementation.

### 2.2 Business intent and requirements

| Module | Role |
|---|---|
| `business_intent.py` | Scenario 15/Prototype 16: explicit clarification, caller-owned rules, provenance-bearing candidate clauses, human acceptance |
| `requirement_ir.py` | Scenario 17: typed finite-domain requirement representation and bounded consistency checks |
| `requirement_evolution.py` | Scenario 18: immutable requirement states, lineage, impact, and branch merge |

The inputs are explicitly constructed records. These modules do not parse natural language, infer stakeholder intent, establish authority, or prove implementation conformance.

### 2.3 Dependency discovery and impact planning

| Module | Role |
|---|---|
| `dependency_discovery.py` | Scenario 20: evidence-bearing dependency candidates and explicit semantic classification |
| `counterfactual_analysis.py` | Scenario 21: analysis of normalized paired run records |
| `coverage_guided.py` | Scenario 22: finite-domain intervention planning and coverage ledger |
| `multifactor_analysis.py` | Scenario 23: joint intervention and 2×2 factorial interaction analysis |
| `adaptive_discovery.py` | Scenario 24: staged single-factor/pairwise/higher-order experiment planning |
| `impact_planning.py` | Scenario 19 / RT-20: completeness evidence binding and conservative action planning |
| `call_site_refactor.py` | RT-05/RT-20 bounded call-site refactor audit |
| `candidate_validation.py` | Materialized candidate validation against exact call-site decisions |
| `candidate_graph_audit.py` | Explicit transitive dependency-closure audit for candidate Snapshots |
| `candidate_semantic_diff.py` | Fail-closed candidate Snapshot / edge / output reconciliation |
| `semantic_dependency_index.py` | Versioned explicit declaration envelope, typed semantic edges, Snapshot-scoped reverse lookup |

The discovery, counterfactual, coverage, and adaptive planners consume normalized evidence or feedback. They do not themselves implement static analysis, runtime tracing, program execution, or a proof of global dependency completeness. The RT-20 candidate audits are scoped to the explicit declaration subset and retain their documented exclusions.

### 2.4 Formal and symbolic analysis path

| Module | Role |
|---|---|
| `formal_core.py` | Scenario 26 finite semantic evaluator and exhaustive finite relational analysis |
| `symbolic_relational.py` | Scenario 27 SMT-LIB relational encoder and solver-process protocol |
| `typed_ir.py` | Scenario 28 strict validator for the Python symbolic AST fragment |
| `proof_boundary.py` | Content-addressed evidence envelope; solver answers are not proofs |
| `qf_lia_ir.py` | Typed canonical relational-query IR, validation, version-2 wire envelope, deterministic SMT-LIB renderer |
| `qf_lia_profile.py` | Scenario 31 conservative Bool/Int QF_LIA candidate-query builder |
| `logos_runner.py` | Scenario 29 pinned cvc5/Logos subprocess adapter with unbound checker verdicts |

The progression is not a chain of verified compiler passes. In particular:
- Scenario 26 is finite-domain enumeration over a Python model.
- Scenario 27 is symbolic SMT-LIB generation over a restricted AST and trusts solver reports.
- Scenario 28 validates the Python AST and records evidence; its optional checker receipt is not authenticated.
- Scenario 29 tests process handling with fake executables; its `CHECKER_REPORTED_CORRECT_UNBOUND` result is intentionally not a language-level proof.
- Scenario 31/32 provide a narrower QF_LIA candidate-query path and typed wire representation. The Python validator/encoder is not formally verified.
- Scenario 34's Lean model is a separate formalization; no theorem currently connects the Python encoder to the Lean semantics and then to CPC assumptions.

## 3. Scenario relationship and overlap classification

| Work | Relationship to adjacent work | Disposition |
|---|---|---|
| 26 finite semantic core | Reference evaluator and finite oracle for selected Python experiments | Distinct from symbolic SMT encoding; finite-model result only |
| 27 symbolic relational | SMT-LIB backend for the restricted Python AST | Distinct from 26's exhaustive finite evaluator; no independent proof checking |
| 28 typed IR / proof boundary | Validates Python AST and binds solver/evidence metadata | Adds a typed admission/evidence layer; does not verify encoder or checker |
| 29 Logos runner | Executes pinned external tools and preserves proof bytes | Process integration layer; not assumption correspondence |
| 30 CPC assumption binding | Research audit/design for exact assumption binding | Research artifact, not a separate Python implementation module |
| 31 QF_LIA profile | Conservative Bool/Int encoder and candidate query builder | Narrower profile than Scenario 27; not a formal proof of source encoding |
| 32 canonical typed relational IR | Versioned typed query and `/2` JSON envelope | Data/serialization contract used by the QF_LIA path; Lean JSON correspondence remains open |
| 33 CPC parser-state binding | Lean parser-state and declaration-binding bridge | Parser-state integration, not source-derived formula proof |
| 34 source-to-query correspondence | Lean source semantics and SC-1–SC-7 proof chain | Formal proof core; does not yet close SCW-30–41 |

Scenario 27 and Scenario 31/32 overlap in relational query generation, but they are not interchangeable: Scenario 27's symbolic backend supports a wider AST/sort surface (including String), while the strict QF_LIA path rejects String and narrows accepted constructs. The Lean Scenario 34 fragment is narrower still in its formal source sorts (Int/Bool) and has its own independent IR.

## 4. Current test inventory and Required CI coverage

The 32 test modules contain 376 `test_*` methods in total. Required CI on the audited HEAD runs these 12 modules:

| CI workflow | Test modules | Methods |
|---|---|---:|
| `qf-lia-profile.yml` | `test_qf_lia_profile.py` | 30 |
| `semantic-dependency-index.yml` | `test_impact_planning.py`, `test_semantic_dependency_index.py`, `test_semantic_graph.py`, `test_identity_lifecycle.py`, `test_call_site_refactor.py`, `test_recursive_identity.py`, `test_contract_model.py`, `test_candidate_validation.py`, `test_candidate_graph_audit.py`, `test_candidate_semantic_diff.py`, `test_candidate_semantic_diff_cip_v2.py` | 147 |
| **Total** | **12 of 32 modules** | **177 of 376 methods** |

The QF_LIA workflow also runs `python -m compileall -q src tests`, so all Python source and test modules are syntax-compiled. Compilation is not test execution.

The following 20 modules (199 `test_*` methods) are not invoked by the current Required CI workflows:

- `test_adaptive_discovery.py`
- `test_binding.py`
- `test_business_intent.py`
- `test_counterfactual_analysis.py`
- `test_coverage_guided.py`
- `test_dependency_discovery.py`
- `test_execution.py`
- `test_finite_relational_consistency.py`
- `test_formal_core.py`
- `test_logos_runner.py`
- `test_multifactor_analysis.py`
- `test_persistence.py`
- `test_project_state.py`
- `test_proof_boundary.py`
- `test_requirement_evolution.py`
- `test_requirement_ir.py`
- `test_scoped_binding.py`
- `test_symbolic_finite_differential.py`
- `test_symbolic_relational.py`
- `test_typed_ir.py`

This is a statement about the current Required CI configuration, not a claim that these tests have never been run. Some have documented local/isolated test runs.

Required CI run [#44801357527](https://github.com/aivibeflow/LLMLang/actions/runs/44801357527) passed on the exact audit snapshot. It passed the QF_LIA and semantic-dependency test steps as well as the other required suites.

## 5. Historical test-execution evidence

The result records contain different evidence levels. They must not be flattened into one claim that the entire family passed a full regression suite.

| Prototype | Recorded test evidence | Current interpretation |
|---|---|---|
| 16 — business intent | 9 focused tests passed locally | Focused local evidence; not full suite or Required CI |
| 17 — Requirement IR | 10 focused tests added; recorded run says not executed | No passing-run claim in the result record |
| 18 — requirement evolution | 9 focused tests added; recorded run says not executed | No passing-run claim in the result record |
| 19 — impact planning | Original result says tests were not run in that commit; current 35-method module is now in Required CI | Current CI closes the test-execution gap for the current test module |
| 20 — dependency discovery | Original result says 12 tests were added but not run; current module has 14 methods and is not in Required CI | No current Required CI execution evidence |
| 21 — counterfactual analysis | 13 focused tests passed in an isolated local harness | The current source and test blob SHAs match the files in recorded commit `e0cd4055db77c02611be505d8ba34bbe819f932d`; this remains local, not Actions evidence |
| 22 — coverage-guided | 11 focused tests passed in an isolated directory | Local evidence; full repository regression was not run |
| 23 — multi-factor | 18 focused tests passed in an isolated directory | Local evidence; not Required CI |
| 24 — adaptive discovery | 21 focused tests passed; 32 tests passed when combined with Scenario 22 | Local focused evidence; full repository regression was not run |
| 26 — finite core | 15 core tests and 1 pairwise consistency test passed in an isolated harness | Local evidence; not Required CI and not a full checkout regression |
| 27 — symbolic relational | 12 fake-solver protocol tests passed; 1 real-Z3 differential test skipped | No real Z3 solving or formula differential run is established |
| 28 — typed IR / proof boundary | 10 typed-IR + 14 proof-boundary tests passed in an isolated harness | Local focused evidence; no real SMT solver or independent checker |
| 29 — Logos runner | 15 fake-executable tests passed; `compileall` passed | Current source/test blobs match recorded commit `c0037ce42bf9b7965d5b67008e1a7899798ac6b9`; no real cvc5/Logos integration |
| 31/32 — strict QF_LIA / wire IR | 30 methods in `test_qf_lia_profile.py` | Executed by current Required CI |
| 33/34 — parser binding / Lean correspondence | Lean build and `Main.lean` run | Executed by current Required CI; see B-02b.1 audit |

The Prototype 27 post-audit correction is authoritative over its earlier count: it records 12 fake-process tests passed and one real-Z3 differential test skipped. The test skip is not evidence of a successful solver run.

## 6. Python-to-Lean and external-checker boundary

The Python path and Lean path have related goals but different implementations and trust assumptions:

1. Python Scenario 26/27/28 uses Python AST classes and Python evaluators/encoders. Scenario 27's supported sort set includes String; Scenario 31's strict QF_LIA builder accepts only Bool/Int.
2. Python Scenario 31/32 constructs a versioned typed query and `llmlang.qf_lia.relational-query/2` JSON envelope. Python validates factor-left/right declarations and the exact factor-difference AST.
3. Lean Scenario 34 independently defines the restricted Int/Bool source semantics and canonical relational formula. It structurally checks a factor difference, but the wire-envelope correspondence task SCW-31 remains open.
4. Lean's CPC parser-state bridge exists, but SCW-32/33 remain open: the parser/checker assumptions are not yet proven to be exactly the source-derived formula.
5. Python Scenario 29's process adapter and fake-executable tests do not constitute real cvc5/Logos proof validation. A checker-reported correct result remains unbound.
6. The Lean proof chain is kernel-checked for its formal fragment, but there is no proof that the Python source parser/encoder or arbitrary production compiler emits that fragment faithfully.

Consequently, neither a passing Python unit suite nor a successful Lean build closes the complete source → Python/JSON → CPC/Logos → language-level proof chain.

## 7. Follow-up items

- Keep the current Required CI coverage explicit; do not describe `compileall` as running all tests.
- Consider adding a separately scoped CI suite for the currently unexecuted 20 test modules, after checking their runtime, optional solver requirements, and external-tool dependencies. Do not blindly make tests requiring unavailable Z3/cvc5/Logos mandatory.
- Preserve local/isolated-run provenance separately from GitHub Actions evidence.
- Keep Scenario 27's skipped real-Z3 test and Scenario 29's absent real cvc5/Logos integration visible.
- Keep the Python encoder and Lean proof core classified as separate artifacts until SCW-30–41 establish the missing correspondence and trust-boundary obligations.

## 8. Conclusion and disposition

**Disposition: B-02b.2 source/test inventory and evidence classification complete.**

The family contains multiple distinct research layers with useful tests, but the test-execution coverage is uneven. Current Required CI runs 12/32 Python test modules and syntax-compiles all 32. Historical local runs provide additional evidence, with explicit limitations and provenance.

No Python implementation, test, result record, or CI workflow was changed by this audit.
