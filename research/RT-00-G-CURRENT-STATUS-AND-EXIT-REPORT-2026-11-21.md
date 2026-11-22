# RT-00 G — Current Status and Exit Report

**Date:** 2026-11-21  
**Audited main baseline:** `017e64b87c87371309197a392165258b8b088dd1`  
**Disposition:** **RT-00 is not complete.** This is a bounded status report; several audit results remain in unmerged PRs and the current inventory manifest is stale.

## 1. Executive status

The audit now has substantive bounded results across inventory freshness, semantic consistency, reproducibility, external provenance, local links/anchors, and cross-document alignment. Those results do not yet form a fully integrated current-main evidence corpus because the relevant PRs remain open and no merge has been performed.

The most important current findings are:

1. Current main contains **490 tracked research artifacts excluding the inventory manifest** and **249 prototype-tree files**. The inventory manifest records 488 artifacts/248 prototypes and is stale: two current paths are missing and four tracked files have SHA/size mismatches.
2. The taxonomy/dependency register is structurally consistent at **26 RT areas and 108 DEP edges**: all IDs unique, all endpoints valid, no self-loops, and two documented non-trivial SCCs.
3. Reproducibility has been refreshed for RT-16 (24/24 tests) and CLI host references (34/34 Python and 34/34 C). RT-04's prior bounded native/LLVM run remains 10/10 native commands and 2/2 LLVM probes. These are scoped results, not broad compiler/runtime conformance.
4. The offline local Markdown/MDX link/anchor scan covered 254 documents in the E PR checkout. It found 82 unresolved occurrences, all in copied upstream snapshots or upstream-site-root paths; no LLMLang-authored local link or available-target anchor error was reported.
5. The prototype role-review counts remain inconsistent: 242 in the inventory aggregate, 245 in the previous PLAN statement, 248 per-file traceability records, and 249 current prototype paths.

No architectural or language-semantic decision is accepted by RT-00. In particular, the ImpHash/ImplHash discrepancy, identity boundaries, contract conformance, dependency/cache completeness, LLVM preservation proof, package trust, and resource enforcement remain unresolved.


## 1A. Current-main inventory freshness update (2026-11-22)

The prior sections above describe their explicitly pinned historical audit baselines and should not be read as current-main counts. A fresh recursive Git-tree comparison at main commit `fc717d9c5a69085d7a524fd6dfc27145f0c35a1c` found 578 research files excluding the inventory manifest (297 Markdown, 3 MDX, 226 Python, 33 Lean), 289 prototype-tree paths, and 137 Scenario-named documents. The manifest records 554 artifacts, has 24 missing paths, 20 stale blob SHA/size records, and no extra paths. 11 prototype paths are absent from the manifest. Traceability metadata on represented paths is not content-review or reproduction evidence. The current manifest has no aggregate prototype role-review field, so historical 242/245/248 counts remain unresolved. Exact path/SHA/size evidence and discrepancy lists are in [RT-00 A current-main inventory freshness reconciliation](RT-00-A-CURRENT-MAIN-INVENTORY-FRESHNESS-RECONCILIATION-2026-11-22.md).

**Effect on RT-00:** Stage A is still open. The inventory manifest itself has not yet been rewritten; the next A task is content-aware reconciliation of the absent paths and per-path prototype review.

## 2. Stage-by-stage status

| Stage | Result | Status |
|---|---|---|
| A — inventory | Recursive audit on main found 490 artifacts, 249 prototype files, two manifest-missing paths, zero extras, four SHA/size mismatches | **Open:** refresh inventory and reconcile per-file role metadata |
| B-03 — cross-cutting semantics | Eight interface/proof gaps recorded; no direct contradiction in reviewed scope | **Bounded pass merged** in PR #124 |
| B-04 — duplicates/supersession | Exact blob grouping and bounded high-risk semantic family review; one expected duplicate licence blob; scoped supersession | **Open/branch-only:** PR #127 is stale/divergent and needs rebase |
| B-05 — traceability graph | Graph semantics, evidence distinctions, and four representative traces | **Open/branch-only:** PR #130 uses stale 488-record count; reconcile against current tree |
| B-06 — contradictions/unresolved | 40-record register; four apparent conflicts reconciled by scope; 18 open design/proof/evidence gaps; no direct core contradiction confirmed | **Open/branch-only:** PR #131 has a C–F follow-up addendum; Required CI run #44938490969 passed all jobs on its updated head |
| C — reproducibility | RT-04, RT-16, and CLI host-reference bounded runs recorded | **Partial:** SQLite provenance, Provider benchmark/profiler, fuel models, and broad prototype reproduction remain open |
| D — external provenance | 13/13 local snapshot blobs match the manifest; README provenance correction is present | **Partial:** upstream signatures were not re-run; OCI/Alive2/REAPI closure and external URL freshness remain open |
| E — links/anchors | Offline scan of 251 Markdown + 3 MDX files; 82 errors all confined to copied snapshots/upstream-root paths | **Local scan complete for pinned checkout:** external URLs and missing-target fragments remain unverified |
| F — document alignment | 26/108 structure validated; candidate/non-normative statuses aligned; stale inventory and prototype-review metadata identified | **Partial:** role-review aggregate and index coverage remain open |
| G — status | Current bounded results and exit gaps consolidated | **Not a closure declaration** |

## 3. Exact inventory freshness result

The non-required recursive audit workflow in PR [#146](https://github.com/aivibeflow/LLMLang/pull/146) checked out exact main commit `017e64b87c87371309197a392165258b8b088dd1` and compared its Git tree with the inventory manifest at revision `b118346ecd499d7962a6ac546fb1031bc7e2bc26`.

| Measure | Current main |
|---|---:|
| Research artifacts (manifest excluded) | 490 |
| Markdown | 250 |
| MDX | 3 |
| Python | 202 |
| Lean | 23 |
| Prototype tree | 249 |
| Scenario-named documents | 136 |
| Taxonomy RT rows | 26 |
| Dependency rows | 108 |

Manifest comparison:

- Missing in manifest:
  - `research/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md`
  - `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py`
- Extra in manifest: 0.
- SHA/size mismatches: 4:
  - `research/PROTOTYPES/DEPENDENCY-GRAPH-01/README.md`
  - `research/README.md`
  - `research/RESEARCH-DEPENDENCY-MAP.md`
  - `research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md`

Artifact [14720512241](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811/artifacts/14720512241) preserves the JSON/Markdown comparison. The workflow did not modify the manifest.

## 4. Dependency and cross-document structure

The current taxonomy has 26 unique RT rows and the dependency map has 108 unique DEP rows. All 108 endpoints resolve to registered RT IDs; there are no duplicate DEP IDs or self-loops. Tarjan SCC analysis finds only:

- RT-05 ↔ RT-12;
- RT-14 ↔ RT-19 ↔ RT-20.

Both are documented feedback relationships. The high-level Mermaid graph is explicitly simplified and omits RT-21–RT-26, which remain present in the detailed taxonomy and edge register.

The Research Option Matrix still says no vector is selected. The Semantic Dependency Index remains a proposal, the Draft Glossary remains a terminology proposal, RT-24 remains non-normative, and ADR-014 remains Proposed. The `ImpHash`/`ImplHash` discrepancy remains unresolved.

## 5. Reproducibility and provenance evidence

### C — bounded reproduction

- RT-04: historical Actions run #44774296240 records 10/10 native commands and 2/2 LLVM preservation probes.
- RT-16: run [#44937172020](https://github.com/aivibeflow/LLMLang/actions/runs/44937172020) passed 24/24 authorization decision tests.
- CLI host references: the same run passed 34/34 Python-reference and 34/34 C-reference cases.
- The CLI results are host-reference calibration, not LLMLang compiler conformance. RT-16's finite in-memory model is not production authorization/security evidence.

Remaining: exact SQLite source-ID equality and full source/package checksums; Package Provider benchmark results are log-only and the optional profiler remains unexecuted; Scenario 36 fuel models lack dedicated tests; the broad prototype corpus has not been uniformly reproduced.

### D — external snapshots

The 13 local snapshot files match their manifest upstream blob SHAs (13/13). This validates current local blob-to-manifest integrity. It does not re-fetch upstream repositories or repeat signature verification from the pinned D audit. OCI and Alive2 snapshots remain partial; REAPI proto import closure is incomplete; external URL freshness is not established.

## 6. Local links and anchors

The E workflow's final run [#44938052704](https://github.com/aivibeflow/LLMLang/actions/runs/44938052704) scanned 251 Markdown and 3 MDX files (254 total) in the PR checkout:

- 2,876 link occurrences;
- 1,312 unique;
- 1,630 accepted;
- 82 errors;
- 1,164 excluded.

All 82 errors are confined to upstream snapshots: 44 MCP root-absolute upstream-site paths, 32 OCI links to omitted documents, and six Alive2 references to omitted assets/README material. No LLMLang-authored local link or available-target anchor error was reported. The scan ran offline, so external URL availability and fragments on missing targets remain unverified. It does not validate non-Markdown resources or index completeness.

## 7. Open PR and branch state

All listed RT-00 follow-up PRs remain open and unmerged:

| PR | Scope | Current qualification |
|---|---|---|
| [#127](https://github.com/aivibeflow/LLMLang/pull/127) | B4 duplicate/supersession | Pinned to older merge-base `f09047a...`; divergent from main `017e64b...`; rebase and inventory reconciliation required |
| [#130](https://github.com/aivibeflow/LLMLang/pull/130) | B5 traceability graph | Based on main `017e64b...`; report's 488 count is stale and must be refreshed to 490 |
| [#131](https://github.com/aivibeflow/LLMLang/pull/131) | B6 unresolved register | 40-record bounded register with C–F follow-up addendum; Required CI run #44938490969 passed all jobs |
| [#136](https://github.com/aivibeflow/LLMLang/pull/136) | C reproduction workflow | Non-required workflow; RT-16/CLI run passed |
| [#137](https://github.com/aivibeflow/LLMLang/pull/137) | RT-04 status correction | Documentation correction based on existing successful run |
| [#138](https://github.com/aivibeflow/LLMLang/pull/138) | C evidence refresh | Records RT-16/CLI exact inputs and run evidence |
| [#141](https://github.com/aivibeflow/LLMLang/pull/141) | D provenance reconciliation | Records 13/13 local blob verification and corrects stale D statement |
| [#142](https://github.com/aivibeflow/LLMLang/pull/142) | E link/anchor audit | Offline scan workflow and report; Required CI passed on latest checked head |
| [#145](https://github.com/aivibeflow/LLMLang/pull/145) | F cross-document alignment | PLAN/report updates; latest Required CI attempt was cancelled during superseding commits and needs a clean completed run |
| [#146](https://github.com/aivibeflow/LLMLang/pull/146) | A inventory freshness | Exact recursive comparison; audit workflow and Required CI passed |

Other branch-only experiments (#128, #129, and stale #126 / reapplication #139) remain separate research inputs and are not silently treated as merged evidence.

No PR was merged during this work.

## 8. Exit blockers and next sequence

RT-00 cannot be closed until the following are resolved or explicitly accepted as bounded limitations:

1. Reconcile/rebase B4 #127 against current main; refresh the inventory manifest with the two missing paths and four blob/size mismatches; register the new audit reports in the research index.
2. Refresh B5 #130's inventory count and graph coverage against the exact 490-file current tree.
3. Reconcile prototype-family mapping metadata (242 aggregate / 245 prior PLAN count / 248 manifest traceability / 249 current paths) and determine the content-review status of the seven-file delta from the aggregate.
4. Refresh B6 after B4/B5 and the C–F reports are integrated; preserve the 40-record historical register and append new evidence rather than overwriting history.
5. Complete claim-level Research → Claim → RT/DEP → Scenario → Prototype → Test → Evidence → PLAN traceability; a file-level graph is not a claim-level proof graph.
6. Complete remaining reproducibility/provenance work: SQLite source identity and archive/package checksums, Provider benchmark/profiler, Scenario 36 fuel tests, and broader prototype execution.
7. Complete external snapshot decisions and validation: OCI/Alive2/REAPI completeness, external URL freshness, signature revalidation, and import closure where needed.
8. Complete index coverage and non-Markdown resource checks; validate every relevant artifact is discoverable from the intended index.
9. Reconcile current PLAN exit criteria and historical snapshots, then produce a final closure report only after the preceding blockers are addressed.

**Final disposition:** RT-00 has progressed from inventory and first-pass audits to several reproducible bounded checks and current cross-document validation. The corpus is not yet fully reconciled, claim-level traceability is incomplete, and several audit PRs are branch-only. **Do not mark RT-00 complete.**


## 9. Current-main refresh — 2026-11-21, after B4 merge

This addendum supersedes the "current" labels in §§1–8 above where they refer to baseline `017e64b`. Those sections remain as a historical snapshot; they are not deleted or silently rewritten.

**Current main:** `b0142c27f5632a859c379b78a10cb22f500ebfd8`, including merged RT-23 PR #126 and B4 PR #152.

### 9.1 Current inventory and taxonomy

| Measure | Current main |
|---|---:|
| Research artifacts (manifest excluded) | 493 |
| Markdown | 252 |
| MDX | 3 |
| Python | 203 |
| Lean | 23 |
| Prototype-tree files | 250 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

The 493 count is derived from the exhaustive recursive audit at `017e64b`, exact commit delta to `b52ba2f` (two added, six modified, zero deleted), and exact delta to `b0142c2` (one B4 report added, zero deleted). A new full recursive enumeration at `b0142c2` was not run.

The main inventory manifest remains at 488 records. A current reconciliation is proposed in [PR #149](https://github.com/aivibeflow/LLMLang/pull/149): 494 records on its branch (493 current-main artifacts plus its own reconciliation report), five previously absent main paths, 253 Markdown, 250 prototype files, and five refreshed existing blob records. JSON validation and the branch freshness workflow pass; Required CI also passes all eight jobs. The manifest is not yet merged.

Prototype counts remain distinct: 242 individually role-mapped artifacts, 245 earlier PLAN aggregate, 248 previous manifest paths, and 250 actual prototype paths. They must not be treated as equivalent review coverage.

### 9.2 Current audit stage and PR state

| Stage | Current result | Current PR/evidence |
|---|---|---|
| A — inventory | Exact manifest reconciliation proposed; 494 branch records | [#149](https://github.com/aivibeflow/LLMLang/pull/149); freshness audit #44942162064 success; Required CI #44942162141 success |
| B-03 | Bounded cross-cutting consistency audit | Merged #124 |
| B-04 | Exact blob grouping and bounded semantic duplicate/supersession review | Merged #152; current-main report is in main |
| B-05 | Traceability graph refreshed for current main and RT-23 | [#151](https://github.com/aivibeflow/LLMLang/pull/151); Required CI #44942296329 success |
| B-06 | Original 40-record unresolved register refreshed for current main | [#154](https://github.com/aivibeflow/LLMLang/pull/154); Required CI #44942398727 success |
| C — reproducibility | RT-16/CLI bounded tests; RT-04 status/evidence; SQLite source identity and archive digests being tightened | [#165](https://github.com/aivibeflow/LLMLang/pull/165), [#166](https://github.com/aivibeflow/LLMLang/pull/166), [#167](https://github.com/aivibeflow/LLMLang/pull/167), [#164](https://github.com/aivibeflow/LLMLang/pull/164) |
| D — external provenance | 13/13 local snapshot blob matches; incompleteness remains explicit | [#168](https://github.com/aivibeflow/LLMLang/pull/168); Required CI #44943037414 success |
| E — links/anchors | 256 Markdown/MDX documents; 82 errors confined to upstream snapshots; 16/17 curated external references returned content, POSIX returned 403 | [#160](https://github.com/aivibeflow/LLMLang/pull/160) local scan; [#169](https://github.com/aivibeflow/LLMLang/pull/169) curated external check |
| F — cross-document alignment | 26 RT/108 DEP structurally valid; two documented SCCs; prototype count populations reconciled | [#158](https://github.com/aivibeflow/LLMLang/pull/158); Required CI #44942523316 success |
| G — status | This current-main addendum; no closure claim | [#155](https://github.com/aivibeflow/LLMLang/pull/155) |

Additional validation:
- PR #165 Required CI #44942990482 and reproducibility smoke workflow #44942990515 both passed.
- PR #166 Required CI #44942995298 passed; its native reproduction workflow #44942995286 passed 10/10 native commands and 2/2 LLVM probes; artifacts 14722417949 and 14722227550.
- PR #167 Required CI #44942997999 passed.
- PR #164 Required CI #44942585935 passed; native reproduction workflow #44942585953 passed 10/10 native commands and 2/2 LLVM probes, including all three archive SHA-256 checks and exact Scenario 130 SQLite source-ID matching; artifacts 14722660960 and 14722122244.
- PR #168 Required CI #44943037414 passed.

The old-baseline PRs #136–#138, #141, and #142 were closed as superseded by current-main replacements #165–#167, #168, and #160 respectively. C-02 PR #163 was closed as superseded by #164. These closures did not merge or discard any main changes.

### 9.3 Remaining exit blockers

1. Merge/integrate the current-main audit PRs only when explicitly authorized; then refresh inventory once more to include all merged reports, source/workflow changes, and updated blob metadata.
2. Complete claim-level traceability. The file-level graph does not establish that each claim has an executable test and evidence tied to the same source revision.
3. Reconcile the remaining Scenario 102 historical focused-run provenance; the current eight-method file is byte-identical to the source in the 364-test Required CI run, but the older seven-test focused run's exact revision remains unknown.
4. Await and inspect the final native reproduction runs for #164 and #166; the new SQLite source ID is a prospective baseline, not retrospective historical proof.
5. Resolve remaining Ubuntu package archive, runner/container image, and rustup bootstrap identity limitations.
6. Preserve manual-only benchmark behavior; the Provider profiler and durable raw benchmark artifact remain open.
7. Add dedicated tests for Scenario 36 fuel models before claiming reproduction.
8. Decide whether external URL availability and full snapshot closure are required; OCI/Alive2/REAPI remain intentionally partial.
9. Complete index coverage and non-Markdown resource checks, then reconcile PLAN exit criteria against the integrated current main.

**Final disposition:** B4 is merged and the A–G audit has more current-main, CI-backed slices. The inventory manifest remains stale on main, several audit PRs are still branch-only, claim-level traceability is incomplete, and some experiments/provenance boundaries remain open. **RT-00 is not complete. No merge has been performed in this continuation.**


## 10. Claim-level pilot and B6 evidence refresh — 2026-11-21

This addendum supersedes the relevant open-item descriptions in §9 without rewriting the historical 40-record B6 snapshot.

### 10.1 B5 claim-level traceability pilot

B5 PR #151 now includes [Scenario 130 claim-level traceability pilot](RT-00-B-05-01-SCENARIO-130-CLAIM-TRACEABILITY-PILOT-2026-11-21.md). It traces four executable claims through report sections, model/probe symbols, test methods, exact source blobs, Required CI, native reproduction, and retained artifacts. A fifth broader implication remains conditional. The local IDs S130-C01–C05 are not a global Claim ID scheme. The pilot is branch-only; latest Required CI was pending when this addendum was written.

### 10.2 B6 register refresh

B6 PR #154 preserves the original 40 B6-local records and appends one bounded evidence record, bringing the machine-readable register to 41 records. It updates:
- Scenario 130's prospective exact SQLite source-ID and archive-integrity evidence;
- Scenario 102's current eight-method test execution evidence while preserving the unresolved historical seven-test run provenance;
- D's 13/13 local snapshot identity result;
- E's 16/17 curated external-reference reachability result;
- the current replacement PR state.

The global Claim ID gap and corpus-wide claim/test/evidence completeness remain unresolved. Latest Required CI was pending when this addendum was written.

### 10.3 Completed reproduction and external-reference checks

- C-02 PR #164: Required CI passed; native reproduction passed 10/10 commands and LLVM preservation passed 2/2 probes. SQLite/Python source archive and LLVM package SHA-256 checks passed; the exact prospective Scenario 130 SQLite source ID matched. Artifacts 14722660960 and 14722122244.
- C PR #166: Required CI passed; fresh RT-04 native reproduction passed 10/10 commands and LLVM preservation passed 2/2 probes. Artifacts 14722417949 and 14722227550.
- C PR #165: Required CI and bounded RT-16/CLI smoke workflow passed.
- E-02 PR #169: 16 of 17 curated reference URLs returned content; POSIX returned 403 to the checker and remains indeterminate. This does not establish corpus-wide external URL availability.

### 10.4 Remaining exit blockers

1. Complete claim-level traces for additional scenarios and RT areas; do not generalize the Scenario 130 pilot to corpus-wide completeness.
2. Keep the historical Scenario 102 seven-test run provenance unresolved unless its exact source revision can be recovered; current eight-method source execution is confirmed in the 364-test Required CI run.
3. Preserve the prospective/historical distinction for Scenario 130's SQLite source identity.
4. Resolve remaining Ubuntu package archive, runner/container image, and rustup bootstrap identity limits.
5. Complete Provider benchmark/profiler and Scenario 36 fuel-model tests.
6. Decide whether full external URL availability and full snapshot closure are required; the POSIX 403 is indeterminate and OCI/Alive2/REAPI remain partial.
7. Complete index coverage and non-Markdown resource checks, refresh the inventory after integrating the audit PRs, and reconcile PLAN exit criteria.

**Updated disposition:** bounded C–E results are now materially stronger, and one claim-level traceability pilot exists. B5/B6 are still branch-only, the main inventory is stale, and corpus-wide claim/evidence closure remains open. **RT-00 is not complete.**


## 11. Subsequent validation status

After §10 was authored, the latest B5 and B6 Required CI runs completed:

- B5 PR #151 latest Required CI [#44943905241](https://github.com/aivibeflow/LLMLang/actions/runs/44943905241) and policy [#44943905230](https://github.com/aivibeflow/LLMLang/actions/runs/44943905230) passed after adding the Scenario 130 pilot.
- B6 PR #154 latest Required CI [#44944020348](https://github.com/aivibeflow/LLMLang/actions/runs/44944020348) and policy [#44944020365](https://github.com/aivibeflow/LLMLang/actions/runs/44944020365) passed after appending the 41st B6 record.
- G PR #155 Required CI [#44944083284](https://github.com/aivibeflow/LLMLang/actions/runs/44944083284) and policy [#44944083280](https://github.com/aivibeflow/LLMLang/actions/runs/44944083280) passed.

These are successful branch validations, not merged-main evidence. The PRs remain open and unmerged.


## 12. Current-main refresh after RT-17, RT-26, and RT-05 merges — 2026-11-21

The report's preceding sections preserve the earlier audit snapshots and their exact baselines. This section updates the current-main status without rewriting those historical observations.

### 12.1 Current main and exact change deltas

Current main is `3a3f90bcf06c8ba2678dfefa789ab49671247442`.

After the prior G baseline `b0142c27f5632a859c379b78a10cb22f500ebfd8`, the exact commit comparisons show:

| Change | Research paths added | Research Markdown | Research Python | Prototype paths |
|---|---:|---:|---:|---:|
| RT-17 diagnostic replay (PR #128) | 2 | 1 | 1 | 1 |
| RT-26 cooperative budget reservation (PR #129) | 2 | 1 | 1 | 1 |
| RT-05 typed SPG import validation (PR #132) | 3 | 1 | 2 | 2 |
| **Net change** | **7** | **3** | **4** | **4** |

PR #170 added the MIT license, and the Authors attribution commit added `AUTHORS.md`; neither adds a research artifact. The RT-26 hierarchical resource-accounting report was modified by PR #129 but was not a newly added path.

Derived current-main totals are therefore:

| Measure | Current count |
|---|---:|
| Research artifacts, excluding inventory manifest | 500 |
| Markdown | 255 |
| MDX | 3 |
| Python | 207 |
| Lean | 23 |
| Prototype-tree files | 254 |
| Scenario-named documents | 136 |
| RT taxonomy rows | 26 |
| DEP rows | 108 |

The RT and DEP row counts were independently recounted from current-main taxonomy and dependency-map tables. The artifact/file totals are derived from the exhaustive `017e64b` inventory baseline plus exact commit deltas through `3a3f90b`; **a fresh full recursive tree enumeration at `3a3f90b` has not been run**.

### 12.2 Inventory status

The inventory manifest on current main still contains 488 artifact records and records the old source revision `b118346ecd499d7962a6ac546fb1031bc7e2bc26`. It therefore does not cover the five additions previously identified for RT-23, RT-24, and B4, nor the seven later additions listed above. The prior current-main reconciliation attempt did not land on main. A new exact recursive-tree audit and manifest refresh are still required; do not treat branch-only audit output as current-main evidence.

The separate prototype populations remain distinct: 242 individually role-mapped artifacts, 245 earlier PLAN aggregate, 248 previous manifest paths, and 254 current prototype-tree paths. The count of 254 is derived from exact additions since the last audited tree; the per-file role review has not been extended to those additions.

### 12.3 Open audit work and current PRs

At this refresh, the open RT-00 continuation PRs are:

- [PR #155](https://github.com/aivibeflow/LLMLang/pull/155) — G report against the previous `b0142c2` baseline; superseded by this current-main refresh.
- [PR #158](https://github.com/aivibeflow/LLMLang/pull/158) — F alignment against the previous `b0142c2` baseline; requires a current-main delta review.
- [PR #160](https://github.com/aivibeflow/LLMLang/pull/160) — E link/anchor audit against the previous `b0142c2` baseline; its result remains useful for that checkout, but the new RT-17/RT-26/RT-05 paths need link/anchor coverage.
- [PR #165](https://github.com/aivibeflow/LLMLang/pull/165) — bounded reproducibility smoke workflow; its evidence remains scoped to RT-16 and CLI host-reference calibration.

The RT-17, RT-26, and RT-05 merges add experimental evidence, not accepted architecture decisions. RT-26 runtime/OS enforcement, resource attribution and overhead remain open; RT-17 diagnostic replay evidence is a bounded prototype; RT-05 admission validation does not close global Claim ID or SPG conformance questions.

### 12.4 Updated exit blockers

1. Run a fresh recursive tree/blob/size audit at current main `3a3f90b`; refresh the 488-record manifest to the exact current tree and preserve the historical manifests/counts.
2. Extend the inventory's per-file role metadata to the seven newly added research paths only after reviewing each artifact's actual content and evidence.
3. Rebase or replace F and E audits on current main and rerun the affected checks for the newly added documents.
4. Extend claim-level traceability beyond the Scenario 130 pilot; do not infer corpus-wide completeness from the bounded pilot.
5. Continue reproducibility closure for Provider benchmark/profiler, Scenario 36 fuel model, exact environment/source provenance, and remaining native/runtime experiments.
6. Complete external-source provenance and snapshot-closure decisions, including the indeterminate POSIX response and partial OCI/Alive2/REAPI material.
7. Reconcile PLAN exit criteria and all cross-document indexes after the current inventory is corrected.

**Current disposition:** current-main research count is 500 by exact commit-delta accounting, but the main manifest remains at 488. E/F reports are one change-set behind, claim-level traceability is still a bounded pilot, and reproducibility/provenance work remains incomplete. **RT-00 is not complete. No PR has been merged as part of this refresh.**


## 13. Current-main refresh after RT-24 and RT-09 preservation merges — 2026-11-21

The preceding sections remain historical snapshots at their stated revisions. This section updates the latest repository state without retroactively rewriting prior evidence.

### 13.1 Latest main and exact deltas

Current main is `6aaac5518082e99627d0c28c6dabcddf8bad4933`.

Since §12's baseline `3a3f90bcf06c8ba2678dfefa789ab49671247442`, exact commit comparisons show:

| Merged change | Research paths added | Markdown | Python | Prototype paths |
|---|---:|---:|---:|---:|
| RT-24 closed three-way merge core | 2 | 1 | 1 | 1 |
| RT-09 mutable byte-view preservation probe | 2 | 1 | 1 | 1 |
| **Net change** | **4** | **2** | **2** | **2** |

The new paths are:
- `research/RT-24-CLOSED-THREE-WAY-MERGE.md`
- `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_semantic_merge_core.py`
- `research/RT-09-13-MUTABLE-BYTE-VIEW-PRESERVATION.md`
- `research/PROTOTYPES/LLVM-PRESERVATION-01/llvm_mutable_view_probe.py`

Derived latest-main totals are:

| Measure | Count |
|---|---:|
| Research artifacts, excluding inventory manifest | 504 |
| Markdown | 257 |
| MDX | 3 |
| Python | 209 |
| Lean | 23 |
| Prototype-tree files | 256 |
| Scenario-named documents | 136 |
| RT taxonomy rows | 26 |
| DEP rows | 108 |

The RT and DEP counts were recounted from the current taxonomy and dependency-map tables. The artifact/file totals are derived from the exhaustive `017e64b` inventory baseline plus exact commit deltas through `6aaac55`; **a fresh full recursive tree enumeration at `6aaac55` has not been run**.

### 13.2 Inventory and cross-document status

The current-main inventory manifest still contains 488 records and source revision `b118346ecd499d7962a6ac546fb1031bc7e2bc26`. It is now at least 16 research artifacts behind the derived 504-path count. The previously prepared inventory refresh did not land on main. A new exact recursive tree/blob/size audit is required before publishing a replacement manifest; do not treat branch-only inventory counts as current-main validation.

The 242/245/248/256 prototype values continue to describe different populations: individually role-mapped artifacts, earlier PLAN aggregate, previous manifest paths, and current prototype paths. No claim is made that the newly added prototype files have undergone the same role-review depth.

The latest merges add executable evidence for RT-24 semantic merge and RT-09 mutable byte-view preservation. They do not establish full RT-24 merge correctness, production compiler/backend conformance, or complete LLVM semantic preservation.

### 13.3 Current open audit PRs

At this refresh, the open RT-00 continuation PRs are:
- [PR #155](https://github.com/aivibeflow/LLMLang/pull/155) — G against the older `b0142c2` baseline; superseded by this refresh.
- [PR #158](https://github.com/aivibeflow/LLMLang/pull/158) — F alignment against `b0142c2`; requires review of the new RT-17/RT-26/RT-05/RT-24/RT-09 artifacts.
- [PR #160](https://github.com/aivibeflow/LLMLang/pull/160) — E link/anchor audit against `b0142c2`; rerun affected checks for the newly added documents.
- [PR #165](https://github.com/aivibeflow/LLMLang/pull/165) — bounded RT-16/CLI reproducibility smoke workflow; the workflow's scope remains valid, but its PR base predates current main.

### 13.4 Updated exit blockers

1. Run a fresh recursive tree/blob/size audit at `6aaac55`; reconcile the 488-record manifest to the exact current tree and preserve historical counts.
2. Extend per-file role metadata to the newly added RT-17, RT-26, RT-05, RT-24, and RT-09 artifacts only after bounded content review.
3. Refresh E/F checks against the current tree, including the newly added reports and prototype source files.
4. Extend claim-level traceability beyond the Scenario 130 pilot; do not infer corpus-wide completeness.
5. Continue reproducibility closure for Provider benchmark/profiler, Scenario 36 fuel model, exact environment/source provenance, and remaining native/runtime experiments.
6. Complete external-source provenance and snapshot-closure decisions, including indeterminate and partial upstream materials.
7. Reconcile PLAN exit criteria and all cross-document indexes after the inventory is corrected.

**Current disposition:** latest-main research count is 504 by exact commit-delta accounting, while the manifest remains at 488. The E/F audit snapshots predate five merged experimental slices, claim-level traceability remains a bounded pilot, and reproducibility/provenance work remains incomplete. **RT-00 is not complete. No PR has been merged as part of this refresh.**

## 14. Current-main refresh after subsequent audit and experiment integrations — 2026-11-21

Sections 1–13 preserve their original audit snapshots and exact baselines. In particular, the PR-state table in §13.3 and the 504-artifact count in §13 apply to the 6aaac55 snapshot, not to the later current main. This section updates the derived counts without rewriting those historical observations.

**Current main:** dcf727806d6e4495bc941d143e871c22e425fb4d. Comparing baseline 6aaac5518082e99627d0c28c6dabcddf8bad4933 with current main yields 29 commits, 45 newly added research paths, and no deleted research paths. The additions comprise 25 Markdown, 12 Python, three Lean, two MJS, two C, and one JSON file; 19 of the added paths are under research/PROTOTYPES/.

Derived current-main totals are:

| Measure | Count |
|---|---:|
| Research artifacts, excluding inventory manifest | 549 |
| Markdown | 282 |
| MDX | 3 |
| Python | 221 |
| Lean | 26 |
| Prototype-tree paths | 275 |
| Scenario-named documents | 136 |
| RT taxonomy rows | 26 |
| DEP edges | 108 |

The counts start from the documented 6aaac55 totals in §13 and apply the exact Git commit delta. The current taxonomy and dependency map were independently recounted at 26 RT rows and 108 DEP rows. This is a commit-delta reconciliation, not a new exhaustive filesystem enumeration.

The inventory manifest remains at 488 records; it was not changed in the compared commit range. It is therefore 61 records behind the derived 549-path count. A fresh recursive tree/blob/size audit and manifest refresh are still required. The 242/245/248 role-review and historical manifest populations remain distinct from the 275 current prototype-tree paths.

The earlier open-PR table and statements that audit PRs remain unmerged are historical. Subsequent integrations have added the A, D, E, and F audit reports and the RT-17, RT-24, RT-26 and related prototype evidence. Their integration does not establish corpus-wide claim-level traceability, full reproducibility, complete external snapshot closure, or RT-00 completion.

**Updated disposition:** current-main research paths total 549 by exact commit-delta accounting, while the manifest remains at 488. Claim-level traceability remains a bounded pilot, per-file role review does not cover all 275 prototype paths, and reproducibility/provenance/index-coverage work remains incomplete. **RT-00 is not complete.**

## 15. Current-main status refresh — 2026-11-22

This section supersedes the 549-artifact snapshot in §14. The latest recursive audit is [PR #219](https://github.com/aivibeflow/LLMLang/pull/219), workflow [#44951486838](https://github.com/aivibeflow/LLMLang/actions/runs/44951486838), exact checkout `7f962bb4ffe921891d6c817ddef692fad7421590`, artifact [14725633019](https://github.com/aivibeflow/LLMLang/actions/runs/44951486838/artifacts/14725633019). It found 554 research artifacts excluding the manifest, 66 missing paths, 20 SHA/size mismatches and zero extra paths. The corresponding 554-record reconciliation was merged through PR #221 (merge commit `b40fbaba8ac0d065f402cb59cd851e44840646fa`). The inventory contains 554 unique sorted records and category totals summing to 554.

### 15.1 Current corpus counts

| Measure | Count |
|---|---:|
| Research artifacts, excluding inventory manifest | 554 |
| Markdown / MDX | 284 / 3 |
| Python / Lean | 222 / 28 |
| Prototype-tree paths | 278 |
| Scenario-named paths | 137 |
| RT taxonomy rows / DEP edges | 26 / 108 |

The stored Scenario crosswalk maps 136 files, leaving one Scenario-named path discrepancy unresolved. The recorded semantic review covers 242 individually role-triaged prototype files; 36 current prototype paths lie outside that recorded individual-role total. The inventory establishes path/blob/size metadata only; it does not infer semantic review for the 66 inventory-only additions.

### 15.2 Integrated bounded evidence

- **RT-06:** 13/13 exact CPython 3.12.14 tests passed in run #44948779526.
- **RT-09:** 16/16 exact CPython 3.12.14 tests passed in run #44948779526; this is Python-level ordered lowering, not LLVM or machine-code proof.
- **RT-13:** the report declares 12,800 WebAssembly memory32 oracle comparisons and two negative controls. A retained exact CI reproduction is not yet recorded.
- **RT-07 / Scenario 34:** the direct typed-source-to-CPC gate binds declarations, compares the complete ordered assumptions, and requires a complete Logos verdict for the tested fragment. JSON/wire correspondence and broader renderer/parser obligations remain open.
- **RT-24 call-target merge:** 18/18 tests passed under CPython 3.12.14 in run #44950912463. The runner used Git 2.56.1 rather than the report-declared 2.52.0; exact version reproduction remains open.
- **RT-24 Git replay source closure:** the report and test evidence are present in the 554-path snapshot. Exact reproduction under Git 2.52.0 is the subject of PR #225.
- **RT-26:** reservation and cancellation models passed 7/7 exact CPython 3.12.14 tests in run #44949563913. Their scope is cooperative cumulative-budget models, not production resource enforcement.

The RT-04 local PLAN anchor correction was merged in PR #218. PR #220 was closed as a duplicate because its only source change was already integrated by #218. PR #222 was closed as already integrated by PR #208; the RT-26 status and reproduction addenda are present on main.

### 15.3 Active follow-up PRs

| PR | Scope | Current disposition |
|---|---|---|
| [#224](https://github.com/aivibeflow/LLMLang/pull/224) | Latest research link/anchor audit and RT-04 anchor refresh | Open |
| [#225](https://github.com/aivibeflow/LLMLang/pull/225) | Reproduce RT-24 Git replay under declared Git 2.52.0 | Open |
| [#226](https://github.com/aivibeflow/LLMLang/pull/226) | Structure contracts and atomic commit verification synthesis | Open |

### 15.4 Remaining RT-00 gaps

RT-00 is not complete. Inventory path/blob/size reconciliation is merged for the 554-artifact snapshot, but semantic role review of 36 prototype paths, the 137-versus-136 Scenario crosswalk discrepancy, claim-level graph coverage, exact RT-13 reproduction, RT-24 Git 2.52.0 reproduction, external-source snapshot closure, full reproducibility/provenance, and PLAN exit-criteria reconciliation remain open. No bounded experiment is promoted to a general semantic guarantee.
