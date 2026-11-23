# RT-00 A — Current-main inventory freshness reconciliation

**Date:** 2026-11-23
**Baseline:** `main` at `96431c71cd479a742831ebd7d28d4b1e60c1ebe3`
**Scope:** recursive `research/` tree versus `RESEARCH-CORPUS-INVENTORY-2026-11-20.json`
**Disposition:** exact path/blob/size reconciliation; no claim validation or experiment reproduction

## 1. Method

Enumerate the recursive Git tree at the baseline, exclude only the inventory manifest itself, and compare every remaining path's blob SHA and byte size with the inventory. Review the one missing file's content and nearby plan context to add a bounded traceability classification. Recompute the final PR-tree counts and repeat the path/blob/size comparison after adding this report and refreshing the manifest.

The inventory workflow uses the same Git-tree, blob-size, and path comparison model: [.github/workflows/research-inventory-freshness-audit.yml](../.github/workflows/research-inventory-freshness-audit.yml). The current-main comparison is performed locally here; the PR workflow must validate the final head independently.

## 2. Baseline result

At baseline `96431c71cd479a742831ebd7d28d4b1e60c1ebe3`, the recursive tree contains 588 research artifacts excluding the manifest. The manifest contains 585 records: three paths are missing, there are zero extra records, and one existing record has a stale SHA/size pair.

| Missing path | Role observed in content | Traceability boundary |
|---|---|---|
| `research/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md` | Requirements and evaluation criteria for Git-resident SPG storage; no physical layout or serialization format is selected. | The report identifies itself as RT-27 and is related to RT-24/Git representation work in Stage 4. RT-27 is not registered as a row in the current research taxonomy or dependency map. This inventory entry is a provisional file-to-plan mapping, not proof that RT-27 is an accepted standalone research area. |
| `research/GIT-BINARY-SPG-STORAGE-EFFICIENCY.md` | Preliminary comparison and benchmark plan for Git delta storage of immutable SPG containers. It explicitly marks the earlier synthetic measurements unverified. | Stage 4.2 is the current plan location. Its relationship to a standalone RT area and dependency edges remains unregistered. |
| `research/RT-00-QUALITY-RULES-ROLLOUT-OPTIONS-2026-11-23.md` | Qualitative comparison of corpus-wide, priority-ordered, and hybrid rollout strategies for the RT-08 evidence conventions. | The document is linked from the 0.2 plan entry and is a recommendation, not adopted policy. |

The one stale record is `research/RESEARCH-TAXONOMY.md`, changed when PR #247 linked the quality-rules rollout study from RT-08. No path was removed and no extra path is present. The three missing documents and one changed taxonomy file account for the full delta from the prior manifest.

## 3. Refreshed snapshot and verification

The refreshed manifest contains 589 records for the exact PR tree: the 588 baseline artifacts plus this audit report. It includes the three previously absent documents and this report, refreshes the taxonomy and README blob records, and records the open RT-27 taxonomy/dependency-map registration boundary. Recomputed tree totals are 308 Markdown, 3 MDX, 226 Python, 33 Lean, 289 prototype paths, and 137 Scenario-named paths; the taxonomy and dependency map remain at 26 RT rows and 108 DEP edges.

The local exact-tree check compares all 587 record paths, Git blob SHAs, and byte sizes against the staged PR tree. The GitHub inventory-freshness workflow is the independent PR-head check; its result is pending until the pull request runs.

The existing [research index coverage auditor](../.github/scripts/audit_research_index_coverage.py) was run after adding RT-27, the Git storage-efficiency report, the quality-rules rollout report, and this report to `research/README.md`. It scanned 311 research Markdown/MDX documents; all four new index targets have designated-index inbound links. Across the full corpus, 57 documents lacked a link from a designated index and 23 had no inbound link at all. It found 38 unresolved local targets, all in the partial OCI and Alive2 snapshots, and 492 links to existing non-Markdown resources. These are candidate discoverability findings from a conservative parser, not automatic proof of orphaning or corpus completeness.

## 4. Limits and remaining dependencies

- This audit verifies inventory path/blob/size integrity only. It does not validate claims, execute tests, inspect generated outputs, or reproduce experiments.
- The index coverage result does not close corpus discoverability: 57 documents lack designated-index inbound links and 23 lack any inbound links; each candidate requires content review before being classified as an orphan.
- The RT-27 document still needs an explicit decision whether it is a standalone taxonomy area or a Stage 4 subtopic, and corresponding dependency-map treatment. The plan records this as an open traceability dependency.
- Scenario-named path/crosswalk reconciliation, semantic duplicate/supersession/orphan/contradiction review, external snapshot completeness, claim-level evidence validation, and exact experiment provenance remain open as stated in §0.1.
- Inventory completeness must be refreshed again after subsequent research files merge; this snapshot is tied to the recorded tree and is not a permanent count.
