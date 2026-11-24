# RT-00 B-02b.4 — Orphan and traceability-gap audit

**Audit snapshot:** `dcbb3085bfc6fb45eaaf520ca27aef4e93a628ae`  
**Date:** 2026-11-20  
**Scope:** `DEPENDENCY-GRAPH-01` file roles and cross-references, existing corpus audit/semantic-traceability reports, current research inventory, and related RT-05/RT-11/RT-24 documents.  
**Method:** current Git tree and inventory comparison, per-file family mapping review, repository-wide reference checks for basename omissions, and reconciliation against existing audit claims.

## 1. Executive result

No unclassified file was found in the 103-file `DEPENDENCY-GRAPH-01` family: all 103 files have an individual inventory role, traceability method/confidence, and semantic-review basis. A missing basename in the family README is not sufficient evidence of an orphan.

The remaining problems are different:
- the machine-readable corpus inventory is stale relative to current main;
- a prior family evidence-review document contains a stale SCW-05 status;
- the older corpus audit still cites an obsolete “latest” Lean CI run;
- the full machine-readable import/test/fixture/evidence graph is not yet consolidated from the separate source reviews.

## 2. Family file-role and orphan review

The current inventory contains 103 entries under `research/PROTOTYPES/DEPENDENCY-GRAPH-01/`. All 103 have:
- a traceability item mapping;
- a recorded mapping method and confidence;
- a semantic-review basis;
- an individual or family-level role record.

Inventory review states:
- 7 entries: `first-pass-content-triage`;
- 90 entries: `file-role-triaged`;
- 6 entries: `first-pass-module-role-review`.

No family entry has a missing traceability method, confidence, or semantic-review basis. This confirms first-pass file-role coverage, not that every relationship or experimental claim has been independently verified.

### 2.1 README basename omissions that are not orphans

The family README is an overview, not a complete manifest. Several source modules are not named directly there but have explicit relationships elsewhere:

| File | Additional traceability evidence |
|---|---|
| `src/identity_lifecycle.py`, `tests/test_identity_lifecycle.py` | [RT-05 Identity Lifecycle Experiment](../../semantic-representation/RT-05/RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) and Required CI |
| `src/recursive_identity.py`, `tests/test_recursive_identity.py` | [RT-05 Recursive Identity Experiment](../../semantic-representation/RT-05/RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md) and Required CI |
| `src/call_site_refactor.py`, `tests/test_call_site_refactor.py` | [RT-05/RT-20 Call Site Refactoring Experiment](../../semantic-representation/RT-05/RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md) and Required CI |
| `src/semantic_graph.py`, `tests/test_semantic_graph.py` | [RT-24 Identity and SPG Reconciliation](../../toolchain-and-collaboration/RT-24/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md) and Required CI |
| `src/binding_build_benchmark.py` | [RT-11 Binding Invalidation Benchmark](../../toolchain-and-collaboration/RT-11/RT-11-BINDING-INVALIDATION-BENCHMARK.md) and PLAN.md; benchmark driver, not a missing unit-test implementation |

`src/__init__.py` is a package marker, not a standalone research result. The benchmark module is intentionally exercised as a benchmark with a local C compiler rather than as an ordinary unit-test module.

The remaining Python modules and test modules are mapped through the family README, Prototype result documents, RT documents, import relationships, or CI workflows. No orphan conclusion is justified from README omissions alone.

### 2.2 Lean family links

The Lean subproject's 21 source modules, Lake build definition, toolchain pin, two SCW documents, and parser integration entrypoint have explicit roles in the family README, Scenario 34, SCW-04/05, and the B-02b.1 proof-graph audit. The historical SCW-04 document is a dated boundary audit, not a current dependency description.

## 3. Existing corpus audit reports and stale claims

The current main tree contains several related audit documents. They must be treated as separate snapshots, not merged into one undated “current” status:

1. `RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md` records first-pass file-role triage for all 240 prototype-tree files, including 103 Dependency Graph family files. It explicitly says this is not claim-level validation or full supersession review.
2. `RESEARCH-CORPUS-PROTOTYPE-EVIDENCE-DEPENDENCY-GRAPH-01-2026-11-20.md` is pinned to baseline `e2aa15b8006659f6d256aa61fd294911aa73c21f`. Its statement that the SCW-05 breakdown is still In progress is stale: the current SCW-05 document marks all seven scoped tasks complete, and Scenario 34 says the same.
3. `RESEARCH-CORPUS-AUDIT-2026-11-20.md` already records that the SCW-05 tasks were corrected, but its family-evidence paragraph still names CI run #44766546452 as the latest relevant Logos-binding run. The current exact-HEAD Required CI run is #44801357527.
4. The new B-02b.1 audit records the current Lean proof graph, 125 Lean examples, current toolchain, and open SCW-30–41 boundary.
5. The B-02b.2 audit records current Python module/test counts and Required CI coverage.
6. The B-02b.3 audit distinguishes Scenario 15/17–34 progression, numbering exceptions, and historical/superseded status text.

Recommended handling: preserve the older audit baselines and add a dated current-state addendum or explicit supersession note. Do not rewrite historical observations as though they were never true.

## 4. Corpus inventory freshness check

The inventory file at this snapshot is:

`research/RESEARCH-CORPUS-INVENTORY-2026-11-20.json`

Its `revision` field is `3b087952675e51e566cfa90ef8037cc3ac1c2e32` (“RT-00: append Dependency Graph evidence audit”), while the current main snapshot is `dcbb3085bfc6fb45eaaf520ca27aef4e93a628ae`.

Exact current-tree comparison:

| Check | Result |
|---|---:|
| Tracked files under `research/`, including the inventory itself | 476 |
| Current research artifacts excluding the inventory itself | 475 |
| Inventory records | 471 |
| Exact path + blob SHA + size matches | 471 |
| Missing inventory records | 4 |
| Existing records with stale SHA/size | 5 |
| Inventory records for nonexistent paths | 0 |

### 4.1 Missing records

| Current path | Explanation |
|---|---|
| `research/PROTOTYPES/PACKAGE-INDEX-01/profile_package_provider.py` | Added after inventory revision |
| `research/PROTOTYPES/PACKAGE-INDEX-01/run_tests_with_timings.py` | Added after inventory revision |
| `research/RT-25-MEMORY-ALLOCATOR-COMPATIBILITY-AND-BENCHMARKING.md` | Added by PR #110 |
| `research/RT-00-B-02B-1-LEAN-PROOF-GRAPH-AUDIT-2026-11-20.md` | Added by merged PR #111 |

### 4.2 Stale path records

Five existing paths have changed Git blob SHA and size since the inventory revision:

- `research/PROTOTYPES/PACKAGE-INDEX-01/README.md`;
- `research/PROTOTYPES/PACKAGE-INDEX-01/benchmark_package_provider.py`;
- `research/README.md`;
- `research/RESEARCH-DEPENDENCY-MAP.md`;
- `research/RESEARCH-TAXONOMY.md`.

The first two changed in the Package Provider work; the last three were updated by PR #110 when RT-25 was registered. The inventory's counts and index-check metadata therefore also need regeneration against the current main tree.

PR #113 and PR #115 are open at this snapshot and are not included in this comparison. If either is merged, its new report file must be included in the next inventory refresh.

## 5. Numbering and relationship gaps retained as unresolved

- Scenario 16 has no report. Prototype 16 explicitly links to Scenario 15; this is a known numbering exception, not grounds to invent or renumber a scenario.
- Scenario 25 is a research proposal with no dedicated Prototype 25. It was registered by PR #110 and does not require a prototype result file.
- Scenario 30 is a source-level CPC assumption-binding analysis; it has no standalone Prototype 30. Its implementation path is continued in Scenario 33.
- The family contains 13 Prototype result documents (16–24 and 26–29), not a contiguous 16–29 series.
- Scenario 34's formal proof and Scenario 33's parser-state binding are related but do not collapse into one claim. The source-derived JSON/CPC correspondence remains open.

These cases should remain explicit in inventory and index metadata; they should not be “fixed” by fabricating matching-number artifacts.

## 6. Remaining graph work

First-pass individual file roles are complete, but the complete graph requested by RT-00 still needs consolidation. The graph should distinguish at least:

- implementation imports and module dependencies;
- implementation-to-test relationships;
- test-to-fixture and test-to-external-tool relationships;
- prototype-to-result-report and scenario-to-prototype links;
- CI workflow-to-command/module relationships;
- evidence-to-exact-source revision and environment;
- historical/superseded document sections;
- unresolved or conditional relationships.

The B-02b.1–B-02b.3 reports supply detailed slices of this graph. B-02b.5 should reconcile them with the existing inventory and produce a single evidence graph/index update rather than infer relationships from directory names.

## 7. Conclusion and disposition

**Disposition: B-02b.4 orphan/traceability triage complete; corpus inventory freshness defect confirmed.**

There are no unclassified Dependency Graph family files in the current inventory. The remaining issue is not a set of obvious orphans: it is the gap between first-pass file-role mappings and a consolidated evidence graph, plus a stale corpus inventory and stale audit-status text.

No implementation, test, historical result, or inventory file was changed by this audit.
