# Research Corpus Audit — 2026-11-20

**Research item:** PLAN.md §0.1, Reconcile the research corpus  
**Status:** Partial audit; repository-wide reconciliation is not yet complete  
**Scope:** Read-only review of the research index, taxonomy, dependency map, preparation pack, external-reference register, and selected linked artifacts on `main` as inspected on 2026-11-20.  
**Normative boundary:** This report records documentation and inventory findings only. It makes no language, architecture, identity, or implementation decisions.

## 1. Executive summary

The research corpus has a substantial management structure: a central index, a taxonomy, a cross-area dependency map, a dated research-state register, an eight-brief preparation pack, and an external-reference register. The sampled index links and all eight preparation briefs checked in this audit resolve.

The main concrete issue is **stale summary counts in PLAN.md**:

- PLAN.md says the taxonomy defines **18 research areas**; the current taxonomy enumerates **23 areas (RT-01 through RT-23)**.
- PLAN.md says the dependency map contains **35 initial edges**; the current dependency map contains **77 registered edge IDs (DEP-001 through DEP-077)**.

The historical statement that the corpus contained 102 files "at plan creation" is explicitly historical and should not be treated as a current inventory count.

This audit does **not** claim that every file under `research/` has been inventoried or that all links have been checked. The available repository interface in this session exposed file fetch/search operations but no recursive directory/tree listing. The remaining checklist items therefore stay open.

## 2. Evidence and checks performed

### 2.1 Research index

- Read `research/README.md`.
- Extracted **78 unique relative Markdown link targets** from the index.
- Checked 15 representative linked targets, including the research-state register, option matrix, preparation/reference indexes, core semantics, RT-04 alternatives, and Scenarios 36–40 and 94–97. All 15 fetched successfully.
- The index contains **59 distinct scenario numbers** in its scenario references, with the highest referenced scenario being **133**. This is an index-reference count, not a count of files in the repository.

**Result:** sampled index links resolve. The other 63 unique targets were not checked in this pass, and index completeness is unproven.

### 2.2 Taxonomy and dependency map

- `research/RESEARCH-TAXONOMY.md` contains 23 distinct research-area entries, RT-01 through RT-23.
- `research/RESEARCH-DEPENDENCY-MAP.md` contains 77 distinct dependency IDs, DEP-001 through DEP-077, with no gaps in that ID range.
- PLAN.md still reports 18 research areas and 35 initial dependency edges in its Stage 0.3 evidence/progress text.

**Finding:** PLAN.md's summary figures no longer describe the current taxonomy and dependency map. The 35-edge figure may have been correct for an earlier snapshot, but the plan does not label it as historical.

### 2.3 Preparation pack

- Read `research/preparation/README.md`.
- Verified that all eight preparation briefs linked from its execution-order table exist.
- The pack clearly distinguishes preparation instructions from executed research evidence and requires source revisions, tool versions, fixtures, commands, raw outputs, negative/UNKNOWN cases, limitations, and decision boundaries.
- The pack itself records a documentation-alignment note about Scenario 34 / SCW task ordering.

**Result:** the preparation index and its eight linked briefs are present. Their scientific readiness and every internal cross-reference were not re-audited here.

### 2.4 External references

- Read `research/references/README.md`.
- Verified that `research/references/SNAPSHOT-MANIFEST.json` exists.
- The register identifies four version-pinned snapshot groups (MCP, OCI, Alive2, and Bazel REAPI), preserves licence/attribution notes, and distinguishes copied snapshots from live external references.
- The register states that 13 stored source/licence files were checked against upstream blob IDs. This audit recorded that assertion but did not independently download and re-hash the upstream files.

**Result:** reference documentation and manifest are present; upstream snapshot integrity was not independently re-verified.

### 2.5 Selected cross-document checks

The following files were fetched successfully during the audit:

- `PLAN.md`
- `research/README.md`
- `research/RESEARCH-TAXONOMY.md`
- `research/RESEARCH-DEPENDENCY-MAP.md`
- `research/RESEARCH-STATE-2026-11-19.md`
- `research/RESEARCH-OPTION-MATRIX-01.md`
- `research/preparation/README.md`
- `research/references/README.md`
- `research/references/SNAPSHOT-MANIFEST.json`
- `draft/GLOSSARY.md`
- Eight preparation briefs listed in §2.3
- The 15 representative index targets listed in §2.1

A successful fetch establishes that a path exists at the inspected revision; it does not establish that its content is current, non-duplicative, or correctly classified.

## 3. Findings and recommended actions

| ID | Finding | Impact | Recommended action |
|---|---|---|---|
| RCA-01 | PLAN.md reports 18 taxonomy areas, while the current taxonomy contains 23 (RT-01–RT-23). | Readers may underestimate the research programme and miss RT-19–RT-23. | Update the plan's summary count and identify the taxonomy as the source of truth. |
| RCA-02 | PLAN.md reports 35 dependency edges, while the current map contains 77 (DEP-001–DEP-077). | The plan's progress summary understates the current dependency register. | Update the count and label it as a snapshot count, or avoid duplicating a volatile count. |
| RCA-03 | The research index has 78 unique local link targets; only 15 were checked in this audit. | Broken links or unindexed artifacts may remain. | Run a complete automated relative-link check and report failures by source file and target. |
| RCA-04 | The index and taxonomy describe many scenario results, but this audit did not enumerate the complete directory tree. | Orphaned, duplicate, superseded, and unindexed files cannot yet be ruled out. | Generate a path-based inventory of every file under research/, classify it, and map it to plan items. |
| RCA-05 | The external-reference register records upstream integrity checks, but they were not reproduced here. | Snapshot integrity is supported by recorded evidence, not independently re-established by this audit. | Preserve the manifest and periodically verify upstream blob IDs and licence files with a reproducible script. |

## 4. Reconciliation decisions

1. Do not delete or rewrite historical research merely because a newer scenario exists.
2. Keep preparation briefs distinct from executed research results.
3. Keep copied primary-source snapshots distinct from LLMLang-authored analysis.
4. Treat the taxonomy and dependency map as the current detailed registers; update duplicated summary counts in PLAN.md.
5. Do not mark PLAN.md §0.1 complete on the basis of this partial audit.

## 5. Remaining work for full completion of PLAN.md §0.1

- [ ] Enumerate every file under `research/`, including nested prototypes, tests, fixtures, generated outputs, and snapshots.
- [ ] Classify each file as research note, experiment specification, implementation/prototype, test evidence, external source snapshot, generated artifact, index, or decision record.
- [ ] Map every artifact to one or more research items/stages.
- [ ] Identify duplicates, superseded versions, orphaned files, and contradictions.
- [ ] Check every relative link in all research Markdown documents, not only the top-level index.
- [ ] Verify exact commit/revision and tool versions for reproducibility-sensitive results.
- [ ] Reconcile the summary counts in PLAN.md with the detailed registers.

## 6. Sources inspected

- `PLAN.md`
- `research/README.md`
- `research/RESEARCH-TAXONOMY.md`
- `research/RESEARCH-DEPENDENCY-MAP.md`
- `research/RESEARCH-STATE-2026-11-19.md`
- `research/RESEARCH-OPTION-MATRIX-01.md`
- `research/preparation/README.md` and its eight linked briefs
- `research/references/README.md` and `research/references/SNAPSHOT-MANIFEST.json`
- `draft/GLOSSARY.md`

---

**Conclusion:** Stage 0.1 has produced a reproducible partial audit and identified two concrete stale plan metrics. A full artifact-level reconciliation remains open because a complete repository tree and all cross-document links were not enumerated in this pass.
