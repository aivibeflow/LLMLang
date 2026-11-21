# RT-00 A — Inventory Manifest Freshness Reconciliation

**Date:** 2026-11-21  
**Source baseline:** `017e64b87c87371309197a392165258b8b088dd1` (main)  
**Disposition:** current path/blob inventory is reconciled in the accompanying manifest update; historical semantic-role counts remain separately qualified.

## 1. Purpose and method

The RT-00 A freshness workflow in PR #146 compared the inventory manifest against a recursive Git-tree enumeration of main at the exact source baseline above. It did not modify the manifest. This follow-up applies the findings to the manifest in a dedicated PR.

The comparison uses tracked Git paths, blob object IDs, and byte sizes. The inventory excludes its own manifest file to avoid self-reference. File-role and semantic-review fields are not inferred from hashes; new records below are based on the explicit RT-24 source-completeness report and its paired test.

## 2. Baseline comparison

Before adding this reconciliation report, the current main tree contained:

| Measure | Count |
|---|---:|
| Research artifacts excluding inventory manifest | 490 |
| Markdown files | 250 |
| MDX files | 3 |
| Python files | 202 |
| Lean files | 23 |
| Prototype-tree files | 249 |
| Scenario-named documents | 136 |
| RT taxonomy entries | 26 |
| DEP edges | 108 |

The manifest at revision `b118346ecd499d7962a6ac546fb1031bc7e2bc26` recorded 488 research artifacts and 248 prototype-tree files.

### Paths absent from the manifest

| Path | Role |
|---|---|
| `research/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md` | RT-24 bounded experimental report; evaluates DEP-088, DEP-091, DEP-093 and references the paired executable fixture |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py` | Seven focused tests for closed source inventories, merge-tree completeness, exact call reconstruction, and evidence replay |

No extra manifest paths were found.

### Existing records with stale blob metadata

The following records had stale SHA/size metadata and are refreshed from the exact baseline tree:

| Path | Current Git blob SHA | Bytes |
|---|---|---:|
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/README.md` | `7c089218c455bf23cd5dc4f8063fb471d90818d9` | 34,757 |
| `research/README.md` | `e4e7a476764aca9b1b2da116c76fd488c4496699` | 26,047 |
| `research/RESEARCH-DEPENDENCY-MAP.md` | `5afa970c7cd5f4bf3e232102a9453b1f91bdb02c` | 49,945 |
| `research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md` | `0b5b503e3c5641aaec200865c33fd1ce2b7fa482` | 29,561 |

## 3. Prototype-count semantics

The following counts refer to different populations and must not be conflated:

- **242** — `semantic_traceability_review.prototype_family_review.individually_mapped_files`: the historical aggregate of individually role-triaged prototype artifacts.
- **245** — an earlier PLAN aggregate; its underlying per-file reconciliation is not established by this count.
- **248** — the previous inventory manifest's prototype-tree file count and per-file traceability-record population.
- **249** — the actual prototype-tree path count in the audited main tree.

The RT-24 test adds a current prototype path and is now explicitly recorded. Its role is grounded in the paired RT-24 report and its seven test methods. This per-file record does not retroactively rewrite the historical 242/245 role-review aggregates or establish that every prototype file has equal claim-level or execution review.

## 4. Manifest update

The accompanying manifest change:
- updates the source revision to the exact tree used for the reconciliation;
- adds the two missing path records;
- refreshes four stale blob SHA/size pairs;
- updates counts to 491 research artifacts after this reconciliation report is included, 251 Markdown files, 202 Python files, and 249 prototype-tree files;
- increments the audit-report and prototype-test category totals;
- records the comparison outcome and the separate meanings of prototype counts.

The 491 artifact count includes this reconciliation report. The manifest itself remains excluded.

## 5. Limitations

This is a path/blob/size reconciliation, not a new full content audit. The RT-24 report and paired test were inspected to assign bounded file roles. Existing semantic traceability and prototype family-review aggregates remain historical where explicitly labelled. No claim-level completeness, test execution, semantic conformance, external provenance, or architecture decision is inferred from inventory membership.

The inventory freshness workflow and its original evidence remain in [PR #146](https://github.com/aivibeflow/LLMLang/pull/146), run [#44938305811](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811), artifact [14720512241](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811/artifacts/14720512241).
