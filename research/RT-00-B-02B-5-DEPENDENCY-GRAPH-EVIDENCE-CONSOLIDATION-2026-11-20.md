# RT-00 B-02b.5 — Dependency Graph evidence consolidation

**Audit snapshot:** `dcbb3085bfc6fb45eaaf520ca27aef4e93a628ae`  
**Date:** 2026-11-20  
**Scope:** Consolidation of B-02b.1–B-02b.4 findings for `DEPENDENCY-GRAPH-01`, its Scenario 15/17–34 relationships, the Python/Lean evidence boundaries, and the corpus inventory.  
**Decision boundary:** research-corpus reconciliation only; no language or architecture decision is accepted.

## 1. Consolidated result

The Dependency Graph research family is not a single implementation. It contains:
- requirements and business-intent models;
- content-addressed semantic identity and lifecycle models;
- dependency discovery, counterfactual, coverage, and impact-planning experiments;
- a finite Python semantic oracle and a separate symbolic SMT backend;
- a strict QF_LIA typed query path and versioned JSON envelope;
- a cvc5/Logos process adapter and a separate Lean parser-state bridge;
- a kernel-checked Lean source-semantics proof chain for a restricted Int/Bool fragment.

The B-02b audit has established:
1. a current Lean import/proof graph and SC-1–SC-7 declaration crosswalk;
2. a complete inventory of the family’s 32 Python source modules and 32 test modules;
3. an execution-evidence matrix distinguishing current Required CI from historical isolated test runs;
4. a scenario progression/supersession map from Scenario 15 through Scenario 34;
5. a file-role and corpus-inventory reconciliation, including exact missing/stale inventory records.

The correct overall claim remains bounded: Scenario 34 proves the correspondence chain for its declared deterministic Int/Bool fragment through the canonical relational query. It does not yet prove that the Python-generated version-2 JSON or CPC assumptions are exactly that source-derived formula.

## 2. Evidence reports

| Substage | Result | Status |
|---|---|---|
| B-02b.1 | [Lean proof graph audit](RT-00-B-02B-1-LEAN-PROOF-GRAPH-AUDIT-2026-11-20.md) | Merged in PR #111 |
| B-02b.2 | Python prototype and test-evidence audit | PR [#113](https://github.com/aivibeflow/LLMLang/pull/113), open; checks passed |
| B-02b.3 | Scenario overlap and supersession audit | PR [#115](https://github.com/aivibeflow/LLMLang/pull/115), open; checks passed |
| B-02b.4 | Orphan and traceability-gap audit | PR [#116](https://github.com/aivibeflow/LLMLang/pull/116), open at the time of this snapshot; one check still running |

The reports are documentation-only. No prototype implementation, test, Lean proof, historical result, or workflow was modified by B-02b.1–B-02b.4.

## 3. Consolidated family graph

### 3.1 Python research lines

- Semantic graph/identity: `semantic_graph.py`, persistence, binding, project state, execution, scoped binding, identity lifecycle, recursive identity.
- Requirements: business intent, typed Requirement IR, requirement evolution.
- Experimental dependency evidence: dependency discovery, counterfactual analysis, coverage-guided planning, multi-factor analysis, adaptive scheduling.
- Impact planning: completeness evidence, call-site refactoring, candidate validation, graph closure, semantic diff, semantic dependency index.
- Formal prototypes: finite core, symbolic relational encoder, typed IR, proof-boundary envelope, QF_LIA query IR/profile, Logos process runner.

These are separate executable models with explicit finite/normalized-input boundaries. They are not a general source parser or verified compiler.

### 3.2 Lean source-to-query proof line

The current Lean source graph separates:
- source/query terms and declarations;
- checked source typing/evaluation;
- concrete and symbolic command semantics;
- program and paired observations;
- canonical relational-query construction;
- QF_LIA admissibility and the Logos AST adapter;
- parser-state/JSON/CPC integration.

SC-1–SC-7 are represented by kernel-checked declarations and 125 Lean examples. The exact audited main revision passed Required CI run [#44801357527](https://github.com/aivibeflow/LLMLang/actions/runs/44801357527).

A static scan found no explicit `sorry`, `admit`, project-local `axiom`, or `opaque` declaration in the 21 Lean files. This is not the automated theorem-dependency audit required by SCW-39.

### 3.3 External checker boundary

The Python Logos runner has 15 fake-executable tests but no real cvc5/Logos integration evidence. The Lean parser-state bridge builds and tests the pinned parser API, retains parser declaration state, decodes the version-2 query envelope, and structurally compares the complete assumption list on the current fixtures.

That bridge does not prove the decoded query came from the source semantics. The open Scenario 34 obligations SCW-30–41 remain material, especially:
- SCW-30 solver-facing declaration closure;
- SCW-31 source-derived JSON/wire correspondence;
- SCW-32 connection of the proved formula to Logos terms and parser-state identities;
- SCW-33 exact CPC assumptions bound to the source-derived formula;
- SCW-34 explicit trusted-computing-base boundary;
- SCW-35–38 adversarial acceptance fixtures;
- SCW-39 automated axiom audit;
- SCW-40 dedicated proof CI gate;
- SCW-41 milestone acceptance evidence.

## 4. Test evidence and Required CI

The family contains 32 Python test modules with 376 methods named `test_*`. Required CI runs 12 modules (177 such methods) and compiles all Python source and test modules with `compileall`. The other 20 modules have historical focused local/isolated test records of varying quality; they are not currently part of Required CI.

Important distinctions:
- Scenario 21 and Scenario 29 historical test source/test blobs match their cited implementation commits.
- Scenario 27's 12 fake-solver tests pass, but its real-Z3 differential test was skipped.
- Scenario 28's 24 focused tests passed in an isolated harness, but no real solver/checker was run.
- Scenario 29's 15 fake-executable tests passed, but no real cvc5/Logos proof was generated or checked.
- Scenario 31/32's 30 QF_LIA profile tests are in Required CI.
- Lean build and `Main.lean` parser/semantic integration tests are in Required CI.

No full local Python suite or real external-solver integration was performed by this audit.

## 5. File-role and orphan disposition

The inventory has individual role metadata for all 103 files in `DEPENDENCY-GRAPH-01`. README basename omissions are resolved by direct links from RT-05, RT-11, RT-24, Scenario 34, tests, or CI. In particular, the binding benchmark is linked from RT-11; identity lifecycle, recursive identity, and call-site refactor are linked from RT-05/RT-20; the semantic graph is linked from RT-24.

No unclassified family file was found. The full machine-readable import/test/fixture/CI/evidence graph still needs to be consolidated; role classification is not the same as complete edge coverage.

## 6. Corpus inventory reconciliation

At the audit snapshot:
- current tracked research tree: 476 files including the inventory manifest;
- current research artifacts excluding the manifest: 475;
- inventory records: 471;
- exact path/blob/size matches: 471;
- missing records: 4;
- stale SHA/size records: 5;
- extra inventory records: 0.

The four missing paths are:
- `research/PROTOTYPES/PACKAGE-INDEX-01/profile_package_provider.py`;
- `research/PROTOTYPES/PACKAGE-INDEX-01/run_tests_with_timings.py`;
- `research/RT-25-MEMORY-ALLOCATOR-COMPATIBILITY-AND-BENCHMARKING.md`;
- `research/RT-00-B-02B-1-LEAN-PROOF-GRAPH-AUDIT-2026-11-20.md`.

The five stale path records are the Package Index README and benchmark, plus `research/README.md`, `RESEARCH-DEPENDENCY-MAP.md`, and `RESEARCH-TAXONOMY.md`. The inventory revision is `3b087952675e51e566cfa90ef8037cc3ac1c2e32`, not the audited main revision.

The inventory must be regenerated after the consolidated report and index links are committed. Pending PRs #113, #115, and #116 must be included only after they merge; they are not part of this main snapshot.

## 7. Documentation freshness

The following current-state text needs a later documentation reconciliation while preserving historical evidence:
- family README and Scenario 34 still mention Lean 4.34.0; current toolchain is 4.36.0;
- family README and old corpus audit cite run #44766546452 as latest; current exact-main Required CI is #44801357527;
- Scenario 30's top status says no Lean wrapper exists, superseded by Scenario 33;
- Scenario 31's top status says no code changes, contradicted by its own implementation section and Scenario 32;
- Scenario 32's “CI running” status is superseded by Scenario 33's completed parser bridge;
- Scenario 33 contains old toolchain and run references;
- an earlier family evidence review still says SCW-05 is In progress, while the current SCW-05 breakdown and Scenario 34 mark its seven scoped tasks Complete.

Do not delete historical experiment results or claim that a later parser bridge retroactively proves the Python encoder.

## 8. Next work

1. Complete the B-02b.5 inventory refresh against the exact branch snapshot, including new files and updated blob identities.
2. Add links to the accepted B-02b audit reports in the research index.
3. After PRs #113/#115/#116 are reviewed and merged or closed, refresh the inventory again if their files enter main.
4. Continue the remaining RT-00 reproducibility and external-snapshot audits (C and D), then links/anchors (E), full index/taxonomy/plan reconciliation (F), and final report (G).

## 9. Conclusion

**Disposition: B-02b semantic audit slices are complete as documented, subject to PR review and inventory consolidation.** The family is well classified at file-role level; the important remaining risks are incomplete source-to-CPC proof correspondence, uneven Python test execution in Required CI, stale audit/version references, and inventory freshness.

No normative language or architecture decision is made by this report.
