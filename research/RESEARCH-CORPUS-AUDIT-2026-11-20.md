# Research Corpus Audit — 2026-11-20

**Research item:** PLAN.md §0.1, Reconcile the research corpus  
**Status:** Partial; complete tracked-path inventory and limited link checks recorded, semantic reconciliation still open  
**Primary snapshot revision:** `2a9b6e5072efc542e823c529cf3cdee838f9ad36`  
**Normative boundary:** This report records documentation and inventory findings only. It makes no language, architecture, identity, or implementation decisions.

## 1. Executive summary

The recursive Git tree at the primary snapshot revision contains **446 tracked files under `research/`**:

- 233 Markdown/MDX files (230 `.md` and 3 `.mdx`);
- 194 Python files;
- 7 Lean source files and one Lean toolchain pin;
- 3 JSON files;
- 1 C file, 1 Rust file, 1 TOML file, 1 Protocol Buffers schema, and 4 text files;
- 225 files under `research/PROTOTYPES/`;
- 24 files under `research/preparation/` and `research/references/`.

A machine-readable inventory snapshot records all 446 paths, Git blob SHAs, byte sizes, coarse categories, and qualified path-based traceability metadata: [RESEARCH-CORPUS-INVENTORY-2026-11-20.json](RESEARCH-CORPUS-INVENTORY-2026-11-20.json).

The main index's relative links and the preparation index's brief links resolve. Exact Git-blob comparison found one repeated blob: the same Apache-2.0 licence text is stored alongside both OCI and REAPI snapshots. This is expected shared licence content, not evidence of duplicated research.

The audit remains **partial**. The inventory classifies paths and records tentative mappings; it does not verify every artifact's semantic contents, determine every supersession relationship, prove index completeness, or reproduce all experiments.

## 2. Evidence and checks performed

### 2.1 Repository inventory

- Retrieved the recursive Git tree for `main` at revision `2a9b6e5072efc542e823c529cf3cdee838f9ad36`.
- Enumerated all 446 tracked files whose paths begin with `research/`.
- Recorded path, Git blob SHA, byte size, coarse artifact category, and traceability metadata for every file in the inventory JSON.
- Distinguished scenario-named reports, prototype implementations, tests, prototype readmes/reports, preparation briefs, external snapshots/licences, structured fixtures, and research documents.
- Recorded direct RT/scenario identifiers as high-confidence path evidence. Prototype-family mappings are explicitly marked medium confidence; files without reliable path identifiers remain unassigned rather than receiving guessed mappings.

The inventory is a reproducible path-level snapshot. It is not a claim that every file's contents have been read or validated.

### 2.2 Research index links

- Read `research/README.md`.
- Extracted **83 unique relative Markdown link targets**.
- Checked each target against the recursive Git tree at the snapshot revision: **0 missing targets**.
- Checked the eight preparation briefs linked by `research/preparation/README.md`; all eight exist. The other links in that preparation index, including the reference register and glossary, also resolve.

**Result:** all local links checked in these two index files resolve. Links in the other research Markdown/MDX files have not been exhaustively checked. Successful path resolution does not prove that the main index covers every artifact.

### 2.3 Taxonomy and dependency map

- `research/RESEARCH-TAXONOMY.md` contains 23 research-area entries, RT-01 through RT-23.
- `research/RESEARCH-DEPENDENCY-MAP.md` contains 77 dependency IDs, DEP-001 through DEP-077, with no gaps in that ID range.
- The previous Stage 0.3 summary in `PLAN.md` reported 18 areas and 35 edges; this was stale.

**Correction:** PLAN.md §0.3 now reports the current counts (23 areas and 77 edges). The taxonomy and dependency map remain evolving research registers; the existence of an edge does not make it an accepted architecture rule.

### 2.4 Preparation pack and external references

- The preparation index links eight preparation briefs; all eight resolve.
- The briefs distinguish preparation instructions from executed research evidence and specify reproducibility expectations such as source revisions, tool versions, fixtures, commands, raw outputs, negative/UNKNOWN cases, limitations, and decision boundaries.
- The external-reference register identifies four pinned snapshot groups: MCP, OCI, Alive2, and Bazel Remote Execution API.
- The reference register states that 13 stored source/licence files were checked against upstream blob IDs. This audit did not independently retrieve and re-hash those upstream files.

### 2.5 Exact blob comparison

Git blob SHA comparison across the 446 inventory entries found one repeated blob:

| Blob SHA | Paths | Assessment |
|---|---|---|
| `d645695673349e3947e8e5ae42332d0ac3164cd7` | `research/references/snapshots/OCI/LICENSE-APACHE-2.0.txt`; `research/references/snapshots/REAPI/LICENSE-APACHE-2.0.txt` | Expected shared Apache-2.0 licence text; retain both colocated copies for snapshot attribution. |

No other byte-identical files were found by this Git-blob comparison. This does not detect near-duplicates, overlapping research, or superseded documents with different contents.

## 3. Findings and actions

| ID | Finding | Action / status |
|---|---|---|
| RCA-01 | The corpus has 446 tracked paths, but previously lacked a complete path inventory. | Added the machine-readable inventory snapshot. |
| RCA-02 | Artifact-to-item mapping is not uniformly explicit in filenames. | Added qualified path-based mappings; content-level verification remains open. |
| RCA-03 | All 83 relative links in the main research index resolve. | Link existence check complete; index completeness remains open. |
| RCA-04 | All eight preparation briefs linked by the preparation index exist. | Path check complete; scientific readiness and internal link scan remain open. |
| RCA-05 | PLAN.md §0.3 reported stale taxonomy/dependency counts. | Corrected to 23 research areas and 77 dependency edges. |
| RCA-06 | One exact duplicate blob is shared by the OCI and REAPI Apache-2.0 licence files. | Classified as intentional shared licence content; no deletion proposed. |
| RCA-07 | External snapshot integrity and experiment reproducibility have not been independently re-established. | Preserve pinned revisions and existing manifest; verify source blobs and experiment environments in a later pass. |

## 4. Reconciliation rules

1. Do not delete or rewrite historical research merely because a newer scenario exists.
2. Keep preparation briefs distinct from executed research results.
3. Keep copied primary-source snapshots distinct from LLMLang-authored analysis.
4. Treat the taxonomy and dependency map as detailed evolving registers; do not copy stale fixed counts into other documents.
5. Treat path-derived mappings as inventory hints, not as accepted semantic traceability.
6. Keep research exploratory; architectural or language decisions must be recorded separately in the appropriate decision/specification documents.

## 5. Remaining work for full completion of PLAN.md §0.1

- [ ] Read and validate the content-level mapping for every artifact, including prototypes, tests, fixtures, generated outputs, RFCs, and snapshots.
- [ ] Map every artifact to explicit research item(s) and plan stage(s); resolve low-confidence and unassigned entries.
- [ ] Identify semantically duplicate, superseded, orphaned, and contradictory documents.
- [ ] Check every relative link in all research Markdown/MDX files, not only the main and preparation indexes.
- [ ] Verify exact source revision, tool versions, commands, fixtures, expected outputs, and negative cases for each reproducibility-sensitive experiment.
- [ ] Independently re-verify external snapshot blob identities and licence provenance.
- [ ] Confirm that the research index exposes every relevant artifact or provides clear directory-level indexes for grouped artifacts.

## 6. Sources inspected

- Recursive Git tree at `2a9b6e5072efc542e823c529cf3cdee838f9ad36`.
- `PLAN.md`
- `research/README.md`
- `research/RESEARCH-TAXONOMY.md`
- `research/RESEARCH-DEPENDENCY-MAP.md`
- `research/preparation/README.md` and its eight linked briefs
- `research/references/README.md` and `research/references/SNAPSHOT-MANIFEST.json`
- `draft/GLOSSARY.md`

---

**Conclusion:** the repository-wide path inventory, coarse artifact classification, Git-blob duplicate check, main-index relative-link check, and preparation-index path check are now recorded. PLAN.md §0.1 remains partially validated until semantic traceability, complete cross-document link validation, supersession/orphan/contradiction analysis, and reproducibility verification are complete.
