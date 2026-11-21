# RT-00 A — Inventory Manifest Freshness Reconciliation

**Date:** 2026-11-21  
**Audited main revision:** `1d0a40714fa1a43f48ca73c32a89a0dba7ce2157`  
**Earlier exhaustive tree baseline:** `017e64b87c87371309197a392165258b8b088dd1`  
**Intermediate main revision:** `b52ba2fb32e2c315997c74d8924c2c9aaeb177dc`  
**Disposition:** inventory path/blob metadata is reconciled to the current main tree plus this report; historical semantic-role counts remain separately qualified.

## 1. Purpose and method

The RT-00 A freshness workflow in PR #146 compared the inventory manifest against a recursive Git-tree enumeration of main at `017e64b87c87371309197a392165258b8b088dd1`. This follow-up applies those findings and accounts for merged RT-23 PR #126, merged B4 audit PR #152, merged RT-26 budget-reservation evidence PR #129, and merged RT-17 diagnostic replay PR #128.

The exact GitHub commit comparison from `017e64b` to `b52ba2f` reports two added paths, six modified paths, and no deleted paths. The additions are the RT-23 recovery report and its paired Dependency Graph test. The subsequent exact comparison from `b52ba2f` to `b0142c2` reports one added path (the B4 audit report) and zero deletions. The exact comparison from `b0142c2` to `1d0a407` adds the RT-17 report and paired test, modifies PLAN and the research index, and adds AUTHORS.md outside the research tree; no research paths are deleted. The manifest excludes itself.

The comparison uses tracked Git paths, blob object IDs, and byte sizes. File-role and semantic-review fields are not inferred from hashes; new records are based on the explicit RT-23/RT-24/RT-17 reports and paired test contents.

## 2. Current main tree

The earlier recursive audit measured 490 research artifacts, 250 Markdown, 3 MDX, 202 Python, 23 Lean, 249 prototype-tree files, and 136 Scenario-named documents at baseline `017e64b`.

PR #126 adds two research artifacts (one Markdown report and one Python test), bringing the tree to 492. PR #152 adds the B4 Markdown audit report, bringing main at `b0142c2` to 493 research artifacts. PR #128 then adds the RT-17 Markdown report and Python test, bringing current main at `1d0a407` to 495 research artifacts. No research paths were deleted. Current main contains:

| Measure | Count |
|---|---:|
| Research artifacts excluding inventory manifest | 495 |
| Markdown files | 253 |
| MDX files | 3 |
| Python files | 204 |
| Lean files | 23 |
| Prototype-tree files | 251 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

These totals are derived from the exhaustive `017e64b` tree audit plus exact commit comparisons `017e64b...b52ba2f`, `b52ba2f...b0142c2`, and `b0142c2...1d0a407`; a fresh full recursive enumeration at `1d0a407` was not run.

## 3. Paths absent from the previous manifest

| Path | Role |
|---|---|
| `research/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md` | RT-24 bounded experimental report; evaluates DEP-088, DEP-091, DEP-093 and references its paired executable fixture |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py` | Seven focused tests for closed source inventories, merge-tree completeness, exact call reconstruction, and evidence replay |
| `research/RT-23-EXACT-TREE-COMMIT-RECOVERY.md` | RT-23 bounded local Git publication/retry study |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_commit_recovery.py` | Eight focused tests for exact commit publication, operation receipts, retries, and ref movement |
| `research/RT-00-B-04-CORPUS-DUPLICATE-AND-SUPERSESSION-AUDIT-2026-11-21.md` | Merged RT-00 B4 audit report; current-main exact blob grouping and bounded semantic candidate-family review |
| `research/RT-17-DIAGNOSTIC-REPLAY.md` | Merged RT-17 bounded Scenario 95 diagnostic-location and repair-applicability experiment; four executable fixture tests |
| `research/PROTOTYPES/DIAGNOSTIC-REPLAY-01/test_diagnostic_replay.py` | Four focused tests for UTF-8/16/32 position conversion, stale/incomplete reports, deterministic multi-file edit staging, and behavior-preserving repair validation |

No extra manifest paths were found at the earlier audited baseline. The PR #126, #152, and #128 additions are explicitly added to the current manifest.

## 4. Existing records with stale blob metadata

The following current-main records are refreshed:

| Path | Current Git blob SHA | Bytes |
|---|---|---:|
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/README.md` | `505c759a0d0d0927529c0ef0a0f77573e7d7deaa` | 35,110 |
| `research/README.md` | `04c132e793599dd5ac24384da79da69b8e728790` | 27072 |
| `research/RESEARCH-DEPENDENCY-MAP.md` | `5afa970c7cd5f4bf3e232102a9453b1f91bdb02c` | 49,945 |
| `research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md` | `2be7ddb8c530127e3c20a2bd383236afdc70e8df` | 29,948 |
| `research/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md` | `e404b263c773499573bead4c3cdff9991dd5285b` | 39,470 |

The RT-24 test is a newly added inventory record and uses its post-PR-#126 blob metadata rather than the stale pre-merge snapshot.

## 5. Prototype-count semantics

The following counts describe different populations and must not be conflated:

- **242** — `semantic_traceability_review.prototype_family_review.individually_mapped_files`: the historical aggregate of individually role-triaged prototype artifacts.
- **245** — an earlier PLAN aggregate; its underlying per-file reconciliation is not established by this count.
- **248** — the previous inventory manifest's prototype-tree file count and per-file traceability-record population.
- **251** — the current main prototype-tree path count after PR #126 added the RT-23 test and PR #128 added the RT-17 diagnostic replay test, derived from the earlier exhaustive tree audit plus exact commit comparisons.

The RT-23, RT-24, and RT-17 tests are now explicitly recorded. Their file roles are grounded in the paired reports and their test methods. These per-file records do not retroactively rewrite the historical 242/245 role-review aggregates or establish that every prototype file has equal claim-level or execution review.

## 6. Manifest update

The accompanying manifest change:
- uses the exact branch source revision immediately before the manifest update;
- adds the seven missing path records (RT-23 report/test, RT-24 report/test, B4 report, RT-17 report/test);
- refreshes stale blob SHA/size metadata;
- includes this reconciliation report;
- updates totals to 496 research artifacts including this report, 254 Markdown files, 3 MDX files, 204 Python files, 23 Lean files, 251 prototype-tree files, and 136 Scenario-named documents;
- updates category totals and records the distinction between inventory coverage and historical prototype role-review counts.

The 496 artifact count includes this reconciliation report; current main contributes 495 artifacts, including the merged B4 report and RT-17 report/test. The inventory manifest itself remains excluded.

## 7. Limitations

This is a path/blob/size reconciliation derived from the exhaustive earlier tree audit and an exact subsequent commit comparison, not a fresh full recursive enumeration of the current main tree. The RT-23/RT-24/RT-17 reports and paired tests were inspected to assign bounded file roles. Existing semantic traceability and prototype family-review aggregates remain historical where explicitly labelled. No claim-level completeness, broad test execution, semantic conformance, external provenance, or architecture decision is inferred from inventory membership.

The original freshness workflow evidence remains in [PR #146](https://github.com/aivibeflow/LLMLang/pull/146), run [#44938305811](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811), artifact [14720512241](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811/artifacts/14720512241). The subsequent exact commit comparisons are `017e64b...b52ba2f`, `b52ba2f...b0142c2`, and `b0142c2...1d0a407`.


## 8. PR-head recursive verification

The reusable inventory freshness workflow checked out the PR head and performed a second full recursive Git-tree comparison after the manifest update. Run [#44942162064](https://github.com/aivibeflow/LLMLang/actions/runs/44942162064) scanned revision `db667e8b53e74933e2a9164dada4b1b45e9d5510` and reported **status: exact**:

- Research artifacts excluding the manifest: 494
- Manifest records: 494
- Missing paths: 0
- Extra paths: 0
- SHA/size mismatches: 0

Artifact [14721893351](https://github.com/aivibeflow/LLMLang/actions/runs/44942162064/artifacts/14721893351) preserves the JSON/Markdown report. ZIP SHA-256: `36db81442be9723ccb9ee33b6d46672409d13b459f88a2b3ed3040b7223802ed`.

This verifies the exact earlier PR tree at that revision, not the refreshed current main or claim-level semantic completeness.


## 9. Current-main refresh after RT-17 merge

The previous §8 verification was performed before RT-17 merged. Current main advanced to `1d0a40714fa1a43f48ca73c32a89a0dba7ce2157`. The exact `b0142c2...1d0a407` delta adds two research artifacts (RT-17 report and test), modifies PLAN and the research README, and adds AUTHORS.md outside the research tree.

The intermediate RT-17 refresh included seven paths absent from the old 488-record manifest:
- RT-23 report and test;
- RT-24 source-completeness report and test;
- merged B4 audit report;
- RT-17 diagnostic replay report and test.

The intermediate branch manifest contained 496 records: 495 current-main research artifacts plus this A reconciliation report. It recorded 254 Markdown files, 3 MDX, 204 Python, 23 Lean, and 251 prototype-tree files. The updated README indexes RT-17 and the A/B4 reports. PLAN preserves the 242/245/248/251 prototype-count distinction, indexes RT-17 output, and records the merged RT-26 budget-reservation evidence. The current branch freshness workflow must be rerun on the final manifest head; the earlier 494/494 result in §8 is retained as a historical verification only.

RT-26's merged evidence is bounded: separate checks overshoot in four of six schedules; serialized reservation matches direct subtree accounting over 4,320 transitions. Runtime and OS enforcement measurements remain open. RT-17's four fixture tests cover Unicode location conversion, diagnostic snapshot validity, deterministic multi-file edit staging, and behavioral regression detection; human/agent evaluation remains open.

No fresh full recursive tree enumeration at `1d0a407` is claimed. No claim-level completeness or broader runtime enforcement is inferred from these additions.


## 10. Current-main refresh after RT-05, RT-09/13, RT-24, and RT-26 merges

Main advanced from `1d0a40714fa1a43f48ca73c32a89a0dba7ce2157` to `6aaac5518082e99627d0c28c6dabcddf8bad4933`. The exact commit comparison reports nine added research paths, three modified research paths, and no research-path deletions. The additions correspond to merged RT-26 budget reservation, RT-05 typed SPG import validation, RT-24 closed three-way merge, and RT-09/13 mutable byte-view preservation. The modified files are the dependency map, taxonomy, and RT-26 hierarchical resource accounting area report.

Current main at `6aaac55` is therefore estimated at:

| Measure | Count |
|---|---:|
| Research artifacts excluding inventory manifest | 504 |
| Markdown files | 257 |
| MDX files | 3 |
| Python files | 209 |
| Lean files | 23 |
| Prototype-tree files | 256 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

These totals are derived from the exhaustive earlier tree audit plus exact commit deltas through `6aaac55`; no new full recursive tree enumeration at that revision is claimed. The PR branch manifest is updated to 505 records (504 current-main artifacts plus this A report), 258 Markdown, 3 MDX, 209 Python, 23 Lean, and 256 prototype-tree files.

### 10.1 Nine additional paths added to the manifest

| Path | Bounded role |
|---|---|
| `research/PROTOTYPES/BUDGET-RESERVATION-01/test_budget_reservation.py` | Four RT-26 interleaving, linearization, retry, and cancellation tests |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_admission.py` | Independent validation/admission of imported typed SPG values |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_semantic_merge_core.py` | Six RT-24 closed-inventory three-way merge tests |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_spg_admission.py` | Five imported-SPG integrity, executable-edge, snapshot, and conformance-boundary tests |
| `research/PROTOTYPES/LLVM-PRESERVATION-01/llvm_mutable_view_probe.py` | Native LLVM/C++ mutable byte-view preservation probe |
| `research/RT-05-TYPED-SPG-IMPORT-VALIDATION.md` | Bounded imported-graph admission experiment; nine rehashed invalid graphs rejected |
| `research/RT-09-13-MUTABLE-BYTE-VIEW-PRESERVATION.md` | LLVM/C++ mutable overlapping byte-view observation comparison |
| `research/RT-24-CLOSED-THREE-WAY-MERGE.md` | Closed semantic-inventory three-way merge experiment |
| `research/RT-26-COOPERATIVE-BUDGET-RESERVATION.md` | Bounded cooperative hierarchical budget reservation experiment |

### 10.2 Three modified research records with refreshed blob metadata

| Path | Current Git blob SHA | Bytes |
|---|---|---:|
| `research/RESEARCH-DEPENDENCY-MAP.md` | `2a9d7151b46d9b3350652ea9d85b52af0b2aa1a0` | 50,211 |
| `research/RESEARCH-TAXONOMY.md` | `1779ebe41a133dea5eeab536d16d400f74974ffd` | 45,925 |
| `research/RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md` | `9475e7199dc66d2c18ea2bb331ff9a69c4694cd7` | 14,342 |

The earlier seven missing paths and five original stale metadata records remain included. The refreshed manifest now records 16 paths absent from the previous 488-record manifest, plus this reconciliation report, and nine existing records whose blob metadata was refreshed.

### 10.3 Research interpretation limits

The merged evidence improves bounded coverage but does not close the corresponding research areas:
- RT-05 import admission does not prove source provenance, all graph encodings, or runtime resource limits.
- RT-09/13 byte-view results cover the declared finite probe and toolchain, not all aliasing, allocator, lifetime, concurrency, or target cases.
- RT-24 closed three-way merge emits structural candidates; identity, reverse-reference, mapping, review, and exact-tree publication gates remain separate.
- RT-26 serialized reservation matches direct subtree accounting in the fixture, but runtime/OS enforcement, overhead, and portability remain open.

No architecture decision is inferred from these experiment results.


## 11. Current-main refresh after RT-07 and RT-10 merges

Main advanced from `6aaac5518082e99627d0c28c6dabcddf8bad4933` to `7b4453293d0c0001cd29f1f1256818f03e5176f8`. The exact comparison adds four research paths, modifies the dependency map and taxonomy, and updates PLAN and the Logos-binding workflow. No research paths were deleted.

Current main at `7b44532` is estimated at:

| Measure | Count |
|---|---:|
| Research artifacts excluding inventory manifest | 508 |
| Markdown files | 259 |
| MDX files | 3 |
| Python files | 209 |
| Lean files | 24 |
| Prototype-tree files | 258 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

The four new research paths are:
- `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ObservableRewrite.lean`;
- `research/PROTOTYPES/POSIX-IO-01/nonblocking_pipe.c`;
- `research/RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md`;
- `research/RT-10-POSIX-NONBLOCKING-PIPE-IO.md`.

The two reports add bounded formal rewrite-preservation and nonblocking pipe-I/O evidence. The Lean proof preserves result, error, and ordered event trace over its declared typed scalar grammar. The C fixture compares libc and raw Linux x86-64 adapters over 112 expected observations. Neither establishes general compiler correctness or full POSIX conformance.

The refreshed PR branch manifest contains 509 records: 508 current-main research artifacts plus this reconciliation report; 260 Markdown, 3 MDX, 209 Python, 24 Lean, and 258 prototype-tree files. It now accounts for 20 paths absent from the original 488-record manifest. Existing modified records include the dependency map and taxonomy with current-main blob metadata. The latest recursive-tree freshness workflow must be checked on the final manifest head before this report is treated as verified.

No full recursive tree enumeration at `7b44532` is claimed here; totals are derived from the previous exhaustive tree audit and exact commit deltas through this revision.


## 12. Current-main refresh after RT-10 structured-scope evidence

Main advanced from `7b4453293d0c0001cd29f1f1256818f03e5176f8` to `11c7f191aa9f14197a6e170cacc7f08175a48501`. The exact comparison adds two research paths, modifies PLAN, the dependency map, and taxonomy, and deletes no research paths.

Current main at `11c7f19` is estimated at:

| Measure | Count |
|---|---:|
| Research artifacts excluding inventory manifest | 510 |
| Markdown files | 260 |
| MDX files | 3 |
| Python files | 210 |
| Lean files | 24 |
| Prototype-tree files | 259 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

The two new research paths are:
- `research/PROTOTYPES/STRUCTURED-SCOPE-01/scope_join.py` — finite executable model for nested task-scope completion and cleanup joins;
- `research/RT-10-STRUCTURED-SCOPE-JOIN.md` — report of 1,260 nested task-event orderings, with the transitive join matching the lifetime oracle and unsafe early publication leaving live loans in 198 schedules.

The current main dependency map and taxonomy blobs are refreshed to:
- `research/RESEARCH-DEPENDENCY-MAP.md`: `6d20695323a3f2adf6448cc2921758a156f658d1`, 50,901 bytes;
- `research/RESEARCH-TAXONOMY.md`: `6e241dd63a01adc46a7c7963cffcaa86bbfb284f`, 46,504 bytes.

The refreshed branch manifest contains 511 records: 510 current-main research artifacts plus this reconciliation report; 261 Markdown, 3 MDX, 210 Python, 24 Lean, and 259 prototype-tree files. It accounts for 22 paths absent from the original 488-record manifest. The RT-10 scope-join result is a finite model; it does not establish runtime task scheduler correctness, arbitrary cancellation behavior, or OS-level resource enforcement.


## 13. Current-main refresh after RT-23/24 interface-mapping evidence

Main advanced from `11c7f191aa9f14197a6e170cacc7f08175a48501` to `0088a239cdd52ac37567001ae9f9eeec87384736`. The exact comparison adds two research paths, modifies PLAN, the dependency map, and taxonomy, and refreshes the RT-23 worktree report. No research paths were deleted.

Current main at `0088a23` is estimated at:

| Measure | Count |
|---|---:|
| Research artifacts excluding inventory manifest | 512 |
| Markdown files | 261 |
| MDX files | 3 |
| Python files | 211 |
| Lean files | 24 |
| Prototype-tree files | 260 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

The two new research paths are:
- `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_interface_mapping_merge.py` — six tests for deterministic disjoint-key merge, same-key review, duplicate export claims, signature incompatibility, exact revision publication, and reconstruction of reported edits;
- `research/RT-23-INTERFACE-MAPPING-MERGE.md` — bounded interface mapping merge experiment.

The modified records are:
- `research/RESEARCH-DEPENDENCY-MAP.md`: `5304dc1cfe37a8e5a8788e53d700f2fb0db1f324`, 51,393 bytes;
- `research/RESEARCH-TAXONOMY.md`: `614b67c35ca3df8502253cc6acf60b3766f5a97d`, 46,783 bytes;
- `research/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md`: `90fcba55d8cbff05141a6e9f53841f1cea1d8101`, 39,645 bytes.

The refreshed branch manifest contains 513 records: 512 current-main research artifacts plus this reconciliation report; 262 Markdown, 3 MDX, 211 Python, 24 Lean, and 260 prototype-tree files. It accounts for 24 paths absent from the original 488-record manifest. The RT-23/24 mapping result is bounded: disjoint keys can still claim the same export, and publication requires exact revisions and semantic context. It does not establish a general automatic-merge policy.


## 14. Current-main refresh after B5 traceability integration

Main advanced from `0088a239cdd52ac37567001ae9f9eeec87384736` to `f33a311a21f751e65434292b9ff3a912b3939555`. The exact comparison adds two Markdown research artifacts: the B5 complete traceability graph audit and its Scenario 130 claim-level pilot. No research paths were deleted.

Current main at `f33a311` is estimated at:

| Measure | Count |
|---|---:|
| Research artifacts excluding inventory manifest | 514 |
| Markdown files | 263 |
| MDX files | 3 |
| Python files | 211 |
| Lean files | 24 |
| Prototype-tree files | 260 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

The two new paths are:
- `research/RT-00-B-05-COMPLETE-TRACEABILITY-GRAPH-AUDIT-2026-11-21.md` — baseline-scoped corpus traceability graph audit;
- `research/RT-00-B-05-01-SCENARIO-130-CLAIM-TRACEABILITY-PILOT-2026-11-21.md` — local claim-to-test-to-evidence pilot with four executable claims and one conditional implication.

The pilot's local identifiers are not a global Claim ID namespace. Its source/evidence binding is specific to Scenario 130 and the recorded C-02 reproduction head. The B5 graph report remains a dated baseline audit and does not automatically incorporate later RT-05/07/09/10/23/24/26 results.

The refreshed branch manifest contains 515 records: 514 current-main research artifacts plus this A reconciliation report; 264 Markdown, 3 MDX, 211 Python, 24 Lean, and 260 prototype-tree files. It accounts for 26 paths absent from the original 488-record manifest. The current main inventory itself remains at 488 records until this reconciliation PR is integrated. No fresh recursive tree enumeration at `f33a311` is claimed; totals are derived from the previous exhaustive tree audit and exact commit deltas.


## 15. Current-main metadata refresh after taxonomy/dependency-map reconciliation

Main advanced from `f33a311a21f751e65434292b9ff3a912b3939555` to `78b06273c4bbc1569e336de5d40cc61be3898c0d`. This delta adds no research paths and modifies PLAN, the dependency map, and taxonomy. The current research-tree totals remain 514 artifacts excluding the inventory manifest: 263 Markdown, 3 MDX, 211 Python, 24 Lean, and 260 prototype-tree files.

Current-main blob metadata:
- `research/RESEARCH-DEPENDENCY-MAP.md`: `4946f810cf35c0f0ce8baafe3defccba94298abe`, 51,700 bytes;
- `research/RESEARCH-TAXONOMY.md`: `c819fa190067263b51b52a75fedfd62a5b051290`, 47,000 bytes.

The A branch remains at 515 inventory records: 514 current-main research artifacts plus this report. Its manifest has 26 added-path records relative to the original 488-record manifest, and its stale metadata list is refreshed to the exact current main blobs. No new research paths were introduced by this latest metadata-only delta.


## 16. Exact current-tree reconciliation — 2026-11-21

A fresh recursive Git-tree audit was run by [PR #203](https://github.com/aivibeflow/LLMLang/pull/203), workflow [#44949110891](https://github.com/aivibeflow/LLMLang/actions/runs/44949110891), against exact checkout `853a52c61f35f9022a1e6075e9b7079273eb7d9f`. The retained artifact is [14724657613](https://github.com/aivibeflow/LLMLang/actions/runs/44949110891/artifacts/14724657613), digest `sha256:9992b378a2dc02af32adc46dff8c130fd1b3c27d929bf3c9fd3e43c00beadfd1`.

### 16.1 Exact result

| Measure | Result |
|---|---:|
| Research artifacts excluding manifest | 538 |
| Previous manifest records | 488 |
| Missing paths | 50 |
| Extra manifest paths | 0 |
| SHA/size mismatches | 20 |
| Markdown | 276 |
| MDX | 3 |
| Python | 218 |
| Lean | 26 |
| Prototype-tree paths | 270 |
| Scenario-named paths | 137 |
| Taxonomy RT rows | 26 |
| Dependency rows | 108 |

The reconciliation adds 50 exact path/blob/size records and refreshes all 20 stale existing blob metadata records. No path was removed. The manifest now contains 538 sorted records, and category counts sum to exactly 538. The manifest excludes itself to avoid self-reference.

### 16.2 Semantic-review boundary

The 50 added records are explicitly marked inventory-only: no semantic RT ownership, Claim mapping, or PLAN-stage mapping is inferred from a filename or directory. Of the 270 prototype-tree paths, 242 remain the historical individually role-triaged count; 22 current prototype paths added since that review remain unreviewed at individual-file role level. Prototype family counts in this audit are path counts, not semantic coverage.

The exact audit counts 137 Scenario-named paths while the stored scenario crosswalk contains 136 mapped files. This one-path discrepancy is preserved as unresolved; no scenario ID or mapping is invented. The historical Scenario 16 gap remains separately unresolved.

### 16.3 Scope and next work

This closes the path/SHA/size freshness defect for the audited tree only. It does not close individual role review for the 22 prototype paths, refresh the complete scenario crosswalk, or validate every claim/test/evidence edge. The inventory's historical index checks and role-review counts remain explicitly dated. A separate semantic follow-up must review the 22 prototype files and reconcile the 137-versus-136 scenario path count without changing historical mappings absent evidence.


## 17. Latest-main exact-tree refresh — 2026-11-21

A second recursive audit was required because main advanced with RT-24 call-target merge evidence after the prior 538-path snapshot. The latest exact audit is [PR #207](https://github.com/aivibeflow/LLMLang/pull/207), workflow [#44949694311](https://github.com/aivibeflow/LLMLang/actions/runs/44949694311), scanned checkout `0bffdf1ee7e4db1b2c78394257b3530fc8f2cddd`. Artifact [14725405742](https://github.com/aivibeflow/LLMLang/actions/runs/44949694311/artifacts/14725405742), digest `sha256:65c2a0b4d0b60504c098d0f53bf95e23a2f06becd1a56983af31022d873c21db`.

| Measure | Latest exact result |
|---|---:|
| Research artifacts excluding manifest | 546 |
| Missing paths in previous manifest | 58 |
| Extra manifest paths | 0 |
| SHA/size mismatches | 20 |
| Markdown / MDX | 280 / 3 |
| Python / Lean | 221 / 26 |
| Prototype-tree paths | 274 |
| Scenario-named paths | 137 |
| RT / DEP rows | 26 / 108 |

The final reconciliation now records 546 sorted artifacts, adds the 58 missing paths, refreshes all 20 stale existing SHA/size records, and removes no paths. Category totals sum to 546. The 58 new records are explicitly inventory-only and do not infer semantic ownership, claim links, or PLAN stages.

The 242 individually role-triaged prototype-file count remains a historical semantic review result. The current 274-path prototype tree must not be described as 274 individually reviewed files. The difference of 32 paths lies outside the recorded individual role-triage count; this is a coverage gap, not a claim that all 32 were newly added. The Scenario crosswalk still maps 136 files while the exact path scan counts 137 Scenario-named paths; that one-path discrepancy remains unresolved.

The 538-path snapshot in §16 is retained as a historical audit result. §17 supersedes it for the latest main tree. RT-00 remains incomplete at semantic review, claim/evidence traceability, and external provenance layers.


## 18. Latest-main exact-tree refresh — 2026-11-21

Main advanced with RT-13 WASM memory32 evidence and the updated G status report after the 546-path audit. A new recursive audit was run in [PR #210](https://github.com/aivibeflow/LLMLang/pull/210), workflow [#44950395839](https://github.com/aivibeflow/LLMLang/actions/runs/44950395839), against exact checkout `405b2463299f4c01657a775576a8497a4dc800a7`. Artifact [14725497257](https://github.com/aivibeflow/LLMLang/actions/runs/44950395839/artifacts/14725497257), digest `sha256:c3eaa19d783f17e2e977e9e2563b17c2ef7f791ebc609b4477a689c5418af35f`.

| Measure | Latest exact result |
|---|---:|
| Research artifacts excluding manifest | 549 |
| Missing paths in previous manifest | 61 |
| Extra manifest paths | 0 |
| SHA/size mismatches | 20 |
| Markdown / MDX | 282 / 3 |
| Python / Lean | 221 / 26 |
| Prototype-tree paths | 275 |
| Scenario-named paths | 137 |
| RT / DEP rows | 26 / 108 |

The latest manifest reconciliation now records 549 sorted paths, adds 61 records, refreshes 20 existing blob/size records, and removes no paths. Category totals sum to 549. All 61 additions are inventory-only; no semantic RT ownership, claim links, or PLAN stages are inferred from filenames.

The historical semantic review records 242 individually role-triaged prototype files. The latest tree has 275 prototype paths, leaving 33 paths outside that recorded individual-role total; this is a coverage difference, not a claim that every such path is newly added. The Scenario crosswalk remains at 136 mapped files while the exact tree counts 137 Scenario-named paths. That one-path discrepancy remains unresolved.

Sections 16 and 17 preserve the 538- and 546-path snapshots respectively. Section 18 supersedes both for the latest main snapshot. RT-00 remains incomplete: inventory freshness is reconciled for this snapshot, but semantic role review, Scenario crosswalk reconciliation, claim-level traceability, reproducibility, and provenance are still open.
